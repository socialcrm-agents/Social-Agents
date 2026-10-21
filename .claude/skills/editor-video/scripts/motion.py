"""Clipes de motion graphics (composições HTML/CSS 3D/Three.js renderizadas no Chromium).

Cada entrada de timeline["motion"]:
  {"template": "moldura" | "camadas" | ... | "page": "/work/motion/custom/x.html",
   "t0": s, "t1": s, "layer": "front" | "full" | "behind", "params": {...},
   "needs_video": bool,   # a composição usa os quadros reais (plate = imagem inteira, cut = só a pessoa)
   "hand": bool}          # rastreia a mão (params.hand = [[x, y] | null por quadro], coordenadas 0..1)

layer:  front  -> por cima do vídeo (fundo transparente)
        full   -> substitui a imagem na janela (a composição desenha tudo, normalmente com os quadros reais)
        behind -> entre o fundo e a pessoa (precisa de máscara; ex.: logo 3D atrás da cabeça)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from common import FONTS_DIR, SKILL_DIR, EditorError, ffmpeg, log

MOTION_DIR = SKILL_DIR / "assets" / "motion"
RENDERER = Path(__file__).resolve().parent / "motion_render.mjs"
WEBGL = {"estudio3d", "objeto3d"}  # templates Three.js (render com WebGL/SwiftShader, mais lento)


def page_for(item: dict) -> str:
    if item.get("page"):
        return item["page"]
    tpl = MOTION_DIR / "templates" / f"{item['template']}.html"
    if not tpl.exists():
        names = ", ".join(sorted(p.stem for p in (MOTION_DIR / "templates").glob("*.html")))
        raise EditorError(f"Template de motion '{item['template']}' não existe. Disponíveis: {names}")
    return f"/templates/{item['template']}.html"


def extract_frames(aroll: Path, mask: Path | None, grade: str, t0: float, t1: float, out: Path, fps: int) -> dict:
    """Quadros reais da janela: plate (JPG com a cor do estilo), cut (PNG só da pessoa, via máscara) e
    bg (o cenário sem a pessoa: a área dela é preenchida com o próprio fundo desfocado)."""
    out.mkdir(parents=True, exist_ok=True)
    plate, cut, bg = out / "plate", out / "cut", out / "bg"
    if (out / "done.json").exists():
        return json.loads((out / "done.json").read_text())
    for d in (plate, cut, bg):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()
    dur = t1 - t0
    ffmpeg(["-ss", f"{t0:.3f}", "-i", str(aroll), "-t", f"{dur:.3f}", "-vf", f"{grade},fps={fps}",
            "-q:v", "3", str(plate / "%05d.jpg")])
    if mask:
        ffmpeg(["-ss", f"{t0:.3f}", "-i", str(aroll), "-ss", f"{t0:.3f}", "-i", str(mask), "-t", f"{dur:.3f}",
                "-filter_complex", f"[0:v]{grade},fps={fps},format=rgba[g];"
                                   f"[1:v]fps={fps},format=gray,erosion,erosion,gblur=sigma=1.5[m];"
                                   "[g][m]alphamerge", "-compression_level", "1", str(cut / "%05d.png")])
        ffmpeg(["-ss", f"{t0:.3f}", "-i", str(aroll), "-ss", f"{t0:.3f}", "-i", str(mask), "-t", f"{dur:.3f}",
                "-filter_complex", f"[0:v]{grade},fps={fps},format=gbrp,split[g1][g2];[g2]gblur=sigma=45[bl];"
                                   f"[1:v]fps={fps},format=gray,dilation,dilation,dilation,gblur=sigma=10,format=gbrp[m];"
                                   "[g1][bl][m]maskedmerge,format=yuv420p", "-q:v", "3", str(bg / "%05d.jpg")])
    count = len(list(plate.glob("*.jpg")))
    info = {"count": count, "has_cut": bool(mask)}
    (out / "done.json").write_text(json.dumps(info))
    return info


def render_clip(item: dict, project: Path, aroll: Path, mask: Path | None, tl: dict, hands=None) -> Path:
    work = project / "work"
    mdir = work / "motion"
    mdir.mkdir(parents=True, exist_ok=True)
    w, h, fps = tl["w"], tl["h"], tl["fps"]
    t0, t1 = item["t0"], item["t1"]
    params = dict(item.get("params", {}))
    params.setdefault("cues", {})
    params["format"] = {"w": w, "h": h}
    if item.get("needs_video"):
        shots = json.dumps(tl["shots"], sort_keys=True)
        key = hashlib.sha1(f"{shots}{t0}{t1}{tl['grade']}{bool(mask)}{w}x{h}".encode()).hexdigest()[:10]
        fdir = mdir / f"frames_{key}"
        info = extract_frames(aroll, mask, tl["grade"], t0, t1, fdir, fps)
        rel = fdir.relative_to(work).as_posix()
        params["video"] = {"plate": f"/work/{rel}/plate/%05d.jpg",
                           "cut": f"/work/{rel}/cut/%05d.png" if info["has_cut"] else None,
                           "bg": f"/work/{rel}/bg/%05d.jpg" if info["has_cut"] else None, "count": info["count"]}
    # arquivos locais do usuário (logo, imagem) viram URLs servidas a partir de work/motion/assets
    for key, val in list(params.items()):
        if isinstance(val, str) and key in ("image", "src", "logo", "photo") and Path(val).expanduser().exists():
            src = Path(val).expanduser()
            dst = mdir / "assets" / f"{hashlib.sha1(str(src).encode()).hexdigest()[:8]}_{src.name}"
            dst.parent.mkdir(exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
            params[key] = f"/work/{dst.relative_to(work).as_posix()}"
    if item.get("hand") and hands is not None:
        a, b = int(t0 * fps), int(t1 * fps)
        params["hand"] = hands[a:b]
    page = page_for(item)
    sig = hashlib.sha1(json.dumps([page, params, t1 - t0, w, h, fps], sort_keys=True).encode()
                       + _page_bytes(page, work)).hexdigest()[:12]
    out = mdir / f"clip_{sig}.mov"
    if out.exists():
        return out
    job = {"page": page, "out": str(out), "w": w, "h": h, "fps": fps, "duration": round(t1 - t0, 3), "params": params,
           "opaque": item.get("layer") == "full", "webgl": item.get("webgl", item.get("template") in WEBGL),
           "roots": {"/": str(MOTION_DIR), "/fonts/": str(FONTS_DIR), "/work/": str(work)}}
    job_file = mdir / f"job_{sig}.json"
    job_file.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["node", str(RENDERER), str(job_file)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise EditorError(f"Motion '{item.get('template') or page}' falhou:\n{proc.stderr[-1500:]}")
    log(f"   motion {item.get('template') or page}: {proc.stdout.strip().split(' -> ')[0]}")
    return out


def _page_bytes(page: str, work: Path) -> bytes:
    """Conteúdo da página entra no cache: editar o HTML força um novo render do clipe."""
    path = work / page[len("/work/"):] if page.startswith("/work/") else MOTION_DIR / page.lstrip("/")
    return path.read_bytes() if path.exists() else b""


def hand_track(aroll: Path, fps: int, w: int = 1080, h: int = 1920) -> list:
    """Centro da mão (0..1) em cada quadro do A-roll, suavizado; None quando não há mão."""
    from vision import MP_DIR, _frames, _mp

    model = MP_DIR / "hand_landmarker.task"
    if not model.exists():
        raise EditorError("Modelo de mão ausente. Rode: python3 scripts/setup.py --models")
    mp, BaseOptions, vision = _mp()
    det = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model)), running_mode=vision.RunningMode.VIDEO, num_hands=1))
    pts = []
    try:
        fw, fh = (270, 480) if h > w else (480, 270)
        for n, fr in enumerate(_frames(str(aroll), fw, fh, fps)):
            res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(fr)),
                                       int(n * 1000 / fps))
            if res.hand_landmarks:
                lm = res.hand_landmarks[0]
                ids = (0, 5, 9, 13, 17)  # palma
                pts.append([sum(lm[i].x for i in ids) / 5, sum(lm[i].y for i in ids) / 5])
            else:
                pts.append(None)
    finally:
        det.close()
    smooth, last = [], None
    for p in pts:
        if p is None:
            smooth.append(last if last else None)
            continue
        last = p if last is None else [last[0] * 0.55 + p[0] * 0.45, last[1] * 0.55 + p[1] * 0.45]
        smooth.append([round(last[0], 4), round(last[1], 4)])
    found = sum(1 for p in pts if p)
    log(f"   mão detectada em {found}/{len(pts)} quadros")
    return smooth
