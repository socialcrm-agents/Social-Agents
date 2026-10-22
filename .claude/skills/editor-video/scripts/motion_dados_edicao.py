"""Dados reais para os templates de edição visual (transcricao, tomadas): palavras da fala com tempo, onda do
áudio e o que a edição cortou. Chamado por motion.render_clip para cada animação (gancho motion_dados_*)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np


def _peaks(src: Path | str, start: float, dur: float, bars: int) -> list[float]:
    """Picos normalizados (0..1) do áudio entre start e start+dur, em `bars` colunas."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{max(start, 0):.3f}", "-t", f"{dur:.3f}",
                           "-i", str(src), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    a = np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768
    if not len(a):
        return [0.0] * bars
    chunks = np.array_split(np.abs(a), bars)
    pk = np.array([c.max() if len(c) else 0 for c in chunks])
    pk = np.sqrt(pk / (pk.max() or 1))  # raiz: a onda fica "cheia" como nos editores
    return [round(float(x), 2) for x in pk]


def _bruto(project: Path, raw_bars: int = 120) -> dict:
    """Onda do bruto inteiro (1º clipe) + trechos removidos pela edição (fração 0..1, com motivo)."""
    edl = json.loads((project / "edl.json").read_text()) if (project / "edl.json").exists() else {}
    proj = json.loads((project / "project.json").read_text())
    clip = proj["clips"][0]
    raw = float(edl.get("raw_duration") or clip.get("duration") or 1)
    segs = sorted((s["in"], s["out"], s.get("words", [])) for s in edl.get("segments", []) if s["clip"] == clip["id"])
    dropped = set(edl.get("dropped", []))
    cuts, pos, prev_last = [], 0.0, -1
    for a, b, ws in segs + [(raw, raw, [])]:
        if a > pos + 0.03:
            first = ws[0] if ws else None
            # palavras que caíram entre o fim do segmento anterior e o início deste = repetição/tropeço
            rep = first is not None and any(prev_last < d < first for d in dropped)
            motivo = "REPETIDO" if rep else ("PAUSA" if a - pos >= 0.3 else "RESPIRO")
            cuts.append({"a": round(pos / raw, 4), "b": round(a / raw, 4), "m": motivo, "s": round(a - pos, 1)})
        if ws:
            prev_last = ws[-1]
        pos = max(pos, b)
    pausas = sum(1 for c in cuts if c["m"] != "REPETIDO")
    return {"peaks": _peaks(clip["path"], 0, raw, raw_bars), "cuts": cuts, "raw": round(raw, 1),
            "final": round(float(edl.get("edit_duration") or raw), 1),
            "erros": len(dropped) + pausas, "cortes": len(cuts)}


def transcricao(params, *, tl, aroll, t0, t1, project):
    """Palavras da fala na janela (tempo relativo ao clipe), onda do vídeo editado e o bruto com os cortes."""
    words = tl.get("words", [])
    params.setdefault("palavras", [{"w": x["w"], "a": round(x["t0"] - t0, 2), "b": round(x["t1"] - t0, 2)}
                                   for x in words if x["t1"] > t0 - 2.5 and x["t0"] < t1 + 2.5])
    params.setdefault("total_palavras", len(words))
    params.setdefault("primeira", next((i for i, x in enumerate(words) if x["t1"] > t0), 0))
    params.setdefault("onda", _peaks(aroll, t0 - 2.5, (t1 - t0) + 5.0, 220))  # janela com folga para correr
    try:
        b = _bruto(Path(project))
    except (OSError, KeyError, ValueError):
        b = {}
    if b:
        params.setdefault("bruto", {k: b[k] for k in ("peaks", "cuts", "raw", "final")})
        params.setdefault("erros", b["erros"])
        params.setdefault("cortes", b["cortes"])


def _thumb(src: str, at: float, out: Path) -> None:
    if not out.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(at, 0):.3f}", "-i", str(src),
                        "-frames:v", "1", "-vf", "scale=240:-2", "-q:v", "4", str(out)], capture_output=True)


def tomadas(params, *, work, tl, aroll, t0, t1, project):
    """Cada tomada ganha miniatura e mini onda: do bruto (`tempo` em segundos do 1º clipe) ou do vídeo editado."""
    proj = json.loads((Path(project) / "project.json").read_text())
    clip = proj["clips"][0]["path"]
    assets = Path(work) / "motion" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    itens = params.get("itens") or []
    for i, it in enumerate(itens):
        if "tempo" in it:
            src, at, dur = clip, float(it["tempo"]), float(it.get("dur", 1.6))
        else:
            src, at, dur = aroll, t0 + (t1 - t0) * i / max(len(itens), 1), 1.6
        if not it.get("image"):
            f = assets / f"take_{Path(src).stem}_{at:.2f}.jpg"
            _thumb(src, at + 0.2, f)
            it["image"] = f"/work/{f.relative_to(Path(work)).as_posix()}"
        it.setdefault("onda", _peaks(src, at, dur, 40))


def enriquecer(tpl, params, item, *, work, tl, aroll, mask, t0, t1, w, h, fps, project):
    if tpl == "transcricao":
        transcricao(params, tl=tl, aroll=aroll, t0=t0, t1=t1, project=project)
    elif tpl == "tomadas":
        tomadas(params, work=work, tl=tl, aroll=aroll, t0=t0, t1=t1, project=project)
