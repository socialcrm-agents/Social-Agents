#!/usr/bin/env python3
"""Orquestrador do editor de vídeo.

  run.py new <projeto> --clips a.mp4 b.mp4 [--style reels_viral] [--broll pasta_ou_arquivos ...]
         (--clips/--broll também aceitam link do Google Drive, Dropbox ou .mp4: baixa em <projeto>/fontes/)
         [--hook "texto"] [--cta "texto"]
  run.py all <projeto>          transcreve, escolhe tomadas, planeja e renderiza (v1)
  run.py plan <projeto>         só replaneja (após mudar estilo/overrides)
  run.py render <projeto>       replaneja e renderiza uma nova versão
  run.py styles                 lista os estilos
  run.py variacoes <projeto> [--ganchos 3]      uma versão por gancho (grave 3 ganchos seguidos + o corpo)
  run.py curta <projeto> [--segundos 30 15]     versões curtas terminando em fim de frase

Correções por texto: use edit.py (aplica a mudança e renderiza a próxima versão).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from common import (STYLES_DIR, EditorError, load_json, load_style, log, main_guard, probe, project_paths,
                    require_tools, save_json)
from drive import LinkError, baixar, eh_link

HERE = Path(__file__).resolve().parent
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def step(script: str, project: Path, *extra: str) -> None:
    t = time.time()
    proc = subprocess.run([sys.executable, str(HERE / script), str(project), *extra])
    if proc.returncode != 0:
        raise EditorError(f"{script} falhou")
    log(f"   ({script}: {time.time() - t:.1f}s)")


def collect(items: list[str], exts: set[str], fontes: Path | None = None) -> list[Path]:
    """Arquivos, pastas ou links (Google Drive, Dropbox, http): links são baixados em <projeto>/fontes/."""
    out: list[Path] = []
    for it in items or []:
        if eh_link(it):
            if fontes is None:
                raise EditorError(f"Link não aceito aqui: {it}")
            log(f"Baixando {it} ...")
            try:
                out.append(baixar(it, fontes))
            except LinkError as exc:
                raise EditorError(str(exc)) from exc
            continue
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
    if a.brand:
        from common import load_brand
        load_brand(a.brand)  # falha cedo se a marca não existir
    paths = project_paths(project)
    if paths["project"].exists() and not a.force:
        raise EditorError(f"{project} já existe. Use --force para recriar.")
    for k in ("work", "renders", "versions", "qa"):
        paths[k].mkdir(parents=True, exist_ok=True)
    clips = []
    for n, p in enumerate(collect(a.clips, VIDEO_EXT, project / "fontes"), 1):
        info = probe(p)
        if not info["has_audio"]:
            log(f"Aviso: {p.name} não tem áudio; não dá para cortar por fala (use como B-roll).")
        clips.append({"id": f"c{n}", **info})
    if not clips:
        raise EditorError("Nenhum clipe de vídeo informado (--clips).")
    broll = [{"id": f"b{n}", "path": str(p), "kind": "image" if p.suffix.lower() in IMAGE_EXT else "video",
              **({} if p.suffix.lower() in IMAGE_EXT else {"duration": probe(p)["duration"]})}
             for n, p in enumerate(collect(a.broll, VIDEO_EXT | IMAGE_EXT, project / "fontes"), 1)]
    save_json(paths["project"], {
        "style": a.style, "format": a.format, "brand": a.brand, "clips": clips, "broll": broll, "version": 0,
        "overrides": {"word_fixes": {}, "cuts": [], "restores": [], "behind_add": [], "behind_remove": [],
                      "emphasis_add": [], "broll_at": [], "broll_remove": [], "caption": {}, "zoom": {},
                      "hook": a.hook, "cta": a.cta, "behind_enabled": None, "notes": []},
    })
    log(f"Projeto criado: {project} ({len(clips)} clipe(s), {len(broll)} B-roll, estilo {a.style}, formato {a.format})")


def cmd_all(a) -> None:
    project = Path(a.project).resolve()
    step("transcribe.py", project)
    cmd_render(a)


def cmd_plan(a) -> None:
    project = Path(a.project).resolve()
    step("analyze.py", project)
    step("plan.py", project)
    step("conectores.py", project)


def cmd_render(a) -> None:
    project = Path(a.project).resolve()
    cmd_plan(a)
    step("render.py", project, *(f"--{k}" for k in ("draft", "max") if getattr(a, k, False)))


def _temp_render(project: Path, tweak, label: str) -> Path | None:
    """Renderiza uma variação sem mexer de vez no projeto (o project.json volta ao original no fim)."""
    import shutil
    paths = project_paths(project)
    backup = paths["project"].read_text(encoding="utf-8")
    try:
        proj = load_json(paths["project"])
        tweak(proj)
        save_json(paths["project"], proj)
        for script in ("analyze.py", "plan.py", "render.py"):
            step(script, project)
        last = load_json(paths["project"])["version"]
        src = next(paths["renders"].glob(f"v{last}_*.mp4"))
        dst = paths["renders"] / f"{label}.mp4"
        shutil.copy2(src, dst)
        log(f"   -> {dst}")
        return dst
    finally:
        version = load_json(paths["project"])["version"]
        orig = json.loads(backup)
        orig["version"] = version
        save_json(paths["project"], orig)


def cmd_variacoes(a) -> None:
    """Você gravou N ganchos seguidos e depois o corpo: gera uma versão por gancho (para testar qual vende)."""
    import analyze
    project = Path(a.project).resolve()
    paths = project_paths(project)
    words = load_json(paths["transcript"])["words"]
    proj = load_json(paths["project"])
    drop, _ = analyze.analyze(words, load_style(proj["style"], proj.get("brand")), proj.get("overrides", {}))
    kept = [w for i, w in enumerate(words) if i not in drop]
    sents, cur = [], []
    for w in kept:
        cur.append(w["w"])
        if w["w"].endswith((".", "!", "?")):
            sents.append(" ".join(cur))
            cur = []
    hooks = sents[:a.ganchos]
    log("Ganchos encontrados:\n" + "\n".join(f"  {n}. {h}" for n, h in enumerate(hooks, 1)))
    for n, hook in enumerate(hooks, 1):
        others = [h for h in hooks if h != hook]
        _temp_render(project, lambda p, o=others: p["overrides"].setdefault("cuts", []).extend(o), f"gancho{n}")


def cmd_curta(a) -> None:
    """Versões curtas (ex.: 30 s e 15 s) que terminam em fim de frase, mantendo gancho e fechamento."""
    project = Path(a.project).resolve()
    for s in a.segundos:
        _temp_render(project, lambda p, s=s: p.__setitem__("target_duration", s), f"curta_{s}s")


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
    n.add_argument("--brand", default=None, help="kit de marca em brands/<slug> (cores, fontes, logo, voz, CTAs)")
    n.add_argument("--hook", default=None)
    n.add_argument("--cta", default=None)
    n.add_argument("--format", default="9:16", choices=["9:16", "16:9", "1:1", "4:5"],
                   help="9:16 Reels/TikTok/Shorts, 16:9 YouTube/aula/podcast, 1:1 ou 4:5 feed")
    n.add_argument("--force", action="store_true")
    for name in ("all", "plan", "render"):
        sp = sub.add_parser(name)
        sp.add_argument("project")
        if name != "plan":
            sp.add_argument("--draft", action="store_true", help="prévia rápida (qualidade menor)")
            sp.add_argument("--max", action="store_true", help="compressão mais lenta, arquivo menor")
    sub.add_parser("styles")
    v = sub.add_parser("variacoes", help="uma versão por gancho gravado")
    v.add_argument("project")
    v.add_argument("--ganchos", type=int, default=3)
    c = sub.add_parser("curta", help="versões curtas terminando em fim de frase")
    c.add_argument("project")
    c.add_argument("--segundos", type=int, nargs="+", default=[30, 15])
    a = ap.parse_args()
    {"new": cmd_new, "all": cmd_all, "plan": cmd_plan, "render": cmd_render, "styles": cmd_styles,
     "variacoes": cmd_variacoes, "curta": cmd_curta}[a.cmd](a)


if __name__ == "__main__":
    main_guard(main)
