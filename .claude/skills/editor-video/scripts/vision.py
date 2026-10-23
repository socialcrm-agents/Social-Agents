"""Rosto e recorte da pessoa com MediaPipe (Apache-2.0), 100% local.

- face_track(): centro do rosto ao longo do clipe (para centralizar zooms).
- person_mask(): vídeo de máscara (branco = pessoa) do A-roll montado, usado para
  colocar palavras ATRÁS da pessoa, + topo da cabeça por segundo.
Modelos baixados uma vez de storage.googleapis.com (scripts/setup.py --models).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np

from common import MODELS_DIR, EditorError, log

MP_DIR = MODELS_DIR / "mediapipe"
FACE_MODEL = MP_DIR / "blaze_face_short_range.tflite"
SEG_MODEL = MP_DIR / "selfie_segmenter.tflite"


def _mp():
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
    except (ImportError, OSError) as exc:
        raise EditorError(f"MediaPipe indisponível ({exc}). Linux: sudo apt install libegl1 libgles2 libgl1; "
                          "pip install mediapipe") from exc
    for m in (FACE_MODEL, SEG_MODEL):
        if not m.exists():
            raise EditorError(f"Modelo {m.name} ausente. Rode: python3 scripts/setup.py --models")
    return mp, BaseOptions, vision


def _frames(path: str, w: int, h: int, fps: float, start: float = 0.0, dur: float | None = None):
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", path]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    proc.wait()


def face_track(path: str, fps: float = 4.0, aspect: float = 9 / 16) -> list[dict]:
    """[{t, cx, cy, h}] normalizados no quadro final (já recortado em 'cover' no formato do projeto)."""
    mp, BaseOptions, vision = _mp()
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(FACE_MODEL)), min_detection_confidence=0.55))
    out = []
    try:
        fw, fh = (360, 640) if aspect < 1 else (640, 360)
        for n, fr in enumerate(_frames(path, fw, fh, fps)):
            res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(fr)))
            if res.detections:
                b = max(res.detections, key=lambda d: d.bounding_box.width).bounding_box
                out.append({"t": round(n / fps, 2), "cx": (b.origin_x + b.width / 2) / fw,
                            "cy": (b.origin_y + b.height / 2) / fh, "h": b.height / fh})
    finally:
        det.close()
    return out


def person_mask(aroll: Path, out_mask: Path, W: int = 1080, H: int = 1920, fps: int = 30) -> list[dict]:
    """Escreve a máscara (cinza, WxH) e devolve por quadro: cobertura e topo da cabeça (px).

    Suavização temporal (média com o quadro anterior) reduz o "tremido" da borda entre quadros.
    """
    mp, BaseOptions, vision = _mp()
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=str(SEG_MODEL)), output_confidence_masks=True))
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(FACE_MODEL)), min_detection_confidence=0.55))
    w, h = (270, 480) if H > W else (480, 270)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-nostdin", "-f", "rawvideo", "-pix_fmt", "gray",
                            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                            "-vf", f"scale={W}:{H}:flags=bicubic,gblur=sigma=2.2",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
                            str(out_mask)], stdin=subprocess.PIPE)
    stats, prev = [], None
    try:
        for n, fr in enumerate(_frames(str(aroll), w, h, fps)):
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(fr))
            conf = seg.segment(img).confidence_masks[0].numpy_view().reshape(h, w)
            m = np.clip((conf - 0.35) / 0.3, 0, 1)
            if prev is not None:
                m = 0.65 * m + 0.35 * prev
            prev = m
            enc.stdin.write((m * 255).astype(np.uint8).tobytes())
            face = None
            if n % 3 == 0:
                d = det.detect(img).detections
                if d:
                    b = max(d, key=lambda x: x.bounding_box.width).bounding_box
                    face = [b.origin_x / w, b.origin_y / h, b.width / w, b.height / h]
            rows = np.where(m[:, int(w * 0.3):int(w * 0.7)].max(axis=1) > 0.5)[0]
            stats.append({"cov": round(float(m.mean()), 3),
                          "top": int(rows[0] * H / h) if len(rows) else None, "face": face})
    finally:
        enc.stdin.close()
        enc.wait()
        seg.close()
        det.close()
    log(f"   máscara da pessoa: {len(stats)} quadros")
    return stats
