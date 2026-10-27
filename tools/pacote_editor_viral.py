#!/usr/bin/env python3
"""Gera o material de lançamento do Editor Viral (versão leve que roda dentro do Claude e do ChatGPT).

  python3 tools/pacote_editor_viral.py        -> dist/Editor-Viral-Lancamento-AAAA-MM-DD/

Saída:
  1-PARA-O-CLIENTE/editor-viral-claude.zip      a skill (o cliente sobe no Claude)
  1-PARA-O-CLIENTE/modelo-voz-editor-viral.zip  plano B sem internet (o cliente só usa se o Claude pedir)
  1-PARA-O-CLIENTE/COMO-USAR-NO-CLAUDE.pdf/.txt e COMO-USAR-NO-CHATGPT.txt
  2-VOCE-CRIA-O-GPT/                            instruções + arquivos para você criar o GPT uma vez
  3-PAGINA-DE-DOWNLOAD/textos-da-pagina.md      textos prontos para a página de entrega
  LEIA-ME-PRIMEIRO.txt                          o teste de 15 minutos antes de vender
Rodas Python e modelo de voz são baixados uma vez (PyPI e GitHub) e ficam em ~/.cache/editor-viral-pacote.
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SK = RAIZ / ".claude" / "skills" / "editor-viral"
CACHE = Path.home() / ".cache" / "editor-viral-pacote"
MODELO = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
VERSAO_SHERPA = "2.0.1"
PYS = ("3.10", "3.11", "3.12", "3.13")


def baixar_rodas() -> list[Path]:
    d = CACHE / "rodas"
    d.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, "-m", "pip", "download", "--no-deps", "-q", "-d", str(d), "--only-binary=:all:",
            "--platform", "manylinux2014_x86_64"]
    if not list(d.glob("imageio_ffmpeg-*.whl")):
        subprocess.run(base + ["--python-version", "3.11", "imageio-ffmpeg==0.6.0"], check=True)
    if not list(d.glob("sherpa_onnx_core-*.whl")):
        subprocess.run(base + ["--python-version", "3.11", f"sherpa-onnx-core=={VERSAO_SHERPA}"], check=True)
    for v in PYS:
        tag = "cp" + v.replace(".", "")
        if not list(d.glob(f"sherpa_onnx-{VERSAO_SHERPA}-{tag}-*.whl")):
            subprocess.run(base + ["--python-version", v, f"sherpa-onnx=={VERSAO_SHERPA}"], check=True)
    return sorted(d.glob("*.whl"))


def baixar_modelo() -> list[Path]:
    d = CACHE / "modelo"
    d.mkdir(parents=True, exist_ok=True)
    alvo = [d / "base-encoder.int8.onnx", d / "base-decoder.int8.onnx", d / "base-tokens.txt", d / "silero_vad.onnx"]
    if not all(p.exists() for p in alvo[:3]):
        tgz = d / "w.tar.bz2"
        urllib.request.urlretrieve(MODELO + "sherpa-onnx-whisper-base.tar.bz2", tgz)
        with tarfile.open(tgz) as t:
            for m in t.getmembers():
                if Path(m.name).name in {p.name for p in alvo}:
                    m.name = Path(m.name).name
                    t.extract(m, d)
        tgz.unlink()
    if not alvo[3].exists():
        urllib.request.urlretrieve(MODELO + "silero_vad.onnx", alvo[3])
    return alvo


def zipar(destino: Path, arquivos: list[tuple[Path, str]], comprimir: bool = True) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED if comprimir else zipfile.ZIP_STORED) as z:
        for src, nome in arquivos:
            z.write(src, nome)
    return destino


def skill_arquivos(prefixo: str = "editor-viral/") -> list[tuple[Path, str]]:
    out = []
    for p in sorted(SK.rglob("*")):
        rel = p.relative_to(SK).as_posix()
        if p.is_file() and "__pycache__" not in rel and not rel.startswith("chatgpt/"):
            out.append((p, prefixo + rel))
    return out


COMO_CLAUDE = """EDITOR VIRAL NO CLAUDE - como instalar (1 vez) e usar

PRECISA: conta no Claude com plano pago (Pro ou superior). A instalação é feita 1 vez e vale no computador
e no celular (é a mesma conta).

INSTALAR (5 minutos - pelo computador ou pelo navegador do celular em claude.ai):
1. Baixe o arquivo editor-viral-claude.zip (NÃO descompacte).
2. Entre em claude.ai > clique no seu nome > Configurações > Recursos (Capabilities).
3. Ligue "Execução de código e criação de arquivos" (Code execution and file creation).
4. Em "Skills", clique em "Enviar skill" (Upload skill) e escolha o editor-viral-claude.zip.
5. Pronto. Confira se "editor-viral" aparece ligado na lista.

USAR (computador ou app do celular):
1. Abra uma conversa nova.
2. Toque no + (anexar) e escolha o vídeo da galeria (até ~1 minuto, gravado em 1080p).
3. Escreva: "edita esse vídeo".
4. Em 2-4 minutos o Claude devolve o vídeo pronto para baixar (+ legenda .srt).
5. Peça ajustes do seu jeito: "legenda maior", "tira o começo", "sem música", "faz 3 versões de gancho".

OUTROS PEDIDOS: "me faz um roteiro de 30 segundos para [seu nicho]", "me dá 10 ganchos", "como gravar no celular".

SE O CLAUDE DISSER QUE FALTA O MODELO DE VOZ: anexe o arquivo modelo-voz-editor-viral.zip na conversa
(pelo computador; é grande) e peça "configura o editor".
"""

COMO_GPT = """EDITOR VIRAL NO CHATGPT - como usar

PRECISA: conta no ChatGPT (o plano pago dá mais vídeos por dia; no gratuito o limite de uso é menor).

USAR (computador ou app do celular):
1. Abra o link do Editor Viral que veio no seu acesso: {link_gpt}
2. Toque no + (anexar) e escolha o vídeo da galeria (até ~1 minuto, gravado em 1080p).
3. Escreva: "edita esse vídeo".
4. Em 2-4 minutos ele devolve o link para baixar o vídeo pronto (+ legenda .srt).
5. Peça ajustes do seu jeito: "legenda maior", "tira o começo", "sem música", "faz 3 versões de gancho".

DICA: fixe o Editor Viral na barra lateral do ChatGPT para achar rápido.
"""

COMO_CRIAR_GPT = """CRIAR O GPT "EDITOR VIRAL" (você faz 1 vez; os clientes só usam o link)

1. No ChatGPT (computador): Explorar GPTs > Criar > aba "Configurar".
2. Nome: Editor Viral. Descrição: "Edita seus vídeos com legenda animada, cortes, zoom, voz limpa e trilha.
   Mande o vídeo e escreva: edita esse vídeo."
3. Instruções: cole TODO o conteúdo de instrucoes-do-gpt.txt.
4. Iniciadores de conversa (conversation starters):
   - Edita esse vídeo (anexe o vídeo)
   - Me faz um roteiro de 30 segundos para o meu nicho
   - Me dá 10 ganchos para o meu produto
   - Como eu gravo um vídeo bom no celular?
5. Conhecimento: envie TODOS os arquivos da pasta ARQUIVOS-PARA-SUBIR (são {n} arquivos).
   Se algum .zip for recusado, envie os arquivos de dentro dele no lugar (pasta SE-O-ZIP-FOR-RECUSADO).
6. Recursos: marque "Interpretador de código e análise de dados" (Code Interpreter). Pode desmarcar
   Navegação e Geração de imagem.
7. Foto: o logo do Editor Viral.
8. Salvar > "Qualquer pessoa com o link" (não "Público na loja", para não vazar para quem não comprou).
9. Copie o link e coloque na área de membros e no COMO-USAR-NO-CHATGPT.txt.

TESTE ANTES DE VENDER (5 minutos): abra o GPT pelo celular, anexe um vídeo seu de 30 s e escreva
"edita esse vídeo". Tem que voltar o vídeo com legenda, corte e zoom.
"""

LEIA_ME = """EDITOR VIRAL - MATERIAL DE LANÇAMENTO ({data})

O QUE É: a versão leve do editor, que roda DENTRO do Claude e do ChatGPT do cliente. Corta pausas e erros,
põe legenda animada com palavra em destaque e emoji, zoom no momento certo, voz limpa, trilha sem direitos,
gancho forte, 3 versões de gancho e formatos 9:16/4:5/1:1. Também traz o método (roteiro, 30 ganchos,
gravação no celular, checklist). Custo por vídeo para você: zero (roda na conta do cliente).

PASTAS
1-PARA-O-CLIENTE       o que vai na página de download (zip do Claude + guias)
2-VOCE-CRIA-O-GPT      você cria o GPT 1 vez e entrega o link aos clientes
3-PAGINA-DE-DOWNLOAD   textos prontos para a página/área de membros

TESTE OBRIGATÓRIO ANTES DE VENDER (15 minutos) - eu não consigo testar dentro do Claude e do ChatGPT daqui:
[ ] Claude: instale o editor-viral-claude.zip na sua conta, abra o APP DO CELULAR, anexe um vídeo de 30 s
    e escreva "edita esse vídeo". Volta o vídeo editado?
[ ] Claude: se ele disser que falta o modelo de voz, anote (a internet da caixinha bloqueou o download;
    aí o cliente usa o modelo-voz-editor-viral.zip, e eu ajusto a página).
[ ] ChatGPT: crie o GPT (2-VOCE-CRIA-O-GPT/COMO-CRIAR-O-GPT.txt) e faça o mesmo teste pelo celular.
[ ] Teste um vídeo de 1 minuto em cada um para saber o limite real e escrever na página.
Me mande o resultado (print) e eu ajusto o que precisar antes de abrir as vendas.
"""

PAGINA = """# Página de download — Editor Viral

## Título
**Seu acesso ao Editor Viral chegou.** Escolha onde você quer editar:

## Bloco 1 — Claude (recomendado: melhor qualidade)
- Botão: **Baixar o Editor Viral para Claude** → `editor-viral-claude.zip`
- Botão secundário: **Como instalar (5 min)** → `COMO-USAR-NO-CLAUDE.txt` (ou o vídeo de instalação)
- Nota: precisa de conta Claude Pro. Instala 1 vez e funciona no computador e no celular.

## Bloco 2 — ChatGPT
- Botão: **Abrir o Editor Viral no ChatGPT** → [link do GPT]
- Nota: é só abrir o link, anexar o vídeo e escrever "edita esse vídeo". Fixe na barra lateral.

## Bloco 3 — Como usar (3 passos)
1. Grave seu vídeo no celular (em pé, 1080p, de 20 a 60 segundos).
2. Anexe na conversa e escreva **"edita esse vídeo"**.
3. Baixe o vídeo pronto. Quer mudar algo? Peça do seu jeito: "legenda maior", "tira o começo", "faz 3 versões".

## Bloco 4 — O que o Editor Viral faz
- Corta pausas, gaguejos e frases repetidas
- Legenda animada palavra por palavra, com a palavra forte gigante e emoji
- Zoom no momento certo
- Voz limpa de estúdio (tira o ruído do ambiente)
- Trilha sem direitos autorais que abaixa quando você fala
- Gancho forte nos 3 primeiros segundos + 3 versões para testar no anúncio
- Formatos 9:16, 4:5 e 1:1 e legenda .srt
- Método: roteiro de 30 s, 30 ganchos prontos, guia de gravação no celular e checklist do criativo que vende

## Bloco 5 — Perguntas frequentes
- **Funciona no celular?** Sim, no app do Claude e do ChatGPT. A instalação no Claude é feita 1 vez
  (pelo computador ou navegador) e depois vale no app.
- **Qual o tamanho máximo do vídeo?** Até ~1 minuto por vez (vídeo longo: mande em partes).
- **Preciso pagar por vídeo?** Não. Roda na sua conta do Claude ou do ChatGPT.
- **Precisa instalar programa?** Não. Tudo roda dentro do Claude/ChatGPT.
- **E efeitos 3D, produto voando, troca de fundo?** Fazem parte do **Editor Viral PRO**. [botão do upsell]
- **Deu erro?** Abra uma conversa nova e mande de novo. Persistindo: [suporte].

## Bloco 6 — Upsell
**Editor Viral PRO**: efeitos 3D, produto voando na mão, palavra atrás de você, troca de fundo, 2.5D e
motion de nível agência. [botão]
"""


def guia_pdf(lanc: Path) -> Path:
    """Guia do cliente (início + método) em PDF, via Chromium do Playwright."""
    import markdown
    md = (lanc / "guia-inicio.md").read_text(encoding="utf-8") + "\n\n<div style='page-break-before:always'></div>\n\n" \
        + (SK / "references" / "metodo.md").read_text(encoding="utf-8")
    css = ("@page{size:A4;margin:16mm}body{font-family:Poppins,Arial,sans-serif;color:#1a1a1a;font-size:11.5pt;"
           "line-height:1.5}h1{font-size:26pt;border-bottom:4px solid #FFD400;padding-bottom:6px}h2{margin-top:22px;"
           "border-left:6px solid #FFD400;padding-left:10px}table{border-collapse:collapse;width:100%;font-size:10pt}"
           "th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}th{background:#FFF6CC}"
           "code{background:#f3f3f3;padding:1px 4px;border-radius:4px}blockquote{border-left:4px solid #ddd;"
           "margin:0;padding-left:12px;color:#444}")
    html = CACHE / "guia.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
                    f"{markdown.markdown(md, extensions=['tables'])}</body></html>", encoding="utf-8")
    pdf = lanc / "Guia-Editor-Viral.pdf"
    js = CACHE / "pdf.cjs"
    js.write_text("const{chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
                  "const p=await b.newPage();await p.goto('file://'+process.argv[2]);await p.pdf({path:process.argv[3],"
                  "format:'A4',printBackground:true});await b.close();})();")
    raiz_npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js), str(html), str(pdf)], check=True, env={**__import__("os").environ,
                                                                          "NODE_PATH": raiz_npm})
    return pdf


def main() -> None:
    data = datetime.date.today().isoformat()
    out = RAIZ / "dist" / f"Editor-Viral-Lancamento-{data}"
    if out.exists():
        shutil.rmtree(out)
    rodas = baixar_rodas()
    modelo = baixar_modelo()
    cli = out / "1-PARA-O-CLIENTE"
    zipar(cli / "editor-viral-claude.zip", skill_arquivos())
    zipar(cli / "modelo-voz-editor-viral.zip", [(p, p.name) for p in modelo], comprimir=False)
    (cli / "COMO-USAR-NO-CLAUDE.txt").write_text(COMO_CLAUDE, encoding="utf-8")
    (cli / "COMO-USAR-NO-CHATGPT.txt").write_text(COMO_GPT.format(link_gpt="[cole aqui o link do GPT]"),
                                                  encoding="utf-8")
    gpt = out / "2-VOCE-CRIA-O-GPT"
    sub = gpt / "ARQUIVOS-PARA-SUBIR"
    sub.mkdir(parents=True)
    for nome in ("editor_viral.py", "dsp.py", "trilha.py"):
        shutil.copy2(SK / "scripts" / nome, sub / nome)
    shutil.copy2(SK / "references" / "metodo.md", sub / "metodo.md")
    zipar(sub / "recursos-editor-viral.zip", [(p, p.relative_to(SK / "assets").as_posix())
                                             for p in sorted((SK / "assets").rglob("*")) if p.is_file()])
    zipar(sub / "programas-editor-viral.zip", [(p, p.name) for p in rodas
                                               if not p.name.startswith("vosk")], comprimir=False)
    shutil.copy2(cli / "modelo-voz-editor-viral.zip", sub / "modelo-voz-editor-viral.zip")
    reserva = gpt / "SE-O-ZIP-FOR-RECUSADO"
    for z in sub.glob("*.zip"):
        with zipfile.ZipFile(z) as zz:
            zz.extractall(reserva / z.stem)
    shutil.copy2(SK / "chatgpt" / "instrucoes-do-gpt.txt", gpt / "instrucoes-do-gpt.txt")
    (gpt / "COMO-CRIAR-O-GPT.txt").write_text(COMO_CRIAR_GPT.format(n=len(list(sub.iterdir()))), encoding="utf-8")
    pag = out / "3-PAGINA-DE-DOWNLOAD"
    pag.mkdir()
    (pag / "textos-da-pagina.md").write_text(PAGINA, encoding="utf-8")
    (out / "LEIA-ME-PRIMEIRO.txt").write_text(LEIA_ME.format(data=data), encoding="utf-8")
    # os 2 arquivos para a conversa que monta a página: o briefing e o zip do que a página disponibiliza
    lanc = SK / "lancamento"
    pdf = guia_pdf(lanc)
    shutil.copy2(lanc / "BRIEFING-PAGINA-DE-ACESSO.md", pag / "BRIEFING-PAGINA-DE-ACESSO.md")
    zipar(pag / "ARQUIVOS-PARA-A-PAGINA.zip",
          [(cli / "editor-viral-claude.zip", "editor-viral-claude.zip"), (pdf, "Guia-Editor-Viral.pdf"),
           (cli / "COMO-USAR-NO-CLAUDE.txt", "COMO-USAR-NO-CLAUDE.txt"),
           (cli / "COMO-USAR-NO-CHATGPT.txt", "COMO-USAR-NO-CHATGPT.txt")])
    for p in sorted(out.rglob("*")):
        if p.is_file() and "SE-O-ZIP" not in str(p):
            print(f"{p.stat().st_size / 1e6:8.1f} MB  {p.relative_to(out)}")
    print(f"OK: {out}")


if __name__ == "__main__":
    main()
