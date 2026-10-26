#!/usr/bin/env python3
"""Voz limpa de estúdio: tira o ruído do ambiente, o "embolado" do celular e o chiado do S, sem robotizar.

Duas rotas, a melhor que existir na máquina:
  1. Resemble Enhance (MIT, IA; instale com: python setup.py --voz-ia). Tira ruído e reverberação de sala.
  2. Local (numpy, sempre disponível). O editor sabe ONDE você fala (transcrição): aprende o ruído nas pausas e
     o subtrai por frequência (Wiener com piso de -15 dB e suavização no tempo, sem "água"), baixa o ruído que
     sobra entre as frases, corta grave de mesa/vento (75 Hz), tira o embolado (250 Hz), dá presença (3,2 kHz)
     e ar (10 kHz), segura o S (de-esser dinâmico 5-9 kHz) e nivela com um compressor suave.
Depois disso o render só nivela (compressor + loudness): o highpass/afftdn da cadeia padrão saem.

  voz.py limpar entrada.wav saida.wav [--fala "0.3-2.1,2.6-5.0"]     limpa um arquivo
  voz.py medir arquivo.wav [--fala ...]                               ruído nas pausas, voz, SNR, sibilância
Pedido no projeto: edit.py <proj> --voz estudio   (off volta ao tratamento padrão)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

import dsp
from dsp import SR

VERSAO = "voz3"
N_FFT, HOP = 1024, 256
PISO_DB = -15.0          # o ruído cai no máximo 15 dB por frequência (mais que isso soa robótico)
PAUSA_DB = -10.0         # redução extra do que sobra entre frases (com rampas, nunca corta palavra)
MARGEM = 0.12            # folga em volta de cada palavra (o horário da transcrição não é exato)


# ---------------------------------------------------------------------------------------------------------------
# leitura/escrita

def ler(path: Path) -> np.ndarray:
    """Qualquer áudio/vídeo -> mono 48 kHz float (via ffmpeg)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<f4").astype(float)


def mascara_fala(n: int, fala: list, margem: float = MARGEM) -> np.ndarray:
    """1 onde há fala (com folga), 0 nas pausas."""
    m = np.zeros(n, bool)
    for a, b in fala:
        m[max(int((a - margem) * SR), 0):min(int((b + margem) * SR), n)] = True
    return m


# ---------------------------------------------------------------------------------------------------------------
# rota local

def _stft(x: np.ndarray) -> np.ndarray:
    jan = np.sqrt(np.hanning(N_FFT + 1)[:-1])
    pad = np.concatenate([np.zeros(N_FFT), x, np.zeros(N_FFT)])
    n_q = 1 + (len(pad) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n_q)[:, None]
    return np.fft.rfft(pad[idx] * jan, axis=1)


def _istft(X: np.ndarray, n: int) -> np.ndarray:
    jan = np.sqrt(np.hanning(N_FFT + 1)[:-1])
    quadros = np.fft.irfft(X, N_FFT, axis=1) * jan
    out = np.zeros(HOP * (len(quadros) - 1) + N_FFT)
    peso = np.zeros_like(out)
    for i, q in enumerate(quadros):
        out[i * HOP:i * HOP + N_FFT] += q
        peso[i * HOP:i * HOP + N_FFT] += jan ** 2
    out /= np.maximum(peso, 1e-8)
    return out[N_FFT:N_FFT + n]


def perfil_ruido(P: np.ndarray, pausa_q: np.ndarray) -> np.ndarray:
    """Potência média do ruído por frequência: nas pausas (se houver ≥ 0,3 s) ou nos 10% de quadros mais baixos."""
    if pausa_q.sum() * HOP / SR >= 0.3:
        return np.median(P[pausa_q], axis=0) * 1.4      # mediana subestima a média de um ruído (~ln2): corrige
    energia = P.sum(axis=1)
    baixos = energia <= np.quantile(energia, 0.1)
    return P[baixos].mean(axis=0)


def tirar_ruido(x: np.ndarray, fala: list | None) -> np.ndarray:
    X = _stft(x)
    P = np.abs(X) ** 2
    t_q = (np.arange(len(X)) * HOP - N_FFT + N_FFT / 2) / SR
    falando = np.zeros(len(X), bool)
    for a, b in (fala or []):
        falando |= (t_q >= a - MARGEM) & (t_q <= b + MARGEM)
    N = perfil_ruido(P, ~falando if fala else np.zeros(len(X), bool))
    piso = 10 ** (PISO_DB / 20)
    # Wiener decisão-dirigida (Ephraim-Malah): estimativa a priori suavizada no tempo = sem ruído musical
    G = np.empty_like(P)
    ant = np.zeros(P.shape[1])
    for i in range(len(P)):
        post = P[i] / (N + 1e-12)
        prio = 0.96 * ant / (N + 1e-12) + 0.04 * np.maximum(post - 1, 0)
        g = prio / (1 + prio)
        G[i] = np.maximum(g, piso)
        ant = (G[i] ** 2) * P[i]
    # sem suavizar entre frequências: os harmônicos da voz ficam a ~3 bins um do outro e borrariam (-5 dB de SNR)
    return _istft(X * G, len(x))


def baixar_pausas(x: np.ndarray, fala: list) -> np.ndarray:
    """Redução extra entre frases (gate suave com rampas de 80 ms)."""
    alvo = np.where(mascara_fala(len(x), fala), 1.0, 10 ** (PAUSA_DB / 20))
    rampa = dsp.seg(0.08)
    k = np.ones(rampa) / rampa
    g = np.convolve(np.pad(alvo, (rampa // 2, rampa - 1 - rampa // 2), mode="edge"), k, mode="valid")
    return x * np.maximum(g, alvo)   # a rampa nunca abaixa dentro da fala


def deesser(x: np.ndarray, limiar_db: float = -10.0, max_db: float = 8.0) -> np.ndarray:
    """Abaixa só a banda do S (5-9 kHz) quando ela passa a energia da voz por mais de limiar_db."""
    banda = dsp.filtro_fft(x, dsp.combina(dsp.r_passa_alta(5000, 4), dsp.r_passa_baixa(9000, 4)))
    resto = x - banda
    w = dsp.seg(0.005)
    nb = np.sqrt(dsp._media_movel(banda ** 2, w) + 1e-12)
    nt = np.sqrt(dsp._media_movel(x ** 2, w) + 1e-12)
    excesso = np.clip(20 * np.log10(nb / nt) - limiar_db, 0, max_db)
    g = 10 ** (-dsp._media_movel(excesso, dsp.seg(0.02)) / 20)
    return resto + banda * g


EQ = dsp.combina(dsp.r_passa_alta(75, 3), dsp.r_sino(250, -2.5, 1.2), dsp.r_sino(3200, 2.5, 1.0),
                 dsp.r_prateleira(10000, 2.0, alta=True))


def limpar_local(x: np.ndarray, fala: list | None) -> np.ndarray:
    y = tirar_ruido(x, fala)
    if fala:
        y = baixar_pausas(y, fala)
    y = dsp.filtro_fft(y, EQ)
    y = deesser(y)
    y = dsp.compressor(y[None, :], limiar_db=-24, razao=2.0, ataque=0.008, soltura=0.12)[0]
    pico = np.max(np.abs(y)) or 1.0
    return y * min(1.0, 0.89 / pico)


# ---------------------------------------------------------------------------------------------------------------
# rota IA (Resemble Enhance, opcional)

_IA = r"""
import sys, torch, torchaudio
from resemble_enhance.enhancer.inference import denoise, enhance
x, sr = torchaudio.load(sys.argv[1]); x = x.mean(0)
dev = "cuda" if torch.cuda.is_available() else "cpu"
y, sr2 = (enhance(x, sr, dev, nfe=32, solver="midpoint", lambd=0.9, tau=0.5) if dev == "cuda" else denoise(x, sr, dev))
torchaudio.save(sys.argv[2], y.unsqueeze(0).cpu(), sr2)
"""


def tem_ia() -> bool:
    import importlib.util
    return importlib.util.find_spec("resemble_enhance") is not None


def limpar_ia(entrada: Path, saida: Path) -> bool:
    tmp = saida.with_name(saida.stem + ".ia.wav")
    proc = subprocess.run([sys.executable, "-c", _IA, str(entrada), str(tmp)], capture_output=True, text=True)
    if proc.returncode or not tmp.exists():
        print(f"   voz IA falhou ({(proc.stderr or '').strip()[-200:]}); usando a limpeza local", file=sys.stderr)
        return False
    y = ler(tmp)
    tmp.unlink(missing_ok=True)
    y = dsp.filtro_fft(y, dsp.combina(dsp.r_passa_alta(75, 3), dsp.r_sino(3200, 1.5, 1.0)))
    dsp.grava_wav(saida, y * min(1.0, 0.89 / (np.max(np.abs(y)) or 1)))
    return True


# ---------------------------------------------------------------------------------------------------------------
# API usada pelo render

def limpar(entrada: Path, saida: Path, fala: list | None, modo: str = "auto") -> str:
    """Limpa a voz de `entrada` (áudio ou vídeo) em `saida` (WAV 48 kHz). Devolve a rota usada."""
    entrada, saida = Path(entrada), Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    if modo in ("auto", "ia") and tem_ia():
        bruto = saida.with_name(saida.stem + ".bruto.wav")
        dsp.grava_wav(bruto, ler(entrada))
        ok = limpar_ia(bruto, saida)
        bruto.unlink(missing_ok=True)
        if ok:
            return "ia"
    x = ler(entrada)
    dsp.grava_wav(saida, limpar_local(x, fala))
    return "local"


def chave(chave_audio: str, fala: list) -> str:
    rota = "ia" if tem_ia() else "local"
    return hashlib.sha1(json.dumps([VERSAO, rota, chave_audio, fala]).encode()).hexdigest()[:16]


def voz_do_projeto(tl: dict, aroll: Path, work: Path, chave_aroll: str) -> Path | None:
    """WAV da voz limpa (em cache) quando a timeline pede voz de estúdio; senão None (tratamento padrão)."""
    if (tl.get("audio") or {}).get("voz") != "estudio":
        return None
    import trilha
    fala = [[round(a, 2), round(b, 2)] for a, b in trilha.regioes_fala(tl.get("words", []), tl["duration"], 0.25)[0]]
    k = chave(chave_aroll, fala)
    out = Path(work) / f"voz_{k}.wav"
    if not out.exists():
        rota = limpar(aroll, out, fala)
        print(f"   voz de estúdio ({rota}): {out.name}")
    return out


# ---------------------------------------------------------------------------------------------------------------
# medição

def medir(x: np.ndarray, fala: list | None) -> dict:
    """Ruído nas pausas, nível da voz, SNR e sibilância (energia 5-9 kHz relativa)."""
    m = mascara_fala(len(x), fala or [], margem=0.05) if fala else None
    if m is None or m.all() or not m.any():
        q = np.abs(x)
        m = q > np.quantile(q, 0.5)
    pausa = x[~mascara_fala(len(x), fala or [], margem=0.15)] if fala else x[~m]
    voz = x[m]
    ruido_db = dsp.rms_db(pausa) if pausa.size > SR * 0.2 else None
    voz_db = dsp.rms_db(voz)
    s = dsp.filtro_fft(voz, dsp.combina(dsp.r_passa_alta(5000, 4), dsp.r_passa_baixa(9000, 4)))
    return {"ruido_pausas_db": round(ruido_db, 1) if ruido_db is not None else None, "voz_db": round(voz_db, 1),
            "snr_db": round(voz_db - ruido_db, 1) if ruido_db is not None else None,
            "sibilancia_db": round(dsp.rms_db(s) - voz_db, 1)}


def _fala_arg(s: str | None) -> list | None:
    if not s:
        return None
    return [[float(a), float(b)] for a, b in (p.split("-") for p in s.split(","))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    li = sub.add_parser("limpar")
    li.add_argument("entrada")
    li.add_argument("saida")
    li.add_argument("--fala", help="trechos com fala em segundos: 0.3-2.1,2.6-5.0")
    li.add_argument("--modo", choices=["auto", "ia", "local"], default="auto")
    me = sub.add_parser("medir")
    me.add_argument("arquivo")
    me.add_argument("--fala")
    a = ap.parse_args()
    if a.cmd == "limpar":
        fala = _fala_arg(a.fala)
        antes = medir(ler(Path(a.entrada)), fala)
        rota = limpar(Path(a.entrada), Path(a.saida), fala, a.modo)
        depois = medir(ler(Path(a.saida)), fala)
        print(json.dumps({"rota": rota, "antes": antes, "depois": depois}, ensure_ascii=False))
    else:
        print(json.dumps(medir(ler(Path(a.arquivo)), _fala_arg(a.fala)), ensure_ascii=False))


if __name__ == "__main__":
    main()
