"""Mapa de gatilhos: o que é dito (frase, palavra, valor em dinheiro, enumeração) vira efeito + som + impacto.

Regras em triggers/padrao.json (todas as marcas) + brands/<slug>/triggers.json (da marca).
Saída: animações automáticas (marcadas "auto"; um pedido explícito do usuário sempre vence), SFX e efeitos de quadro.
"""

from __future__ import annotations

import re

from pathlib import Path

from common import SKILL_DIR, load_json, norm

ORDINAIS = {"primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2, "terceiro": 3, "terceira": 3,
            "quarto": 4, "quarta": 4, "quinto": 5, "quinta": 5}
NUM_WORDS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
             "oito": 8, "nove": 9, "dez": 10, "vinte": 20, "trinta": 30, "cinquenta": 50, "cem": 100}


def load_rules(brand: dict) -> list[dict]:
    rules = list((load_json(SKILL_DIR / "triggers" / "padrao.json") or {}).get("regras", []))
    if brand and brand.get("triggers"):
        extra = load_json(Path(brand["_dir"]) / brand["triggers"]) or {}
        rules = extra.get("regras", []) + rules  # regras da marca têm prioridade
    return rules


def _clean(w: str) -> str:
    return re.sub(r"[.,;:!?…\"“”]", "", w)


def _rest(words, i, n=5) -> str:
    out = []
    for w in words[i:i + n]:
        out.append(_clean(w["w"]))
        if w["w"].endswith((".", "!", "?", ",")):
            break
    return " ".join(out).upper()


def _number(tok: str):
    n = norm(tok)
    if n in NUM_WORDS:
        return float(NUM_WORDS[n])
    t = _clean(tok).replace("R$", "").replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _fill(obj, ctx: dict):
    """Troca {placeholders}; um valor que é só "{valor}" vira número."""
    if isinstance(obj, dict):
        return {k: _fill(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fill(v, ctx) for v in obj]
    if isinstance(obj, str):
        whole = re.fullmatch(r"\{(\w+)\}", obj)
        if whole and whole.group(1) in ctx:
            return ctx[whole.group(1)]
        return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), obj)
    return obj


def find(words: list[dict], rule: dict, cta_keywords: set[str]) -> list[tuple[float, float, dict]]:
    """(início, fim, contexto) de cada ocorrência do gatilho."""
    q, seq, hits = rule["quando"], [norm(w["w"]) for w in words], []
    for phrase in q.get("frase", []) + q.get("palavra", []):
        target = [norm(x) for x in phrase.split()]
        for i in range(len(seq) - len(target) + 1):
            if seq[i:i + len(target)] == target:
                j = i + len(target)
                ctx = {"frase": phrase.upper(), "resto": _rest(words, j)}
                if norm(target[0]) in ("comenta", "comente"):
                    nxt = _clean(words[j]["w"]).upper() if j < len(words) else ""
                    if norm(nxt).upper() not in {norm(k).upper() for k in cta_keywords}:
                        continue
                    ctx["palavra_cta"] = nxt
                hits.append((words[i]["t0"], words[min(j, len(words) - 1)]["t1"], ctx))
    if q.get("dinheiro"):
        for i, w in enumerate(words):
            val = _number(w["w"])
            if val is None:
                continue
            nxt = [norm(x["w"]) for x in words[i + 1:i + 3]]
            prev = norm(words[i - 1]["w"]) if i else ""
            mult = "mil" if "mil" in nxt else "mi" if any(x.startswith("milh") for x in nxt) else ""
            if "reais" in nxt or prev in ("r", "r$") or "r$" in w["w"].lower():
                k = i + 1 + (1 if mult else 0) + (1 if "reais" in nxt else 0)
                ctx = {"valor": val, "decimais": 1 if val % 1 else 0, "sufixo": f" {mult}" if mult else "",
                       "resto": _rest(words, k, 4), "frase": w["w"]}
                hits.append((w["t0"], words[min(k, len(words) - 1)]["t1"], ctx))
    if q.get("enumeracao"):
        marks = [i for i, s in enumerate(seq) if s in ORDINAIS]
        groups, cur = [], []
        for i in marks:
            if cur and (words[i]["t0"] - words[cur[-1]]["t0"] > 12 or ORDINAIS[seq[i]] != ORDINAIS[seq[cur[-1]]] + 1):
                if len(cur) >= 2:
                    groups.append(cur)
                cur = []
            if not cur and ORDINAIS[seq[i]] != 1:
                continue
            cur.append(i)
        if len(cur) >= 2:
            groups.append(cur)
        for g in groups:
            t0 = words[g[0]]["t0"]
            items = [{"text": _rest(words, i + 1, 5).capitalize(), "at": round(words[i]["t0"] - t0, 3)} for i in g]
            hits.append((t0, words[g[-1]]["t1"] + 1.8, {"items": items}))
    return sorted(hits, key=lambda h: h[0])


ZONA_BAIXA = {"botao_cta"}  # efeitos na parte de baixo da tela não disputam espaço com os de cima


def apply(words, rules, style_name: str, total: float, cta_keywords=(), busy=()) -> tuple[list, list, list]:
    motions, sfx, fx = [], [], []
    taken = [(a, b, "cima") for a, b in busy]
    for rule in rules:
        if rule.get("estilos") and style_name not in rule["estilos"]:
            continue
        last = -99.0
        for t0, t_end, ctx in find(words, rule, set(cta_keywords)):
            if t0 - last < rule.get("intervalo_min", 3.0) or t0 > total - 0.8:
                continue
            eff = rule.get("efeito")
            if eff:
                dur = eff.get("dur") or max(t_end - t0, 1.6)
                a, b = round(max(t0 - 0.05, 0), 3), round(min(t0 + dur, total), 3)
                zona = "baixo" if eff["template"] in ZONA_BAIXA else "cima"
                clash = [y for x, y, z in taken if a < y - 0.2 and b > x + 0.2 and z == zona]
                if clash and max(clash) - a < 1.0 and b - max(clash) >= 1.2:
                    a = round(max(clash), 3)          # espera o efeito anterior sair (até 1 s de atraso)
                elif clash:
                    continue
                params = _fill(eff.get("params", {}), ctx)
                if "items" in ctx:
                    params["items"] = ctx["items"]
                motions.append({"template": eff["template"], "t0": a, "t1": b, "params": params, "auto": True,
                                "trigger": rule["nome"], **({"layer": eff["layer"]} if eff.get("layer") else {})})
                taken.append((a, b, zona))
            if rule.get("som"):
                sfx.append({"type": rule["som"], "t": round(max(t0 - 0.02, 0), 3), "gain": rule.get("volume", 0.6)})
            if rule.get("fx"):
                fx.append({"type": rule["fx"], "t": round(t0 + 0.05, 3)})
            last = t0
    return motions, sfx, fx
