#!/usr/bin/env python3
"""Transcreve cada clipe com tempo por palavra.

Motor padrão: NVIDIA Parakeet TDT 0.6B v3 (multilíngue, inclui português) rodando
offline via sherpa-onnx, com timestamps por token. Alternativa: faster-whisper
(EDITOR_VIDEO_ASR=whisper), quando o HuggingFace estiver acessível.

Saída: transcript.json com palavras {w, t0, t1, clip} e silêncios por clipe.
Uso: transcribe.py <projeto>
"""

from __future__ import annotations

import os
import re
import sys
import wave
from pathlib import Path

import numpy as np

from common import MODELS_DIR, EditorError, ffmpeg, load_json, log, main_guard, project_paths, save_json

PARAKEET = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
SR = 16000
MAX_CHUNK = 40.0


def silences(audio: np.ndarray, min_dur: float = 0.18) -> list[tuple[float, float]]:
    """Pausas por energia com limiar adaptativo (ruído de fundo + 7 dB).

    Um limiar fixo (-35 dB) falha em gravação de celular com ruído ambiente;
    aqui o piso de ruído é medido no próprio clipe.
    """
    hop = SR // 50  # 20 ms
    frames = audio[: len(audio) // hop * hop].reshape(-1, hop)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    thr = min(np.percentile(db, 8) + 7, np.percentile(db, 50) - 6)
    quiet = db < thr
    out, start = [], None
    for i, q in enumerate(list(quiet) + [False]):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * 0.02 >= min_dur:
                out.append((round(start * 0.02, 3), round(i * 0.02, 3)))
            start = None
    return out


def energy_min(audio: np.ndarray, a: float, b: float) -> float:
    """Instante de menor energia entre a e b (ponto seguro para dividir o áudio)."""
    hop = SR // 50
    seg = audio[int(a * SR): int(b * SR)]
    frames = seg[: len(seg) // hop * hop].reshape(-1, hop)
    return a + int(np.argmin((frames ** 2).mean(axis=1))) * 0.02


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def chunk_points(audio, duration: float, sil: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Divide o áudio em pedaços de até MAX_CHUNK segundos, cortando em silêncio (ou no ponto mais baixo)."""
    cuts, start = [], 0.0
    mids = [(s + e) / 2 for s, e in sil if e - s >= 0.25]
    while duration - start > MAX_CHUNK:
        options = [m for m in mids if start + 4 < m <= start + MAX_CHUNK]
        cut = options[-1] if options else energy_min(audio, start + MAX_CHUNK - 8, start + MAX_CHUNK)
        cuts.append((start, cut))
        start = cut
    cuts.append((start, duration))
    return cuts


def tokens_to_words(tokens, stamps, offset, chunk_end, sil) -> list[dict]:
    words: list[dict] = []
    for tok, ts in zip(tokens, stamps):
        ts += offset
        if tok.startswith(" ") or not words:
            if re.fullmatch(r"\s*[.,!?;:…]+", tok) and words:
                words[-1]["w"] += tok.strip()
                continue
            words.append({"w": tok.strip(), "t0": ts, "last": ts})
        else:
            words[-1]["w"] += tok
            words[-1]["last"] = ts
    for i, w in enumerate(words):
        nxt = words[i + 1]["t0"] if i + 1 < len(words) else chunk_end
        end = min(nxt - 0.02, w["last"] + 0.32)
        for s, e in sil:  # termina a palavra onde o silêncio começa
            if w["last"] - 0.05 <= s < end:
                end = s
                break
        w["t1"] = round(max(end, w["last"] + 0.06), 3)
        w["t0"] = round(w["t0"], 3)
        del w["last"]
    return [w for w in words if w["w"]]


def parakeet_recognizer():
    import sherpa_onnx

    d = MODELS_DIR / PARAKEET
    if not (d / "tokens.txt").exists():
        raise EditorError(f"Modelo Parakeet não encontrado em {d}. Rode: python3 scripts/setup.py --models")
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(d / "encoder.int8.onnx"), decoder=str(d / "decoder.int8.onnx"),
        joiner=str(d / "joiner.int8.onnx"), tokens=str(d / "tokens.txt"),
        model_type="nemo_transducer", num_threads=os.cpu_count() or 4)


def transcribe_parakeet(rec, audio: np.ndarray, duration: float, sil) -> list[dict]:
    words = []
    for a, b in chunk_points(audio, duration, sil):
        stream = rec.create_stream()
        stream.accept_waveform(SR, audio[int(a * SR):int(b * SR)])
        rec.decode_stream(stream)
        res = stream.result
        words += tokens_to_words(res.tokens, res.timestamps, a, b, sil)
    return words


def transcribe_whisper(wav: Path) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(os.environ.get("EDITOR_VIDEO_WHISPER", "small"), device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(wav), language="pt", word_timestamps=True, vad_filter=False)
    return [{"w": w.word.strip(), "t0": round(w.start, 3), "t1": round(w.end, 3)} for s in segs for w in s.words]


def main() -> None:
    project = Path(sys.argv[1])
    paths = project_paths(project)
    proj = load_json(paths["project"])
    if not proj:
        raise EditorError("project.json não encontrado. Rode run.py new primeiro.")
    backend = os.environ.get("EDITOR_VIDEO_ASR", "parakeet")
    rec = parakeet_recognizer() if backend == "parakeet" else None
    all_words, clip_sil = [], {}
    for clip in proj["clips"]:
        wav = paths["work"] / f"{clip['id']}.wav"
        ffmpeg(["-i", clip["path"], "-vn", "-ac", "1", "-ar", str(SR), "-af", "highpass=f=70", str(wav)])
        audio = read_wav(wav)
        sil = silences(audio)
        clip_sil[clip["id"]] = [[round(s, 3), round(e, 3)] for s, e in sil]
        log(f"Transcrevendo {clip['id']} ({clip['duration']:.1f}s) com {backend}...")
        words = transcribe_parakeet(rec, audio, clip["duration"], sil) if rec else transcribe_whisper(wav)
        for w in words:
            w["clip"] = clip["id"]
        all_words += words
    fixes = proj.get("overrides", {}).get("word_fixes", {})
    save_json(paths["transcript"], {"backend": backend, "words": all_words, "silences": clip_sil, "word_fixes_applied_in_plan": bool(fixes)})
    text = " ".join(w["w"] for w in all_words)
    (project / "transcript.txt").write_text(text + "\n", encoding="utf-8")
    log(f"OK: {len(all_words)} palavras -> transcript.json / transcript.txt")


if __name__ == "__main__":
    main_guard(main)
