#!/usr/bin/env python3
"""Seletor de efeitos por intenção narrativa — a direção premium do Editor Viral IA™.

Em vez de espalhar efeitos, decide CENA A CENA (uma frase = uma cena) o que entra, por quê e o que fica de fora:
  1. intenção da fala   gancho, virada, dor, prova, número, lista, produto, pergunta, cta, respiro
  2. contexto           o que já está na tela (pedido seu, gatilho automático, tela cheia), duração da cena
  3. linguagem visual   a família de transições e a paleta do estilo (consistência entre cenas)
  4. densidade          orçamento: algo muda a cada ~2-3 s, nunca dois heróis juntos, tela cheia no máx. 1 a cada
                        8 s, transição no máx. 1 a cada 2,5 s, nunca o mesmo efeito duas cenas seguidas

A biblioteca é curta de propósito (poucos efeitos, muito bem feitos):
  palavra_chave  palavra dita, gigante, com emoji e cor da emoção (legenda "com a cara dos concorrentes")
  profundidade   2.5D: câmera anda, fundo em paralaxe, palavra entre o cenário e a pessoa (gancho)
  produto3d      produto recortado em 3D de verdade (quando há foto do produto: params.produto)
  transições     zoom_impacto, whip (chicote), glitch, swipe — no ritmo da fala, na virada da cena

Ligado com o override "direcao": "premium" (edit.py --direcao premium). Sem ele, nada muda.
  python seletor.py <projeto>     relatório do que o seletor escolheu, cena a cena (lê timeline.json)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import emocao
from common import norm

INTENCOES = {
    "cta": r"\b(comenta|comente|clica|clique|toque|toca|link|segue|siga|compra|compre|carrinho|garanta|chama|manda)",
    "pergunta": r"\?$|^(voce sabia|por que|porque|como|o que|qual|sera que|ja pensou)",
    "dor": r"\b(problema|dificil|cansad|travad|perde|perdeu|sofre|nao consegue|frustr|medo|erro|errad|dor)",
    "prova": r"\b(resultado|comprovad|cliente|vendi|faturei|depoimento|consegui|funcionou|prova)",
    "virada": r"^(mas|so que|porem|entao|ai|agora|e se|na verdade|o segredo)\b",
    "lista": r"\b(primeiro|segundo|terceiro|dois|duas|tres|passos|dicas|sabores|opcoes|tipos)\b",
    "produto": r"\b(esse|essa|este|esta|aqui|olha|olhadinha|produto|chiclete|kit|curso|app)\b",
    "numero": r"(\d|r\$|reais|por cento|%)",
}
TRANSICAO = {"virada": "whip", "dor": "glitch", "prova": "zoom_impacto", "numero": "zoom_impacto",
             "lista": "swipe", "produto": "swipe", "pergunta": "zoom_impacto"}
# família de transições por linguagem visual (consistência: um vídeo não mistura todas)
FAMILIA = {"pro_clean": {"zoom_impacto", "whip", "swipe"}, "editorial_premium": {"whip"},
           "anuncio_conversao": {"zoom_impacto", "swipe", "glitch", "whip"},
           "reels_viral": {"zoom_impacto", "whip", "glitch", "swipe"}}
SOM = {"zoom_impacto": ("boom", 0.55), "whip": ("whoosh", 0.6), "glitch": ("glitch", 0.5), "swipe": ("whoosh", 0.5)}
HEROI_GAP, TRANS_GAP, FULL_GAP = 2.0, 2.5, 8.0


def cenas(words: list[dict]) -> list[dict]:
    """Batidas da fala: frase (pontuação final ou pausa > 0,6 s); frase longa (> 3 s) quebra na vírgula, com
    batidas de 1,2 s no mínimo. `nova` = começa uma frase (troca de cena de verdade: lugar de transição)."""
    out, atual, nova = [], [], True
    for i, w in enumerate(words):
        atual.append(i)
        prox = words[i + 1] if i + 1 < len(words) else None
        fim_frase = w["w"].rstrip()[-1:] in ".?!" or prox is None or prox["t0"] - w["t1"] > 0.6
        dur = words[atual[-1]]["t1"] - words[atual[0]]["t0"]
        virgula = w["w"].rstrip().endswith(",") and dur >= 1.2 and prox is not None and \
            (prox and _resto_frase(words, i + 1) >= 1.2)
        if (fim_frase and (dur >= 1.2 or prox is None)) or (virgula and dur >= 1.2 and _frase_longa(words, atual[0])):
            out.append({"i": list(atual), "t0": words[atual[0]]["t0"], "t1": words[atual[-1]]["t1"],
                        "fala": " ".join(words[k]["w"] for k in atual), "nova": nova})
            atual, nova = [], fim_frase
    return out


def _fim_da_frase(words: list[dict], i: int) -> int:
    j = i
    while j + 1 < len(words) and not (words[j]["w"].rstrip()[-1:] in ".?!" or words[j + 1]["t0"] - words[j]["t1"] > 0.6):
        j += 1
    return j


def _resto_frase(words: list[dict], i: int) -> float:
    return words[_fim_da_frase(words, i)]["t1"] - words[i]["t0"]


def _frase_longa(words: list[dict], ini: int) -> bool:
    return words[_fim_da_frase(words, ini)]["t1"] - words[ini]["t0"] > 3.0


def intencao(c: dict, n: int) -> str:
    txt = " ".join(norm(x) for x in c["fala"].split())
    if n == 0:
        return "gancho"
    bruto = c["fala"].strip().lower()
    for nome in ("cta", "pergunta", "dor", "prova", "virada", "lista", "numero", "produto"):
        alvo = bruto if nome in ("pergunta", "numero") else txt
        if re.search(INTENCOES[nome], alvo):
            return nome
    return "respiro"


def palavra_chave(words: list[dict], idx: list[int]) -> int | None:
    """A palavra que vira destaque: a marcada como ênfase; senão a de mais peso emocional/número/tamanho."""
    marcadas = [i for i in idx if words[i].get("emph")]
    if marcadas:
        return marcadas[0]
    def peso(i):
        w = words[i]["w"]
        n = norm(w)
        if len(n) < 3:
            return 0
        e, emo = emocao.da_palavra(w)
        return (3 if emo else 0) + (2 if e != "neutro" else 0) + (2 if any(ch.isdigit() for ch in w) else 0) + min(len(n), 10) / 10
    melhor = max(idx, key=peso, default=None)
    return melhor if melhor is not None and peso(melhor) >= 2 else None


def _ocupado(t0: float, t1: float, motion: list[dict]) -> bool:
    """Há outro elemento de texto/tela cheia no intervalo exato (um herói por momento)."""
    return any(m["t0"] < t1 - 0.1 and m["t1"] > t0 + 0.1 and m.get("template") not in ("icone", "passa_mao")
               for m in motion)


def direcionar(words: list[dict], motion: list[dict], style_name: str, total: float, ov: dict) -> dict:
    """Decisões cena a cena. Devolve {"motion": [...], "fx": [...], "sfx": [...], "relatorio": [...]}."""
    fam = FAMILIA.get(style_name, FAMILIA["pro_clean"])
    produto = (ov.get("direcao_cfg") or {}).get("produto")
    cs = cenas(words)
    # paleta consistente: no máximo 2 cores de emoção no vídeo (as mais frequentes); o resto usa a 1ª
    contagem: dict[str, int] = {}
    for c in cs:
        e = emocao.da_frase([words[i]["w"] for i in c["i"]])
        contagem[e] = contagem.get(e, 0) + (1 if e != "neutro" else 0)
    paleta = [e for e, _ in sorted(contagem.items(), key=lambda kv: -kv[1]) if e != "neutro"][:2] or ["curiosidade"]
    novos, fx, sfx, rel = [], [], [], []
    ult_heroi, ult_trans, ult_full, ult_tipo, ult_trans_tipo, seguidas = -9.0, -9.0, -99.0, None, None, 0
    for n, c in enumerate(cs):
        it = intencao(c, n)
        dur = c["t1"] - c["t0"]
        d = {"cena": f"c{n + 1}", "t0": round(c["t0"], 2), "t1": round(c["t1"], 2), "fala": c["fala"], "intencao": it,
             "escolha": [], "descartado": []}
        k_pal = palavra_chave(words, c["i"])
        jan = (words[k_pal]["t0"] - 0.1, words[k_pal]["t1"] + 0.9) if k_pal is not None else (c["t0"], c["t1"])
        ocupado = _ocupado(jan[0], jan[1], motion + novos) if it != "gancho" else _ocupado(c["t0"], c["t1"], motion + novos)
        # --- transição na entrada da cena (não na primeira, nem colada noutra, nem onde já entra tela cheia)
        tipo = TRANSICAO.get(it)
        if n and tipo and c.get("nova", True):
            if tipo not in fam:
                d["descartado"].append(f"transição {tipo}: fora da linguagem {style_name}")
            elif c["t0"] - ult_trans < TRANS_GAP:
                d["descartado"].append(f"transição {tipo}: outra há {c['t0'] - ult_trans:.1f}s (densidade)")
            elif tipo == ult_trans_tipo:
                d["descartado"].append(f"transição {tipo}: mesma da cena anterior (repetição)")
            elif any(abs(m["t0"] - c["t0"]) < 0.4 and m.get("layer") == "full" for m in motion):
                d["descartado"].append(f"transição {tipo}: tela cheia já entra com chicote")
            else:
                t = round(max(c["t0"] - 0.06, 0), 3)
                if tipo == "swipe":  # passa a mão na tela: a própria mão (com rastro) é a transição
                    novos.append({"template": "passa_mao", "t0": max(t - 0.22, 0), "t1": round(t + 0.34, 3),
                                  "params": {}, "auto": True, "origem": "seletor", "layer": "front",
                                  "rosto": "livre", "id": f"s_passa_mao_{n}"})
                else:
                    fx.append({"type": tipo, "t": t, "origem": "seletor"})
                som, g = SOM[tipo]
                sfx.append({"type": som, "t": max(t - 0.05, 0), "gain": g})
                ult_trans, ult_trans_tipo = c["t0"], tipo
                d["escolha"].append(f"transição {tipo}")
        # --- herói da cena
        if it in ("cta", "pergunta"):
            d["descartado"].append("herói: cta/pergunta já têm bloco próprio (botão, pergunta na tela)")
        elif ocupado:
            d["descartado"].append("herói: cena já tem um elemento (seu pedido ou gatilho) — um herói por momento")
        elif (words[k_pal]["t0"] if k_pal is not None else c["t0"]) - ult_heroi < HEROI_GAP:
            d["descartado"].append(f"herói: outro há {c['t0'] - ult_heroi:.1f}s (densidade)")
        else:
            k = palavra_chave(words, c["i"])
            w = words[k] if k is not None else None
            texto = re.sub(r"[.,;:!?…\"“”]", "", w["w"]).upper() if w else ""
            emo, emoji = emocao.da_palavra(w["w"]) if w else ("neutro", None)
            emo = emo if emo in paleta else paleta[0]
            cores = emocao.cor(emo)
            if it == "gancho" and dur >= 2.2 and c["t0"] - ult_full >= FULL_GAP and ult_tipo != "profundidade" and texto:
                m = {"template": "profundidade", "t0": round(c["t0"], 3), "t1": round(min(c["t1"] + 0.3, total), 3),
                     "params": {"movimento": "dolly", "intensidade": 0.7, "texto": texto, "cor": cores["cor"],
                                "texto_at": round(max(w["t0"] - c["t0"] - 0.05, 0.1), 3)}}
                ult_full = c["t0"]
            elif it == "produto" and produto and ult_tipo != "produto3d":
                m = {"template": "produto3d", "t0": round(c["t0"], 3), "t1": round(min(c["t1"] + 0.4, total), 3),
                     "params": {"image": produto, "entrada": "voa"}}
            elif texto and (seguidas < 2 or c["t0"] - ult_heroi > 4.0):   # não 3 palavras-chave coladas
                ini = w["t0"] - 0.06
                m = {"template": "palavra_chave", "t0": round(ini, 3), "t1": round(min(max(w["t1"] + 0.9, ini + 1.2), total), 3),
                     "params": {"text": texto, "emoji": emoji, "cor": cores["cor"], "cor2": cores["cor2"], "emocao": emo}}
                sfx.append({"type": cores["sfx"], "t": round(ini + 0.04, 3), "gain": 0.45})
            else:
                m = None
                d["descartado"].append("herói: sem palavra forte dita nesta cena" if not texto
                                       else "herói: 3ª palavra-chave seguida (repetição)")
            if m:
                m.update(auto=True, origem="seletor", layer="full" if m["template"] == "profundidade" else "front",
                         id=f"s_{m['template']}_{k if k is not None else n}")
                if m["template"] in ("profundidade",):
                    m["needs_video"] = True
                if m["template"] in ("profundidade", "produto3d"):
                    m["webgl"] = True
                novos.append(m)
                ult_heroi = m["t0"]
                seguidas = seguidas + 1 if m["template"] == ult_tipo else 1
                ult_tipo = m["template"]
                d["escolha"].append(f"herói {m['template']}" + (f" '{texto}' {emoji or ''} ({emo})" if texto else ""))
        rel.append(d)
    return {"motion": novos, "fx": fx, "sfx": sfx, "relatorio": rel, "paleta": paleta}


# ------------------------------------------------------------------------------------------- QA de densidade
def densidade(tl: dict) -> dict:
    """Ritmo e poluição visual da timeline pronta: mudanças por janela de 3 s, buracos, heróis simultâneos."""
    total = tl["duration"]
    ev = sorted([m["t0"] for m in tl.get("motion", [])] + [f["t"] for f in tl.get("fx", [])]
                + [b["t0"] for b in tl.get("behind", [])] + [b["t0"] for b in tl.get("broll", [])]
                + [s["t0"] for s in tl.get("shots", [])[1:]])
    janelas = []
    t = 0.0
    while t < total - 0.5:
        janelas.append(sum(1 for e in ev if t <= e < t + 3))
        t += 3
    buracos = []
    prev = 0.0
    for e in ev + [total]:
        if e - prev > 4.5:
            buracos.append([round(prev, 1), round(e, 1)])
        prev = max(prev, e)
    grandes = [m for m in tl.get("motion", []) if m.get("layer") in ("front", "full") and m.get("template") != "icone"]
    juntos = []
    for a in grandes:
        for b in grandes:
            if a is not b and a["t0"] < b["t0"] < a["t1"] - 0.25 and a.get("layer") != "full" and b.get("layer") != "full" \
                    and not ({a.get("zona"), b.get("zona")} >= {"topo", "barra"}):
                juntos.append([a.get("id"), b.get("id"), round(b["t0"], 2)])
    fulls = sorted(m["t0"] for m in tl.get("motion", []) if m.get("layer") == "full")
    full_perto = [round(b, 2) for a, b in zip(fulls, fulls[1:]) if b - a < 6]
    alertas = []
    if buracos:
        alertas.append(f"monotonia: nada muda em {buracos}")
    if juntos:
        alertas.append(f"dois heróis ao mesmo tempo: {juntos}")
    if full_perto:
        alertas.append(f"tela cheia colada em outra (< 6 s) em {full_perto}")
    if janelas and max(janelas) > 5:
        alertas.append(f"poluição: {max(janelas)} mudanças em 3 s")
    return {"mudancas_por_3s": janelas, "media": round(sum(janelas) / max(len(janelas), 1), 2),
            "buracos": buracos, "herois_juntos": juntos, "alertas": alertas}


def legibilidade(tl: dict) -> dict:
    """Leitura no celular: legenda e textos de tela com tamanho mínimo (44 px em 1080 de largura)."""
    k = tl["w"] / 1080
    cap = tl["captions"]["cfg"]
    alertas = []
    if cap["size"] < 44 * k:
        alertas.append(f"legenda pequena: {cap['size']}px (mín. {int(44 * k)})")
    for m in tl.get("motion", []):
        tam = (m.get("params") or {}).get("size")
        if isinstance(tam, (int, float)) and tam > 3 and tam < 44 * k:
            alertas.append(f"{m.get('id')}: texto {tam}px")
    return {"alertas": alertas}


def main() -> int:
    import json
    proj = Path(sys.argv[1])
    tl = json.loads((proj / "timeline.json").read_text(encoding="utf-8"))
    d = tl.get("direcao")
    if d:
        for c in d["relatorio"]:
            print(f"{c['cena']} {c['t0']:5.1f}-{c['t1']:5.1f}s [{c['intencao']:<9}] {c['fala'][:60]}")
            for e in c["escolha"]:
                print(f"     + {e}")
            for e in c["descartado"]:
                print(f"     - {e}")
    else:
        print("direção premium desligada (edit.py --direcao premium)")
    print(json.dumps({"densidade": densidade(tl), "legibilidade": legibilidade(tl)}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
