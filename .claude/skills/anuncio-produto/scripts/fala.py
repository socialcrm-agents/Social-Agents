"""Texto de tela -> texto falado em pt-BR (números, preços, porcentagens, medidas) para a voz sintética.

A legenda mostra o texto como foi escrito ("R$ 129,90", "30h", "10%"); a voz lê por extenso
("cento e vinte e nove reais e noventa centavos", "trinta horas", "dez por cento").
"""

from __future__ import annotations

import re

UNI = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
       "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
CEM = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
       "oitocentos", "novecentos"]


def _ate_mil(n: int) -> str:
    if n < 20:
        return UNI[n]
    if n < 100:
        d, u = divmod(n, 10)
        return DEZ[d] + (f" e {UNI[u]}" if u else "")
    if n == 100:
        return "cem"
    c, r = divmod(n, 100)
    return CEM[c] + (f" e {_ate_mil(r)}" if r else "")


def extenso(n: int) -> str:
    """Inteiro por extenso (até 999 milhões), no padrão falado do Brasil."""
    if n < 1000:
        return _ate_mil(n)
    if n < 1_000_000:
        m, r = divmod(n, 1000)
        head = "mil" if m == 1 else f"{_ate_mil(m)} mil"
        if not r:
            return head
        return f"{head} e {_ate_mil(r)}" if r < 100 or r % 100 == 0 else f"{head} {_ate_mil(r)}"
    mi, r = divmod(n, 1_000_000)
    head = "um milhão" if mi == 1 else f"{extenso(mi)} milhões"
    return head if not r else f"{head} e {extenso(r)}" if r < 1000 else f"{head} {extenso(r)}"


def _num(s: str) -> tuple[int, int | None]:
    """'1.299,90' -> (1299, 90); '129' -> (129, None)."""
    s = s.strip()
    if "," in s:
        inteiro, dec = s.split(",", 1)
    else:
        inteiro, dec = s, None
    inteiro = int(inteiro.replace(".", "") or 0)
    return inteiro, (int(dec.ljust(2, "0")[:2]) if dec else None)


def _reais(m: re.Match) -> str:
    r, c = _num(m.group(1))
    txt = f"{extenso(r)} {'real' if r == 1 else 'reais'}" if r else ""
    if c:
        txt += (" e " if txt else "") + f"{extenso(c)} {'centavo' if c == 1 else 'centavos'}"
    return txt or "zero reais"


UNIDADES = {"ml": "mililitros", "l": "litros", "g": "gramas", "kg": "quilos", "mg": "miligramas", "cm": "centímetros",
            "mm": "milímetros", "m": "metros", "h": "horas", "min": "minutos", "x": "vezes", "mah": "miliampères",
            "w": "watts", "gb": "gigas", "tb": "terabytes", "km": "quilômetros"}


def falado(texto: str) -> str:
    t = texto
    t = re.sub(r"R\$\s*([\d.]+(?:,\d{1,2})?)", _reais, t)
    t = re.sub(r"(\d+(?:,\d+)?)\s*%", lambda m: f"{_dec(m.group(1))} por cento", t)
    t = re.sub(r"(\d+(?:,\d+)?)\s*(ml|kg|mg|mm|cm|km|min|mah|gb|tb|l|g|m|h|x|w)\b",
               lambda m: f"{_dec(m.group(1))} {UNIDADES[m.group(2).lower()]}", t, flags=re.I)
    t = re.sub(r"\b(\d{1,2})x\b", lambda m: f"{extenso(int(m.group(1)))} vezes", t)
    t = re.sub(r"\d+(?:\.\d{3})*(?:,\d+)?", lambda m: _dec(m.group(0)), t)
    t = t.replace("+", " mais ").replace("&", " e ").replace("/", " por ")
    return re.sub(r"\s+", " ", t).strip()


def _dec(s: str) -> str:
    i, d = _num(s)
    if d is None:
        return extenso(i)
    frac = s.split(",", 1)[1]
    return f"{extenso(i)} vírgula {' '.join(extenso(int(c)) for c in frac) if frac.startswith('0') else extenso(int(frac))}"


if __name__ == "__main__":
    for x in ["De R$ 199 por apenas R$ 129,90!", "30h de bateria", "10% de vitamina C", "frasco de 30 ml",
              "Parcele em 12x", "Mais de 1.500 vendidos", "R$ 1.299,00", "4,8 estrelas"]:
        print(x, "->", falado(x))
