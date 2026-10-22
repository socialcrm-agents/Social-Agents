"""Utilitários da VSL: ficha da oferta (ficha.json), caminhos, dinheiro em reais, erros em português.

Só biblioteca padrão: a skill roda com Python 3.10+ puro, sem pip install.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
HIPOTESE = "[HIPÓTESE]"

ETAPAS = ["diagnostico", "publico", "oferta", "angulos", "roteiro", "pagina", "gravacao", "edicao", "criativos",
          "lancamento", "otimizacao"]
ETAPA_NOME = {
    "diagnostico": "Diagnóstico (produto, ticket, momento)",
    "publico": "Público (dores, desejos, objeções)",
    "oferta": "Oferta (promessa, mecanismos, stack, garantia)",
    "angulos": "Ângulos e big idea",
    "roteiro": "Roteiro da VSL",
    "pagina": "Página de vendas",
    "gravacao": "Gravação",
    "edicao": "Edição e hospedagem do vídeo",
    "criativos": "Criativos (anúncios)",
    "lancamento": "Lançamento (calendário e campanhas)",
    "otimizacao": "Otimização pelas métricas",
}

DEFAULTS: dict = {
    "slug": "",
    "etapa": "diagnostico",
    "criado_em": "",
    "produto": {"nome": "", "formato": "", "entrega": "", "preco": 0, "preco_ancora": 0, "parcelas": 12,
                "valor_parcela": 0, "moeda": "BRL", "checkout_url": "", "garantia_dias": 7, "garantia_texto": ""},
    "publico": {"quem": "", "consciencia": "", "dores": [], "desejos": [], "objecoes": [], "medos": [],
                "palavras": []},
    "oferta": {"promessa": "", "prazo_resultado": "", "big_idea": "",
               "mecanismo_problema": {"nome": "", "explicacao": ""},
               "mecanismo_solucao": {"nome": "", "explicacao": ""},
               "stack": [], "bonus": [], "escassez": "",
               "order_bump": {"nome": "", "preco": 0}, "upsell": {"nome": "", "preco": 0}},
    "autor": {"nome": "", "credencial": "", "historia": "", "foto": ""},
    "provas": [],
    "faq": [],
    "vsl": {"duracao_min": 0, "delay_oferta_s": 0, "embed": "", "status": "roteiro"},
    "pagina": {"headline": "", "subheadline": "", "aviso_play": "⚠️ Assista até o final — o vídeo sai do ar em breve",
               "chamada_botao": "QUERO COMEÇAR AGORA", "bullets": [], "para_quem": [], "nao_para_quem": [],
               "rodape": ""},
    "marca": {"cor": "#7C5CFF", "cor2": "#22C55E", "fundo": "#0B0B12", "texto": "#F5F5F7", "fonte": "system"},
    "trafego": {"canal": "", "verba_dia": 0},
    "lancamento": {"inicio": "", "horas_por_dia": 2},
}

# campos que precisam estar preenchidos para a etapa ser considerada pronta (usado pelo status)
OBRIGATORIOS = {
    "diagnostico": ["produto.nome", "produto.formato", "produto.preco", "produto.entrega"],
    "publico": ["publico.quem", "publico.dores", "publico.desejos", "publico.objecoes"],
    "oferta": ["oferta.promessa", "oferta.mecanismo_problema.nome", "oferta.mecanismo_solucao.nome",
               "oferta.stack", "produto.garantia_dias"],
    "angulos": ["oferta.big_idea"],
    "roteiro": ["vsl.duracao_min"],
    "pagina": ["pagina.headline", "pagina.bullets", "produto.checkout_url", "vsl.delay_oferta_s"],
    "gravacao": [],
    "edicao": ["vsl.embed"],
    "criativos": [],
    "lancamento": ["lancamento.inicio", "trafego.canal"],
    "otimizacao": [],
}


class VslError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    print(f"ERRO: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- caminhos e ficha

def raiz(dir_arg: str | None = None) -> Path:
    """Pasta dos projetos: --dir ou ./vsl."""
    return Path(dir_arg).expanduser().resolve() if dir_arg else Path.cwd() / "vsl"


def pasta(slug: str, dir_arg: str | None = None) -> Path:
    p = raiz(dir_arg) / slug
    if not (p / "ficha.json").exists():
        existentes = ", ".join(sorted(x.name for x in raiz(dir_arg).glob("*/ficha.json"))) if raiz(dir_arg).exists() else ""
        raise VslError(f"Projeto '{slug}' não encontrado em {raiz(dir_arg)}"
                       + (f" (existentes: {existentes})" if existentes else " — crie com: projeto.py novo \"Nome\""))
    return p


def mesclar(base: dict, extra: dict) -> dict:
    """Defaults + ficha salva: o que está salvo vence; chaves novas dos defaults aparecem."""
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = mesclar(out[k], v)
        else:
            out[k] = v
    return out


def carregar(slug: str, dir_arg: str | None = None) -> tuple[dict, Path]:
    p = pasta(slug, dir_arg)
    try:
        dados = json.loads((p / "ficha.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise VslError(f"ficha.json com erro de formato (linha {e.lineno}, coluna {e.colno}): {e.msg}")
    return mesclar(DEFAULTS, dados), p


def salvar(ficha: dict, p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    (p / "ficha.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def nova(nome: str) -> dict:
    f = copy.deepcopy(DEFAULTS)
    f["slug"] = slugify(nome)
    f["criado_em"] = dt.date.today().isoformat()
    f["produto"]["nome"] = nome
    return f


# ---------------------------------------------------------------- texto e dinheiro

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:60] or "projeto"


def reais(v: float | int | None, centavos: bool | None = None) -> str:
    """297 -> 'R$ 297'; 30.72 -> 'R$ 30,72'; 1997 -> 'R$ 1.997'."""
    v = float(v or 0)
    if centavos is None:
        centavos = abs(v - round(v)) > 0.004
    txt = f"{v:,.2f}" if centavos else f"{round(v):,}"
    return "R$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".")


def parcela(produto: dict) -> tuple[int, float]:
    """(número de parcelas, valor da parcela). Sem valor_parcela informado, divide sem juros."""
    n = int(produto.get("parcelas") or 1)
    valor = float(produto.get("valor_parcela") or 0)
    if n > 1 and not valor and produto.get("preco"):
        valor = round(float(produto["preco"]) / n, 2)
    return n, valor


def parcelado(produto: dict) -> str:
    n, v = parcela(produto)
    return f"{n}x de {reais(v, centavos=True)}" if n > 1 and v else reais(produto.get("preco"))


def obter(d: dict, caminho: str):
    cur = d
    for parte in caminho.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(parte)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(parte)
        else:
            return None
    return cur


def definir(d: dict, caminho: str, valor) -> None:
    partes = caminho.split(".")
    cur = d
    for parte in partes[:-1]:
        if isinstance(cur, list):
            cur = cur[int(parte)]
        else:
            cur = cur.setdefault(parte, {})
    if isinstance(cur, list):
        cur[int(partes[-1])] = valor
    else:
        cur[partes[-1]] = valor


def vazio(v) -> bool:
    return v in (None, "", 0, [], {}) or (isinstance(v, dict) and all(vazio(x) for x in v.values()))


def hipoteses(d, prefixo: str = "") -> list[str]:
    """Caminhos de todos os textos que ainda começam com [HIPÓTESE]."""
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            out += hipoteses(v, f"{prefixo}.{k}" if prefixo else k)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out += hipoteses(v, f"{prefixo}.{i}")
    elif isinstance(d, str) and d.strip().startswith(HIPOTESE):
        out.append(prefixo)
    return out
