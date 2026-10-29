"""Cérebro do editor: a Claude API lê a transcrição e decide as operações do edit.py.

Saída sempre estruturada (structured outputs), então o worker só converte em argumentos de linha de comando.
Sem ANTHROPIC_API_KEY (ou se a chamada falhar), devolve None e o worker segue com as regras automáticas
da skill. Para correções sem chave, `regras_correcao` cobre os pedidos mais comuns.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

import config

SYSTEM = """Você é o editor de vídeos curtos (Reels/TikTok/Shorts) de um serviço pelo WhatsApp. Recebe a
transcrição de um vídeo bruto, o relatório automático de tomadas e o estilo, e decide as operações de edição.

Regras fixas:
- O primeiro segundo tem que ser o gancho: corte aberturas fracas ("É isso", "Então...", "Oi gente").
- "cuts": trechos EXATOS da transcrição a remover (tomada ruim que sobrou, fora do assunto, repetição).
- "fixes": correções de palavras que o reconhecimento de voz errou, no formato "errado=certo" (nomes, marcas).
- "hook": faixa curta (até 6 palavras, MAIÚSCULAS) TIRADA DO QUE A PESSOA DIZ. Nunca prometa resultado,
  número ou prova que não esteja na fala. Vazio se o estilo for editorial_premium.
- "cta": só se a pessoa pedir algo no fim (ex.: "COMENTA EU QUERO"); senão vazio.
- "motion": no máximo 2 animações, só quando a fala pede (passos -> moldura com itens; números -> infografico;
  frase-chave -> carimbo). Cada item: template, at (trecho falado exato), dur (s), params (JSON em texto).
  Templates permitidos: moldura, infografico, carimbo, checklist, notificacao, botao_cta, anotacao.
- "fx": efeitos de impacto "tipo@palavra" (tremida, clarao, glitch, whip), no máximo 3.
- "resumo": 1 frase em português para o cliente dizendo o que você fez.
Nada de texto sobre o rosto; nada abaixo da zona segura (a skill já cuida do posicionamento).

Em CORREÇÃO, você recebe o pedido do cliente e o estado atual; devolva só as operações que atendem o pedido,
mais estas quando couber: caption_size ("+15%"/"-10%"), zoom (off|suave|forte), style (reels_viral|
anuncio_conversao|editorial_premium), restores (trechos para voltar), behind (on|off), icons (on|off)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "cuts": {"type": "array", "items": {"type": "string"}},
        "restores": {"type": "array", "items": {"type": "string"}},
        "fixes": {"type": "array", "items": {"type": "string"}},
        "hook": {"type": "string"},
        "cta": {"type": "string"},
        "motion": {"type": "array", "items": {
            "type": "object",
            "properties": {"template": {"type": "string"}, "at": {"type": "string"}, "dur": {"type": "number"},
                           "params": {"type": "string"}},
            "required": ["template", "at", "dur", "params"], "additionalProperties": False}},
        "fx": {"type": "array", "items": {"type": "string"}},
        "caption_size": {"type": "string"},
        "zoom": {"type": "string", "enum": ["", "off", "suave", "forte"]},
        "style": {"type": "string", "enum": ["", "reels_viral", "anuncio_conversao", "editorial_premium"]},
        "behind": {"type": "string", "enum": ["", "on", "off"]},
        "icons": {"type": "string", "enum": ["", "on", "off"]},
        "resumo": {"type": "string"},
    },
    "required": ["cuts", "restores", "fixes", "hook", "cta", "motion", "fx", "caption_size", "zoom", "style",
                 "behind", "icons", "resumo"],
    "additionalProperties": False,
}


def _client():
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    return anthropic.Anthropic()


def _call(user: str, job: int | None) -> dict | None:
    client = _client()
    if client is None:
        return None
    import anthropic
    try:
        resp = client.messages.create(
            model=config.MODEL,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": config.EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as exc:
        print(f"   cérebro indisponível ({exc.__class__.__name__}); seguindo com as regras automáticas", flush=True)
        return None
    if job is not None:
        import fila
        custo = fila.registrar_uso(job, config.MODEL, resp.usage)
        print(f"   cérebro: {resp.usage.input_tokens}+{resp.usage.output_tokens} tokens (US$ {custo:.4f})", flush=True)
    if resp.stop_reason != "end_turn":
        print(f"   cérebro parou com {resp.stop_reason}; seguindo com as regras automáticas", flush=True)
        return None
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text) if text else None


def decidir(transcricao: str, takes: str, estilo: str, job: int | None = None) -> dict | None:
    return _call(f"ESTILO: {estilo}\n\nTRANSCRIÇÃO:\n{transcricao}\n\nRELATÓRIO DE TOMADAS:\n{takes}", job)


def corrigir(pedido: str, estado: dict, transcricao: str, job: int | None = None) -> dict | None:
    user = (f"CORREÇÃO pedida pelo cliente: {pedido}\n\nESTADO ATUAL (overrides): "
            f"{json.dumps(estado, ensure_ascii=False, sort_keys=True)}\n\nTRANSCRIÇÃO:\n{transcricao}")
    return _call(user, job) or regras_correcao(pedido)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def regras_correcao(pedido: str) -> dict | None:
    """Pedidos comuns sem IA (fallback). None = não entendi."""
    p = _norm(pedido)
    ops: dict = {}
    if "legenda" in p and any(w in p for w in ("maior", "aumenta", "grande")):
        ops["caption_size"] = "+15%"
    if "legenda" in p and any(w in p for w in ("menor", "diminui", "pequena")):
        ops["caption_size"] = "-12%"
    if "zoom" in p:
        ops["zoom"] = "off" if any(w in p for w in ("sem", "tira", "remove")) else ("forte" if "mais" in p else "suave")
    for key, style in (("viral", "reels_viral"), ("premium", "editorial_premium"), ("anuncio", "anuncio_conversao")):
        if key in p:
            ops["style"] = style
    m = re.search(r"(?:tira|corta|remove)\s+(?:o|a|os|as)?\s*[\"“']?([^\"”']{2,60})[\"”']?", pedido, re.I)
    if m and "zoom" not in p and "legenda" not in p:
        ops["cuts"] = [m.group(1).strip(" .")]
    m = re.search(r"gancho\s*[:=]?\s*[\"“']([^\"”']+)[\"”']", pedido, re.I)
    if m:
        ops["hook"] = m.group(1).strip().upper()
    if "sem palavra atras" in p or "tira a palavra atras" in p:
        ops["behind"] = "off"
    if not ops:
        return None
    ops["resumo"] = "Ajustei: " + ", ".join(ops)
    return ops


def para_argumentos(ops: dict) -> list[str]:
    """Operações estruturadas -> argumentos do edit.py."""
    a: list[str] = []
    for c in ops.get("cuts") or []:
        a += ["--cut", c]
    for r in ops.get("restores") or []:
        a += ["--restore", r]
    for f in ops.get("fixes") or []:
        if "=" in f:
            a += ["--fix", f]
    for key, flag in (("hook", "--hook"), ("cta", "--cta"), ("caption_size", "--caption-size"), ("zoom", "--zoom"),
                      ("style", "--style"), ("behind", "--behind"), ("icons", "--icons")):
        if ops.get(key):
            a += [flag, str(ops[key])]
    for m in ops.get("motion") or []:
        try:
            params = json.loads(m.get("params") or "{}")
        except json.JSONDecodeError:
            params = {}
        a += ["--motion", json.dumps({"template": m["template"], "at": m["at"], "dur": m.get("dur", 3),
                                      "params": params}, ensure_ascii=False)]
    for fx in ops.get("fx") or []:
        if "@" in fx:
            a += ["--fx", fx]
    return a
