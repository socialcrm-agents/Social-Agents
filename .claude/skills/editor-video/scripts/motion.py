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
WEBGL = {"estudio3d", "objeto3d", "profundidade", "produto3d", "cena3d", "maquete"}  # templates Three.js (render com WebGL/SwiftShader, mais lento)


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
    jobs = [["-ss", f"{t0:.3f}", "-i", str(aroll), "-t", f"{dur:.3f}", "-vf", f"{grade},fps={fps}",
             "-q:v", "3", str(plate / "%05d.jpg")]]
    if mask:
        jobs.append(["-ss", f"{t0:.3f}", "-i", str(aroll), "-ss", f"{t0:.3f}", "-i", str(mask), "-t", f"{dur:.3f}",
                     "-filter_complex", f"[0:v]{grade},fps={fps},format=rgba[g];"
                                        f"[1:v]fps={fps},format=gray,erosion,erosion,gblur=sigma=1.5[m];"
                                        "[g][m]alphamerge", "-compression_level", "1", str(cut / "%05d.png")])
        jobs.append(["-ss", f"{t0:.3f}", "-i", str(aroll), "-ss", f"{t0:.3f}", "-i", str(mask), "-t", f"{dur:.3f}",
                     "-filter_complex", f"[0:v]{grade},fps={fps},format=gbrp,split[g1][g2];[g2]gblur=sigma=45[bl];"
                                        f"[1:v]fps={fps},format=gray,dilation,dilation,dilation,gblur=sigma=10,format=gbrp[m];"
                                        "[g1][bl][m]maskedmerge,format=yuv420p", "-q:v", "3", str(bg / "%05d.jpg")])
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:  # as três extrações são independentes
        list(pool.map(ffmpeg, jobs))
    count = len(list(plate.glob("*.jpg")))
    info = {"count": count, "has_cut": bool(mask)}
    (out / "done.json").write_text(json.dumps(info))
    return info


def render_clip(item: dict, project: Path, aroll: Path, mask: Path | None, tl: dict, hands=None,
                chave: str | None = None, chaves_planos: list | None = None) -> Path:
    """Renderiza (ou reaproveita) o clipe. `chave` = chave do componente (revisao.chave_motion): com ela o cache
    responde antes de extrair quadros ou rastrear mão/rosto, e mudar outro trecho do vídeo não refaz este clipe."""
    work = project / "work"
    mdir = work / "motion"
    mdir.mkdir(parents=True, exist_ok=True)
    if chave and (mdir / f"clip_{chave}.mov").exists():
        # decisões tomadas no render do clipe (ex.: palavra sem espaço acima da cabeça vai para a frente/topo)
        lado = mdir / f"clip_{chave}.item.json"
        if lado.exists():
            item.update(json.loads(lado.read_text(encoding="utf-8")))
        return mdir / f"clip_{chave}.mov"
    w, h, fps = tl["w"], tl["h"], tl["fps"]
    t0, t1 = item["t0"], item["t1"]
    params = json.loads(json.dumps(item.get("params", {})))  # cópia profunda (itens são reescritos abaixo)
    params.setdefault("cues", {})
    params["format"] = {"w": w, "h": h}
    if item.get("needs_video"):
        if chaves_planos is not None:  # só os planos sob a janela importam (um corte em outro trecho não refaz)
            import revisao
            shots = json.dumps(revisao.planos_na_janela(tl, chaves_planos, t0, t1))
        else:
            shots = json.dumps(tl["shots"], sort_keys=True)
        key = hashlib.sha1(f"{shots}{t0 if chaves_planos is None else 0}{t1 - t0 if chaves_planos is not None else t1}"
                           f"{tl['grade']}{bool(mask)}{w}x{h}".encode()).hexdigest()[:10]
        fdir = mdir / f"frames_{key}"
        info = extract_frames(aroll, mask, tl["grade"], t0, t1, fdir, fps)
        rel = fdir.relative_to(work).as_posix()
        params["video"] = {"plate": f"/work/{rel}/plate/%05d.jpg",
                           "cut": f"/work/{rel}/cut/%05d.png" if info["has_cut"] else None,
                           "bg": f"/work/{rel}/bg/%05d.jpg" if info["has_cut"] else None, "count": info["count"]}
    # arquivos locais do usuário (logo, imagens, cenários) viram URLs servidas a partir de work/motion/assets
    def localize(obj, key=""):
        if isinstance(obj, dict):
            return {k: localize(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [localize(v, key) for v in obj]
        if isinstance(obj, str) and key in ("image", "images", "imagens", "imagem", "src", "logo", "photo", "foto", "modelo") and not obj.startswith("/work/") \
                and Path(obj).expanduser().is_file():
            src = Path(obj).expanduser()
            dst = mdir / "assets" / f"{hashlib.sha1(str(src).encode()).hexdigest()[:8]}_{src.name}"
            dst.parent.mkdir(exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
            return f"/work/{dst.relative_to(work).as_posix()}"
        return obj
    params = localize(params)
    # cards de vídeo (carrossel, pedaços): cada vídeo vira uma sequência de quadros servida ao navegador
    for it in params.get("items", []) if isinstance(params.get("items"), list) else []:
        if isinstance(it, dict) and it.get("video") and Path(str(it["video"])).expanduser().exists():
            src = Path(it["video"]).expanduser()
            key = hashlib.sha1(f"{src}{it.get('start', 0)}{t1 - t0}".encode()).hexdigest()[:10]
            fdir = mdir / f"vid_{key}"
            if not (fdir / "done").exists():
                fdir.mkdir(parents=True, exist_ok=True)
                ffmpeg(["-ss", f"{float(it.get('start', 0)):.3f}", "-i", str(src), "-t", f"{t1 - t0:.3f}",
                        "-vf", f"fps={fps},scale=540:-2", "-q:v", "4", str(fdir / "%05d.jpg")])
                (fdir / "done").write_text("ok")
            it["frames"] = f"/work/{fdir.relative_to(work).as_posix()}/%05d.jpg"
            it["count"] = len(list(fdir.glob("*.jpg")))
            del it["video"]
    tpl = item.get("template")
    if tpl == "onda_audio" and "wave" not in params:
        params["wave"] = wave_data(project)
    if tpl == "pedacos":
        params.setdefault("head", head_position(work, t0, t1, w, h))
        if not params.get("items"):
            params["items"] = snapshots(aroll, tl, mdir, work, params.get("count", 6))
    if tpl == "visor" and params.get("foco"):
        params.setdefault("head", head_position(work, t0, t1, w, h))
    if tpl == "palavra" and "y" not in params:
        # palavra atrás da cabeça: a base das letras fica um pouco abaixo do topo da cabeça; sem espaço acima
        # da cabeça (rosto colado no topo), ela vem para a frente, no alto, em vez de sumir atrás da pessoa
        head = head_position(work, t0, t1, w, h)
        size = params.setdefault("size", 340)
        if head["top"] * h < 220 + size * 0.75:
            # sem espaço acima da cabeça: vai para a frente, no alto, e a cena recua (desce) para abrir espaço
            item["layer"] = "front"
            item["zona"] = "topo"
            item["libera"] = int(220 + size * 0.95)
            params["y"] = round(220 / h, 3)
        else:
            params["y"] = round(max(head["top"] * h - size * 0.75, 220) / h, 3)
    if item.get("hand") and hands is not None:
        a, b = int(t0 * fps), int(t1 * fps)
        params["hand"] = hands[a:b]
    # dados extras por template (rosto quadro a quadro, mãos, palavras...): módulos motion_dados_*.py
    import importlib
    import pkgutil
    for mod in sorted(m.name for m in pkgutil.iter_modules([str(Path(__file__).parent)]) if m.name.startswith("motion_dados_")):
        importlib.import_module(mod).enriquecer(tpl, params, item, work=work, tl=tl, aroll=aroll, mask=mask,
                                                t0=t0, t1=t1, w=w, h=h, fps=fps, project=project)
    page = page_for(item)
    sig = hashlib.sha1(json.dumps([page, params, t1 - t0, w, h, fps], sort_keys=True).encode()
                       + _page_bytes(page, work)).hexdigest()[:12]
    out = mdir / f"clip_{chave or sig}.mov"
    decidido = {k: item[k] for k in ("layer", "zona", "libera") if k in item}
    if chave:
        (mdir / f"clip_{chave}.item.json").write_text(json.dumps(decidido), encoding="utf-8")
    if out.exists():
        return out
    job = {"page": page, "out": str(out), "w": w, "h": h, "fps": fps, "duration": round(t1 - t0, 3), "params": params,
           "opaque": item.get("layer") == "full", "webgl": item.get("webgl", item.get("template") in WEBGL),
           "roots": {"/": str(MOTION_DIR), "/fonts/": str(work / "fonts" if (work / "fonts").is_dir() else FONTS_DIR),
                     "/work/": str(work)}}
    job_file = mdir / f"job_{sig}.json"
    job_file.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["node", str(RENDERER), str(job_file)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise EditorError(f"Motion '{item.get('template') or page}' falhou:\n{proc.stderr[-1500:]}")
    log(f"   motion {item.get('template') or page}: {proc.stdout.strip().split(' -> ')[0]}")
    return out


def wave_data(project: Path, bars: int = 220) -> dict:
    """Onda do áudio bruto (1º clipe) + trechos cortados pela edição, normalizados 0..1, e durações."""
    import wave as wv
    from common import load_json
    edl = load_json(project / "edl.json") or {}
    proj = load_json(project / "project.json")
    clip = proj["clips"][0]
    wav = project / "work" / f"{clip['id']}.wav"
    with wv.open(str(wav)) as f:
        a = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
    chunks = np.array_split(np.abs(a), bars)
    peaks = np.array([c.max() if len(c) else 0 for c in chunks])
    peaks = (peaks / (peaks.max() or 1)).round(3).tolist()
    dur = clip["duration"]
    kept = sorted((s["in"], s["out"]) for s in edl.get("segments", []) if s["clip"] == clip["id"])
    cuts, pos = [], 0.0
    for a_, b_ in kept:
        if a_ > pos + 0.05:
            cuts.append([round(pos / dur, 4), round(a_ / dur, 4)])
        pos = max(pos, b_)
    if pos < dur - 0.05:
        cuts.append([round(pos / dur, 4), 1.0])
    return {"peaks": peaks, "cuts": cuts, "raw": round(dur, 2), "final": edl.get("edit_duration", dur)}


def head_position(work: Path, t0: float, t1: float, w: int, h: int) -> dict:
    """Centro e topo da cabeça na janela (pela máscara/rosto do render); padrão: centro, 30% da altura."""
    from common import load_json
    stats = load_json(work / "mask_stats.json") or []
    win = [s for s in stats[int(t0 * 30): int(t1 * 30)] if s.get("face") and s.get("top")]
    if not win:
        return {"x": 0.5, "top": 0.3}
    xs = sorted(s["face"][0] + s["face"][2] / 2 for s in win)
    tops = sorted(s["top"] for s in win)
    return {"x": round(xs[len(xs) // 2], 3), "top": round(tops[len(tops) // 2] / h, 3)}


def snapshots(aroll: Path, tl: dict, mdir: Path, work: Path, n: int) -> list[dict]:
    """n quadros do próprio vídeo editado, espalhados no tempo (para pedaços/carrossel)."""
    out = []
    dur = tl.get("duration") or 10
    sdir = mdir / "snaps"
    sdir.mkdir(exist_ok=True)
    for i in range(n):
        t = dur * (i + 0.5) / n
        f = sdir / f"snap_{hashlib.sha1(f'{aroll}{t:.2f}'.encode()).hexdigest()[:8]}.jpg"
        if not f.exists():
            ffmpeg(["-ss", f"{t:.2f}", "-i", str(aroll), "-frames:v", "1", "-vf", f"{tl['grade']},scale=360:-2", str(f)])
        out.append({"image": f"/work/{f.relative_to(work).as_posix()}"})
    return out


def _page_bytes(page: str, work: Path) -> bytes:
    """Conteúdo da página entra no cache: editar o HTML força um novo render do clipe."""
    path = work / page[len("/work/"):] if page.startswith("/work/") else MOTION_DIR / page.lstrip("/")
    # a biblioteca comum (lib/*.js, *.css) também entra: mudar uma ilustração refaz os clipes que a usam
    lib = b"".join(f.read_bytes() for f in sorted((MOTION_DIR / "lib").glob("*.*")))
    return (path.read_bytes() if path.exists() else b"") + lib


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
