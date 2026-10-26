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

import revisao
from common import (FORMATS, EditorError, load_brand, load_json, load_style, log, main_guard, norm, perfil, project_paths,
                    save_json)

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas num numa para pra pro por com sem que se
e ou mas como quando onde eu tu ele ela nos vos eles elas voce voces te me lhe isso isto aquilo esse essa este esta
meu minha seu sua ja nao sim mais menos muito pouco tambem so tudo todo toda todos todas ser estar ter ir vai vou
foi era tem ta to tao aqui ali la entao agora porque pois sabe olha da uma ao aos""".split())
POWER = set("""sistema produto produtos dinheiro venda vendas vender lucro lucrativo resultado resultados gratis rapido
rapida simples facil segredo erro erros mecanismo estrutura eficiente irresistivel oferta promessa nicho ia conteudo
automatico teoria prova garantia hoje nunca sempre ninguem tempo metodo estrategia cliente clientes faturamento
milhoes mil reais real digital escala viral perigo atencao urgente gratuito bonus desconto""".split())
VISUAL_CUES = {"olhada", "olha", "veja", "vendo", "mostrando", "mostrar", "aqui", "tela", "sistema", "exemplo", "repara"}
# ícones automáticos (Lucide) para palavras faladas; o Claude pode pedir outros com --motion
ICON_WORDS = {
    "dinheiro": "banknote", "lucro": "trending-up", "vendas": "trending-up", "venda": "shopping-cart", "vender": "shopping-cart",
    "tempo": "clock", "rapido": "zap", "rapida": "zap", "sistema": "cpu", "produto": "package", "produtos": "package",
    "ia": "bot", "inteligencia": "brain", "celular": "smartphone", "casa": "house", "imovel": "building-2",
    "apartamento": "building-2", "metro": "train-front", "medico": "stethoscope", "saude": "heart-pulse", "ideia": "lightbulb",
    "erro": "circle-x", "erros": "circle-x", "resultado": "chart-line", "resultados": "chart-line", "clientes": "users",
    "cliente": "users", "mensagem": "message-circle", "whatsapp": "message-circle", "instagram": "instagram",
    "video": "video", "aula": "graduation-cap", "curso": "graduation-cap", "conteudo": "file-video", "perguntas": "circle-help",
    "questoes": "circle-help", "escolhas": "list-checks", "oferta": "tag", "promessa": "handshake", "nicho": "target",
    "simples": "sparkles", "segredo": "lock", "gratis": "gift", "agenda": "calendar", "preco": "dollar-sign",
    "desconto": "percent", "garantia": "shield-check", "estrutura": "layers", "mecanismo": "cog", "eficiente": "rocket",
}
# padrões de cada template: camada e se usa os quadros reais da pessoa
MOTION_DEFAULTS = {
    "moldura": {"layer": "full", "needs_video": True}, "camadas": {"layer": "full", "needs_video": True},
    "quadrinho": {"layer": "full", "needs_video": True},
    # zona "topo": ocupa o alto do quadro -> a cena recua (desce) se a cabeça estiver alta e o CTA vai para baixo
    # zona "barra": só uma barra fina no alto (HUD) -> o CTA vai para baixo, sem recuo
    "pergunta": {"layer": "front", "zona": "topo"}, "player": {"layer": "front", "zona": "topo"},
    "palavra": {"layer": "behind"},
    "visor": {"layer": "full", "needs_video": True}, "editor_ia": {"layer": "full", "needs_video": True},
    "dividida": {"layer": "full", "needs_video": True}, "empilha": {"layer": "front"},
    "etiqueta": {"layer": "front", "zona": "topo"},
    "manchete": {"layer": "front", "zona": "topo"}, "proibido": {"layer": "front", "zona": "topo"}, "comentario": {"layer": "front"},
    "final": {"layer": "full"}, "hud": {"layer": "front", "zona": "barra"}, "pontos": {"layer": "full", "needs_video": True},
    "recorte": {"layer": "full", "needs_video": True}, "maos": {"layer": "front", "zona": "barra"},
    "transcricao": {"layer": "full", "needs_video": True}, "tomadas": {"layer": "front", "zona": "topo"},
    "estudio3d": {"layer": "full", "needs_video": True}, "profundidade": {"layer": "full", "needs_video": True},
    "palavra_chave": {"layer": "front", "zona": "meio"}, "passa_mao": {"layer": "front", "rosto": "livre"}, "objeto3d": {"layer": "front"},
    "mapa": {"layer": "front"}, "infografico": {"layer": "front", "zona": "topo"}, "documentario": {"layer": "full"},
    "icone": {"layer": "front"},
    "tela_ia": {"layer": "full"}, "carrossel3d": {"layer": "full", "needs_video": True},
    "notificacao": {"layer": "front"}, "botao_cta": {"layer": "front"}, "anotacao": {"layer": "front"},
    "carimbo": {"layer": "front", "zona": "topo", "params": {"y": 0.2}},
    "checklist": {"layer": "front", "zona": "topo"}, "onda_audio": {"layer": "front"},
    "pedacos": {"layer": "behind"}, "card_fogo": {"layer": "front"},
    "clones": {"layer": "full", "needs_video": True}, "cenario": {"layer": "full", "needs_video": True},
    "giro": {"layer": "front"}, "luz": {"layer": "front"},
    "vendas": {"layer": "front"}, "tabela": {"layer": "front"}, "cronometro": {"layer": "front"},
    "produto3d": {"layer": "front"},
}
DEFAULT_CTA = {"reels_viral": "SEGUE PRA VER MAIS", "anuncio_conversao": "CLIQUE EM SAIBA MAIS", "editorial_premium": "Link na bio",
               "pro_clean": "SEGUE PRA VER MAIS"}


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
            out.append({"clip": seg["clip"], "in": a, "out": b, **({"gancho": True} if seg.get("gancho") else {})})
    return out


def find_word(words: list[dict], phrase: str, after: float = 0.0, ultima: bool = False) -> dict | None:
    """Primeira ocorrência do trecho falado (1+ palavras) a partir de `after` segundos.
    Devolve a primeira palavra do trecho (início) ou, com ultima=True, a última (onde o trecho termina)."""
    target = [n for n in (norm(x) for x in phrase.split()) if n]
    seq = [norm(w["w"]) for w in words]
    for i in range(len(seq) - len(target) + 1):
        # palavras do corte de gancho (repetidas no começo) não servem de âncora: vale o lugar original da fala
        if target and words[i]["t0"] >= after - 0.05 and not words[i].get("gancho") and seq[i:i + len(target)] == target:
            return words[i + len(target) - 1] if ultima else words[i]
    return None


def resolve_cues(obj, words: list[dict], t0: float, t1: float, fixes: dict | None = None):
    """Troca valores "at": "palavra" (e chaves *_at) pelo tempo relativo ao início do clipe.
    A âncora passa pelas mesmas correções de palavra da legenda (pedido feito com a grafia do ASR continua valendo)."""
    if isinstance(obj, list):
        return [resolve_cues(x, words, t0, t1, fixes) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if (k == "at" or k.endswith("_at")) and isinstance(v, str):
            hit = find_word(words, v, t0)
            if not hit and fixes:
                hit = find_word(words, " ".join(fix_word(x, fixes) for x in v.split()), t0)
            if not (hit and hit["t0"] < t1):
                log(f"   aviso: âncora '{v}' não encontrada dentro da animação ({t0:.1f}-{t1:.1f}s); usando 0,5 s")
            out[k] = round(min(max(hit["t0"] - t0, 0), t1 - t0), 3) if hit and hit["t0"] < t1 else 0.5
        else:
            out[k] = resolve_cues(v, words, t0, t1, fixes)
    return out



def motion_sfx(motion: list[dict], k: float = 1.0) -> list[dict]:
    """Design de som das animações: cada entrada tem um som e cada ação dentro dela (digitar, marcar, riscar,
    clicar) tem o seu. k escala tudo (estilo: sfx.motion). Fica abaixo da voz (o mix aplica o ducking)."""
    out = []

    def add(kind, t, gain):
        out.append({"type": kind, "t": round(max(t, 0), 3), "gain": round(gain * k, 3)})

    def rel(m, v, default):
        return m["t0"] + (v if isinstance(v, (int, float)) else default)

    for m in motion:
        tp, p, t0, t1 = m.get("template"), m.get("params", {}), m["t0"], m["t1"]
        if tp in (None, "icone", "vendas", "luz"):
            continue
        if m.get("layer") != "full" and tp != "palavra_chave":  # palavra-chave tem o som da emoção (seletor)
            add("whoosh", t0 - 0.08, 0.3)
        if tp == "pergunta":
            add("click", t0 + 0.1, 0.5)
            add("ding", rel(m, p.get("ate_at"), (t1 - t0) * 0.7), 0.35)
        elif tp in ("checklist", "empilha", "dividida", "moldura", "tela_ia"):
            for it in p.get("items") or p.get("itens") or p.get("steps") or []:
                if isinstance(it, dict) and isinstance(it.get("at"), (int, float)):
                    add("ding" if tp in ("checklist", "empilha") else "click", t0 + it["at"], 0.3)
        elif tp in ("palavra", "final"):
            add("boom", t0 + 0.05, 0.45)
        elif tp == "manchete":
            add("pop", t0 + 0.05, 0.4)
            if p.get("riscar"):
                add("glitch", rel(m, p.get("riscar_at"), (t1 - t0) * 0.6), 0.4)
        elif tp == "proibido":
            add("glitch", rel(m, p.get("x_at"), (t1 - t0) * 0.5), 0.45)
        elif tp == "carimbo":
            add("boom", rel(m, p.get("at"), 0.05), 0.4)
        elif tp == "botao_cta":
            add("riser", t0 - 0.6, 0.3)
            add("click", rel(m, p.get("click_at"), min(1.4, t1 - t0 - 0.6)), 0.55)
        elif tp == "infografico":
            for st in p.get("stats", []):
                add("tick", rel(m, st.get("at"), 0.2), 0.35)
                add("ding", rel(m, st.get("at"), 0.2) + 0.9, 0.25)
        elif tp == "comentario":
            add("click", rel(m, p.get("digitar_ate"), (t1 - t0) * 0.6), 0.45)
        elif tp in ("notificacao", "etiqueta", "player", "tomadas", "giro", "tabela"):
            add("pop", t0 + 0.15, 0.35)
        elif tp in ("hud", "pontos", "recorte", "maos", "transcricao", "editor_ia", "visor"):
            add("tick", t0 + 0.1, 0.3)
            add("tick", t0 + 0.35, 0.25)
    return out

def _desloca_cues(obj, atraso: float):
    """Tempos relativos ("at", "*_at") recuam `atraso` segundos quando o início da animação é adiado."""
    if isinstance(obj, list):
        return [_desloca_cues(x, atraso) for x in obj]
    if not isinstance(obj, dict):
        return obj
    return {k: (round(max(v - atraso, 0.0), 3) if (k == "at" or k.endswith("_at")) and isinstance(v, (int, float))
                and not isinstance(v, bool) else _desloca_cues(v, atraso)) for k, v in obj.items()}


TRANSICOES = {"passa_mao"}  # animações de transição: rápidas de propósito (o mínimo de 1 s é para leitura)


def resolve_overlaps(items: list[dict]) -> list[dict]:
    """Animações de tela cheia têm prioridade: a anterior termina quando a próxima começa, e as de camada
    (front/behind) são cortadas para fora das janelas de tela cheia."""
    full = [m for m in items if m.get("layer") == "full"]
    for a, b in zip(full, full[1:]):
        if a["t1"] > b["t0"]:
            a["t1"] = b["t0"]
    full = [m for m in full if m["t1"] - m["t0"] >= 1.0]
    out = list(full)
    manual = [m for m in items if m.get("layer") != "full" and not m.get("auto")]
    for m in (m for m in items if m.get("layer") != "full"):
        if m.get("auto") and any(m is not x and m["t0"] < x["t1"] and m["t1"] > x["t0"] for x in manual):
            continue
        for f in full:
            if m["t0"] < f["t1"] and m["t1"] > f["t0"]:
                if m["t0"] >= f["t0"]:
                    m["t0"] = f["t1"]
                else:
                    m["t1"] = f["t0"]
        if m["t1"] - m["t0"] >= 1.0 or m.get("template") in TRANSICOES:
            out.append(m)
        elif not m.get("auto"):
            log(f"   aviso: motion {m.get('id', '')} ({m.get('template')}): ficou com {m['t1'] - m['t0']:.2f}s "
                f"(< 1 s) depois de abrir espaço para outra animação; ignorado")
    # dois textos grandes no alto ao mesmo tempo disputam o mesmo espaço: o anterior termina quando o próximo entra
    topo = sorted((m for m in out if m.get("layer") != "full" and (m.get("zona") == "topo" or m.get("template") == "palavra")),
                  key=lambda m: m["t0"])
    for a, b in zip(topo, topo[1:]):
        if a["t1"] > b["t0"]:
            if b["t0"] - a["t0"] >= 1.0:
                a["t1"] = b["t0"]          # o anterior sai quando o próximo entra
            else:
                atraso = a["t1"] - b["t0"]
                b["t0"] = a["t1"]          # o anterior ficaria curto demais: o próximo espera ele sair
                # os tempos internos (item marcado, clique, digitação) são relativos ao início: continuam na palavra
                b["params"] = _desloca_cues(b.get("params", {}), atraso)
    for m in out:
        if m["t1"] - m["t0"] < 1.0 and m.get("layer") != "full" and not m.get("auto") and m.get("template") not in TRANSICOES:
            log(f"   aviso: motion {m.get('id', '')} ({m.get('template')}): {m['t1'] - m['t0']:.2f}s (< 1 s, mínimo "
                f"de leitura); ignorado — estenda o 'until' ou o 'dur'")
    out = [m for m in out if m["t1"] - m["t0"] >= 1.0 or m.get("layer") == "full" or m.get("template") in TRANSICOES]
    return sorted(out, key=lambda m: m["t0"])


def plan_motion(words: list[dict], ov: dict, style: dict, total: float, busy: list[tuple]) -> list[dict]:
    out = []
    removidos = {str(x) for x in ov.get("motion_remove", [])}
    for n, req in enumerate(ov.get("motion", []), 1):
        rid = str(req.get("id") or f"m{n}")
        if str(n) in removidos or rid in removidos:
            continue
        hit = find_word(words, req["at"]) if isinstance(req.get("at"), str) else None
        if isinstance(req.get("at"), str) and not hit and ov.get("word_fixes"):
            hit = find_word(words, " ".join(fix_word(x, ov["word_fixes"]) for x in req["at"].split()))
        if isinstance(req.get("at"), str) and not hit:
            log(f"   aviso: motion {n} ({req.get('template')}): trecho '{req['at']}' não foi falado no corte final; ignorado")
            continue
        t0 = round(max((hit["t0"] - 0.1) if hit else float(req.get("at", 0)), 0), 3)
        # "until" = onde o trecho termina: a animação vai até a ÚLTIMA palavra dele
        end = find_word(words, req["until"], t0, ultima=True) if req.get("until") else None
        if req.get("until") and not end and ov.get("word_fixes"):
            end = find_word(words, " ".join(fix_word(x, ov["word_fixes"]) for x in req["until"].split()), t0,
                            ultima=True)
        t1 = round(min((end["t1"] + 0.2) if end else t0 + float(req.get("dur", 3.0)), total), 3)
        if t1 - t0 < min(float(req.get("dur", 1.5)), 1.2) and t1 >= total - 0.05:
            t0 = round(max(t1 - min(float(req.get("dur", 1.5)), 1.5), 0), 3)  # fala no fim do vídeo: recua
        if t1 - t0 < 0.5:
            log(f"   aviso: motion {n} ({req.get('template')}): janela curta demais ({t1 - t0:.2f}s); ignorado")
            continue
        item = {**MOTION_DEFAULTS.get(req.get("template", ""), {}), **{k: v for k, v in req.items() if k not in ("at", "until", "dur")}}
        item["params"] = {**MOTION_DEFAULTS.get(req.get("template", ""), {}).get("params", {}), **req.get("params", {})}
        item.update(id=rid, t0=t0, t1=t1, params=resolve_cues(item["params"], words, t0, t1, ov.get("word_fixes")))
        if item["params"].get("follow") == "hand":
            item["hand"] = True
        out.append(item)
    out = resolve_overlaps(sorted(out, key=lambda m: m["t0"]))
    if style["graphics"].get("icons") and ov.get("icons", True):
        last = -9.0
        for w in words:
            name = ICON_WORDS.get(norm(w["w"]))
            t0 = w["t0"] - 0.05
            if not name or w.get("gancho") or t0 - last < 4.5 or any(a - 1.0 < t0 < b + 0.2 for a, b in busy) \
                    or any(m["t0"] - 0.5 < t0 < m["t1"] + 0.5 for m in out):
                continue
            out.append({"id": f"i{w.get('i', 0)}", "template": "icone", "layer": "front", "t0": round(t0, 3),
                        "t1": round(min(t0 + 1.6, total), 3),
                        "params": {"icon": name, "label": w["w"].strip(".,!?:;"), "at": 0.0,
                                   "color": style["graphics"]["accent"], "y": 470}, "auto": True})
            last = t0
    return sorted(out, key=lambda m: m["t0"])


def main() -> None:
    project = Path(sys.argv[1])
    paths = project_paths(project)
    proj = load_json(paths["project"])
    edl = load_json(paths["edl"])
    tr = load_json(paths["transcript"])
    if not edl:
        raise EditorError("edl.json não encontrado. Rode analyze.py.")
    style = load_style(proj["style"], proj.get("brand"))
    # timeline persistente: o que mudou à mão em timeline.json desde a última geração vira patch (não se perde)
    paths["work"].mkdir(parents=True, exist_ok=True)
    gerada_path = paths["work"] / "timeline_gerada.json"
    gerada = load_json(gerada_path)
    capturados = revisao.capturar_edicoes(gerada, load_json(paths["timeline"]))
    if capturados:
        o = proj.setdefault("overrides", {})
        o["patches"] = revisao.juntar_patches(o.get("patches", []), capturados)
        save_json(paths["project"], proj)
        log(f"   {len(capturados)} edição(ões) manual(is) da timeline.json guardada(s) como patch (sobrevivem ao replanejamento)")
    ov = dict(proj.get("overrides", {}))
    patches = ov.get("patches", [])
    usados: set = set()
    brand = load_brand(proj.get("brand"))
    # padrões da marca: correções de palavras, CTA por estilo, ícones próprios (o pedido do usuário vence)
    ov["word_fixes"] = {**brand.get("word_fixes", {}), **ov.get("word_fixes", {})}
    if not ov.get("cta"):
        cta = brand.get("cta", {})
        ov["cta"] = cta.get(proj["style"]) or cta.get("default")
    ICON_WORDS.update({norm(k): v for k, v in brand.get("icon_words", {}).items()})
    words_src = tr["words"]
    clips = {c["id"]: c for c in proj["clips"]}
    fw, fh = FORMATS[proj.get("format", "9:16")]
    landscape = fw > fh
    cap = dict(style["captions"])
    if fw != 1080 or fh != 1920:
        # estilos são desenhados em 1080x1920: escala tamanhos e posições para o formato do projeto
        k = 0.72 if landscape else fh / 1920
        cap.update(size=int(cap["size"] * k), emph_size=int(cap["emph_size"] * k),
                   y=int(fh * (0.9 if landscape else cap["y"] / 1920)))
        if landscape:
            cap.update(words_per_page=cap["words_per_page"] + 2, max_chars=int(cap["max_chars"] * 1.8))
    cap.update(ov.get("caption", {}))
    zcfg = {**style["zoom"], **ov.get("zoom", {})}
    zoom_sig = revisao.hk(zcfg)
    # zoom já decidido para um plano (mesmo id) é mantido: um corte não muda o enquadramento do resto do vídeo
    zoom_ant = {s_["id"]: (s_["zoom0"], s_["zoom1"]) for s_ in (gerada or {}).get("shots", [])
                if s_.get("id") and (gerada or {}).get("revisao", {}).get("zoom_sig") == zoom_sig and not s_.get("_patch")}

    # 1) planos com tempo na timeline final + zoom
    # velocidade da fala (ex.: 1.15 = 15% mais rápido, sem mudar o tom); duração quantizada em quadros (sem deriva)
    speed = float(ov.get("speed") or brand.get("speed") or style.get("speed", 1.0))
    if ov.get("sem_cortes"):
        speed = 1.0  # vídeo já editado pelo cliente: ritmo original
    plan_shots, t = [], 0.0
    for n, s in enumerate(shots(edl["segments"], words_src, style)):
        dur = round(round((s["out"] - s["in"]) / speed * 30) / 30, 4)
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
        sid = f"{'g' if s.get('gancho') else ''}s{s['clip']}_{int(round(s['in'] * 1000))}"
        if sid in zoom_ant:
            z0, z1 = zoom_ant[sid]
        plan_shots.append({"id": sid, "clip": s["clip"], "src": clips[s["clip"]]["path"], "in": s["in"], "out": s["out"],
                           "t0": round(t, 3), "t1": round(t + dur, 3), "zoom0": round(z0, 3), "zoom1": round(z1, 3),
                           "cx": 0.5, "cy": 0.42, "speed": speed, **({"gancho": True} if s.get("gancho") else {})})
        t += dur
    total = round(t, 3)
    plan_shots = revisao.aplicar_patches("shots", plan_shots, patches, usados)

    # 2) palavras na timeline final (com correções do usuário)
    fixes = ov.get("word_fixes", {})
    words = []
    dropped = set(edl["dropped"])
    for sh in plan_shots:
        for idx, w in enumerate(words_src):
            if w["clip"] == sh["clip"] and sh["in"] <= (w["t0"] + w["t1"]) / 2 < sh["out"]:
                if idx in dropped:
                    continue
                words.append({"w": fix_word(w["w"], fixes), "t0": round(sh["t0"] + max(w["t0"] - sh["in"], 0) / speed, 3),
                              "t1": round(min(sh["t0"] + (w["t1"] - sh["in"]) / speed, sh["t1"]), 3), "emph": False,
                              "i": idx, **({"gancho": True} if sh.get("gancho") else {})})
    # palavras do corte de gancho: aparecem na legenda, mas gatilhos, ícones, B-roll e palavras atrás usam o lugar
    # original da fala (não disparam duas vezes)
    words_fala = [w for w in words if not w.get("gancho")]

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
        cap_pages.append({"id": f"p{words[p[0]]['i']}", "t0": t0, "t1": round(min(nxt, words[p[-1]]["t1"] + 0.6), 3),
                          "words": p})

    # 5) palavras atrás da pessoa (fora da janela do gancho e do CTA)
    gfx_hook_end = 2.9 if style["graphics"]["hook_banner"] else (4.3 if style["graphics"]["lower_third"] else 0.3)
    cta_start = max(total - 3.2, 0)
    bcfg = dict(style["behind"])
    if landscape:
        bcfg["size"] = int(bcfg["size"] * 0.6)
    behind = []
    enabled = bcfg["enabled"] if ov.get("behind_enabled") is None else ov["behind_enabled"]
    removed = {norm(x) for x in ov.get("behind_remove", [])}
    if enabled:
        cands = sorted((i for i, w in enumerate(words) if w["emph"] and norm(w["w"]) not in removed and not w.get("gancho")),
                       key=lambda i: -score_word(words[i]["w"]))
        for i in cands:
            w = words[i]
            text = apply_case(w["w"].strip(".,!?:;"), bcfg["case"])
            too_close = any(abs(w["t0"] - b["t0"]) < 4.0 or b["text"] == text for b in behind)
            if w["t0"] < gfx_hook_end or w["t0"] + 1.0 > cta_start or too_close or len(behind) >= bcfg["max"]:
                continue
            behind.append({"id": f"b{w['i']}", "text": text, "t0": round(max(w["t0"] - 0.08, 0), 3),
                           "t1": round(min(w["t0"] + 1.9, total), 3)})
        for req in ov.get("behind_add", []):
            hit = next((w for w in words_fala if norm(w["w"]) == norm(req.get("at", req["text"]))), None)
            if hit:
                behind.append({"id": f"b{hit['i']}", "text": apply_case(req["text"], bcfg["case"]),
                               "t0": round(max(hit["t0"] - 0.08, 0), 3),
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
        for w in words_fala:
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
                broll.append({"id": f"r{w['i']}", "src": b["path"], "kind": b["kind"], "t0": w["t0"],
                              "t1": round(w["t0"] + dur, 3),
                              "src_in": round(src_in, 2), "mode": rcfg["mode"], "cue": w["w"]})
                k += 1
        drop = set(ov.get("broll_remove", []))
        broll = [b for n, b in enumerate(broll, 1) if n not in drop]
    for k_req, req in enumerate(ov.get("broll_at", []), 1):
        hit = next((w for w in words_fala if norm(w["w"]) == norm(req["at"].split()[0])), None)
        src = next((b for b in pool if b["id"] == req.get("src")), None) or (pool[0] if pool else None)
        if hit and src:
            broll.append({"id": f"ra{k_req}", "src": src["path"], "kind": src["kind"], "t0": hit["t0"],
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
    logo = brand.get("logo", {})
    if logo.get("watermark") and logo.get("file"):
        graphics.append({"type": "logo", "text": str(Path(brand["_dir"]) / logo["file"]), "t0": 0.0, "t1": total,
                         "position": logo.get("position", "top-right"), "opacity": logo.get("opacity", 0.85)})
    if g["cta"]:
        graphics.append({"type": "cta", "text": ov.get("cta") or DEFAULT_CTA.get(style["name"], "SEGUE PRA VER MAIS"), "t0": round(cta_start, 3), "t1": total})

    # 8) motion graphics: pedidos do usuário/Claude + ícones automáticos
    busy = [(0.0, gfx_hook_end), (cta_start, total)] + [(b["t0"] - 0.3, b["t1"] + 0.3) for b in behind] \
        + [(b["t0"], b["t1"]) for b in broll if b["mode"] != "full"]
    motion = plan_motion(words, ov, style, total, busy)
    # mapa de gatilhos (frase, palavra, dinheiro, enumeração -> efeito + som + impacto); pedido explícito vence
    trig_sfx, fx = [], []
    for req in ov.get("fx_requests", []):
        hit = find_word(words, req["at"]) if req.get("at") else None
        if hit:
            fx.append({"type": req["type"], "t": round(hit["t0"], 3)})
    if ov.get("triggers", True):
        import triggers
        manual = [(m["t0"], m["t1"]) for m in motion if not m.get("auto")]
        auto, trig_sfx, trig_fx = triggers.apply(words_fala, triggers.load_rules(brand), style["name"], total,
                                                 brand.get("cta_keywords", ["PRODUTO"]), busy + manual)
        # gatilho automático não repete um bloco que você já pediu a menos de 6 s (ex.: o mesmo preço dito 2 vezes)
        auto = [m for m in auto if not any(x["template"] == m["template"] and abs(x["t0"] - m["t0"]) < 6
                                           for x in motion if not x.get("auto"))]
        for m in auto:
            m.update({k: v for k, v in MOTION_DEFAULTS.get(m["template"], {}).items() if k not in m})
            wi = min(words_fala, key=lambda w_: abs(w_["t0"] - m["t0"]))["i"] if words_fala else 0
            m["id"] = f"a_{m['template']}_{wi}"
        motion = resolve_overlaps(sorted(motion + auto, key=lambda m: m["t0"]))
        fx += trig_fx
    if ov.get("composicoes"):  # composições de referência (composicoes.py): pedido explícito, vence os automáticos
        import composicoes
        c_mo, c_fx, c_sfx, c_av = composicoes.expandir(ov["composicoes"], words, total, ov)
        for m in c_mo:
            m["params"] = {**MOTION_DEFAULTS.get(m["template"], {}).get("params", {}), **m["params"]}
        for x in c_av:
            log(f"   aviso: {x}")
        janelas_c = [(m["t0"] - 0.2, m["t1"] + 0.2) for m in c_mo]
        motion = [m for m in motion if not (m.get("auto") and any(m["t0"] < b_ and m["t1"] > a_ for a_, b_ in janelas_c))]
        motion = resolve_overlaps(sorted(motion + c_mo, key=lambda m: m["t0"]))
        fx += c_fx
        trig_sfx = trig_sfx + c_sfx
    direcao = None
    if ov.get("direcao") == "premium":  # seletor por intenção (seletor.py): decide cena a cena, com orçamento
        import seletor
        direcao = seletor.direcionar(words, motion, style["name"], total, ov)
        for m in direcao["motion"]:
            m.update({k: v for k, v in MOTION_DEFAULTS.get(m["template"], {}).items() if k not in m})
            m["params"] = {**MOTION_DEFAULTS.get(m["template"], {}).get("params", {}), **m["params"]}
        motion = resolve_overlaps(sorted(motion + direcao["motion"], key=lambda m: m["t0"]))
        fx += direcao["fx"]
        trig_sfx = trig_sfx + direcao["sfx"]
    motion = revisao.aplicar_patches("motion", motion, patches, usados)
    if motion and not perfil()["motion"]:
        log(f"   {len(motion)} animação(ões) puladas: elas fazem parte do Pacote Motion 3D (não instalado)")
        motion, trig_sfx = [], []
    # impacto automático: chicote + whoosh na entrada de animações de tela cheia
    # id ligado ao da animação: uma animação nova antes não renumera os chicotes seguintes (trechos continuam HIT);
    # não duplica o chicote que uma composição já pôs na entrada
    fx += [{"type": "whip", "t": round(max(m["t0"] - 0.05, 0), 3), "id": f"fx_whip_{m['id']}"}
           for m in motion if m.get("layer") == "full"
           and not any(f_["type"] == "whip" and abs(f_["t"] - m["t0"]) < 0.3 for f_ in fx)]
    # palavra gigante não aparece por cima de animação de tela cheia
    fulls = [(m["t0"], m["t1"]) for m in motion if m.get("layer") == "full"]
    behind = [b for b in behind if not any(b["t0"] < t1 and b["t1"] > t0 for t0, t1 in fulls)]
    # palavra automática atrás da pessoa cede lugar a texto grande pedido no mesmo instante (não sobrepõe)
    textos = [(m["t0"] - 0.3, m["t1"] + 0.3) for m in motion if m.get("template") != "icone"]
    behind = [b for b in behind if not any(b["t0"] < t1 and b["t1"] > t0 for t0, t1 in textos)]
    # faixas de texto (gancho, CTA, título) somem durante animação de tela cheia: a animação redesenha o quadro
    # inteiro e o texto por cima atrapalha. Fica o maior pedaço livre (mín. 0,6 s); o CTA que ficaria todo
    # coberto vai para dentro da animação (params.cta), quando ela aceita.
    kept = []
    # o CTA do estilo também sai enquanto um bloco de CTA animado (botão, comentário) está na tela: nada de CTA duplo
    cta_blocos = [(m["t0"], m["t1"]) for m in motion if m.get("template") in ("botao_cta", "comentario")]
    for gr in graphics:
        wins = fulls + (cta_blocos if gr["type"] == "cta" else [])
        if gr["type"] not in ("hook", "cta", "lower_third", "chapter") or not wins:
            kept.append(gr)
            continue
        free, start = [], gr["t0"]
        for a, b in sorted(wins):
            if b <= start or a >= gr["t1"]:
                continue
            if a > start:
                free.append((start, a))
            start = max(start, b)
        if start < gr["t1"]:
            free.append((start, gr["t1"]))
        best = max(free, key=lambda w: w[1] - w[0], default=None)
        if best and best[1] - best[0] >= 0.6:
            kept.append({**gr, "t0": round(best[0], 3), "t1": round(best[1], 3)})
        elif gr["type"] == "cta":
            for m in motion:
                if m.get("layer") == "full" and m["t0"] < gr["t1"] and m["t1"] > gr["t0"]:
                    m["params"].setdefault("cta", gr["text"])
    graphics = kept
    nch = 0
    for gr in graphics:
        if gr["type"] == "chapter":
            nch += 1
        gr["id"] = f"g_{gr['type']}" + (str(nch) if gr["type"] == "chapter" else "")

    # 9) efeitos sonoros (sutis, abaixo da voz)
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
    if s["whoosh"]:
        sfx += [{"type": "whoosh", "t": max(m["t0"] - 0.1, 0), "gain": s["whoosh"] * 0.8} for m in motion
                if m.get("layer") == "full"]
    if s["pop"]:
        sfx += [{"type": "pop", "t": m["t0"] + 0.05, "gain": s["pop"] * 0.8} for m in motion if m.get("template") == "icone"]
    # som de venda em cada notificação da pilha de vendas; tick nas linhas da tabela
    for m in motion:
        if m.get("template") == "vendas":
            ev = m["params"].get("every", 0.45)
            sfx += [{"type": "venda", "t": round(m["t0"] + 0.15 + i * ev, 3), "gain": 0.5}
                    for i in range(len(m["params"].get("items", [])))]
    if s.get("motion", 1.0):
        sfx += motion_sfx(motion, float(s.get("motion", 1.0)))
    sfx += trig_sfx
    sfx.sort(key=lambda x: x["t"])

    behind = revisao.aplicar_patches("behind", behind, patches, usados)
    broll = revisao.aplicar_patches("broll", broll, patches, usados)
    graphics = revisao.aplicar_patches("graphics", graphics, patches, usados)
    for k_fx, f_ in enumerate(fx):
        f_.setdefault("id", f"fx_{f_['type']}_{k_fx}")
    fx = revisao.aplicar_patches("fx", fx, patches, usados)
    revisao.avisar_orfaos(patches, usados)
    musica = ov.get("music") or brand.get("music")
    if isinstance(musica, dict) and musica.get("auto"):
        # trilha sintetizada (trilha.py) na duração exata do vídeo e no ritmo da fala; em cache por pedido
        import trilha
        musica = trilha.trilha_do_projeto(paths["work"], musica, total, words, style["name"])
        a_ = musica["auto"]
        log(f"   trilha{' (IA)' if a_.get('motor') == 'ia' else ''}: {a_['clima']} {a_['bpm']:.0f} BPM "
            f"({a_['palavras_por_s'] or '?'} palavras/s), "
            f"{a_['dur']:.1f} s, volume {musica['volume']}")
    timeline = {
        "style": style["name"], "w": fw, "h": fh, "fps": 30, "duration": total, "format": proj.get("format", "9:16"),
        "shots": plan_shots, "words": words, "captions": {"cfg": cap, "pages": [
            pg for pg in cap_pages if not any(  # o card de pergunta já mostra o que está sendo dito
                m["template"] in ("pergunta", "final", "transcricao", "botao_cta") and m["params"].get("esconde_legenda", True)
                and m["t0"] - 0.05 <= (pg["t0"] + pg["t1"]) / 2 <= m["t1"] for m in motion if m.get("template"))]},
        "behind": behind, "behind_cfg": bcfg, "broll": broll, "graphics": graphics, "graphics_cfg": g,
        "sfx": sfx, "grade": style["grade"],
        "audio": {**style["audio"], "voz": ov["voz"]} if ov.get("voz") else style["audio"],
        "music": musica, "motion": motion, "brand": proj.get("brand"), "fx": fx,
        "revisao": {"zoom_sig": zoom_sig, "patches_aplicados": len(usados)},
    }
    if direcao:
        timeline["direcao"] = {"relatorio": direcao["relatorio"], "paleta": direcao["paleta"]}
    if ov.get("imagem"):  # correção de imagem/estabilização (só aparece quando pedida: timelines antigas não mudam)
        timeline["imagem"] = ov["imagem"]
    save_json(paths["timeline"], timeline)
    save_json(gerada_path, timeline)
    log(f"OK: timeline {total:.1f}s | {len(plan_shots)} planos | {len(cap_pages)} legendas | "
        f"{len(behind)} atrás da pessoa | {len(broll)} B-roll | {len(graphics)} gráficos | {len(motion)} motion | {len(sfx)} SFX")


if __name__ == "__main__":
    main_guard(main)
