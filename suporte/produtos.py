"""Produtos que o atendente conhece: nome, base de conhecimento e regras próprias.

Usado pelo bot do WhatsApp (bot.py) e pelo pacote "colar na conversa" (tools/pacote_atendente.py).
"""

from __future__ import annotations

from pathlib import Path

AQUI = Path(__file__).resolve().parent

PRODUTOS = {
    "editor": {
        "nome": "Editor Viral: Corte Viral, Pacote Motion 3D e Editor no WhatsApp",
        "base": "base-conhecimento.md",
        "regras": (
            "Regras deste produto:\n"
            "- Problema de instalação ou erro: se o cliente ainda não disse, pergunte primeiro o sistema (Mac, "
            "Windows ou Linux) e peça um print ou o texto do erro (de preferência a saída de "
            "`python3 scripts/setup.py`).\n"
            "- Se ele tentou colar o zip no ChatGPT ou na conversa normal do Claude, explique com gentileza por que "
            "não funciona e mostre o caminho certo (Claude Code, ou o Editor no WhatsApp para quem não quer "
            "instalar nada)."),
    },
    "vsl": {
        "nome": "VSL & Oferta",
        "base": "base-conhecimento-vsl.md",
        "regras": (
            "Regras deste produto:\n"
            "- Primeiro descubra onde o cliente usa o pacote (Claude.ai, ChatGPT ou Claude Code); os passos mudam.\n"
            "- Você é o suporte, não o estrategista: não escreva oferta, roteiro nem página aqui. Mostre como "
            "fazer isso no Projeto/GPT dele (ou como retomar com a FICHA DA OFERTA).\n"
            "- Promessa de ganho, cura, depoimento ou garantia jurídica: não opine sobre o caso; explique a regra "
            "da base e, se ele insistir, [ENCAMINHAR_HUMANO]."),
    },
}


def montar_prompt(produto: str) -> str:
    """Prompt do atendente com nome e regras do produto preenchidos (sem a base de conhecimento)."""
    if produto not in PRODUTOS:
        raise SystemExit(f"Produto inválido: {produto} (opções: {', '.join(PRODUTOS)})")
    p = PRODUTOS[produto]
    return ((AQUI / "prompt-sistema.md").read_text(encoding="utf-8")
            .replace("{{PRODUTO}}", p["nome"]).replace("{{REGRAS_PRODUTO}}", p["regras"]))
