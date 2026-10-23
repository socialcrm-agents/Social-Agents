#!/usr/bin/env python3
"""Gera o instalador de dois cliques para Windows: dist/Editor-Viral-Windows-AAAA-MM-DD.zip

  python3 tools/pacote_windows.py                       -> editor-video + anuncio-produto + vsl-oferta
  python3 tools/pacote_windows.py editor-video          -> só as skills escolhidas

O zip leva skills/<nome>/ (mesmos arquivos do empacotar.py, sem material de cliente), INSTALAR.bat, instalar.ps1 e
LEIA-ME.txt. O cliente extrai, dá dois cliques no INSTALAR.bat e usa no app do Claude, no modo Code.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

from empacotar import REPO, SKILLS, files_for

AQUI = Path(__file__).resolve().parent / "windows"
PADRAO = ["editor-video", "anuncio-produto", "vsl-oferta", "creative-studio"]
AGENTES = REPO / ".claude" / "agents"
CREATIVE = REPO / "creative"

LEIA_ME = """EDITOR VIRAL - INSTALAÇÃO NO WINDOWS (2 cliques)

1. Clique com o botão direito neste zip > "Extrair tudo..." > Extrair.
2. Abra a pasta extraída e dê dois cliques em INSTALAR.bat.
   - Se aparecer "O Windows protegeu o computador": clique em "Mais informações" > "Executar assim mesmo".
   - Se o Windows pedir permissão ("Deseja permitir...?"): clique em Sim.
   - Leva de 10 a 25 minutos. Espere aparecer PRONTO em verde.
3. Feche e abra de novo o app do Claude.

COMO USAR
- No app do Claude, clique no ícone </> (Code), no canto de cima, à esquerda.
  (O modo conversa normal, o do balãozinho, enxerga a skill mas NÃO consegue editar: ele não roda programas
  no seu computador. O modo Code roda.)
- Escolha a pasta onde estão os vídeos.
- Digite, por exemplo:
    /editor-video edita os vídeos desta pasta sem cortar nem acelerar, máxima qualidade, com pergunta na tela,
    cards e 3D; troca o fundo se fizer sentido
- O vídeo pronto aparece na pasta renders/ dentro do projeto.

Skills instaladas: {skills}

Deu erro? Mande o arquivo instalacao.log (fica nesta pasta) para o suporte.
"""


def main() -> None:
    skills = [a for a in sys.argv[1:] if not a.startswith("--")] or PADRAO
    for s in skills:
        if not (SKILLS / s / "SKILL.md").exists():
            sys.exit(f"Skill não encontrada: {s}")
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"Editor-Viral-Windows-{dt.date.today().isoformat()}.zip"
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for s in skills:
            for f in files_for(s):
                z.write(f, Path("skills") / s / f.relative_to(SKILLS / s))
                n += 1
            if s == "editor-video":
                z.writestr(f"skills/{s}/perfil.json", json.dumps({"perfil": "completo", "motion": True}))
        if "creative-studio" in skills:
            # equipe (vai para ~/.claude/agents) e contratos (dentro da skill: valem em qualquer pasta)
            for f in sorted(AGENTES.glob("*.md")):
                z.write(f, Path("agents") / f.name)
            for f in sorted(CREATIVE.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, Path("skills") / "creative-studio" / "creative" / f.relative_to(CREATIVE))
        z.write(AQUI / "INSTALAR.bat", "INSTALAR.bat")
        z.write(AQUI / "instalar.ps1", "instalar.ps1")
        z.writestr("LEIA-ME.txt", LEIA_ME.format(skills=", ".join(skills)).replace("\n", "\r\n").encode("utf-8-sig"))
    print(f"OK: {out} ({n} arquivos das skills, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
