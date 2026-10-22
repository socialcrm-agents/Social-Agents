#!/usr/bin/env python3
"""Gera o pacote de venda de UMA skill (zip independente), sem levar a outra junto.

  python3 tools/empacotar.py anuncio-produto      -> dist/anuncio-produto-AAAA-MM-DD.zip
  python3 tools/empacotar.py editor-video         -> dist/editor-video-AAAA-MM-DD.zip

O zip contém só a pasta da skill (scripts, assets, referências, licenças) e um LEIA-ME de instalação.
Modelos (vozes, recorte, transcrição) não vão no zip: o comprador baixa com setup.py --models,
direto das fontes oficiais, o que mantém o pacote pequeno e as licenças limpas.
Marcas de clientes (brands/<slug>) ficam de fora do editor-video; só o modelo vazio vai junto.
"""

from __future__ import annotations

import datetime as dt
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / ".claude" / "skills"
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
PRIVATE = {"editor-video": ["brands/omarcelprado"]}  # material de cliente: nunca vai no pacote

LEIA_ME = """{nome} — instalação

1. Instale o Claude Code (https://claude.com/claude-code), Python 3.10+, ffmpeg e Node.js 18+.
2. Descompacte esta pasta em ~/.claude/skills/{nome}  (Windows: %USERPROFILE%\\.claude\\skills\\{nome})
3. No terminal:
     cd ~/.claude/skills/{nome}
     python3 -m pip install -r requirements.txt
     python3 scripts/setup.py --models
     npm install -g playwright && npx playwright install chromium
     python3 scripts/setup.py          (tem que terminar em READY)
4. Abra o Claude Code em qualquer pasta e digite /{nome}.

Licenças de terceiros: veja assets/fonts (SIL OFL) e o arquivo LICENCAS.txt.
"""


def files_for(skill: str) -> list[Path]:
    root = SKILLS / skill
    private = [root / p for p in PRIVATE.get(skill, [])]
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if any(p.is_relative_to(x) for x in private):
            continue
        out.append(p)
    return out


def licencas(skill: str) -> str:
    base = ["Fontes Anton, Poppins, DM Serif Display, Caveat: SIL Open Font License 1.1 (assets/fonts/OFL-*.txt).",
            "Ícones Lucide: ISC (assets/.../icons/LICENSE).",
            "Playwright (Apache-2.0) e ffmpeg (LGPL/GPL) são instalados à parte e usados como programas externos."]
    if skill == "anuncio-produto":
        base += ["Vozes: Kokoro-82M (Apache-2.0); vozes Piper pt_BR treinadas em dataset CC0 (OHF-Voice).",
                 "Recorte: IS-Net / U2-Net (Apache-2.0). Transcrição opcional: Parakeet TDT v3 (NVIDIA, CC-BY-4.0).",
                 "Modelos baixados pelo setup.py direto das fontes oficiais (GitHub)."]
    else:
        base += ["three.js e opentype.js: MIT. MediaPipe (Apache-2.0). Parakeet TDT v3 (NVIDIA, CC-BY-4.0)."]
    return "\n".join(base) + "\n"


def main() -> None:
    if len(sys.argv) < 2 or not (SKILLS / sys.argv[1] / "SKILL.md").exists():
        names = ", ".join(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
        sys.exit(f"Uso: empacotar.py <skill>   ({names})")
    skill = sys.argv[1]
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"{skill}-{dt.date.today().isoformat()}.zip"
    files = files_for(skill)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, Path(skill) / f.relative_to(SKILLS / skill))
        z.writestr(f"{skill}/LEIA-ME.txt", LEIA_ME.format(nome=skill))
        z.writestr(f"{skill}/LICENCAS.txt", licencas(skill))
    print(f"OK: {out} ({len(files)} arquivos, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
