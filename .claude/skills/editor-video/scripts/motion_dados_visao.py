"""Dados de visão computacional por quadro para os templates hud e maos (MediaPipe, 100% local).

Chamado por motion.render_clip via enriquecer(...). Tudo em 0..1 do quadro final (A-roll já cortado e com zoom).
- hud:  params["rosto"] = [[x0, y0, x1, y1, olhoE_x, olhoE_y, olhoD_x, olhoD_y, boca_x, boca_y] | null, ...] por quadro
- maos: params["maos"]  = [[[x, y] * 21] * n_maos, ...] por quadro (até 2 mãos; [] sem mão)
Resultados ficam em cache em work/motion/visao_<hash>.json (o A-roll muda -> hash muda).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from common import log


def _key(aroll: Path, kind: str, t0: float, t1: float, fps: int) -> str:
    stamp = (aroll.parent / "aroll.key").read_text() if (aroll.parent / "aroll.key").exists() else str(aroll.stat().st_mtime)
    return hashlib.sha1(f"{stamp}{kind}{t0:.3f}{t1:.3f}{fps}".encode()).hexdigest()[:12]


def _cached(work: Path, key: str, fn):
    p = work / "motion" / f"visao_{key}.json"
    if p.exists():
        return json.loads(p.read_text())
    data = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    return data


def _smooth(seq: list, k: float = 0.5, hold: int = 6) -> list:
    """Média exponencial por coordenada; segura o último valor por alguns quadros quando a detecção falha."""
    out, last, miss = [], None, 0
    for v in seq:
        if v is None:
            miss += 1
            out.append(last if last is not None and miss <= hold else None)
            continue
        miss = 0
        if last is None or len(last) != len(v):
            last = list(v)
        else:
            last = [a * k + b * (1 - k) for a, b in zip(last, v)]
        out.append([round(x, 4) for x in last])
    return out


def rosto(aroll: Path, t0: float, t1: float, fps: int, w: int, h: int) -> list:
    from vision import FACE_MODEL, _frames, _mp
    mp, BaseOptions, vision = _mp()
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(FACE_MODEL)), min_detection_confidence=0.5))
    fw, fh = (360, 640) if h > w else (640, 360)
    raw = []
    try:
        for fr in _frames(str(aroll), fw, fh, fps, start=t0, dur=t1 - t0):
            res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(fr)))
            if not res.detections:
                raw.append(None)
                continue
            d = max(res.detections, key=lambda x: x.bounding_box.width)
            b, kp = d.bounding_box, d.keypoints  # keypoints: olho dir., olho esq., nariz, boca, orelhas
            x0, y0 = b.origin_x / fw, b.origin_y / fh
            x1, y1 = (b.origin_x + b.width) / fw, (b.origin_y + b.height) / fh
            raw.append([x0, y0, x1, y1, kp[1].x, kp[1].y, kp[0].x, kp[0].y, kp[3].x, kp[3].y])
    finally:
        det.close()
    n = int(round((t1 - t0) * fps))
    raw = (raw + [None] * n)[:n]
    found = sum(1 for r in raw if r)
    log(f"   hud: rosto em {found}/{n} quadros")
    return _smooth(raw, 0.55)


def maos(aroll: Path, t0: float, t1: float, fps: int, w: int, h: int) -> list:
    from vision import MP_DIR, _frames, _mp
    model = MP_DIR / "hand_landmarker.task"
    if not model.exists():
        log("   maos: modelo hand_landmarker ausente (setup.py --models)")
        return []
    mp, BaseOptions, vision = _mp()
    det = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model)), running_mode=vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=0.3, min_hand_presence_confidence=0.3, min_tracking_confidence=0.3))
    fw, fh = (540, 960) if h > w else (960, 540)  # mão é pequena no quadro: resolução maior que a do rosto
    frames, prev = [], {}
    try:
        for n, fr in enumerate(_frames(str(aroll), fw, fh, fps, start=t0, dur=t1 - t0)):
            res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(fr)),
                                       int(n * 1000 / fps))
            cur = []
            for i, lm in enumerate(res.hand_landmarks or []):
                side = res.handedness[i][0].category_name if res.handedness else str(i)
                pts = [[p.x, p.y] for p in lm]
                if side in prev:  # suaviza cada mão pelo lado (esquerda/direita)
                    pts = [[a[0] * 0.45 + b[0] * 0.55, a[1] * 0.45 + b[1] * 0.55] for a, b in zip(prev[side], pts)]
                prev[side] = pts
                cur.append([[round(x, 3), round(y, 3)] for x, y in pts])
            frames.append(cur)
    finally:
        det.close()
    n = int(round((t1 - t0) * fps))
    frames = (frames + [[]] * n)[:n]
    log(f"   maos: mão em {sum(1 for f in frames if f)}/{n} quadros")
    return frames


def enriquecer(tpl, params, item, *, work, tl, aroll, mask, t0, t1, w, h, fps, project) -> None:
    if tpl == "hud" and "rosto" not in params:
        params["rosto"] = _cached(work, _key(aroll, "rosto", t0, t1, fps), lambda: rosto(aroll, t0, t1, fps, w, h))
    if tpl == "maos" and "maos" not in params:
        params.pop("hand", None)  # o centro da palma já vem dentro dos 21 pontos
        params["maos"] = _cached(work, _key(aroll, "maos", t0, t1, fps), lambda: maos(aroll, t0, t1, fps, w, h))
