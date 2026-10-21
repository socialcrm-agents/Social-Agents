#!/usr/bin/env python3
"""Orquestrador do editor de vídeo.

  run.py new <projeto> --clips a.mp4 b.mp4 [--style reels_viral] [--broll pasta_ou_arquivos ...]
         [--hook "texto"] [--cta "texto"]
  run.py all <projeto>          transcreve, escolhe tomadas, planeja e renderiza (v1)
  run.py plan <projeto>         só replaneja (após mudar estilo/overrides)
  run.py render <projeto>       replaneja e renderiza uma nova versão
  run.py styles                 lista os estilos

Correções por texto: use edit.py (aplica a mudança e renderiza a próxima versão).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from common import STYLES_DIR, EditorError, load_json, log, main_guard, probe, project_paths, require_tools, save_json

HERE = Path(__file__).resolve().parent
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def step(script: str, project: Path, *extra: str) -> None:
    t = time.time()
    proc = subprocess.run([sys.executable, str(HERE / script), str(project), *extra])
    if proc.returncode != 0:
        raise EditorError(f"{script} falhou")
    log(f"   ({script}: {time.time() - t:.1f}s)")


def collect(items: list[str], exts: set[str]) -> list[Path]:
    out: list[Path] = []
    for it in items or []:
        p = Path(it).expanduser().resolve()
        if p.is_dir():
            out += sorted(x for x in p.iterdir() if x.suffix.lower() in exts)
        elif p.exists():
            out.append(p)
        else:
            raise EditorError(f"Arquivo não encontrado: {it}")
    return out


def cmd_new(a) -> None:
    project = Path(a.project).resolve()
    paths = project_paths(project)
    if paths["project"].exists() and not a.force:
        raise EditorError(f"{project} já existe. Use --force para recriar.")
    for k in ("work", "renders", "versions", "qa"):
        paths[k].mkdir(parents=True, exist_ok=True)
    clips = []
    for n, p in enumerate(collect(a.clips, VIDEO_EXT), 1):
        info = probe(p)
        if not info["has_audio"]:
            log(f"Aviso: {p.name} não tem áudio; não dá para cortar por fala (use como B-roll).")
        clips.append({"id": f"c{n}", **info})
    if not clips:
        raise EditorError("Nenhum clipe de vídeo informado (--clips).")
    broll = [{"id": f"b{n}", "path": str(p), "kind": "image" if p.suffix.lower() in IMAGE_EXT else "video",
              **({} if p.suffix.lower() in IMAGE_EXT else {"duration": probe(p)["duration"]})}
             for n, p in enumerate(collect(a.broll, VIDEO_EXT | IMAGE_EXT), 1)]
    save_json(paths["project"], {
        "style": a.style, "clips": clips, "broll": broll, "version": 0,
        "overrides": {"word_fixes": {}, "cuts": [], "restores": [], "behind_add": [], "behind_remove": [],
                      "emphasis_add": [], "broll_at": [], "broll_remove": [], "caption": {}, "zoom": {},
                      "hook": a.hook, "cta": a.cta, "behind_enabled": None, "notes": []},
    })
    log(f"Projeto criado: {project} ({len(clips)} clipe(s), {len(broll)} B-roll, estilo {a.style})")


def cmd_all(a) -> None:
    project = Path(a.project).resolve()
    step("transcribe.py", project)
    cmd_render(a)


def cmd_plan(a) -> None:
    project = Path(a.project).resolve()
    step("analyze.py", project)
    step("plan.py", project)


def cmd_render(a) -> None:
    project = Path(a.project).resolve()
    cmd_plan(a)
    step("render.py", project)


def cmd_styles(_a) -> None:
    for p in sorted(STYLES_DIR.glob("*.json")):
        s = load_json(p)
        log(f"- {p.stem}: {s['label']} - {s['description']}")


def main() -> None:
    require_tools()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("project")
    n.add_argument("--clips", nargs="+", required=True)
    n.add_argument("--broll", nargs="*", default=[])
    n.add_argument("--style", default="reels_viral")
    n.add_argument("--hook", default=None)
    n.add_argument("--cta", default=None)
    n.add_argument("--force", action="store_true")
    for name in ("all", "plan", "render"):
        sub.add_parser(name).add_argument("project")
    sub.add_parser("styles")
    a = ap.parse_args()
    {"new": cmd_new, "all": cmd_all, "plan": cmd_plan, "render": cmd_render, "styles": cmd_styles}[a.cmd](a)


if __name__ == "__main__":
    main_guard(main)
