#!/usr/bin/env python3
"""Transforma edl.json + estilo + correções do usuário em timeline.json.

A timeline é o "projeto de edição" legível: tomadas com zoom, palavras com tempo
final, páginas de legenda, palavras atrás da pessoa, B-roll, gráficos e SFX.
O Claude pode ler e ajustar este arquivo diretamente antes do render.

Uso: plan.py <projeto>
"""

from __future__ import annotations

import sys
from pathlib import Path

from common import EditorError, load_json, load_style, log, main_guard, norm, project_paths, save_json

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas num numa para pra pro por com sem que se
e ou mas como quando onde eu tu ele ela nos vos eles elas voce voces te me lhe isso isto aquilo esse essa este esta
meu minha seu sua ja nao sim mais menos muito pouco tambem so tudo todo toda todos todas ser estar ter ir vai vou
foi era tem ta to tao aqui ali la entao agora porque pois sabe olha da uma ao aos""".split())
POWER = set("""sistema produto produtos dinheiro venda vendas vender lucro lucrativo resultado resultados gratis rapido
rapida simples facil segredo erro erros mecanismo estrutura eficiente irresistivel oferta promessa nicho ia conteudo
automatico teoria prova garantia hoje nunca sempre ninguem tempo metodo estrategia cliente clientes faturamento
milhoes mil reais real digital escala viral perigo atencao urgente gratuito bonus desconto""".split())
VISUAL_CUES = {"olhada", "olha", "veja", "vendo", "mostrando", "mostrar", "aqui", "tela", "sistema", "exemplo", "repara"}
DEFAULT_CTA = {"reels_viral": "SEGUE PRA VER MAIS", "anuncio_conversao": "CLIQUE EM SAIBA MAIS", "editorial_premium": "Link na bio"}


def fix_word(text: str, fixes: dict) -> str:
    key = norm(text)
    for wrong, right in fixes.items():
        if norm(wrong) == key:
            tail = "".join(ch for ch in text[::-1] if not ch.isalnum())[::-1] if not text[-1:].isalnum() else ""
            return right + tail
    return text


def score_word(w: str) -> float:
    n = norm(w)
    if not n or n in STOP or len(n) < 3:
        return 0.0
    s = 1.0 + min(len(n), 12) / 6
    if n.isdigit() or "%" in w or "$" in w:
        s += 3
    if n in POWER:
        s += 3
    return s


def apply_case(text: str, case: str) -> str:
    if case == "upper":
        return text.upper()
    if case == "title":
        return text[:1].upper() + text[1:].lower()
    return text


def shots(segments, words, style) -> list[dict]:
    """Divide tomadas longas em planos menores (troca de zoom = corte dinâmico sem perder fala)."""
    target = {"alternate": 2.6, "keyword": 3.4, "push": 5.0}[style["zoom"]["mode"]]
    out = []
    for seg in segments:
        pieces, cur_in = [], seg["in"]
        ws = [words[i] for i in seg["words"]]
        for a, b in zip(ws, ws[1:]):
            if b["t0"] - cur_in >= target and seg["out"] - b["t0"] >= 1.2:
                cut = round((a["t1"] + b["t0"]) / 2, 3)
                pieces.append((cur_in, cut))
                cur_in = cut
        pieces.append((cur_in, seg["out"]))
        for a, b in pieces:
            out.append({"clip": seg["clip"], "in": a, "out": b})
    return out


def main() -> None:
    project = Path(sys.argv[1])
    paths = project_paths(project)
    proj = load_json(paths["project"])
    edl = load_json(paths["edl"])
    tr = load_json(paths["transcript"])
    if not edl:
        raise EditorError("edl.json não encontrado. Rode analyze.py.")
    style = load_style(proj["style"])
    ov = proj.get("overrides", {})
    words_src = tr["words"]
    clips = {c["id"]: c for c in proj["clips"]}
    cap = {**style["captions"], **ov.get("caption", {})}
    zcfg = {**style["zoom"], **ov.get("zoom", {})}

    # 1) planos com tempo na timeline final + zoom
    plan_shots, t = [], 0.0
    for n, s in enumerate(shots(edl["segments"], words_src, style)):
        dur = round(s["out"] - s["in"], 3)
        if zcfg.get("off"):
            z0 = z1 = 1.0
        elif zcfg["mode"] == "push":
            punch = n % zcfg["punch_every"] == zcfg["punch_every"] - 1
            z0 = zcfg["punch"] if punch else zcfg["base"]
            z1 = z0 + zcfg["push"]
        else:
            punch = n % zcfg["punch_every"] == 1
            z0 = zcfg["punch"] if punch else zcfg["base"]
            z1 = z0 + zcfg["push"] + (0.03 if punch else 0.0)
        plan_shots.append({"clip": s["clip"], "src": clips[s["clip"]]["path"], "in": s["in"], "out": s["out"],
                           "t0": round(t, 3), "t1": round(t + dur, 3), "zoom0": round(z0, 3), "zoom1": round(z1, 3),
                           "cx": 0.5, "cy": 0.42})
        t += dur
    total = round(t, 3)

    # 2) palavras na timeline final (com correções do usuário)
    fixes = ov.get("word_fixes", {})
    words = []
    for sh in plan_shots:
        for w in words_src:
            if w["clip"] == sh["clip"] and sh["in"] <= (w["t0"] + w["t1"]) / 2 < sh["out"]:
                idx = words_src.index(w)
                if idx in set(edl["dropped"]):
                    continue
                words.append({"w": fix_word(w["w"], fixes), "t0": round(sh["t0"] + max(w["t0"] - sh["in"], 0), 3),
                              "t1": round(min(sh["t0"] + w["t1"] - sh["in"], sh["t1"]), 3), "emph": False})

    # 3) ênfase: melhor palavra de cada frase + pedidos do usuário
    sentence, last_emph = [], -9.0
    for i, w in enumerate(words):
        sentence.append(i)
        if w["w"].endswith((".", "!", "?", ",")) or i == len(words) - 1:
            best = max(sentence, key=lambda k: score_word(words[k]["w"]))
            if score_word(words[best]["w"]) >= 3 and words[best]["t0"] - last_emph > 1.6:
                words[best]["emph"] = True
                last_emph = words[best]["t0"]
            sentence = []
    for extra in ov.get("emphasis_add", []):
        for w in words:
            if norm(w["w"]) == norm(extra):
                w["emph"] = True

    # 4) páginas de legenda
    pages, cur = [], []
    for i, w in enumerate(words):
        if cur:
            chars = sum(len(words[k]["w"]) + 1 for k in cur) + len(w["w"])
            gap = w["t0"] - words[cur[-1]]["t1"]
            if len(cur) >= cap["words_per_page"] or chars > cap["max_chars"] or gap > 0.35 \
                    or words[cur[-1]]["w"].endswith((".", "!", "?")):
                pages.append(cur)
                cur = []
        cur.append(i)
    if cur:
        pages.append(cur)
    cap_pages = []
    for n, p in enumerate(pages):
        t0 = words[p[0]]["t0"]
        nxt = words[pages[n + 1][0]]["t0"] if n + 1 < len(pages) else total
        cap_pages.append({"t0": t0, "t1": round(min(nxt, words[p[-1]]["t1"] + 0.6), 3), "words": p})

    # 5) palavras atrás da pessoa (fora da janela do gancho e do CTA)
    gfx_hook_end = 2.9 if style["graphics"]["hook_banner"] else (4.3 if style["graphics"]["lower_third"] else 0.3)
    cta_start = max(total - 3.2, 0)
    bcfg = style["behind"]
    behind = []
    enabled = bcfg["enabled"] if ov.get("behind_enabled") is None else ov["behind_enabled"]
    removed = {norm(x) for x in ov.get("behind_remove", [])}
    if enabled:
        cands = sorted((i for i, w in enumerate(words) if w["emph"] and norm(w["w"]) not in removed),
                       key=lambda i: -score_word(words[i]["w"]))
        for i in cands:
            w = words[i]
            text = apply_case(w["w"].strip(".,!?:;"), bcfg["case"])
            too_close = any(abs(w["t0"] - b["t0"]) < 4.0 or b["text"] == text for b in behind)
            if w["t0"] < gfx_hook_end or w["t0"] + 1.0 > cta_start or too_close or len(behind) >= bcfg["max"]:
                continue
            behind.append({"text": text, "t0": round(max(w["t0"] - 0.08, 0), 3),
                           "t1": round(min(w["t0"] + 1.9, total), 3)})
        for req in ov.get("behind_add", []):
            hit = next((w for w in words if norm(w["w"]) == norm(req.get("at", req["text"]))), None)
            if hit:
                behind.append({"text": apply_case(req["text"], bcfg["case"]), "t0": round(max(hit["t0"] - 0.08, 0), 3),
                               "t1": round(min(hit["t0"] + req.get("dur", 1.9), total), 3)})
        # a palavra não atravessa troca de plano (a cabeça muda de lugar no corte)
        for b in behind:
            shot = next((s for s in plan_shots if s["t0"] <= b["t0"] < s["t1"]), None)
            if shot and b["t1"] > shot["t1"] and shot["t1"] - b["t0"] >= 0.9:
                b["t1"] = shot["t1"]
        behind.sort(key=lambda b: b["t0"])

    # 6) B-roll: entra em palavras de "olha/veja/sistema", respeitando o espaçamento do estilo
    rcfg = style["broll"]
    broll, pool = [], [b for b in proj.get("broll", [])]
    if pool:
        cursor = {b["id"]: 0.0 for b in pool}
        k = 0
        for w in words:
            if norm(w["w"]) in VISUAL_CUES and w["t0"] > gfx_hook_end and w["t0"] + 1.0 < cta_start:
                if broll and w["t0"] - broll[-1]["t1"] < rcfg["min_gap"]:
                    continue
                b = pool[k % len(pool)]
                dur = min(rcfg["max_dur"], cta_start - w["t0"])
                src_in = cursor[b["id"]]
                if b["kind"] == "video":
                    if src_in + dur > b["duration"]:
                        src_in = 0.0
                    cursor[b["id"]] = src_in + dur + 3.0
                broll.append({"src": b["path"], "kind": b["kind"], "t0": w["t0"], "t1": round(w["t0"] + dur, 3),
                              "src_in": round(src_in, 2), "mode": rcfg["mode"], "cue": w["w"]})
                k += 1
        drop = set(ov.get("broll_remove", []))
        broll = [b for n, b in enumerate(broll, 1) if n not in drop]
    for req in ov.get("broll_at", []):
        hit = next((w for w in words if norm(w["w"]) == norm(req["at"].split()[0])), None)
        src = next((b for b in pool if b["id"] == req.get("src")), None) or (pool[0] if pool else None)
        if hit and src:
            broll.append({"src": src["path"], "kind": src["kind"], "t0": hit["t0"],
                          "t1": round(hit["t0"] + req.get("dur", rcfg["max_dur"]), 3), "src_in": req.get("src_in", 0.0),
                          "mode": req.get("mode", rcfg["mode"]), "cue": req["at"]})
    broll.sort(key=lambda b: b["t0"])
    # cartão/tela dividida já ocupam o centro: a palavra grande não disputa espaço com eles
    behind = [x for x in behind if not any(b["mode"] != "full" and x["t0"] < b["t1"] and x["t1"] > b["t0"] for b in broll)]

    # 7) gráficos
    g = style["graphics"]
    graphics = []
    first_sentence = []
    for w in words:
        first_sentence.append(w["w"])
        if w["w"].endswith((".", "!", "?")) or len(first_sentence) >= 7:
            break
    hook = ov.get("hook") or " ".join(first_sentence).strip(".,")
    if g["hook_banner"]:
        graphics.append({"type": "hook", "text": hook, "t0": 0.0, "t1": min(2.8, total)})
    if g["lower_third"]:
        graphics.append({"type": "lower_third", "text": ov.get("title") or hook, "t0": 0.4, "t1": min(4.2, total)})
    if g["chapter_numbers"]:
        n = 1
        for b in broll:
            graphics.append({"type": "chapter", "text": f"{n:02d}", "t0": b["t0"], "t1": b["t1"]})
            n += 1
    if g["progress_bar"]:
        graphics.append({"type": "progress", "text": "", "t0": 0.0, "t1": total})
    if g["cta"]:
        graphics.append({"type": "cta", "text": ov.get("cta") or DEFAULT_CTA[style["name"]], "t0": round(cta_start, 3), "t1": total})

    # 8) efeitos sonoros (sutis, abaixo da voz)
    s = style["sfx"]
    sfx = []
    if s["whoosh"]:
        sfx += [{"type": "whoosh", "t": max(b["t0"] - 0.12, 0), "gain": s["whoosh"]} for b in broll]
        sfx += [{"type": "whoosh", "t": max(sh["t0"] - 0.1, 0), "gain": s["whoosh"] * 0.5}
                for a, sh in zip(plan_shots, plan_shots[1:]) if abs(sh["zoom0"] - a["zoom0"]) > 0.15]
    if s["pop"]:
        sfx += [{"type": "pop", "t": b["t0"], "gain": s["pop"]} for b in behind]
    if s["riser"] and g["cta"]:
        sfx.append({"type": "riser", "t": max(cta_start - 1.2, 0), "gain": s["riser"]})
    sfx.sort(key=lambda x: x["t"])

    save_json(paths["timeline"], {
        "style": style["name"], "w": 1080, "h": 1920, "fps": 30, "duration": total,
        "shots": plan_shots, "words": words, "captions": {"cfg": cap, "pages": cap_pages},
        "behind": behind, "behind_cfg": bcfg, "broll": broll, "graphics": graphics, "graphics_cfg": g,
        "sfx": sfx, "grade": style["grade"], "audio": style["audio"],
        "music": ov.get("music"),
    })
    log(f"OK: timeline {total:.1f}s | {len(plan_shots)} planos | {len(cap_pages)} legendas | "
        f"{len(behind)} atrás da pessoa | {len(broll)} B-roll | {len(graphics)} gráficos | {len(sfx)} SFX")


if __name__ == "__main__":
    main_guard(main)
