#!/usr/bin/env python3
"""Gera a IA de suporte de um produto pronta para colar numa conversa: dist/Atendente-<produto>-AAAA-MM-DD.zip

  python3 tools/pacote_atendente.py vsl       -> atendente do VSL & Oferta
  python3 tools/pacote_atendente.py editor    -> atendente do Editor Viral

O zip leva INSTRUCOES.md (o prompt do atendente, com nome, regras e contato humano preenchidos),
BASE-DE-CONHECIMENTO.md e LEIA-ME.txt com o passo a passo para montar no ChatGPT (GPT com link público),
num Projeto do Claude ou no WhatsApp (suporte/bot.py, precisa de servidor).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "suporte"))
from produtos import PRODUTOS, montar_prompt  # noqa: E402

CONTATO = {"vsl": REPO / ".claude/skills/vsl-oferta/config.json"}

LEIA_ME = """IA DE SUPORTE — {nome}

Dentro deste zip:
- INSTRUCOES.md          -> o "cérebro" do atendente (como ele fala e o que pode/não pode)
- BASE-DE-CONHECIMENTO.md -> tudo que ele sabe do produto

OPÇÃO 1 — ChatGPT, com link para o cliente (recomendado: não precisa de servidor)
1. chatgpt.com > Explorar GPTs > Criar > aba Configurar.
2. Nome: "Suporte {nome}". Instruções: cole TODO o conteúdo de INSTRUCOES.md.
3. Conhecimento: envie BASE-DE-CONHECIMENTO.md.
4. Desmarque "Geração de imagem"; deixe "Pesquisa na web" desligada (ele deve responder só pela base).
5. Criar > Compartilhar: "Qualquer pessoa com o link". Coloque esse link na área de membros e no e-mail de
   boas-vindas. (O cliente usa com a conta ChatGPT dele, até a gratuita.)

OPÇÃO 2 — Projeto do Claude (para você e sua equipe responderem com ajuda da IA)
1. claude.ai > Projetos > Criar projeto: "Suporte {nome}".
2. "Instruções do projeto": cole INSTRUCOES.md.
3. "Conhecimento do projeto": envie BASE-DE-CONHECIMENTO.md.
4. Cole a pergunta do cliente numa conversa do projeto; a resposta sai pronta para mandar no WhatsApp.
   (Projetos do Claude não abrem para quem está fora da sua conta/equipe, por isso não servem de link público.)

OPÇÃO 3 — Atendente automático no WhatsApp (precisa de servidor e chave da API)
Use suporte/bot.py do repositório com ATENDENTE_PRODUTO={produto} (veja suporte/README.md).

ATUALIZOU O PRODUTO? Gere este zip de novo e troque os dois arquivos no GPT/Projeto.
Quando a IA não souber, ela manda o cliente para: {contato}
"""


def main() -> None:
    produto = sys.argv[1] if len(sys.argv) > 1 else "vsl"
    if produto not in PRODUTOS:
        sys.exit(f"Uso: pacote_atendente.py <{'|'.join(PRODUTOS)}>")
    p = PRODUTOS[produto]
    contato = "o suporte humano"
    if produto in CONTATO and CONTATO[produto].exists():
        contato = json.loads(CONTATO[produto].read_text(encoding="utf-8")).get("suporte") or contato
    if "[preencher" in contato:
        print(f"AVISO: contato do suporte humano não preenchido ({contato}). Edite o config.json do produto.")
    prompt = montar_prompt(produto).replace("pelo WhatsApp", "por mensagem (chat ou WhatsApp)")
    prompt = prompt.replace("[ENCAMINHAR_HUMANO]", f"[ENCAMINHAR_HUMANO] e diga para o cliente falar com: {contato}")
    prompt += ("\n\nA BASE DE CONHECIMENTO é o arquivo BASE-DE-CONHECIMENTO.md anexado. Consulte-o antes de cada "
               "resposta e não use conhecimento de fora dele sobre o produto.\n")
    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    nome_zip = p["nome"].split(":")[0].strip().replace(" & ", "-").replace(" ", "-")
    out = dist / f"Atendente-{nome_zip}-{dt.date.today().isoformat()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("INSTRUCOES.md", prompt)
        z.write(REPO / "suporte" / p["base"], "BASE-DE-CONHECIMENTO.md")
        z.writestr("LEIA-ME.txt", LEIA_ME.format(nome=p["nome"].split(":")[0], produto=produto, contato=contato)
                   .replace("\n", "\r\n").encode("utf-8-sig"))
    print(f"OK: {out} (instruções com {len(prompt)} caracteres; limite do GPT: 8000)")


if __name__ == "__main__":
    main()
