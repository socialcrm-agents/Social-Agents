#!/usr/bin/env python3
"""Atendente "tira-dúvidas" do Editor Viral (Claude API).

  python3 bot.py                 conversa no terminal (sair: Ctrl+C ou "sair")

Uso pelo servidor do WhatsApp:
  from bot import responder
  texto = responder(historico, "não aparece READY")   # historico: lista de {"role", "content"}; é atualizada

Variáveis: ANTHROPIC_API_KEY (ou `ant auth login`), ATENDENTE_MODELO (padrão claude-opus-5-5).
O system (prompt + base de conhecimento) é fixo e vai em cache: depois da 1ª pergunta, ele custa ~10% do preço.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import anthropic

AQUI = Path(__file__).resolve().parent
MODELO = os.environ.get("ATENDENTE_MODELO", "claude-opus-5-5")
MAX_TURNOS = 20          # mensagens guardadas por cliente (as mais antigas saem)
ENCAMINHAR = "[ENCAMINHAR_HUMANO]"

_client: anthropic.Anthropic | None = None


def system_blocks() -> list[dict]:
    """Prompt do atendente + base de conhecimento: prefixo estável, sempre igual, com cache."""
    prompt = (AQUI / "prompt-sistema.md").read_text(encoding="utf-8")
    base = (AQUI / "base-conhecimento.md").read_text(encoding="utf-8")
    return [{"type": "text", "text": f"{prompt}\n\n=== BASE DE CONHECIMENTO ===\n\n{base}",
             "cache_control": {"type": "ephemeral"}}]


def montar_requisicao(historico: list[dict], pergunta: str) -> dict:
    return {
        "model": MODELO,
        "max_tokens": 2000,
        "system": system_blocks(),
        "output_config": {"effort": "low"},
        "messages": [*historico[-MAX_TURNOS:], {"role": "user", "content": pergunta}],
    }


def responder(historico: list[dict], pergunta: str) -> str:
    """Responde e acrescenta pergunta + resposta ao histórico. Texto com ENCAMINHAR = passar para um humano."""
    global _client
    _client = _client or anthropic.Anthropic()
    try:
        resp = _client.messages.create(**montar_requisicao(historico, pergunta))
    except anthropic.AuthenticationError:
        return "Estou sem acesso ao atendimento automático agora. Vou chamar alguém da equipe. " + ENCAMINHAR
    except anthropic.RateLimitError:
        return "Muita gente falando comigo agora 😅 Me manda de novo daqui a um minutinho?"
    except anthropic.APIConnectionError:
        return "Tive um problema de conexão. Pode repetir a mensagem?"
    except anthropic.APIStatusError as e:
        print(f"[bot] erro da API {e.status_code}: {e.message}", file=sys.stderr)
        return "Deu um erro do meu lado. Vou chamar alguém da equipe. " + ENCAMINHAR
    if resp.stop_reason == "refusal":
        texto = "Esse assunto eu não consigo tratar por aqui. Vou passar para alguém da equipe. " + ENCAMINHAR
    else:
        texto = "".join(b.text for b in resp.content if b.type == "text").strip() or ENCAMINHAR
    historico.append({"role": "user", "content": pergunta})
    historico.append({"role": "assistant", "content": texto})
    del historico[:-MAX_TURNOS]
    u = resp.usage
    print(f"[bot] tokens: entrada {u.input_tokens}, cache lido {u.cache_read_input_tokens or 0}, "
          f"cache gravado {u.cache_creation_input_tokens or 0}, saída {u.output_tokens}", file=sys.stderr)
    return texto


def main() -> None:
    historico: list[dict] = []
    print(f"Atendente Editor Viral ({MODELO}). Digite sua dúvida ('sair' para encerrar).")
    while True:
        try:
            pergunta = input("\nvocê> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in {"sair", "exit", "quit"}:
            break
        if pergunta:
            print("\natendente> " + responder(historico, pergunta))


if __name__ == "__main__":
    main()
