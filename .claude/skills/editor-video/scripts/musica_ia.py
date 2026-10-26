#!/usr/bin/env python3
"""Trilha de verdade com IA: ACE-Step 1.5 (MIT, roda no seu computador; treinado em música sem direitos).

O ACE-Step roda como um servidor local (o instalador dele tem start_api_server.bat / .sh, porta 8001). Quando o
servidor está no ar, `--music auto:CLIMA` pede a música a ele no clima, BPM e duração do vídeo; quando não está,
o editor usa a trilha sintetizada (trilha.py) — nada quebra. A música da IA passa pelo mesmo acabamento da
sintetizada: corte na duração exata com final suave, -18 LUFS, pico ≤ -1 dBTP e a curva que a abaixa sob a fala.

  musica_ia.py status                                  o servidor está no ar? (ACESTEP_URL, padrão 127.0.0.1:8001)
  musica_ia.py gerar energia saida.wav --dur 30 [--bpm 128] [--semente 1]
Escolha do motor no projeto: edit.py <proj> --trilha-motor ia|sintetizada|auto  (auto = IA se estiver no ar)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

import dsp
from dsp import SR, seg

VERSAO = "ace15-1"
URL = os.environ.get("ACESTEP_URL", "http://127.0.0.1:8001").rstrip("/")
ESPERA_MAX = float(os.environ.get("ACESTEP_ESPERA", "900"))   # CPU sem placa de vídeo pode levar minutos

# descrição em inglês (o modelo foi treinado com tags em inglês); sempre instrumental, sem voz cantada
PROMPTS = {
    "energia": "energetic modern trap pop instrumental, punchy drums, deep 808 bass, bright synth plucks, "
               "catchy hook, advertising background music, no vocals",
    "inspirador": "inspiring cinematic instrumental, emotional piano, warm strings and pads, uplifting build, "
                  "no vocals",
    "suspense": "dark suspense instrumental, pulsing low synth, ticking percussion, tension build, cinematic, "
                "no vocals",
    "lofi": "chill lofi hip hop instrumental, dusty drums, warm rhodes chords, vinyl texture, relaxed, no vocals",
    "corporativo": "clean corporate instrumental, light acoustic guitar, soft piano, claps, positive and modern, "
                   "no vocals",
}


class Indisponivel(RuntimeError):
    pass


def _req(caminho: str, dados: dict | None = None, timeout: float = 30.0):
    url = caminho if caminho.startswith("http") else URL + caminho
    corpo = json.dumps(dados).encode() if dados is not None else None
    req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json"} if corpo else {},
                                 method="POST" if corpo is not None else "GET")
    chave = os.environ.get("ACESTEP_API_KEY")
    if chave:
        req.add_header("Authorization", f"Bearer {chave}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def disponivel(timeout: float = 1.0) -> bool:
    try:
        _req("/v1/models", timeout=timeout)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _dados(raw: bytes):
    j = json.loads(raw)
    if isinstance(j, dict) and "code" in j and j.get("code") != 200:
        raise RuntimeError(f"ACE-Step respondeu erro: {j.get('error')}")
    return j.get("data") if isinstance(j, dict) and "data" in j else j


def pedir(clima: str, dur: float, bpm: float, semente: int) -> bytes:
    """Gera no servidor e devolve os bytes do áudio (wav)."""
    if clima not in PROMPTS:
        raise ValueError(f"clima '{clima}' sem descrição para a IA")
    try:
        d = _dados(_req("/release_task", {
            "prompt": PROMPTS[clima], "lyrics": "[Instrumental]", "instrumental": True,
            "bpm": int(round(bpm)), "audio_duration": round(max(dur + 2.0, 10.0), 1), "audio_format": "wav",
            "use_random_seed": False, "seed": int(semente), "batch_size": 1, "thinking": False,
            "use_cot_caption": False, "use_cot_language": False, "inference_steps": 8}))
    except (urllib.error.URLError, OSError) as exc:
        raise Indisponivel(f"servidor ACE-Step fora do ar em {URL} ({exc})") from exc
    tarefa = d["task_id"]
    fim = time.time() + ESPERA_MAX
    while True:
        lista = _dados(_req("/query_result", {"task_id_list": [tarefa]}))
        item = lista[0] if lista else {}
        st = item.get("status")
        if st == 1:
            res = item.get("result")
            res = json.loads(res) if isinstance(res, str) else res
            arq = (res[0] if isinstance(res, list) else res)["file"]
            return _req(arq, timeout=120)
        if st == 2:
            raise RuntimeError(f"ACE-Step falhou: {item.get('result') or item.get('error')}")
        if time.time() > fim:
            raise RuntimeError(f"ACE-Step não terminou em {ESPERA_MAX:.0f} s")
        time.sleep(2.0)


def decodificar(dados: bytes, pasta: Path) -> np.ndarray:
    """Bytes de áudio (qualquer formato) -> (2, n) float 48 kHz."""
    tmp = Path(pasta) / f"_ace_{hashlib.sha1(dados).hexdigest()[:10]}.bin"
    tmp.write_bytes(dados)
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(tmp), "-ac", "2", "-ar", str(SR),
                              "-f", "f32le", "-"], capture_output=True, check=True).stdout
    finally:
        tmp.unlink(missing_ok=True)
    return np.frombuffer(raw, "<f4").astype(float).reshape(-1, 2).T


def acabamento(x: np.ndarray, dur: float, fala: list | None, abaixa_db: float) -> np.ndarray:
    """Duração exata (completa com silêncio se vier curta), final suave de 1,5 s, -18 LUFS, pico ≤ -1 dBTP e a
    curva que abaixa a trilha sob a fala (a mesma da trilha sintetizada)."""
    import trilha
    n = seg(dur)
    x = x[:, :n] if x.shape[1] >= n else np.pad(x, ((0, 0), (0, n - x.shape[1])))
    nf = min(seg(1.5), n)
    x[:, n - nf:] *= np.cos(np.linspace(0, np.pi / 2, nf)) ** 2
    ni = min(seg(0.03), n)
    x[:, :ni] *= np.linspace(0, 1, ni)
    lufs = dsp.loudness(x[:, :seg(trilha.MAX_DIRETO)])
    if np.isfinite(lufs):
        x = x * dsp.de_db(trilha.ALVO_LUFS - lufs)
    x = dsp.limitador(x, trilha.TETO_DBTP - 0.3)
    if fala and abaixa_db:
        x = x * trilha.automacao_fala(x.shape[1], fala, abaixa_db)
    return x


def chave(clima: str, bpm: float, dur: float, semente: int, fala: list | None, abaixa_db: float) -> str:
    cod = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:10]
    ent = json.dumps([VERSAO, cod, clima, round(float(bpm), 2), round(float(dur), 3), int(semente), fala or [],
                      round(float(abaixa_db), 2)])
    return hashlib.sha256(ent.encode()).hexdigest()[:16]


def gerar_arquivo(clima: str, saida: Path, dur: float, bpm: float, semente: int = 1, fala: list | None = None,
                  abaixa_db: float = 0.0) -> dict:
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    x = acabamento(decodificar(pedir(clima, dur, bpm, semente), saida.parent), dur, fala, abaixa_db)
    dsp.grava_wav(saida, x)
    return {"motor": "ia", "clima": clima, "bpm": bpm, "dur": round(x.shape[1] / SR, 3), "semente": semente,
            "segundos": round(time.time() - t0, 1), "arquivo": str(saida)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    g = sub.add_parser("gerar")
    g.add_argument("clima", choices=sorted(PROMPTS))
    g.add_argument("saida")
    g.add_argument("--dur", type=float, required=True)
    g.add_argument("--bpm", type=float)
    g.add_argument("--semente", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "status":
        ok = disponivel()
        print(f"ACE-Step em {URL}: {'NO AR' if ok else 'fora do ar (a trilha usa o modo sintetizado)'}")
        sys.exit(0 if ok else 1)
    import trilha
    bpm = a.bpm or trilha.bpm_sugerido(a.clima, None)
    print(json.dumps(gerar_arquivo(a.clima, Path(a.saida), a.dur, bpm, a.semente), ensure_ascii=False))


if __name__ == "__main__":
    main()
