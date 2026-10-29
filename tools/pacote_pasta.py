#!/usr/bin/env python3
"""Gera o kit "pasta de edição" para o Claude Code no computador (app do Claude, modo Code):

  python3 tools/pacote_pasta.py   -> dist/Edicao-de-Videos-EditorViral-AAAA-MM-DD.zip   (R$97: editor-viral)
                                     dist/Edicao-de-Videos-PRO-AAAA-MM-DD.zip           (editor-video + equipe)

Cada zip traz a pasta Edicao-de-Videos/ com 1-GRAVACOES, 2-REFERENCIAS, 3-PRONTOS, o CLAUDE.md (o "cérebro":
preparar, aprender o estilo, storyboard, editar, salvar em 3-PRONTOS), os pedidos prontos, o guia do cliente em
PDF e a skill em .claude/skills/ (o Claude Code carrega sozinho ao abrir a pasta).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from empacotar import REPO, SKILLS, files_for  # noqa: E402

KIT = REPO / "kits" / "pasta-edicao"
AGENTES = REPO / ".claude" / "agents"
CREATIVE = REPO / "creative"
RAIZ = "Edicao-de-Videos"
PASTAS = {
    "1-GRAVACOES": "Coloque aqui os vídeos que você gravou (do celular ou da câmera).\n",
    "2-REFERENCIAS": "Coloque aqui vídeos de criadores cujo estilo você gosta, ou cole os links em links.txt.\n",
    "3-PRONTOS": "Aqui aparecem os seus vídeos editados.\n",
}


def pdf_do_guia() -> Path:
    """COMECE-AQUI.md -> PDF (mesmo visual do guia do Editor Viral)."""
    import markdown
    import os
    import subprocess
    css = ("@page{size:A4;margin:16mm}body{font-family:Poppins,Arial,sans-serif;color:#1a1a1a;font-size:11.5pt;"
           "line-height:1.5}h1{font-size:24pt;border-bottom:4px solid #FFD400;padding-bottom:6px}h2{margin-top:20px;"
           "border-left:6px solid #FFD400;padding-left:10px}table{border-collapse:collapse;width:100%;font-size:10pt}"
           "th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}th{background:#FFF6CC}"
           "blockquote{background:#f5f5f5;border-left:4px solid #FFD400;margin:8px 0;padding:8px 12px;"
           "font-family:monospace;font-size:10.5pt}")
    tmp = REPO / "dist" / ".pasta"
    tmp.mkdir(parents=True, exist_ok=True)
    html = tmp / "guia.html"
    md = (KIT / "COMECE-AQUI.md").read_text(encoding="utf-8")
    html.write_text(f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
                    f"{markdown.markdown(md, extensions=['tables'])}</body></html>", encoding="utf-8")
    pdf = tmp / "COMECE-AQUI.pdf"
    js = tmp / "pdf.cjs"
    js.write_text("const{chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
                  "const p=await b.newPage();await p.goto('file://'+process.argv[2]);await p.pdf({path:process.argv[3],"
                  "format:'A4',printBackground:true});await b.close();})();")
    raiz_npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js), str(html), str(pdf)], check=True, env={**os.environ, "NODE_PATH": raiz_npm})
    return pdf


def montar(nome: str, edicao: str, skills: list[str], pdf: Path) -> Path:
    out = REPO / "dist" / f"Edicao-de-Videos-{nome}-{dt.date.today().isoformat()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        def texto(nome: str, conteudo: str) -> None:
            info = zipfile.ZipInfo(nome, dt.datetime.now().timetuple()[:6])
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, conteudo)
        for pasta, txt in PASTAS.items():
            texto(f"{RAIZ}/{pasta}/LEIA-ME.txt", txt)
        texto(f"{RAIZ}/2-REFERENCIAS/links.txt", "")
        z.write(KIT / f"CLAUDE-{edicao}.md", f"{RAIZ}/CLAUDE.md")
        z.write(KIT / "COMECE-AQUI.md", f"{RAIZ}/COMECE-AQUI.md")
        z.write(pdf, f"{RAIZ}/COMECE-AQUI.pdf")
        z.write(KIT / "PROMPTS.txt", f"{RAIZ}/PROMPTS.txt")
        z.write(KIT / "settings.json", f"{RAIZ}/.claude/settings.json")
        for s in skills:
            if s == "editor-viral":
                base = SKILLS / s
                for f in sorted(base.rglob("*")):
                    rel = f.relative_to(base).as_posix()
                    if f.is_file() and "__pycache__" not in rel and not rel.startswith(("es/", "chatgpt/", "lancamento/")):
                        z.write(f, f"{RAIZ}/.claude/skills/{s}/{rel}")
                continue
            for f in files_for(s):
                z.write(f, f"{RAIZ}/.claude/skills/{s}/{f.relative_to(SKILLS / s).as_posix()}")
            if s == "editor-video":
                z.writestr(f"{RAIZ}/.claude/skills/{s}/perfil.json", json.dumps({"perfil": "completo", "motion": True}))
        if "creative-studio" in skills:
            for f in sorted(AGENTES.glob("*.md")):
                z.write(f, f"{RAIZ}/.claude/agents/{f.name}")
            for f in sorted(CREATIVE.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, f"{RAIZ}/.claude/skills/creative-studio/creative/{f.relative_to(CREATIVE).as_posix()}")
    print(f"OK: {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def main() -> None:
    (REPO / "dist").mkdir(exist_ok=True)
    pdf = pdf_do_guia()
    montar("EditorViral", "viral", ["editor-viral"], pdf)
    montar("PRO", "pro", ["editor-video", "creative-studio"], pdf)


if __name__ == "__main__":
    main()
