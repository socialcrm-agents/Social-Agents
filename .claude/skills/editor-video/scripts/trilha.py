#!/usr/bin/env python3
"""Trilha instrumental sem direitos autorais, sintetizada aqui mesmo (numpy) — nada baixado, nada licenciado.

Cada clima é um arranjo completo: bateria (kick com envelope de altura + clique, caixa/palma com ruído
filtrado, chimbal metálico), baixo com subharmônico, acordes com vozes encadeadas (piano, rhodes, pluck),
pad com chorus e reverb por convolução com resposta sintética, e no "energia" o pump de sidechain no kick.
Estrutura: intro curta (filtro abrindo + subida), corpo em duas partes (a segunda mais cheia) e final com
resolução na tônica nos últimos ~2 s, terminando em silêncio exatamente na duração pedida.
Mixagem por alvo de loudness de cada grupo e masterização em -18 LUFS (pico verdadeiro ≤ -1 dBTP), WAV
estéreo 48 kHz 24 bits. Determinística: mesma semente, mesmos bytes.

  trilha.py <clima> saida.wav --dur 30 [--bpm 120] [--semente 1] [--palavras-por-s 2.8]

Climas: energia (trap/pop moderno), inspirador (piano + pad), suspense, lofi, corporativo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

import dsp
from dsp import SR, midi_hz, seg

HERE = Path(__file__).resolve().parent
ALVO_LUFS = -18.0
TETO_DBTP = -1.0
MAX_DIRETO = 90.0  # acima disso o corpo é repetido em blocos de 8 compassos (memória baixa em vídeos longos)

QUALIDADES = {
    "maj": [0, 4, 7], "min": [0, 3, 7], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10],
    "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14], "m9": [0, 3, 7, 10, 14], "maj9": [0, 4, 7, 11, 14],
    "sus2": [0, 2, 7], "sus4": [0, 5, 7],
}

# tônica (MIDI), progressão (grau em semitons, qualidade), acorde de resolução, faixa de BPM, escala do lead
CLIMAS = {
    "energia": {"tonica": 57, "prog": [(0, "madd9"), (8, "maj7"), (3, "add9"), (10, "sus2")], "res": (0, "m9"),
                "bpm": (122, 150), "escala": [0, 3, 5, 7, 10], "rt60": 1.6,
                "mix": {"bateria": 0.0, "baixo": -4.5, "harmonia": -5.0, "lead": -8.0}},
    "inspirador": {"tonica": 60, "prog": [(0, "add9"), (7, "sus4"), (9, "m7"), (5, "maj9")], "res": (0, "maj9"),
                   "bpm": (76, 100), "escala": [0, 2, 4, 7, 9], "rt60": 2.6,
                   "mix": {"bateria": -7.0, "baixo": -6.0, "harmonia": 0.0, "lead": -4.0}},
    "suspense": {"tonica": 50, "prog": [(0, "min"), (0, "madd9"), (8, "maj"), (7, "maj")], "res": (0, "min"),
                 "bpm": (70, 96), "escala": [0, 1, 3, 7, 8], "rt60": 3.0,
                 "mix": {"bateria": -4.0, "baixo": -5.5, "harmonia": 0.0, "lead": -7.0}},
    "lofi": {"tonica": 60, "prog": [(2, "m9"), (7, "7"), (0, "maj9"), (9, "m7")], "res": (0, "maj9"),
             "bpm": (70, 90), "escala": [0, 2, 4, 7, 9], "rt60": 1.4,
             "mix": {"bateria": 0.0, "baixo": -5.5, "harmonia": -1.5, "lead": -12.0}},
    "corporativo": {"tonica": 62, "prog": [(0, "add9"), (5, "maj7"), (9, "m7"), (7, "sus4")], "res": (0, "add9"),
                    "bpm": (100, 124), "escala": [0, 2, 4, 7, 9], "rt60": 1.8,
                    "mix": {"bateria": -2.0, "baixo": -5.0, "harmonia": 0.0, "lead": -3.0}},
}
APELIDOS = {"trap": "energia", "pop": "energia", "energetico": "energia", "energética": "energia",
            "inspiracional": "inspirador", "piano": "inspirador", "tensao": "suspense", "tensão": "suspense",
            "lo-fi": "lofi", "chill": "lofi", "corporate": "corporativo", "institucional": "corporativo"}
# estilo do editor -> clima quando a pessoa pede só "--music auto"
CLIMA_DO_ESTILO = {"reels_viral": "energia", "anuncio_conversao": "energia", "editorial_premium": "inspirador",
                   "pro_clean": "corporativo"}


def nome_clima(clima: str) -> str:
    c = (clima or "").strip().lower()
    c = APELIDOS.get(c, c)
    if c not in CLIMAS:
        raise ValueError(f"clima '{clima}' não existe. Use: {', '.join(CLIMAS)}")
    return c


def bpm_sugerido(clima: str, palavras_por_s: float | None) -> int:
    """Fala rápida pede trilha mais rápida: 2 palavras/s = ponta lenta da faixa do clima, 4/s = ponta rápida."""
    lo, hi = CLIMAS[nome_clima(clima)]["bpm"]
    if not palavras_por_s:
        return int(round((lo + hi) / 2))
    k = min(max((palavras_por_s - 2.0) / 2.0, 0.0), 1.0)
    return int(round(lo + (hi - lo) * k))


def ritmo_da_fala(words: list[dict]) -> float | None:
    """Palavras por segundo de fala (só o tempo em que a pessoa fala, sem as pausas longas)."""
    if len(words) < 4:
        return None
    falando = sum(min(w["t1"] - w["t0"], 1.2) for w in words)
    gaps = sum(min(max(b["t0"] - a["t1"], 0), 0.35) for a, b in zip(words, words[1:]))
    return len(words) / max(falando + gaps, 0.5)


# ---------------------------------------------------------------------------------------------------------------
# instrumentos (cada um devolve um array mono; o arranjo posiciona e faz o pan)

def kick(rng, tipo: str = "pop") -> np.ndarray:
    longo = tipo == "808"
    n = seg(0.9 if longo else 0.45)
    t = dsp.tempo(n)
    f = (50 if longo else 52) + (120 if longo else 95) * np.exp(-t / 0.03)
    corpo = dsp.senoide(f, n) * (np.exp(-t / (0.22 if longo else 0.16)))
    clique = dsp.passa_alta(rng.standard_normal(n), 2500, 2) * np.exp(-t / 0.0035) * 0.22
    beater = np.sin(2 * np.pi * 1400 * t) * np.exp(-t / 0.006) * 0.15
    x = dsp.satura(corpo * 1.1 + clique + beater, 1.6)
    return dsp.fades(x, 0.0005, 0.02)


def caixa(rng) -> np.ndarray:
    n = seg(0.35)
    t = dsp.tempo(n)
    corpo = 0.55 * np.sin(2 * np.pi * (180 + 40 * np.exp(-t / 0.01)) * t) * np.exp(-t / 0.07)
    corpo += 0.25 * np.sin(2 * np.pi * 330 * t) * np.exp(-t / 0.045)
    esteira = dsp.filtro_fft(rng.standard_normal(n), dsp.combina(dsp.r_passa_alta(1600, 2), dsp.r_passa_baixa(9500, 2),
                                                                 dsp.r_sino(5000, 3, 1.2)))
    esteira = esteira / (np.std(esteira) + 1e-9) * 0.32 * np.exp(-t / 0.13)
    return dsp.fades(dsp.satura(corpo + esteira, 1.4), 0.0005, 0.03)


def palma(rng) -> np.ndarray:
    n = seg(0.4)
    t = dsp.tempo(n)
    base = dsp.filtro_fft(rng.standard_normal(n), dsp.combina(dsp.r_passa_banda(1300, 0.9), dsp.r_passa_alta(700, 2)))
    base /= np.std(base) + 1e-9
    env = np.zeros(n)
    for k, ti in enumerate((0.0, 0.0105, 0.0215)):
        env += (0.8 + 0.1 * k) * np.exp(-np.maximum(t - ti, 0) / 0.005) * (t >= ti)
    env += 0.75 * np.exp(-np.maximum(t - 0.031, 0) / 0.11) * (t >= 0.031)
    return dsp.fades(dsp.satura(base * env * 0.45, 1.3), 0.0005, 0.03)


_METAL = np.array([205.3, 304.4, 369.6, 522.7, 540.0, 800.0])  # razões do chimbal analógico clássico


def chimbal(rng, aberto: bool = False) -> np.ndarray:
    n = seg(0.45 if aberto else 0.12)
    t = dsp.tempo(n)
    metal = np.zeros(n)
    for f in _METAL * 1.9:
        tab = dsp.tabela_onda(np.array([1 / k if k % 2 else 0 for k in range(1, int(SR / 2 / f))]))
        metal += dsp.osc_tabela(tab, f, n, rng.uniform())
    x = 0.35 * metal / len(_METAL) + 0.65 * rng.standard_normal(n)
    x = dsp.filtro_fft(x, dsp.combina(dsp.r_passa_alta(7200, 3), dsp.r_sino(10500, 3, 1.0), dsp.r_passa_baixa(17000, 2)))
    x /= np.std(x) + 1e-9
    env = np.exp(-t / (0.22 if aberto else 0.028))
    return dsp.fades(x * env * 0.3, 0.0003, 0.01)


def shaker(rng) -> np.ndarray:
    n = seg(0.11)
    t = dsp.tempo(n)
    x = dsp.filtro_fft(rng.standard_normal(n), dsp.combina(dsp.r_passa_banda(6500, 1.2), dsp.r_passa_alta(3000, 2)))
    env = np.clip(t / 0.012, 0, 1) * np.exp(-np.maximum(t - 0.012, 0) / 0.035)
    return dsp.fades(x / (np.std(x) + 1e-9) * env * 0.25, 0.001, 0.01)


def prato(rng, dur: float = 2.2) -> np.ndarray:
    n = seg(dur)
    t = dsp.tempo(n)
    metal = np.zeros(n)
    for f in _METAL * 3.1:
        metal += np.sign(np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)))
    x = 0.25 * metal / len(_METAL) + rng.standard_normal(n)
    x = dsp.filtro_fft(x, dsp.combina(dsp.r_passa_alta(3800, 2), dsp.r_passa_baixa(15000, 2)))
    x /= np.std(x) + 1e-9
    env = np.exp(-t / (dur / 3.2)) * np.clip(t / 0.002, 0, 1)
    return dsp.fades(x * env * 0.22, 0.0005, 0.3)


def tambor_grave(rng) -> np.ndarray:
    """Tímpano/impacto cinematográfico (suspense e final)."""
    n = seg(2.2)
    t = dsp.tempo(n)
    f = 52 + 38 * np.exp(-t / 0.06)
    corpo = dsp.senoide(f, n) * np.exp(-t / 0.65) + 0.4 * dsp.senoide(f * 1.5, n) * np.exp(-t / 0.25)
    pele = dsp.passa_baixa(rng.standard_normal(n), 900, 2) * np.exp(-t / 0.05) * 0.25
    return dsp.fades(dsp.satura(corpo + pele, 1.3), 0.001, 0.4)


def nota_piano(f: float, dur: float, vel: float) -> np.ndarray:
    n = seg(dur + 1.2)
    t = dsp.tempo(n)
    tau0 = float(np.clip(3.2 * (261.6 / f) ** 0.5, 0.8, 6.0))
    x = np.zeros(n)
    brilho = 0.55 + 0.45 * vel
    for k in range(1, 11):
        fk = f * k * math.sqrt(1 + 0.00038 * k * k)
        if fk > SR * 0.45:
            break
        a = (1 / k ** 1.15) * brilho ** (k - 1)
        tau = tau0 / (1 + 0.45 * (k - 1))
        env = 0.65 * np.exp(-t / (tau * 0.18)) + 0.35 * np.exp(-t / tau)
        if k <= 3:  # cordas em uníssono levemente desafinadas: o batimento que dá vida ao piano
            x += a * env * 0.5 * (np.sin(2 * np.pi * fk * 1.0006 * t) + np.sin(2 * np.pi * fk * 0.9994 * t + 0.7))
        else:
            x += a * env * np.sin(2 * np.pi * fk * t)
    martelo = np.exp(-t / 0.004) * np.sin(2 * np.pi * min(f * 7, 6000) * t) * 0.05
    abafa = np.where(t < dur, 1.0, np.exp(-(t - dur) / 0.16))
    return dsp.fades((x + martelo) * abafa * vel, 0.0015, 0.05)


def nota_rhodes(f: float, dur: float, vel: float) -> np.ndarray:
    n = seg(dur + 0.9)
    t = dsp.tempo(n)
    indice = 0.25 + 1.6 * vel * np.exp(-t / 0.22)
    x = np.sin(2 * np.pi * f * t + indice * np.sin(2 * np.pi * f * t))
    x += 0.12 * vel * np.sin(2 * np.pi * f * 14.1 * t) * np.exp(-t / 0.03) if f * 14.1 < SR * 0.45 else 0
    env = np.exp(-t / 1.9) * np.clip(t / 0.002, 0, 1)
    abafa = np.where(t < dur, 1.0, np.exp(-(t - dur) / 0.12))
    return dsp.fades(x * env * abafa * vel * 0.6, 0.001, 0.04)


def nota_pluck(f: float, dur: float, vel: float, brilho: float = 0.7) -> np.ndarray:
    n = seg(dur + 0.5)
    t = dsp.tempo(n)
    x = np.zeros(n)
    for k in range(1, 24):
        fk = f * k
        if fk > SR * 0.42:
            break
        tau = 0.55 / k ** (1.1 - 0.5 * brilho)
        x += (1 / k) * np.exp(-t / tau) * np.sin(2 * np.pi * fk * t + 0.3 * k)
    abafa = np.where(t < dur, 1.0, np.exp(-(t - dur) / 0.08))
    return dsp.fades(x * abafa * vel * 0.5, 0.001, 0.03)


def nota_pad(f: float, dur: float, vel: float, brilho: float = 0.35, ataque: float = 0.5) -> np.ndarray:
    n = seg(dur + 1.2)
    tab = dsp.tabela_onda(dsp.serra_limitada(f, brilho))
    x = np.zeros(n)
    for k, c in enumerate((-9.0, 0.0, 8.0)):
        x += dsp.osc_tabela(tab, f * 2 ** (c / 1200), n, 0.31 * k)
    env = dsp.env_adsr(n, ataque, 1.0, 0.8, 1.0, dur)
    return dsp.fades(x / 3 * env * vel, 0.002, 0.08)


def nota_baixo(f: float, dur: float, vel: float, tipo: str = "sub") -> np.ndarray:
    """Baixo com subharmônico: fundamental + oitava abaixo (sub) + harmônicos saturados para aparecer no celular."""
    n = seg(dur + 0.25)
    t = dsp.tempo(n)
    if tipo == "808":
        fv = f * (1 + 0.6 * np.exp(-t / 0.018))
        base = dsp.senoide(fv, n)
        x = dsp.satura(base * 1.8, 2.2) * 0.8 + 0.12 * dsp.senoide(fv / 2, n)
        env = np.clip(t / 0.003, 0, 1) * (0.55 + 0.45 * np.exp(-t / 0.3))
    else:
        tab = dsp.tabela_onda(dsp.serra_limitada(f, 0.15))
        corpo = dsp.osc_tabela(tab, f, n)
        corpo = dsp.passa_baixa(corpo, 380 + 500 * vel, 2)
        x = 0.7 * dsp.senoide(f, n) + 0.45 * corpo + 0.4 * dsp.senoide(f / 2, n)
        x = dsp.satura(x, 1.3)
        env = dsp.env_adsr(n, 0.006, 0.35, 0.7, 0.12, dur)
    abafa = np.where(t < dur, 1.0, np.exp(-(t - dur) / (0.05 if tipo == "808" else 0.07)))
    return dsp.fades(x * env * abafa * vel, 0.002, 0.03)


def subida(rng, dur: float) -> np.ndarray:
    """Ruído com filtro abrindo (preparação para a entrada da bateria)."""
    n = seg(dur)
    x = dsp.ruido(rng, n, "rosa")
    fc0, fc1 = 300.0, 9000.0
    x = dsp.filtro_variavel(x, lambda f, tt: dsp.r_passa_banda(fc0 * (fc1 / fc0) ** min(max(tt / dur, 0), 1), 1.4)(f))
    env = (dsp.tempo(n) / dur) ** 2
    return dsp.fades(x * env * 0.25, 0.01, 0.02)


def vinil(rng, n: int) -> np.ndarray:
    """Chiado de fita + estalos de vinil (lofi)."""
    chiado = dsp.filtro_fft(rng.standard_normal(n), dsp.combina(dsp.r_passa_alta(2000, 1), dsp.r_passa_baixa(9000, 2)))
    chiado = chiado / (np.std(chiado) + 1e-9) * 0.012
    estalos = np.zeros(n)
    pos = rng.choice(n, size=max(int(n / SR * 9), 1), replace=False)
    estalos[pos] = rng.uniform(-1, 1, len(pos)) * rng.uniform(0.05, 0.4, len(pos))
    estalos = dsp.filtro_fft(estalos, dsp.combina(dsp.r_passa_alta(900, 1), dsp.r_passa_baixa(7000, 1)))
    return chiado + estalos


# ---------------------------------------------------------------------------------------------------------------
# harmonia

def voicing(tonica: int, grau: int, qual: str, centro: int) -> list[int]:
    """Coloca cada nota do acorde na oitava mais perto de `centro` (encadeamento suave entre acordes)."""
    out = set()
    for iv in QUALIDADES[qual]:
        pc = (tonica + grau + iv) % 12
        m = centro - 6 + ((pc - (centro - 6)) % 12)
        out.add(m + (12 if iv >= 12 and m < centro else 0))
    return sorted(out)


def raiz_baixo(tonica: int, grau: int) -> int:
    pc = (tonica + grau) % 12
    return 36 + ((pc - 36) % 12)  # entre C2 e B2 (65-123 Hz); o sub fica uma oitava abaixo


# ---------------------------------------------------------------------------------------------------------------
# arranjo

class Grade:
    def __init__(self, bpm: float, swing: float = 0.5):
        self.bpm = bpm
        self.batida = 60.0 / bpm
        self.compasso = 4 * self.batida
        self.swing = swing

    def t(self, compasso: int, passo: float) -> float:
        """Tempo do passo (0..15, semicolcheias) no compasso, com swing nas colcheias de contratempo."""
        base = compasso * self.compasso + passo * self.batida / 4
        if self.swing != 0.5 and int(passo) % 4 == 2 and passo == int(passo):
            base += (self.swing - 0.5) * self.batida
        return base


def estrutura(dur: float, g: Grade) -> dict:
    """Intro curta, corpo (A e B) e o começo da resolução, todos na grade."""
    b = g.batida
    t_res = round((dur - 2.0) / b) * b
    t_res = min(max(t_res, dur - 2.6), dur - 1.4)
    if dur < 5:
        t_res = dur * 0.6
    t_res = max(t_res, 0.0)
    n_intro = 1 if g.compasso >= 2.0 else 2
    intro = min(n_intro * g.compasso, 0.2 * dur)
    intro = math.floor(intro / b + 1e-6) * b
    if intro < b:
        intro = 0.0
    c_ini = int(round(intro / g.compasso)) if intro and abs(intro / g.compasso - round(intro / g.compasso)) < 1e-6 else None
    n_comp = int(math.ceil(t_res / g.compasso)) + 1
    corpo_comp = max(n_comp - (c_ini or 0), 1)
    b_ini = (c_ini or 0) + max(corpo_comp // 2, 2)
    return {"intro": intro, "t_res": t_res, "n_comp": n_comp, "parte_b": b_ini * g.compasso, "dur": dur}


def _toca(bus, notas, fn, pan: float = 0.0, cache: dict | None = None, ate: float | None = None) -> None:
    """notas: (t, dur, midi, vel). Corta a duração das notas que passariam de `ate` (a resolução)."""
    cache = {} if cache is None else cache
    for t, d, m, v in notas:
        if ate is not None:
            if t >= ate - 1e-6:
                continue
            d = min(d, max(ate - t, 0.05))
        d, v = round(d, 2), round(v * 20) / 20  # quantizado: notas repetidas saem do cache (bem mais rápido)
        key = (round(m, 3), d, v)
        if key not in cache:
            cache[key] = fn(midi_hz(m), d, v)
        dsp.soma_em(bus, dsp.mono_para_estereo(cache[key], pan), seg(t))


def _bate(bus, eventos, amostras: list, pan: float = 0.0, ate: float | None = None) -> None:
    for t, v, k in eventos:
        if ate is not None and t >= ate - 1e-6:
            continue
        dsp.soma_em(bus, dsp.mono_para_estereo(amostras[k % len(amostras)] * v, pan), seg(t))


def pump(n: int, batidas: list[float], prof: float = 0.55, solta: float = 0.16) -> np.ndarray:
    """Ganho do sidechain: abaixa a harmonia em cada kick e volta em ~solta s."""
    g = np.ones(n)
    ln = seg(solta * 4)
    tt = dsp.tempo(ln)
    forma = 1 - prof * np.exp(-tt / solta) * np.clip(tt / 0.004, 0, 1)
    for t in batidas:
        i0 = seg(t) if t > 0 else 0
        m = min(ln, n - i0)
        if m > 0:
            g[i0:i0 + m] = np.minimum(g[i0:i0 + m], forma[:m])
    return g


def arranjar(clima: str, dur: float, bpm: float, semente: int) -> dict[str, np.ndarray]:
    """Monta os grupos (bateria, baixo, harmonia, lead) já com efeitos, ainda sem a mixagem final."""
    cfg = CLIMAS[clima]
    rng_t = np.random.default_rng([semente, 1])  # humanização e escolhas do arranjo
    tonica = cfg["tonica"] + int(rng_t.choice([-2, -1, 0, 0, 1, 2]))
    swing = 0.58 if clima == "lofi" else 0.5
    g = Grade(bpm, swing)
    est = estrutura(dur, g)
    n = seg(dur)
    t_res, intro, parte_b = est["t_res"], est["intro"], est["parte_b"]
    trap = clima == "energia" and bpm >= 125
    bus = {k: np.zeros((2, n)) for k in ("bateria", "baixo", "harmonia", "lead")}

    def r(k):
        return np.random.default_rng([semente, 100 + k])

    amostras = {
        "kick": [kick(r(i), "808" if trap else "pop") for i in range(2)],
        "caixa": [caixa(r(10 + i)) for i in range(3)],
        "palma": [palma(r(20 + i)) for i in range(3)],
        "hh": [chimbal(r(30 + i)) for i in range(4)],
        "hho": [chimbal(r(40), aberto=True)],
        "shaker": [shaker(r(50 + i)) for i in range(4)],
    }
    ev = {k: [] for k in ("kick", "caixa", "palma", "hh", "hho", "shaker", "tambor")}
    notas = {k: [] for k in ("baixo", "acorde", "pad", "arpejo", "lead", "drone")}
    centro = 64 if clima != "suspense" else 60
    motivo = [(p, int(rng_t.integers(0, 5))) for p in range(0, 32, 2) if rng_t.uniform() < 0.55]
    hum = lambda s: float(rng_t.normal(0, s))  # noqa: E731
    vel = lambda base, var=0.08: float(np.clip(base + rng_t.normal(0, var), 0.2, 1.0))  # noqa: E731

    for c in range(est["n_comp"]):
        t0 = c * g.compasso
        if t0 >= t_res:
            break
        grau, qual = cfg["prog"][c % len(cfg["prog"])]
        voz = voicing(tonica, grau, qual, centro)
        raiz = raiz_baixo(tonica, grau)
        tem_bateria = t0 >= intro - 1e-6
        em_b = t0 >= parte_b - 1e-6
        T = g.t

        if clima == "energia":
            notas["pad"].append((t0, g.compasso, voz[0] - 12, 0.7))
            notas["pad"] += [(t0, g.compasso, m, 0.55) for m in voz]
            if tem_bateria:
                passos_k = [0, 7, 10] if c % 2 == 0 else [0, 3, 10, 13]
                if not trap:
                    passos_k = [0, 4, 8, 12]
                ev["kick"] += [(T(c, p), vel(1.0 if p == 0 else 0.88, 0.04), c) for p in passos_k]
                for p in ([8] if trap else [4, 12]):
                    ev["palma"].append((T(c, p) + 0.004, vel(0.95, 0.04), c))
                    ev["caixa"].append((T(c, p), vel(0.7, 0.05), c + p))
                hh = range(0, 16, 1 if (em_b and trap) else 2) if trap else [2, 6, 10, 14]
                for p in hh:
                    ev["hh"].append((T(c, p), vel(0.75 if p % 4 == 0 else 0.5, 0.06), p))
                if trap and c % 2 == 1:  # rolo de chimbal (tercinas de semicolcheia) no último tempo
                    ev["hh"] += [(T(c, 12) + i * g.batida / 6, vel(0.45 + 0.07 * i, 0.03), i) for i in range(6)]
                if not trap:
                    ev["shaker"] += [(T(c, p), vel(0.5 if p % 2 else 0.3, 0.05), p) for p in range(16)]
                if c % 4 == 3:
                    ev["hho"].append((T(c, 14), vel(0.6, 0.05), 0))
                for i, p in enumerate(passos_k):
                    fim = passos_k[i + 1] if i + 1 < len(passos_k) else 16
                    notas["baixo"].append((T(c, p), (fim - p) * g.batida / 4 * 0.95, raiz, 0.9))
                if em_b:
                    for p in (0, 3, 6, 10, 12):
                        notas["acorde"] += [(T(c, p), g.batida * 0.45, m + 12, vel(0.55, 0.05)) for m in voz[:3]]
                    esc = cfg["escala"]
                    for p, gi in motivo:
                        if p // 16 == c % 2:
                            nota = tonica + 12 + esc[(gi + (grau % 5)) % len(esc)]
                            notas["lead"].append((T(c, p % 16), g.batida * 0.45, nota, vel(0.7, 0.08)))
            else:
                notas["baixo"].append((t0, g.compasso, raiz, 0.5))

        elif clima == "inspirador":
            padrao = [0, 1, 2, 3, 2, 1, 2, 3]  # sobe e desce pelas vozes do acorde
            arp = [voz[0] - 12] + voz
            for i, p in enumerate(range(0, 16, 2)):
                m = arp[padrao[i] % len(arp)] + (12 if i in (3, 4) else 0)
                notas["arpejo"].append((T(c, p) + hum(0.004), g.batida * 0.9, m, vel(0.55 if i % 2 else 0.68)))
            notas["acorde"].append((t0, g.compasso, raiz + 12, vel(0.75, 0.04)))
            notas["acorde"].append((t0, g.compasso, raiz + 24, vel(0.55, 0.04)))
            if c >= 1 or not intro:
                notas["pad"] += [(t0, g.compasso, m, 0.5) for m in voz]
            notas["baixo"].append((t0, g.compasso, raiz, 0.6))
            if tem_bateria and em_b:
                ev["kick"] += [(T(c, p), vel(0.75, 0.04), c) for p in (0, 10)]
                ev["caixa"] += [(T(c, p), vel(0.5, 0.04), p) for p in (8,)]
                ev["hh"] += [(T(c, p), vel(0.35 if p % 4 else 0.45, 0.04), p) for p in range(0, 16, 2)]
            if em_b:
                notas["lead"] += [(T(c, 0), g.compasso * 0.9, voz[-1] + 12, vel(0.5, 0.03))]

        elif clima == "suspense":
            notas["drone"].append((t0, g.compasso, raiz + 12, 0.7))
            notas["drone"] += [(t0, g.compasso, m - 12, 0.45) for m in voz]
            for p in range(0, 16, 2):  # ostinato grave em colcheias, acento no tempo
                notas["arpejo"].append((T(c, p), g.batida * 0.42, raiz + 12 + (12 if p in (6, 14) else 0),
                                        vel(0.75 if p % 4 == 0 else 0.5, 0.04)))
            if tem_bateria:
                ev["hh"] += [(T(c, p), vel(0.32 if p % 4 else 0.42, 0.03), p) for p in range(0, 16, 2)]
                if c % 2 == 0:
                    ev["tambor"].append((t0, vel(0.9, 0.04), 0))
                if em_b:
                    ev["kick"] += [(T(c, p), vel(0.8, 0.04), c) for p in (0, 6)]
                    notas["lead"].append((t0, g.compasso * 0.98, tonica + 24 + (1 if c % 2 else 0), 0.45))
            notas["baixo"].append((t0, g.compasso, raiz, 0.55))

        elif clima == "lofi":
            notas["acorde"] += [(T(c, 0) + hum(0.006) + 0.008 * i, g.batida * (2.4 if c % 2 else 3.7), m,
                                 vel(0.6, 0.05)) for i, m in enumerate(voz)]
            if c % 2 == 1:
                notas["acorde"] += [(T(c, 10) + hum(0.006), g.batida * 1.2, m, vel(0.45, 0.05)) for m in voz[1:]]
            if tem_bateria:
                ev["kick"] += [(T(c, p) + hum(0.004), vel(0.9, 0.05), c) for p in ([0, 10] if c % 2 == 0 else [0, 7, 10])]
                ev["caixa"] += [(T(c, p) + 0.012 + hum(0.004), vel(0.75, 0.05), p) for p in (4, 12)]
                ev["hh"] += [(T(c, p) + hum(0.005), vel(0.5 if p % 4 == 0 else 0.3, 0.07), p) for p in range(0, 16, 2)]
                notas["baixo"] += [(T(c, 0), g.batida * 2.45, raiz, 0.75), (T(c, 10), g.batida * 1.45, raiz + (7 if c % 2 else 0), 0.6)]
            else:
                notas["baixo"].append((t0, g.compasso, raiz, 0.45))
            if em_b:
                esc = cfg["escala"]
                for p, gi in motivo[:4]:
                    if p // 16 == c % 2:
                        notas["lead"].append((T(c, p % 16), g.batida * 0.8, tonica + 12 + esc[gi % len(esc)], vel(0.5)))

        else:  # corporativo
            arp = voz + [voz[1] + 12]
            for i, p in enumerate(range(0, 16, 2)):
                notas["arpejo"].append((T(c, p), g.batida * 0.42, arp[(i * 2) % len(arp)] if i % 2 else arp[i % len(arp)],
                                        vel(0.7 if i % 4 == 0 else 0.55)))
            notas["pad"] += [(t0, g.compasso, m + 12, 0.45) for m in voz[:3]]
            if tem_bateria:
                ev["kick"] += [(T(c, p), vel(0.85, 0.04), c) for p in (0, 4, 8, 12)]
                ev["palma"] += [(T(c, p), vel(0.7, 0.04), p) for p in (4, 12)]
                ev["shaker"] += [(T(c, p), vel(0.55 if p % 2 else 0.3, 0.05), p) for p in range(16)]
                notas["baixo"] += [(T(c, p), g.batida * 0.42, raiz, vel(0.8 if p % 4 == 0 else 0.65, 0.04)) for p in range(0, 16, 2)]
            else:
                notas["baixo"].append((t0, g.compasso, raiz, 0.5))
            if em_b:
                notas["lead"] += [(T(c, p), g.batida * 1.6, voz[-1] + 12 - (0 if p == 0 else 2), vel(0.5, 0.04))
                                  for p in (0, 8)]

    # ---- resolução: tônica segurada até o fim, impacto no início dela ----
    g_res, q_res = cfg["res"]
    voz_res = voicing(tonica, g_res, q_res, centro)
    raiz_res = raiz_baixo(tonica, g_res)
    d_res = max(dur - t_res, 0.3)
    if t_res > 0.5:
        if clima in ("energia", "corporativo"):
            ev["kick"].append((t_res, 1.0, 0))
        if clima == "suspense":
            ev["tambor"].append((t_res, 1.0, 1))
    notas_res = [(t_res, d_res, m, 0.62) for m in voz_res]
    baixo_res = [(t_res, d_res, raiz_res, 0.7)]

    # ---- síntese ----
    rng_s = np.random.default_rng([semente, 2])
    _bate(bus["bateria"], ev["kick"], amostras["kick"], 0.0, t_res + 0.01)
    _bate(bus["bateria"], ev["caixa"], amostras["caixa"], 0.05, t_res)
    _bate(bus["bateria"], ev["palma"], amostras["palma"], -0.05, t_res)
    _bate(bus["bateria"], ev["hh"], amostras["hh"], 0.25, t_res)
    _bate(bus["bateria"], ev["hho"], amostras["hho"], 0.25, t_res)
    _bate(bus["bateria"], ev["shaker"], amostras["shaker"], -0.35, t_res)
    if ev["tambor"]:
        _bate(bus["bateria"], ev["tambor"], [tambor_grave(r(60)), tambor_grave(r(61))], 0.0, t_res + 0.01)
    if t_res > 0.5 and clima in ("energia", "corporativo", "inspirador"):
        dsp.soma_em(bus["bateria"], dsp.mono_para_estereo(prato(r(70), min(d_res + 0.3, 3.0)) * 0.9, 0.0), seg(t_res))
    # subida antes da bateria entrar (e antes da resolução nos climas com batida)
    alvos = {"energia": [intro], "corporativo": [intro], "inspirador": [parte_b]}.get(clima, [])
    for alvo in [a for a in alvos if g.batida * 2 <= a < t_res - g.batida]:
        dsub = min(g.batida * 2, alvo)
        x = subida(r(80), dsub)
        dsp.soma_em(bus["bateria"], np.stack([x, dsp.atraso_modulado(x, np.full(len(x), 0.011))]), seg(alvo - dsub))

    tipo_baixo = "808" if trap else "sub"
    cache_b: dict = {}
    _toca(bus["baixo"], notas["baixo"], lambda f, d, v: nota_baixo(f, d, v, tipo_baixo), 0.0, cache_b, t_res)
    _toca(bus["baixo"], baixo_res, lambda f, d, v: nota_baixo(f, d, v, "sub"), 0.0, {})

    h = bus["harmonia"]
    cache_h: dict = {}
    brilho_pad = {"energia": 0.45, "inspirador": 0.3, "suspense": 0.12, "lofi": 0.2, "corporativo": 0.5}[clima]
    fpad = lambda f, d, v: nota_pad(f, d, v, brilho_pad, 0.35 if clima == "energia" else 0.8)  # noqa: E731
    for i, nt in enumerate(notas["pad"]):
        _toca(h, [nt], fpad, (-0.4, 0.4, -0.15, 0.15)[i % 4] * 0.8, cache_h, t_res)
    for i, nt in enumerate(notas["drone"]):
        _toca(h, [nt], lambda f, d, v: nota_pad(f, d, v, 0.1, 1.5), (-0.5, 0.5, 0.0)[i % 3], cache_h, t_res + 0.6)
    if clima == "inspirador":
        _toca(h, notas["arpejo"], nota_piano, 0.1, {}, t_res)
        _toca(h, notas["acorde"], nota_piano, -0.1, {}, t_res)
        _toca(h, notas_res + [(t_res, d_res, voz_res[0] - 12, 0.7)], nota_piano, 0.0, {})
        _toca(h, [(t_res, d_res, m, 0.4) for m in voz_res], fpad, 0.0, {})
    elif clima == "lofi":
        _toca(h, notas["acorde"], nota_rhodes, 0.0, {}, t_res)
        _toca(h, notas_res, nota_rhodes, 0.0, {})
    elif clima == "suspense":
        _toca(h, notas["arpejo"], lambda f, d, v: nota_pluck(f, d, v, 0.25), 0.0, {}, t_res)
        _toca(h, [(t_res, d_res, m - 12, 0.5) for m in voz_res], lambda f, d, v: nota_pad(f, d, v, 0.1, 0.05), 0.0, {})
    elif clima == "corporativo":
        _toca(h, notas["arpejo"], lambda f, d, v: nota_pluck(f, d, v, 0.55), 0.2, {}, t_res)
        _toca(h, notas_res, lambda f, d, v: nota_pluck(f, d, v, 0.55), 0.0, {})
        _toca(h, [(t_res, d_res, m + 12, 0.4) for m in voz_res[:3]], fpad, 0.0, {})
    else:  # energia
        _toca(h, notas["acorde"], lambda f, d, v: nota_pluck(f, d, v, 0.85), 0.0, {}, t_res)
        _toca(h, [(t_res, d_res, m, 0.5) for m in voz_res], fpad, 0.0, {})
    lead_fn = {"energia": lambda f, d, v: nota_pluck(f, d, v, 0.95), "inspirador": nota_piano,
               "suspense": lambda f, d, v: nota_pad(f, d, v, 0.05, 1.2), "lofi": nota_rhodes,
               "corporativo": lambda f, d, v: nota_pluck(f, d, v, 0.8)}[clima]
    _toca(bus["lead"], notas["lead"], lead_fn, 0.15, {}, t_res)

    # ---- efeitos por grupo ----
    h = dsp.chorus(h, 2.5, 12.0, 0.3, 0.45 if clima != "inspirador" else 0.25)
    if clima == "lofi":  # wow/flutter de fita em toda a harmonia
        tt = dsp.tempo(n)
        wow = (1.6 + 1.2 * np.sin(2 * np.pi * 0.45 * tt) + 0.25 * np.sin(2 * np.pi * 5.5 * tt)) / 1000
        h = np.stack([dsp.atraso_modulado(c, wow) for c in h])
        h = dsp.filtro_fft(h, dsp.combina(dsp.r_passa_baixa(5200, 2), dsp.r_passa_alta(120, 1)))
    ir = dsp.resposta_reverb(rng_s, cfg["rt60"], 22, 0.5)
    h = h + 0.38 * dsp.convolve_fft(h, ir)
    lead = bus["lead"]
    lead = lead + 0.3 * dsp.convolve_fft(lead, ir)
    ir_sala = dsp.resposta_reverb(np.random.default_rng([semente, 3]), 0.7, 6, 0.4, 0.8)
    bat = bus["bateria"]
    bat = bat + (0.10 if clima != "suspense" else 0.3) * dsp.convolve_fft(bat, ir_sala)
    if clima == "lofi":
        bat = dsp.filtro_fft(bat, dsp.r_passa_baixa(6500, 2))
        bat = bat + dsp.mono_para_estereo(vinil(rng_s, n), 0.0) * 0.6
    baixo = dsp.filtro_fft(bus["baixo"], dsp.combina(dsp.r_passa_alta(28, 3), dsp.r_passa_baixa(4000, 2)))
    if clima == "energia":  # sidechain: harmonia e lead "respiram" no kick
        pp = pump(n, [t for t, _, _ in ev["kick"] if t < t_res], 0.6 if trap else 0.45)
        h = h * pp
        lead = lead * pp
    # intro: filtro abrindo na harmonia até a bateria entrar
    if intro > 0:
        ni = seg(intro + 0.15)
        trecho = h[:, :ni]
        fc0 = 350.0

        def resp(f, tt, _i=intro):
            fc = fc0 * (18000 / fc0) ** min(max(tt / _i, 0), 1)
            return dsp.r_passa_baixa(fc, 2)(f)
        h = h.copy()
        h[:, :ni] = dsp.filtro_variavel(trecho, resp)
    return {"bateria": bat, "baixo": baixo, "harmonia": h, "lead": lead, "_est": est, "_tonica": tonica}


def mixar(grupos: dict, clima: str, dur: float) -> np.ndarray:
    """Equilibra os grupos por loudness (alvos do clima), soma, comprime de leve e masteriza em -18 LUFS."""
    alvo = CLIMAS[clima]["mix"]
    est = grupos["_est"]
    ref_a, ref_b = seg(est["intro"]), seg(max(est["t_res"], est["intro"] + 0.5))
    mix = np.zeros_like(grupos["bateria"])
    for k, rel in alvo.items():
        x = grupos[k]
        if not np.any(x):
            continue
        trecho = x[:, ref_a:ref_b] if ref_b - ref_a > seg(1.0) else x
        lk = dsp.loudness(trecho)
        if lk <= -69:
            lk = dsp.loudness(x)
        if lk <= -69:
            continue
        mix += x * dsp.de_db(-20 + rel - lk)
    mix = dsp.filtro_fft(mix, dsp.combina(dsp.r_passa_alta(32, 3), dsp.r_sino(300, -1.5, 0.8),
                                          dsp.r_prateleira(9000, 1.5, True)))
    mix = dsp.compressor(mix, -24, 2.0, 0.01, 0.18)
    # final: silêncio exato na duração pedida (fade em cosseno nos últimos 0,45 s)
    mix = dsp.fades(mix, 0.004, min(0.45, dur * 0.1))
    for _ in range(3):  # normaliza, limita e confere (o limitador baixa um pouco o loudness)
        mix *= dsp.de_db(ALVO_LUFS - dsp.loudness(mix))
        mix = dsp.limitador(mix, TETO_DBTP - 0.8)
        if abs(dsp.loudness(mix) - ALVO_LUFS) < 0.15:
            break
    if dsp.pico_verdadeiro(mix) > TETO_DBTP:
        mix *= dsp.de_db(TETO_DBTP - 0.1 - dsp.pico_verdadeiro(mix))
    return mix


def gerar(clima: str, dur: float, bpm: float | None = None, semente: int = 1) -> np.ndarray:
    """Trilha pronta (2, round(dur*48000)) masterizada em -18 LUFS."""
    clima = nome_clima(clima)
    if dur <= 0:
        raise ValueError("duração precisa ser > 0")
    bpm = float(bpm or bpm_sugerido(clima, None))
    n_total = seg(dur)
    if dur <= MAX_DIRETO:
        out = mixar(arranjar(clima, dur, bpm, semente), clima, dur)
        return out[:, :n_total]
    # vídeo longo: gera ~MAX_DIRETO s e repete um bloco de 8 compassos do corpo (emenda em cruz na batida)
    compasso = 4 * 60.0 / bpm
    bloco = 8 * compasso
    m = int(math.ceil((dur - MAX_DIRETO) / bloco))
    dur_nucleo = dur - m * bloco
    nucleo = mixar(arranjar(clima, dur_nucleo, bpm, semente), clima, dur_nucleo)
    est = estrutura(dur_nucleo, Grade(bpm))
    c_a = int(math.ceil(est["intro"] / compasso + 1e-6)) + 4
    a, b = seg(c_a * compasso), seg((c_a + 8) * compasso)
    xf = seg(0.02)
    rampa = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
    partes = [nucleo[:, :b - xf].astype(np.float32)]
    cauda = nucleo[:, b - xf:b]
    for y in [nucleo[:, a - xf:b]] * m + [nucleo[:, b - xf:]]:  # cada peça começa xf antes para a emenda em cruz
        partes.append((cauda * (1 - rampa) + y[:, :xf] * rampa).astype(np.float32))
        corpo = y[:, xf:]
        partes.append(corpo[:, :-xf].astype(np.float32))
        cauda = corpo[:, -xf:]
    partes.append(cauda.astype(np.float32))
    out = np.concatenate(partes, axis=1)
    if out.shape[1] < n_total:
        out = np.pad(out, ((0, 0), (0, n_total - out.shape[1])))
    return out[:, :n_total]


# ---------------------------------------------------------------------------------------------------------------
# arquivo, cache e integração com o projeto

def versao() -> str:
    h = hashlib.sha256()
    for f in (HERE / "trilha.py", HERE / "dsp.py"):
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def chave(clima: str, bpm: float, dur: float, semente: int, fala: list | None = None, abaixa_db: float = 0.0) -> str:
    ent = json.dumps([nome_clima(clima), round(float(bpm), 2), round(float(dur), 3), int(semente), versao(),
                      fala or [], round(float(abaixa_db), 2)])
    return hashlib.sha256(ent.encode()).hexdigest()[:16]


def automacao_fala(n: int, fala: list, abaixa_db: float, antes: float = 0.12, depois: float = 0.15,
                   volta: float = 0.35) -> np.ndarray:
    """Ganho que abaixa a trilha `abaixa_db` enquanto a pessoa fala: desce 0,12 s antes da primeira palavra
    (a voz entra limpa) e volta em 0,35 s depois de 0,15 s de silêncio. Curvas em cosseno (sem degrau)."""
    presenca = np.zeros(n)
    for a, b in fala:
        ia, ib = seg(max(a - antes, 0)), seg(b + depois)
        sa, sb = seg(antes), seg(volta)
        i0, i1 = max(ia - sa, 0), min(ib + sb, n)
        if i1 <= i0:
            continue
        idx = np.arange(i0, i1)
        desce = 0.5 - 0.5 * np.cos(np.pi * np.clip((idx - (ia - sa)) / sa, 0, 1))
        sobe = 0.5 + 0.5 * np.cos(np.pi * np.clip((idx - ib) / sb, 0, 1))
        presenca[i0:i1] = np.maximum(presenca[i0:i1], np.minimum(desce, sobe))
    return 10 ** (-abaixa_db * presenca / 20)


def gerar_arquivo(clima: str, saida: Path, dur: float, bpm: float | None = None, semente: int = 1,
                  fala: list | None = None, abaixa_db: float = 0.0) -> dict:
    clima = nome_clima(clima)
    bpm = float(bpm or bpm_sugerido(clima, None))
    x = gerar(clima, dur, bpm, semente)
    amostra = x[:, :seg(MAX_DIRETO)]  # nos longos o resto é repetição do mesmo bloco
    info = {"clima": clima, "bpm": bpm, "dur": round(x.shape[1] / SR, 3), "semente": semente,
            "lufs": round(dsp.loudness(amostra), 2), "pico_dbtp": round(dsp.pico_verdadeiro(amostra), 2),
            "arquivo": str(saida)}
    if fala and abaixa_db:
        x = x * automacao_fala(x.shape[1], fala, abaixa_db)
    dsp.grava_wav(Path(saida), x)
    return info


VOLUME_AUTO = 0.5  # trilha a -18 LUFS × 0,5 (-6 dB) fica ~10 LU abaixo da voz (-14) nas pausas
ABAIXA_FALA_DB = 6.0  # quanto a trilha já vem abaixada sob a fala (o sidechain do render abaixa mais por cima)


def trilha_do_projeto(work: Path, pedido: dict, dur: float, words: list[dict], estilo: str | None = None) -> dict:
    """Resolve um pedido {"auto": True, "clima"?, "volume"?, "bpm"?, "semente"?, "abaixa_fala_db"?} numa
    trilha em cache (work/trilha_<chave>.wav) e devolve a entrada "music" da timeline (o render usa o caminho
    de sempre, com o ducking por sidechain). A trilha já vem com a automação que a abaixa onde há fala."""
    clima = nome_clima(pedido.get("clima") or CLIMA_DO_ESTILO.get(estilo or "", "corporativo"))
    pps = ritmo_da_fala(words)
    bpm = float(pedido.get("bpm") or bpm_sugerido(clima, pps))
    semente = int(pedido.get("semente", 1))
    dur = round(float(dur), 3)
    abaixa = float(pedido.get("abaixa_fala_db", ABAIXA_FALA_DB))
    fala = [[round(a, 2), round(b, 2)] for a, b in regioes_fala(words, dur)[0]] if abaixa else []
    motor = usado = pedido.get("motor", "auto")
    path = None
    if motor in ("auto", "ia"):
        # música de verdade com IA (ACE-Step no ar neste computador); em cache como a sintetizada
        import musica_ia
        k = musica_ia.chave(clima, bpm, dur, semente, fala, abaixa)
        cand = Path(work) / f"trilha_ia_{k}.wav"
        if cand.exists():
            path, usado = cand, "ia"
        elif musica_ia.disponivel():
            try:
                Path(work).mkdir(parents=True, exist_ok=True)
                print(f"   trilha: pedindo a música ao ACE-Step ({clima}, {bpm:.0f} BPM, {dur:.1f}s) ...")
                musica_ia.gerar_arquivo(clima, cand, dur, bpm, semente, fala, abaixa)
                path, usado = cand, "ia"
            except Exception as exc:  # noqa: BLE001 — IA falhou: segue com a sintetizada
                print(f"   aviso: ACE-Step falhou ({exc}); usando a trilha sintetizada", file=sys.stderr)
        elif motor == "ia":
            print(f"   aviso: ACE-Step fora do ar ({musica_ia.URL}); usando a trilha sintetizada", file=sys.stderr)
    if path is None:
        usado = "sintetizada"
        k = chave(clima, bpm, dur, semente, fala, abaixa)
        path = Path(work) / f"trilha_{k}.wav"
        if not path.exists():
            Path(work).mkdir(parents=True, exist_ok=True)
            gerar_arquivo(clima, path, dur, bpm, semente, fala, abaixa)
    auto = {"clima": clima, "bpm": bpm, "dur": dur, "semente": semente, "abaixa_fala_db": abaixa,
            "chave": k, "palavras_por_s": round(pps, 2) if pps else None}
    if usado == "ia" or motor != "auto":   # trilha sintetizada pedida do jeito antigo: timeline idêntica
        auto["motor"] = usado
    return {"path": str(path.resolve()), "volume": float(pedido.get("volume") or VOLUME_AUTO), "auto": auto}


# ---------------------------------------------------------------------------------------------------------------
# medição do ducking com o MESMO grafo de áudio que o render usa

def regioes_fala(words: list[dict], dur: float, pausa_min: float = 0.4) -> tuple[list, list]:
    """(com_fala, sem_fala): intervalos das palavras e as pausas de pelo menos `pausa_min` segundos."""
    fala = []
    for w in sorted(words, key=lambda w: w["t0"]):
        if fala and w["t0"] - fala[-1][1] < pausa_min:
            fala[-1][1] = max(fala[-1][1], w["t1"])
        else:
            fala.append([w["t0"], w["t1"]])
    sem, ini = [], 0.0
    for a, b in fala:
        if a - ini >= pausa_min:
            sem.append([ini, a])
        ini = b
    if dur - ini >= pausa_min:
        sem.append([ini, dur])
    return fala, sem


def _rms_regioes(x: np.ndarray, regioes: list) -> float:
    partes = [x[:, seg(a):seg(b)] for a, b in regioes if seg(b) > seg(a)]
    return dsp.rms_db(np.concatenate(partes, axis=1)) if partes else float("nan")


def medir_ducking(tl: dict, aroll: Path, sfx_files: dict, pasta: Path) -> dict:
    """Renderiza só a trilha como ela sai do mix do render.py (antes e depois do sidechain) e compara o
    nível com fala x sem fala. Usa o grafo que o próprio render.mix_audio monta (nada duplicado aqui)."""
    import subprocess

    import render
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    capt: dict = {}
    original = render.ffmpeg

    def so_captura(args, **kw):  # não roda: só guarda o comando (o arquivo vazio deixa o mix_audio terminar)
        capt["args"] = list(args)
        Path(args[-1]).touch()
    render.ffmpeg = so_captura
    try:
        render.mix_audio(tl, Path(aroll), {"sfx_files": sfx_files}, pasta / "mix.m4a")
    finally:
        render.ffmpeg = original
    args = capt["args"]
    i = args.index("-filter_complex_script")
    entradas, grafo = args[:i], Path(args[i + 1])
    linhas = [ln for ln in grafo.read_text(encoding="utf-8").split(";\n") if not ln.endswith("[aout]")]
    sobras = ["[voice_m]anullsink"] + [f"[s{k}]anullsink" for k in range(len(tl["sfx"]))]
    saidas = {}
    for nome, extra in (("depois", ["[duck]anull[med]"]),
                        ("antes", ["[duck]anullsink", "[med_src]anull[med]"])):
        ls = list(linhas)
        if nome == "antes":  # a mesma trilha, sem o sidechain
            ls = [ln.replace("[mus][voice_sc]", "[mus]asplit=2[med_src][mus2];[mus2][voice_sc]") for ln in ls]
        g = pasta / f"ducking_{nome}.txt"
        g.write_text(";\n".join(ls + sobras + extra), encoding="utf-8")
        wav = pasta / f"trilha_{nome}.wav"
        r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostdin", *entradas,
                            "-filter_complex_script", str(g), "-map", "[med]", "-t", f"{tl['duration']:.3f}",
                            "-c:a", "pcm_s24le", "-ar", str(SR), str(wav)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"ffmpeg falhou medindo o ducking ({nome}):\n{r.stderr[-1500:]}")
        saidas[nome] = dsp.le_wav(wav)
    fala, sem = regioes_fala(tl["words"], tl["duration"])
    d, a = saidas["depois"], saidas["antes"]
    out = {
        "trilha_com_fala_db": round(_rms_regioes(d, fala), 2), "trilha_sem_fala_db": round(_rms_regioes(d, sem), 2),
        "reducao_com_fala_db": round(_rms_regioes(a, fala) - _rms_regioes(d, fala), 2),
        "reducao_sem_fala_db": round(_rms_regioes(a, sem) - _rms_regioes(d, sem), 2),
        "segundos_com_fala": round(sum(b - a_ for a_, b in fala), 2), "segundos_sem_fala": round(sum(b - a_ for a_, b in sem), 2),
    }
    out["diferenca_db"] = round(out["trilha_sem_fala_db"] - out["trilha_com_fala_db"], 2)
    out["ducking_db"] = round(out["reducao_com_fala_db"] - out["reducao_sem_fala_db"], 2)
    return out


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "medir":
        return _main_medir(Path(sys.argv[2]))
    ap = argparse.ArgumentParser(description="Gera trilha instrumental sem direitos autorais (sintetizada).")
    ap.add_argument("clima", help=", ".join(CLIMAS))
    ap.add_argument("saida")
    ap.add_argument("--dur", type=float, required=True, help="duração exata em segundos")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--semente", type=int, default=1)
    ap.add_argument("--palavras-por-s", type=float, help="ritmo da fala, para sugerir o BPM")
    a = ap.parse_args()
    clima = nome_clima(a.clima)
    bpm = a.bpm or bpm_sugerido(clima, a.palavras_por_s)
    info = gerar_arquivo(clima, Path(a.saida), a.dur, bpm, a.semente)
    print(f"OK: {info['arquivo']} | {info['clima']} {info['bpm']:.0f} BPM | {info['dur']} s | "
          f"{info['lufs']} LUFS | pico {info['pico_dbtp']} dBTP")


def _main_medir(projeto: Path) -> None:
    """trilha.py medir <projeto>: ducking da trilha no mix atual do projeto (após um render)."""
    from common import load_json, project_paths
    from sfx import biblioteca
    paths = project_paths(projeto.resolve())
    tl = load_json(paths["timeline"])
    if not tl or not tl.get("music"):
        raise ValueError("o projeto não tem trilha na timeline (use edit.py --music auto ...)")
    work = paths["work"]
    res = medir_ducking(tl, work / "aroll.mkv", biblioteca(work / "sfx"), work / "medicao_ducking")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(2)
