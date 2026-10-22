#!/usr/bin/env python3
"""Instala as skills no Claude Code do computador, para funcionarem em qualquer pasta.

  python3 tools/instalar_skills.py                  instala as três (editor-video, anuncio-produto, vsl-oferta)
  python3 tools/instalar_skills.py anuncio-produto  instala só uma
  python3 tools/instalar_skills.py --copiar         copia em vez de criar atalho (Windows sem modo desenvolvedor)
  python3 tools/instalar_skills.py --modelos        também baixa os modelos (vozes, recorte, transcrição)

Por padrão cria um atalho (symlink) em ~/.claude/skills/<skill> apontando para este repositório: um
`git pull` aqui atualiza a skill instalada. Depois, em qualquer conversa do Claude Code, use
/editor-video, /anuncio-produto ou /vsl-oferta (ou só peça: "edita esse vídeo", "faz um anúncio desse produto",
"quero montar minha VSL").
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = {"editor-video": REPO / ".claude" / "skills" / "editor-video",
          "anuncio-produto": REPO / ".claude" / "skills" / "anuncio-produto",
          "vsl-oferta": REPO / ".claude" / "skills" / "vsl-oferta"}
DEST = Path.home() / ".claude" / "skills"


def install(name: str, copy: bool) -> Path:
    src, dst = SKILLS[name], DEST / name
    DEST.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    if copy:
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        try:
            dst.symlink_to(src, target_is_directory=True)
        except OSError:  # Windows sem permissão de symlink
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
            copy = True
    print(f"OK: {name} -> {dst} ({'cópia' if copy else 'atalho para ' + str(src)})")
    return dst


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names = args or list(SKILLS)
    for n in names:
        if n not in SKILLS:
            sys.exit(f"Skill '{n}' não existe. Opções: {', '.join(SKILLS)}")
    for n in names:
        dst = install(n, "--copiar" in sys.argv)
        setup = [sys.executable, str(dst / "scripts" / "setup.py")]
        if not Path(setup[1]).exists():  # vsl-oferta: só texto e Python puro, nada para baixar
            continue
        if "--modelos" in sys.argv:
            subprocess.run([*setup, "--install", "--models"] + (["--voz-propria"] if n == "anuncio-produto" else []))
        subprocess.run(setup)
    print("\nPronto. Abra o Claude Code em qualquer pasta e use " + " ou ".join(f"/{n}" for n in names) + ".")


if __name__ == "__main__":
    main()
