#!/usr/bin/env python3
"""Narração do anúncio: voz pronta (offline) ou a gravação do próprio cliente, com tempo de cada palavra.

- Voz pronta: cada fala do roteiro vira áudio (Kokoro ou Piper via sherpa-onnx). Se passar da duração pedida,
  a fala é regerada um pouco mais rápida (até 1,22x); se ainda assim não couber, o script avisa quantas
  palavras cortar.
- Gravação do cliente (`"voz": {"arquivo": "..."}`): limpa ruído, encurta pausas longas, transcreve
  (Parakeet) e alinha com o roteiro. A legenda usa a grafia do roteiro (nomes e marcas certos) no tempo real
  da fala.

Saída: work/<roteiro>/voz.wav (48 kHz) + voz.json {falas: [{t0, t1, texto}], palavras: [{w, t0, t1, fala}]}
Uso: voz.py <projeto> [--roteiro roteiro_15s.json]
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata
import wave
from pathlib import Path

import numpy as np

from common import (END_CARD, LEAD, MODELS_DIR, VOICES_FILE, AdError, ffmpeg, load_json, log, main_guard, probe, project_paths,
                    save_json)
from fala import falado

TTS_DIR = MODELS_DIR / "tts"
KOKORO = "kokoro-int8-multi-lang-v1_0"
PARAKEET = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
MAX_SPEED = 1.22


def norm(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in word if not unicodedata.combining(c)))


# ---------- voz pronta ----------

_engines: dict[str, object] = {}


def engine(cfg: dict):
    import sherpa_onnx as so
    key = cfg.get("modelo") or KOKORO
    if key in _engines:
        return _engines[key]
    threads = os.cpu_count() or 4
    if cfg["motor"] == "kokoro":
        d = TTS_DIR / KOKORO
        if not (d / "model.int8.onnx").exists():
            raise AdError("Voz Kokoro não instalada. Rode: python3 scripts/setup.py --models")
        model = so.OfflineTtsModelConfig(kokoro=so.OfflineTtsKokoroModelConfig(
            model=str(d / "model.int8.onnx"), voices=str(d / "voices.bin"), tokens=str(d / "tokens.txt"),
            data_dir=str(d / "espeak-ng-data"), lexicon=str(d / "lexicon-us-en.txt"), lang="pt-br"),
            num_threads=threads)
    else:
        d = TTS_DIR / cfg["modelo"]
        onnx = next(d.glob("*.onnx"), None)
        if not onnx:
            raise AdError(f"Voz {cfg['modelo']} não instalada. Rode: python3 scripts/setup.py --models")
        model = so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(
            model=str(onnx), tokens=str(d / "tokens.txt"), data_dir=str(d / "espeak-ng-data")), num_threads=threads)
    _engines[key] = so.OfflineTts(so.OfflineTtsConfig(model=model))
    return _engines[key]


def trim(a: np.ndarray, sr: int) -> np.ndarray:
    """Tira o silêncio do começo e do fim de cada fala (deixa 40 ms)."""
    hop = sr // 100
    env = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, mode="same"))
    on = np.where(env > max(env.max() * 0.02, 1e-4))[0]
    if not len(on):
        return a
    pad = int(0.04 * sr)
    return a[max(on[0] - pad, 0): on[-1] + pad]


def synth_lines(texts: list[str], cfg: dict, speed: float) -> tuple[list[np.ndarray], int]:
    tts = engine(cfg)
    sid = cfg.get("id", 0)
    out = []
    for t in texts:
        g = tts.generate(falado(t), sid=sid, speed=speed)
        out.append(trim(np.asarray(g.samples, np.float32), g.sample_rate))
    return out, g.sample_rate


def gap_after(text: str) -> float:
    return 0.22 if text.rstrip()[-1:] in "!?." else 0.12


def tts_track(falas: list[str], cfg: dict, speed: float, budget: float, work: Path) -> dict:
    for attempt in range(3):
        audio, sr = synth_lines(falas, cfg, speed)
        total = sum(len(a) / sr for a in audio) + sum(gap_after(t) for t in falas[:-1])
        if total <= budget * 1.03 or speed >= MAX_SPEED:
            break
        speed = round(min(MAX_SPEED, speed * total / budget * 1.01), 3)
        log(f"   narração com {total:.1f}s para {budget:.1f}s: regerando a {speed}x")
    pieces, falas_t, pos = [], [], 0.0
    for i, (t, a) in enumerate(zip(falas, audio)):
        dur = len(a) / sr
        falas_t.append({"t0": round(pos, 3), "t1": round(pos + dur, 3), "texto": t})
        pieces.append(a)
        pos += dur
        if i < len(falas) - 1:
            gap = gap_after(t)
            pieces.append(np.zeros(int(gap * sr), np.float32))
            pos += gap
    raw = work / "voz_raw.wav"
    write_wav(raw, np.concatenate(pieces), sr)
    ffmpeg(["-i", str(raw), "-ar", "48000", "-ac", "1", str(work / "voz.wav")])
    words = []
    for i, f in enumerate(falas_t):
        words += spread(f["texto"], f["t0"], f["t1"], i)
    return {"fonte": "tts", "velocidade": speed, "duracao": round(pos, 3), "falas": falas_t, "palavras": words}


def spread(text: str, t0: float, t1: float, fala: int) -> list[dict]:
    """Distribui as palavras da fala no tempo, proporcional ao tamanho falado de cada uma."""
    toks = text.split()
    weights = [max(len(falado(w)), 2) + 1 for w in toks]
    total = sum(weights)
    out, pos = [], t0
    for w, k in zip(toks, weights):
        d = (t1 - t0) * k / total
        out.append({"w": w, "t0": round(pos, 3), "t1": round(pos + d, 3), "fala": fala})
        pos += d
    return out


def write_wav(path: Path, a: np.ndarray, sr: int) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


# ---------- gravação do cliente ----------

def asr_words(wav16: Path) -> list[dict]:
    import sherpa_onnx
    d = MODELS_DIR / PARAKEET
    if not (d / "tokens.txt").exists():
        raise AdError("Para usar a voz do cliente é preciso o modelo de transcrição. Rode: "
                      "python3 scripts/setup.py --models --voz-propria")
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(d / "encoder.int8.onnx"), decoder=str(d / "decoder.int8.onnx"),
        joiner=str(d / "joiner.int8.onnx"), tokens=str(d / "tokens.txt"),
        model_type="nemo_transducer", num_threads=os.cpu_count() or 4)
    with wave.open(str(wav16)) as f:
        a = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
    sr, step = 16000, 40.0
    words, start = [], 0.0
    while start < len(a) / sr:
        end = min(start + step, len(a) / sr)
        s = rec.create_stream()
        s.accept_waveform(sr, a[int(start * sr): int(end * sr)])
        rec.decode_stream(s)
        res = s.result
        for tok, ts in zip(res.tokens, res.timestamps):
            ts += start
            if tok.startswith(" ") or not words or words[-1].get("_end", 0) < start:
                if re.fullmatch(r"\s*[.,!?;:…]+", tok) and words:
                    words[-1]["w"] += tok.strip()
                    continue
                words.append({"w": tok.strip(), "t0": ts, "t1": ts + 0.1, "_end": end})
            else:
                words[-1]["w"] += tok
                words[-1]["t1"] = ts + 0.1
        start = end
    for i, w in enumerate(words):
        nxt = words[i + 1]["t0"] if i + 1 < len(words) else w["t1"] + 0.3
        w["t1"] = round(min(max(w["t1"], w["t0"] + 0.08), nxt - 0.01), 3)
        w["t0"] = round(w["t0"], 3)
        w.pop("_end", None)
    return [w for w in words if w["w"]]


def own_track(src: Path, falas: list[str], work: Path) -> dict:
    """Limpa a gravação, encurta pausas > 0,35 s e alinha o roteiro com o que foi dito."""
    clean = ("highpass=f=80,afftdn=nf=-30,silenceremove=start_periods=1:start_threshold=-42dB:"
             "stop_periods=-1:stop_duration=0.35:stop_threshold=-42dB:stop_silence=0.14,"
             "acompressor=threshold=-20dB:ratio=3:attack=5:release=90")
    ffmpeg(["-i", str(src), "-vn", "-af", clean, "-ar", "48000", "-ac", "1", str(work / "voz.wav")])
    ffmpeg(["-i", str(work / "voz.wav"), "-ar", "16000", str(work / "voz_16k.wav")])
    heard = asr_words(work / "voz_16k.wav")
    (work / "transcricao.txt").write_text(" ".join(w["w"] for w in heard) + "\n", encoding="utf-8")
    script = [(w, i) for i, f in enumerate(falas) for w in f.split()]
    a, b = [norm(w) for w, _ in script], [norm(w["w"]) for w in heard]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    times: list[tuple[float, float] | None] = [None] * len(script)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            h = heard[blk.b + k]
            times[blk.a + k] = (h["t0"], h["t1"])
    match = sum(t is not None for t in times) / max(len(times), 1)
    dur = probe(work / "voz.wav")["duration"]
    # palavras do roteiro sem par na fala: interpola entre os vizinhos que casaram
    known = [i for i, t in enumerate(times) if t]
    if not known:
        raise AdError("A gravação não bate com o roteiro. Leia work/transcricao.txt e reescreva as falas do "
                      "roteiro com o que foi dito.")
    for i in range(len(times)):
        if times[i]:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        t0 = times[prev][1] if prev is not None else 0.0
        t1 = times[nxt][0] if nxt is not None else dur
        span = (nxt if nxt is not None else len(times)) - (prev if prev is not None else -1)
        pos = i - (prev if prev is not None else -1)
        a0 = t0 + (t1 - t0) * (pos - 1) / span
        times[i] = (a0, a0 + (t1 - t0) / span)
    words = [{"w": w, "t0": round(t[0], 3), "t1": round(t[1], 3), "fala": i} for (w, i), t in zip(script, times)]
    falas_t = []
    for i, f in enumerate(falas):
        ws = [w for w in words if w["fala"] == i]
        falas_t.append({"t0": ws[0]["t0"], "t1": ws[-1]["t1"], "texto": f})
    if match < 0.6:
        log(f"   AVISO: só {match:.0%} do roteiro bate com a gravação. Leia work/transcricao.txt e ajuste as falas.")
    return {"fonte": "gravacao", "arquivo": str(src), "alinhamento": round(match, 2), "duracao": round(dur, 3),
            "falas": falas_t, "palavras": words}


def narrate(project: Path, script: Path) -> dict:
    rot = load_json(script)
    if not rot:
        raise AdError(f"{script.name} não existe. Escreva o roteiro (ver references/roteiros.md).")
    work = project_paths(project)["work"] / script.stem
    work.mkdir(parents=True, exist_ok=True)
    falas = [f["texto"].strip() for f in rot["falas"]]
    voz = rot.get("voz") or load_json(VOICES_FILE)["padrao"]
    sig = hashlib.sha1(json.dumps([falas, voz, rot.get("velocidade"), rot.get("duracao")],
                                  ensure_ascii=False).encode()).hexdigest()[:12]
    cached = load_json(work / "voz.json")
    if cached and cached.get("sig") == sig and (work / "voz.wav").exists():
        log("   narração reaproveitada (roteiro e voz iguais)")
        return cached
    if isinstance(voz, dict) and voz.get("arquivo"):
        src = Path(voz["arquivo"]).expanduser()
        if not src.is_absolute():
            src = project / src
        if not src.exists():
            raise AdError(f"Gravação não encontrada: {src}")
        info = own_track(src, falas, work)
        name = "gravação do cliente"
    else:
        voices = load_json(VOICES_FILE)["vozes"]
        if voz not in voices:
            raise AdError(f"Voz '{voz}' não existe. Opções: {', '.join(voices)}")
        cfg = voices[voz]
        budget = float(rot.get("duracao", 20)) - END_CARD - LEAD
        info = tts_track(falas, cfg, float(rot.get("velocidade") or cfg.get("velocidade", 1.0)), budget, work)
        name = voz
        if info["duracao"] > budget * 1.06:
            sobra = info["duracao"] - budget
            log(f"   AVISO: a narração tem {info['duracao']:.1f}s e cabem {budget:.1f}s mesmo a {MAX_SPEED}x. "
                f"Corte ~{int(sobra * 2.9) + 1} palavras do roteiro.")
    info.update(sig=sig, voz=name)
    save_json(work / "voz.json", info)
    log(f"OK: narração {info['duracao']:.1f}s ({name}, {len(info['falas'])} falas)")
    return info


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    script = project / "roteiro.json"
    if "--roteiro" in sys.argv:
        script = Path(sys.argv[sys.argv.index("--roteiro") + 1])
        script = script if script.is_absolute() else project / script
    narrate(project, script)


if __name__ == "__main__":
    main_guard(main)
