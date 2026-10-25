"""Composições de referência: três efeitos completos (imagem + câmera + som), cronometrados na palavra falada.

Cada composição é UMA ideia bem executada, não uma pilha de efeitos:
  revelacao@palavra       2.5D: a câmera empurra devagar, o fundo ganha profundidade e a palavra aparece ENTRE o
                          cenário e a pessoa na sílaba exata; riser que resolve num impacto; chicote de entrada.
  produto_heroi@palavra   o produto recortado, em 3D de verdade, voa girando e pousa na mão; swoosh na entrada,
                          "plim" no pouso e soco de câmera no instante em que ele para.
  impacto@palavra         soco de câmera + palavra gigante com emoji e cor da emoção + clarão de 2 quadros +
                          tremida curta; o som vem da emoção (dinheiro = caixa, urgência = hit, alegria = bolha...).

Pedido: edit.py --composicao revelacao@"trecho falado" (ou override "composicoes": [{"nome", "at", "params"}]).
São pedidos explícitos: vencem os automáticos (gatilhos e seletor) no mesmo instante.
"""

from __future__ import annotations

import re

import emocao
from common import norm

NOMES = ("revelacao", "produto_heroi", "impacto")


def _acha(words: list[dict], trecho: str) -> tuple[int, int] | None:
    alvo = [n for n in (norm(x) for x in trecho.split()) if n]
    seq = [norm(w["w"]) for w in words]
    for i in range(len(seq) - len(alvo) + 1):
        if alvo and seq[i:i + len(alvo)] == alvo:
            return i, i + len(alvo) - 1
    return None


def _fim_da_frase(words: list[dict], i: int) -> float:
    j = i
    while j + 1 < len(words) and not (words[j]["w"].rstrip()[-1:] in ".?!" or words[j + 1]["t0"] - words[j]["t1"] > 0.6):
        j += 1
    return words[j]["t1"]


def _inicio_da_frase(words: list[dict], i: int) -> float:
    j = i
    while j > 0 and not (words[j - 1]["w"].rstrip()[-1:] in ".?!" or words[j]["t0"] - words[j - 1]["t1"] > 0.6):
        j -= 1
    return words[j]["t0"]


def _texto(words: list[dict], a: int, b: int) -> str:
    return re.sub(r"[.,;:!?…\"“”]", "", " ".join(w["w"] for w in words[a:b + 1])).upper()


def expandir(pedidos: list[dict], words: list[dict], total: float, ov: dict) -> tuple[list, list, list, list[str]]:
    """Pedidos de composição -> (motion, fx, sfx, avisos)."""
    motion, fx, sfx, avisos = [], [], [], []
    for n, p in enumerate(pedidos, 1):
        nome = p.get("nome")
        achou = _acha(words, str(p.get("at", "")))
        if nome not in NOMES:
            avisos.append(f"composição '{nome}' não existe ({', '.join(NOMES)})")
            continue
        if not achou:
            avisos.append(f"composição {nome}: trecho '{p.get('at')}' não foi falado; ignorada")
            continue
        a, b = achou
        w0, w1 = words[a]["t0"], words[b]["t1"]
        texto = p.get("params", {}).get("texto") or _texto(words, a, b)
        if nome == "revelacao" and not p.get("params", {}).get("texto") and b > a:
            import seletor  # revelação lê UMA palavra: a mais forte do trecho
            k = seletor.palavra_chave(words, list(range(a, b + 1)))
            if k is None:  # nenhuma com peso emocional: a mais significativa (mais longa, fora palavras curtas)
                k = max(range(a, b + 1), key=lambda i: len(norm(words[i]["w"])))
            texto = _texto(words, k, k)
        emo, emoji = emocao.da_palavra(words[a]["w"])
        cores = emocao.cor(p.get("params", {}).get("emocao") or (emo if emo != "neutro" else "curiosidade"))
        ident = p.get("id") or f"c_{nome}_{n}"
        if nome == "revelacao":
            t0 = round(max(_inicio_da_frase(words, a) - 0.05, 0), 3)
            t1 = round(min(max(_fim_da_frase(words, b) + 0.35, w1 + 1.2, t0 + 2.2), t0 + 4.5, total), 3)
            motion.append({"template": "profundidade", "t0": t0, "t1": t1, "layer": "full", "needs_video": True,
                           "webgl": True, "id": ident, "composicao": nome,
                           "params": {"movimento": p.get("params", {}).get("movimento", "dolly"), "intensidade": 0.85,
                                      "texto": texto, "cor": cores["cor"], "texto_at": round(max(w0 - t0 - 0.04, 0.05), 3),
                                      "desfoque": 7}})
            fx.append({"type": "whip", "t": round(max(t0 - 0.04, 0), 3)})
            sfx += [{"type": "swoosh", "t": round(max(t0 - 0.08, 0), 3), "gain": 0.55},
                    {"type": "riser", "t": round(max(w0 - 1.1, t0), 3), "gain": 0.45},
                    {"type": "hit", "t": round(w0 - 0.02, 3), "gain": 0.6}]
        elif nome == "produto_heroi":
            produto = p.get("params", {}).get("image") or (ov.get("direcao_cfg") or {}).get("produto")
            if not produto:
                avisos.append("composição produto_heroi: falta a foto do produto (edit.py --produto foto.png)")
                continue
            t0 = round(max(w0 - 0.35, 0), 3)
            t1 = round(min(max(w1 + 1.6, t0 + 2.4), total), 3)
            pousa = round(t0 + 0.95, 3)
            motion.append({"template": "produto3d", "t0": t0, "t1": t1, "layer": "front", "webgl": True, "id": ident,
                           "composicao": nome, "hand": p.get("params", {}).get("entrada", "mao") == "mao",
                           "params": {"image": produto, "entrada": p.get("params", {}).get("entrada", "mao"),
                                      **({"follow": "hand"} if p.get("params", {}).get("entrada", "mao") == "mao" else {})}})
            fx.append({"type": "zoom_impacto", "t": pousa})
            sfx += [{"type": "swoosh", "t": t0, "gain": 0.6}, {"type": "plim", "t": pousa, "gain": 0.55}]
        else:  # impacto
            t0 = round(max(w0 - 0.06, 0), 3)
            t1 = round(min(max(w1 + 1.0, t0 + 1.3), total), 3)
            motion.append({"template": "palavra_chave", "t0": t0, "t1": t1, "layer": "front", "zona": "meio",
                           "id": ident, "composicao": nome,
                           "params": {"text": texto, "emoji": p.get("params", {}).get("emoji", emoji), "cor": cores["cor"],
                                      "cor2": cores["cor2"], "tamanho": 210}})
            fx += [{"type": "zoom_impacto", "t": round(w0 - 0.02, 3)}, {"type": "clarao", "t": round(w0 - 0.02, 3)},
                   {"type": "tremida", "t": round(w0 + 0.05, 3), "force": 0.5}]
            sfx += [{"type": "hit", "t": round(w0 - 0.03, 3), "gain": 0.55},
                    {"type": cores["sfx"], "t": round(w0 + 0.12, 3), "gain": 0.45}]
    for k, f_ in enumerate(fx):  # id estável (não renumera quando outra coisa entra antes)
        f_.setdefault("id", f"fx_{f_['type']}_c{round(f_['t'] * 1000)}")
    return motion, fx, sfx, avisos
