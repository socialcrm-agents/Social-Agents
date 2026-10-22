#!/usr/bin/env python3
"""Gera o pacote de venda de UMA skill (zip independente), sem levar a outra junto.

  python3 tools/empacotar.py anuncio-produto                    -> dist/anuncio-produto-AAAA-MM-DD.zip
  python3 tools/empacotar.py editor-video                       -> dist/editor-video-AAAA-MM-DD.zip (completo)
  python3 tools/empacotar.py editor-video --perfil corte-viral  -> front: cortes, legenda, zoom, palavra atrás,
                                                                    efeitos (sem animações 3D, sem Node/Chromium)
  python3 tools/empacotar.py editor-video --perfil motion       -> Pacote Motion 3D: só os arquivos que faltam ao
                                                                    front; o cliente descompacta POR CIMA da pasta

O código é um só (este repositório, sempre completo). O perfil só escolhe o que entra no zip e grava um
perfil.json que liga ou desliga as animações (scripts/common.py: perfil()).

O zip contém só a pasta da skill (scripts, assets, referências, licenças) e um LEIA-ME de instalação.
Modelos (vozes, recorte, transcrição) não vão no zip: o comprador baixa com setup.py --models,
direto das fontes oficiais, o que mantém o pacote pequeno e as licenças limpas.
Marcas de clientes (brands/<slug>) ficam de fora do editor-video; só o modelo vazio vai junto.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / ".claude" / "skills"
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
PRIVATE = {"editor-video": ["brands/omarcelprado"]}  # material de cliente: nunca vai no pacote
# arquivos do motor de animação (Pacote Motion 3D) dentro da skill editor-video
MOTION = ["assets/motion", "scripts/motion.py", "scripts/motion_render.mjs", "references/motion.md",
          "references/catalogo.md"]
PERFIS = {
    "completo": {"motion": True, "so": None, "sem": []},
    "corte-viral": {"motion": False, "so": None, "sem": MOTION},
    "motion": {"motion": True, "so": MOTION, "sem": []},
}

LEIA_ME_MOTION = """Pacote Motion 3D — instalação (precisa do Corte Viral já instalado)

1. Instale o Node.js 18+ (https://nodejs.org) e rode:
     npm install -g playwright && npx playwright install chromium
2. Descompacte este zip POR CIMA da pasta da skill (~/.claude/skills/editor-video), substituindo perfil.json.
3. Rode python3 ~/.claude/skills/editor-video/scripts/setup.py: a linha "STATUS pacote completo" confirma.
4. No Claude Code, peça: "me coloca numa moldura 3D", "troca meu fundo por um estúdio 3D", "anima isso na tela".
"""

LEIA_ME = """{nome} — instalação

1. Instale o Claude Code (https://claude.com/claude-code), Python 3.10+ e ffmpeg{node}.
2. Descompacte esta pasta em ~/.claude/skills/{nome}  (Windows: %USERPROFILE%\\.claude\\skills\\{nome})
3. No terminal:
     cd ~/.claude/skills/{nome}
     python3 -m pip install -r requirements.txt
     python3 scripts/setup.py --models
{playwright}     python3 scripts/setup.py          (tem que terminar em READY)
4. Abra o Claude Code em qualquer pasta e digite /{nome}.

Licenças de terceiros: veja assets/fonts (SIL OFL) e o arquivo LICENCAS.txt.
"""


def files_for(skill: str, perfil: str = "completo") -> list[Path]:
    root = SKILLS / skill
    cfg = PERFIS[perfil]
    private = [root / p for p in PRIVATE.get(skill, [])]
    excluded = [root / p for p in cfg["sem"]]
    only = [root / p for p in cfg["so"]] if cfg["so"] else None
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.parts) or p.name == "perfil.json":
            continue
        if any(p.is_relative_to(x) for x in private + excluded):
            continue
        if only is not None and not any(p == x or p.is_relative_to(x) for x in only):
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or not (SKILLS / args[0] / "SKILL.md").exists():
        names = ", ".join(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
        sys.exit(f"Uso: empacotar.py <skill> [--perfil completo|corte-viral|motion]   ({names})")
    skill = args[0]
    perfil = sys.argv[sys.argv.index("--perfil") + 1] if "--perfil" in sys.argv else "completo"
    if perfil not in PERFIS or (perfil != "completo" and skill != "editor-video"):
        sys.exit(f"Perfil '{perfil}' inválido para {skill} (perfis do editor-video: {', '.join(PERFIS)})")
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    nome = skill if perfil == "completo" else f"{skill}-{perfil}"
    out = dist / f"{nome}-{dt.date.today().isoformat()}.zip"
    files = files_for(skill, perfil)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, Path(skill) / f.relative_to(SKILLS / skill))
        if skill == "editor-video":
            z.writestr(f"{skill}/perfil.json", json.dumps({"perfil": "corte-viral" if perfil == "corte-viral"
                                                           else "completo", "motion": PERFIS[perfil]["motion"]}))
        z.writestr(f"{skill}/LEIA-ME.txt", LEIA_ME_MOTION if perfil == "motion" else LEIA_ME.format(
            nome=skill, node="" if perfil == "corte-viral" else " e Node.js 18+",
            playwright="" if perfil == "corte-viral" else "     npm install -g playwright && npx playwright install chromium\n"))
        if perfil != "motion":
            z.writestr(f"{skill}/LICENCAS.txt", licencas(skill))
    print(f"OK: {out} ({len(files)} arquivos, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
