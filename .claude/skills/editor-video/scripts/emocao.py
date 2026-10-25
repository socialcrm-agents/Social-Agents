"""Emoção, cor e emoji de uma palavra/frase falada (léxico em português; nada inventado: só olha o que foi dito).

Usado pela legenda viva (palavra-chave gigante com emoji e cor por emoção) e pelo seletor de efeitos.
"""

from __future__ import annotations

from common import norm

# emoção -> cor do destaque (paleta legível sobre vídeo: contraste alto com sombra) e sfx de impacto
EMOCOES = {
    "alegria":    {"cor": "#FACC15", "cor2": "#FB923C", "sfx": "pop"},
    "dinheiro":   {"cor": "#22C55E", "cor2": "#A3E635", "sfx": "venda"},
    "urgencia":   {"cor": "#F43F5E", "cor2": "#FB7185", "sfx": "boom"},
    "alerta":     {"cor": "#F97316", "cor2": "#FACC15", "sfx": "glitch"},
    "confianca":  {"cor": "#60A5FA", "cor2": "#A5B4FC", "sfx": "ding"},
    "curiosidade": {"cor": "#B794FF", "cor2": "#F0ABFC", "sfx": "whoosh"},
    "desejo":     {"cor": "#F472B6", "cor2": "#FDA4AF", "sfx": "pop"},
    "neutro":     {"cor": "#FFFFFF", "cor2": "#E5E7EB", "sfx": "pop"},
}

# palavra normalizada (sem acento) -> (emoção, emoji). Prefixos com "*" casam o começo da palavra.
LEXICO = {
    "dinheiro": ("dinheiro", "💰"), "reais": ("dinheiro", "💸"), "real": ("dinheiro", "💸"), "lucro": ("dinheiro", "📈"),
    "vender": ("dinheiro", "🤑"), "venda*": ("dinheiro", "🤑"), "vendi*": ("dinheiro", "🤑"), "faturar": ("dinheiro", "💰"),
    "fatur*": ("dinheiro", "💰"), "promocao": ("dinheiro", "🏷️"), "desconto": ("dinheiro", "🏷️"), "barato": ("dinheiro", "🏷️"),
    "gratis": ("alegria", "🎁"), "presente": ("alegria", "🎁"), "bonus": ("alegria", "🎁"),
    "rapido": ("urgencia", "⚡"), "agora": ("urgencia", "⏰"), "hoje": ("urgencia", "⏰"), "ultim*": ("urgencia", "⏳"),
    "corre": ("urgencia", "🏃"), "acaba*": ("urgencia", "⏳"), "urgente": ("urgencia", "🚨"),
    "cuidado": ("alerta", "⚠️"), "erro": ("alerta", "❌"), "errado": ("alerta", "❌"), "nunca": ("alerta", "🚫"),
    "pare": ("alerta", "✋"), "problema": ("alerta", "⚠️"), "perig*": ("alerta", "⚠️"), "golpe": ("alerta", "🚨"),
    "segredo": ("curiosidade", "🤫"), "descobri": ("curiosidade", "💡"), "ideia": ("curiosidade", "💡"),
    "olha": ("curiosidade", "👀"), "olhadinha": ("curiosidade", "👀"), "veja": ("curiosidade", "👀"),
    "imagina": ("curiosidade", "💭"), "sabia": ("curiosidade", "🤔"),
    "metodo": ("confianca", "🧠"), "garantia": ("confianca", "🛡️"), "seguro": ("confianca", "🛡️"),
    "comprovado": ("confianca", "✅"), "resultado*": ("confianca", "📈"), "funciona": ("confianca", "✅"),
    "certo": ("confianca", "✅"), "facil": ("confianca", "👌"), "simples": ("confianca", "👌"),
    "gostoso": ("desejo", "😋"), "delicia": ("desejo", "😋"), "lindo": ("desejo", "😍"), "amo": ("desejo", "❤️"),
    "amor": ("desejo", "❤️"), "perfeito": ("desejo", "🤩"), "incrivel": ("alegria", "🤩"), "top": ("alegria", "🔥"),
    "fogo": ("alegria", "🔥"), "viral": ("alegria", "🚀"), "crescer": ("alegria", "🚀"), "sucesso": ("alegria", "🏆"),
    "feliz": ("alegria", "😄"), "chiclete": ("desejo", "🍬"), "doce": ("desejo", "🍬"), "cafe": ("desejo", "☕"),
    "sabor*": ("desejo", "😋"), "menta": ("desejo", "🌿"), "celular": ("neutro", "📱"), "video": ("neutro", "🎬"),
    "tempo": ("urgencia", "⏰"), "dias": ("urgencia", "📅"), "minutos": ("urgencia", "⏱️"),
}


def _busca(n: str):
    if n in LEXICO:
        return LEXICO[n]
    for k, v in LEXICO.items():
        if k.endswith("*") and n.startswith(k[:-1]) and len(n) >= len(k) - 1:
            return v
    return None


def da_palavra(palavra: str) -> tuple[str, str | None]:
    """(emoção, emoji ou None) de uma palavra."""
    n = norm(palavra)
    if n.isdigit() or palavra.strip().startswith("R$"):
        return "dinheiro" if "R$" in palavra else "curiosidade", None
    r = _busca(n)
    return (r[0], r[1]) if r else ("neutro", None)


def da_frase(palavras: list[str]) -> str:
    """Emoção dominante da frase (contagem do léxico; pergunta puxa curiosidade)."""
    conta: dict[str, int] = {}
    for p in palavras:
        e, _ = da_palavra(p)
        if e != "neutro":
            conta[e] = conta.get(e, 0) + 1
    if not conta and palavras and palavras[-1].rstrip().endswith("?"):
        return "curiosidade"
    return max(conta, key=conta.get) if conta else "neutro"


def cor(emocao: str) -> dict:
    return EMOCOES.get(emocao, EMOCOES["neutro"])
