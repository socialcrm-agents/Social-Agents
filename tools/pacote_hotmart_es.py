#!/usr/bin/env python3
"""Pacote em espanhol para a Hotmart: Claude (computador e app), ChatGPT, guias em PDF e o kit do GPT.

  python3 tools/pacote_editor_viral.py --idioma es   (antes: gera o pacote base em espanhol)
  python3 tools/pacote_hotmart_es.py                 -> dist/HOTMART-Editor-Viral-ES-AAAA-MM-DD/
"""

from __future__ import annotations

import datetime as dt
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pacote_editor_viral as pev  # noqa: E402
from empacotar import REPO  # noqa: E402

KIT = REPO / "kits" / "pasta-edicao"
ES = KIT / "es"
SK = REPO / ".claude" / "skills" / "editor-viral"
RAIZ = "Edicion-de-Videos"
PASTAS = {
    "1-GRABACIONES": "Pon aquí los videos que grabaste (del celular o de la cámara).\n",
    "2-REFERENCIAS": "Pon aquí videos de creadores cuyo estilo te gusta, o pega los enlaces en enlaces.txt.\n",
    "3-LISTOS": "Aquí aparecen tus videos editados.\n",
}

LEIA_ME = """EDITOR VIRAL EM ESPANHOL - O QUE SUBIR NA HOTMART ({data})

PASTA 1-SUBIR-EN-HOTMART (é o que o cliente baixa; tudo em espanhol)
  Edicion-de-Videos-ES.zip     Claude no computador (recomendado): pasta com 1-GRABACIONES, 2-REFERENCIAS,
                               3-LISTOS + instruções que o Claude lê sozinho. Sem limite de duração.
  editor-viral-claude-es.zip   Claude no app/web (celular): o cliente sobe em Configuración > Skills.
  Guia-Claude-ES.pdf           passo a passo das duas formas no Claude + método (roteiro, ganchos, gravação).
  Guia-ChatGPT-ES.pdf          passo a passo do GPT + método.
  modelo-voz-editor-viral.zip  só se o Claude do app disser que falta o modelo de voz (é grande: deixe como
                               "arquivo extra"/opcional na Hotmart).
  Na Hotmart, coloque também o LINK do seu GPT em espanhol (passo abaixo) como primeira aula/arquivo.

PASTA 2-CREAR-EL-GPT (só você usa, 1 vez)
  COMO-CRIAR-O-GPT.txt (em português, para você) + instrucciones-del-gpt.txt + ARCHIVOS-PARA-SUBIR/.
  Se você JÁ criou o GPT em espanhol: abra o GPT > Editar > cole as instruções novas por cima e troque o
  editor_viral.py antigo pelo novo de ARCHIVOS-PARA-SUBIR (as instruções e o motor mudaram hoje: estilo,
  storyboard e a legenda que não sobrepõe mais a palavra gigante).

TESTE ANTES DE ABRIR (15 min): um vídeo em espanhol no GPT pelo celular e outro no Claude no computador com
"prepara todo" e "edita mi video". Me mande print se algo travar.
"""

COMO_CRIAR = """CRIAR (OU ATUALIZAR) O GPT "EDITOR VIRAL" EM ESPANHOL

1. ChatGPT no computador: Explorar GPTs > Criar > aba "Configurar".
2. Nome: Editor Viral
   Descrição: Edita tus videos con subtítulos animados, cortes, zoom, voz limpia y música. Manda el video y escribe: edita este video.
3. Instruções: cole TODO o conteúdo de instrucciones-del-gpt.txt.
4. Iniciadores de conversa:
   - Edita este video
   - Aprende mi estilo
   - Hazme un guion de 30 segundos para mi nicho
   - Dame 10 ganchos para mi producto
5. Conhecimento: suba TODOS os arquivos da pasta ARCHIVOS-PARA-SUBIR ({n} arquivos). O idioma.txt é o que faz o
   editor trabalhar em espanhol. Se um .zip for recusado, suba os arquivos de dentro dele (descompacte e suba).
6. Recursos: marque "Interpretador de código e análise de dados". Pode desmarcar navegação e imagem.
7. Salvar > "Qualquer pessoa com o link" (não publique na loja).
8. Copie o link e coloque na Hotmart.
"""


def zip_kit(destino: Path) -> Path:
    def texto(z, nome, conteudo):
        info = zipfile.ZipInfo(nome, dt.datetime.now().timetuple()[:6])
        info.external_attr = 0o644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, conteudo)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for pasta, txt in PASTAS.items():
            texto(z, f"{RAIZ}/{pasta}/LEEME.txt", txt)
        texto(z, f"{RAIZ}/2-REFERENCIAS/enlaces.txt", "")
        z.write(ES / "CLAUDE-viral.md", f"{RAIZ}/CLAUDE.md")
        z.write(ES / "PROMPTS.txt", f"{RAIZ}/PROMPTS.txt")
        z.write(KIT / "settings.json", f"{RAIZ}/.claude/settings.json")
        for src, nome in pev.skill_arquivos(prefixo=f"{RAIZ}/.claude/skills/editor-viral/", idioma="es"):
            z.write(src, nome)
    return destino


def pdf(md: Path, nome: str, tmp: Path) -> Path:
    d = tmp / nome
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(md, d / "guia-inicio.md")
    return pev.guia_pdf(d, SK / "es" / "references" / "metodo.md", nome + ".pdf")


def main() -> None:
    data = dt.date.today().isoformat()
    base = REPO / "dist" / f"Editor-Viral-Espanol-{data}"
    if not base.exists():
        sys.exit("Rode antes: python3 tools/pacote_editor_viral.py --idioma es")
    out = REPO / "dist" / f"HOTMART-Editor-Viral-ES-{data}"
    if out.exists():
        shutil.rmtree(out)
    cli = out / "1-SUBIR-EN-HOTMART"
    cli.mkdir(parents=True)
    tmp = out / ".tmp"
    zip_kit(cli / "Edicion-de-Videos-ES.zip")
    shutil.copy2(base / "1-PARA-EL-CLIENTE" / "editor-viral-claude-es.zip", cli)
    shutil.copy2(base / "1-PARA-EL-CLIENTE" / "modelo-voz-editor-viral.zip", cli)
    shutil.copy2(pdf(ES / "Guia-Claude-ES.md", "Guia-Claude-ES", tmp), cli)
    shutil.copy2(pdf(ES / "Guia-ChatGPT-ES.md", "Guia-ChatGPT-ES", tmp), cli)
    gpt = out / "2-CREAR-EL-GPT"
    shutil.copytree(base / "2-TU-CREAS-EL-GPT" / "ARCHIVOS-PARA-SUBIR", gpt / "ARCHIVOS-PARA-SUBIR")
    shutil.copy2(base / "2-TU-CREAS-EL-GPT" / "instrucciones-del-gpt.txt", gpt)
    (gpt / "COMO-CRIAR-O-GPT.txt").write_text(COMO_CRIAR.format(n=len(list((gpt / "ARCHIVOS-PARA-SUBIR").iterdir()))),
                                              encoding="utf-8")
    (out / "LEIA-ME.txt").write_text(LEIA_ME.format(data=data), encoding="utf-8")
    shutil.rmtree(tmp)
    for p in sorted(out.rglob("*")):
        if p.is_file():
            print(f"{p.stat().st_size / 1e6:8.1f} MB  {p.relative_to(out)}")
    print(f"OK: {out}")


if __name__ == "__main__":
    main()
