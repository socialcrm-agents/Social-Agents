#!/usr/bin/env python3
"""Recorta o produto das fotos (fundo transparente) e tira a paleta de cores dele.

Modelo: IS-Net general use (Apache-2.0, via releases do rembg no GitHub) rodando no onnxruntime, 100% local.
Sem o modelo grande, usa o U2-Net pequeno (u2netp, Apache-2.0).

Uso: recorte.py <projeto>     -> work/recortes/<foto>.png + work/recortes.json
Para cada foto grava: arquivo recortado, área do produto, se encosta na borda (foto de ambiente / produto
cortado) e um veredito "usar_recorte". Fotos de ambiente continuam boas para as cenas de foto inteira.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

from common import MODELS_DIR, AdError, load_json, log, main_guard, project_paths, save_json

CUT_DIR = MODELS_DIR / "recorte"
MODELS = [("isnet-general-use.onnx", 1024, (0.485, 0.456, 0.406), (1.0, 1.0, 1.0)),
          ("u2netp.onnx", 320, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225))]


def _session():
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise AdError("onnxruntime ausente: pip install onnxruntime") from exc
    for name, size, mean, std in MODELS:
        path = CUT_DIR / name
        if path.exists():
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"]), size, mean, std
    raise AdError("Modelo de recorte ausente. Rode: python3 scripts/setup.py --models")


def mask_of(img: Image.Image, sess) -> np.ndarray:
    session, size, mean, std = sess
    x = np.asarray(img.convert("RGB").resize((size, size), Image.BICUBIC), np.float32) / 255.0
    x = ((x - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
    out = session.run(None, {session.get_inputs()[0].name: x})[0][0, 0]
    out = (out - out.min()) / max(out.max() - out.min(), 1e-6)
    m = Image.fromarray((out * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR)
    return np.asarray(m, np.float32) / 255.0


def main_object(alpha: np.ndarray, keep_all: bool = False) -> np.ndarray:
    """Mantém só o maior objeto recortado (o produto) e descarta enfeites soltos da cena (frutas, folhas...)."""
    if keep_all:
        return alpha
    h, w = alpha.shape
    k = max(1, int(max(h, w) / 220))
    small = alpha[::k, ::k] > 0.5
    sh, sw = small.shape
    lab = np.zeros(small.shape, np.int32)
    sizes = [0]
    for y0, x0 in zip(*np.nonzero(small)):
        if lab[y0, x0]:
            continue
        n = len(sizes)
        lab[y0, x0] = n
        stack, size = [(y0, x0)], 0
        while stack:
            y, x = stack.pop()
            size += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < sh and 0 <= xx < sw and small[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    stack.append((yy, xx))
        sizes.append(size)
    if len(sizes) <= 2:
        return alpha
    best = int(np.argmax(sizes))
    keep = np.kron(lab == best, np.ones((k, k), bool))[:h, :w]
    # margem de 2 células para não comer a borda suave do produto
    from PIL import ImageFilter
    keep = np.asarray(Image.fromarray(keep.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * k + 1))) > 0
    return alpha * keep


def palette(rgb: np.ndarray, alpha: np.ndarray, k: int = 4) -> list[str]:
    """Cores principais do produto (k-means simples), da mais presente para a menos presente."""
    px = rgb[alpha > 0.85].reshape(-1, 3).astype(np.float32)
    if len(px) < 50:
        return []
    rng = np.random.default_rng(0)
    px = px[rng.choice(len(px), min(len(px), 6000), replace=False)]
    cent = px[rng.choice(len(px), k, replace=False)]
    for _ in range(12):
        lab = ((px[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
        cent = np.array([px[lab == i].mean(0) if (lab == i).any() else cent[i] for i in range(k)])
    counts = np.bincount(lab, minlength=k)
    order = counts.argsort()[::-1]
    return ["#%02x%02x%02x" % tuple(int(c) for c in cent[i]) for i in order if counts[i] > len(px) * 0.04]


def cut(photo: Path, out_dir: Path, sess, keep_all: bool = False) -> dict:
    img = Image.open(photo)
    img = img.convert("RGB")
    if max(img.size) > 2200:  # fotos de celular: 2200 px já sobra para 1080x1920
        img.thumbnail((2200, 2200), Image.LANCZOS)
    m = mask_of(img, sess)
    alpha = main_object(np.clip((m - 0.12) / 0.76, 0, 1), keep_all)
    cover = float((alpha > 0.5).mean())
    ys, xs = np.where(alpha > 0.5)
    if not len(xs):
        return {"foto": str(photo), "usar_recorte": False, "motivo": "produto não encontrado na foto"}
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    w, h = img.size
    x0, x1, y0, y1 = int(x0), int(x1), int(y0), int(y1)
    edge = int(sum([x0 <= 2, y0 <= 2, x1 >= w - 3, y1 >= h - 3]))
    pad = int(0.04 * max(x1 - x0, y1 - y0))
    box = (max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, w), min(y1 + pad, h))
    rgba = np.dstack([np.asarray(img), (alpha * 255).astype(np.uint8)])
    out = out_dir / f"{photo.stem}.png"
    Image.fromarray(rgba).crop(box).save(out, optimize=False, compress_level=3)
    ok = bool(0.03 < cover < 0.8 and edge <= 1)
    motivo = "" if ok else ("produto ocupa quase a foto toda ou encosta nas bordas: use a foto inteira"
                            if cover >= 0.8 or edge > 1 else "produto muito pequeno na foto")
    return {"foto": str(photo), "recorte": str(out), "usar_recorte": ok, "motivo": motivo,
            "area": round(cover, 3), "bordas": edge, "proporcao": round((box[2] - box[0]) / (box[3] - box[1]), 3),
            "cores": palette(np.asarray(img), alpha), "tamanho": [w, h]}


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    paths = project_paths(project)
    proj = load_json(paths["project"])
    if not proj:
        raise AdError("produto.json não existe. Rode: anuncio.py novo ...")
    out_dir = paths["work"] / "recortes"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = load_json(paths["work"] / "recortes.json", {})
    sess = None
    result = {}
    for f in proj["fotos"]:
        p = Path(f)
        key = f"{p}:{p.stat().st_mtime_ns}"
        if key in cache and Path(cache[key].get("recorte", "")).exists():
            result[key] = cache[key]
            continue
        sess = sess or _session()
        result[key] = cut(p, out_dir, sess, keep_all=bool(proj.get("recorte_todos")))
        r = result[key]
        log(f"   {p.name}: {'recorte OK' if r['usar_recorte'] else 'foto inteira'} "
            f"(área {r.get('area', 0):.0%}) {r.get('motivo', '')}")
    save_json(paths["work"] / "recortes.json", result)


if __name__ == "__main__":
    main_guard(main)
