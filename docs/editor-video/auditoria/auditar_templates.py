#!/usr/bin/env python3
"""Auditoria dos templates de motion: render isolado de cada um (mesmo renderizador do editor), tempo por quadro,
cobertura da tela, ocupação da zona do rosto, determinismo (lint) e folha de contato para a revisão visual.

  python docs/editor-video/auditoria/auditar_templates.py <pasta_saida> [--frames-dir <frames_*/ com plate/cut>]
         [--so palavra_chave,profundidade]

Saída: <pasta_saida>/resultado.json + folha_<n>.jpg (8 templates por folha, 4 instantes cada, sobre quadro real).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
SK = REPO / ".claude" / "skills" / "editor-video"
TPL = SK / "assets" / "motion" / "templates"
RENDERER = SK / "scripts" / "motion_render.mjs"
W, H, FPS, DUR = 1080, 1920, 30, 2.2
INSTANTES = (0.25, 0.7, 1.2, 1.9)

# parâmetros de exemplo (o que um pedido típico mandaria); mídia = quadro real do vídeo de teste
AMOSTRA = {
    "anotacao": {"marks": [{"kind": "circle", "from": [0.3, 0.3], "to": [0.7, 0.5], "at": 0.2},
                           {"kind": "arrow", "from": [0.8, 0.8], "to": [0.6, 0.55], "at": 0.6}]},
    "botao_cta": {"text": "TOQUE NO CARRINHO", "click_at": 1.2},
    "camadas": {"graphic": "OFERTA", "labels": {"fundo": "fundo", "elementos": "texto", "voce": "você"}},
    "card_fogo": {"title": "PROMOÇÃO", "sub": "só hoje", "x": 0.5, "y": 0.6},
    "carimbo": {"text": "APROVADO", "at": 0.2},
    "carrossel3d": {"items": [{"image": "@img"}, {"self": True}, {"image": "@img"}], "title": "bastidores"},
    "cenario": {"scenes": [{"image": "@img", "at": 0.0, "label": "estúdio"}]},
    "checklist": {"title": "2 sabores", "items": [{"text": "Menta", "at": 0.3}, {"text": "Tutti-frutti", "at": 0.9}]},
    "clones": {"copies": [{"label": "eu", "look": "normal"}, {"label": "eu de novo", "look": "neon"}]},
    "comentario": {"texto": "EU QUERO", "chamada": "comenta EU QUERO"},
    "cronometro": {"seconds": 420, "label": "pronto em"},
    "dividida": {},
    "documentario": {"image": "@img", "focus": [0.5, 0.4], "title": "o produto",
                     "marks": [{"x": 0.6, "y": 0.5, "label": "aqui", "at": 0.6, "kind": "circle"}]},
    "editor_ia": {"pedido": "corta as pausas"},
    "empilha": {"itens": [{"text": "RÁPIDO", "at": 0.2}, {"text": "BARATO", "at": 0.7}, {"text": "GOSTOSO", "at": 1.2}]},
    "estudio3d": {"wall_text": "MENTOS"},
    "etiqueta": {"text": "ACHADINHO", "titulo": "achado do dia"},
    "final": {"rotulo": "COMENTA", "palavra": "EU QUERO", "nome": "@marca"},
    "giro": {"texts": ["ANTES", "DEPOIS"], "labels": ["antes", "depois"]},
    "hud": {"rosto": [], "nome": "MARCEL", "rotulo": "CRIADOR"},
    "icone": {"icon": "flame", "label": "quente", "x": 540, "y": 700},
    "infografico": {"stats": [{"value": 15, "prefix": "R$ ", "label": "só hoje", "at": 0.2}]},
    "luz": {"at": 0.2, "dur": 1.2},
    "manchete": {"linhas": ["CHICLETE", "MENTOS UP2U"], "destaque": ["UP2U"], "rotulo": "ACHADINHO"},
    "maos": {"maos": [], "etiqueta": "PRODUTO"},
    "mapa": {"place": "Centro", "poi": "Loja", "time_label": "4 min a pé"},
    "moldura": {"title": "Por que funciona", "items": [{"text": "Rápido", "at": 0.4}, {"text": "Barato", "at": 0.9}]},
    "notificacao": {"app": "Loja", "title": "Pedido confirmado", "text": "Mentos UP2U · R$ 15,00"},
    "objeto3d": {"text": "MENTOS", "x": 0.5, "y": 0.35},
    "onda_audio": {"title": "pausas cortadas"},
    "palavra": {"text": "GOSTOSO."},
    "palavra_chave": {"text": "GOSTOSO", "emoji": "😋", "cor": "#F472B6", "cor2": "#FDA4AF", "y": 0.3},
    "passa_mao": {},
    "pedacos": {},
    "pergunta": {"text": "Você já provou esse chiclete?"},
    "player": {"items": [{"image": "@img"}], "titulo": "antes"},
    "pontos": {},
    "profundidade": {"texto": "MENTOS", "movimento": "dolly", "intensidade": 0.8},
    "proibido": {"icones": ["film", "scissors", "layers"]},
    "quadrinho": {"paineis": [{"ilustracao": "menta", "rotulo": "MENTA", "at": 0.2},
                              {"ilustracao": "frutas", "rotulo": "TUTTI", "at": 0.8}]},
    "recorte": {},
    "tabela": {"left": "Antes", "right": "Depois", "rows": [{"l": "caro", "r": "barato", "at": 0.3}]},
    "tela_ia": {"steps": [{"do": "type", "text": "faz meu roteiro", "at": 0.2}, {"do": "reply", "text": "Pronto!", "at": 1.0}]},
    "tomadas": {"itens": [{"rotulo": "TOMADA 1", "frase": "oi"}, {"rotulo": "TOMADA 2", "frase": "olá", "melhor": True}]},
    "transcricao": {},
    "vendas": {"items": [{"title": "Venda aprovada", "text": "R$ 15,00"}, {"title": "Venda aprovada", "text": "R$ 15,00"}]},
    "visor": {"rotulo": "BRUTO"},
}
LINT = {"setTimeout/setInterval": r"\bset(Timeout|Interval)\s*\(", "requestAnimationFrame": r"requestAnimationFrame",
        "animação CSS automática": r"@keyframes|animation\s*:", "aleatório sem semente": r"Math\.random\(\)"}


def plan_defaults() -> dict:
    sys.path.insert(0, str(SK / "scripts"))
    import motion as mo
    import plan
    return {"defaults": plan.MOTION_DEFAULTS, "webgl": mo.WEBGL}


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    frames = Path(sys.argv[sys.argv.index("--frames-dir") + 1]).resolve() if "--frames-dir" in sys.argv else None
    so = sys.argv[sys.argv.index("--so") + 1].split(",") if "--so" in sys.argv else None
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    info = plan_defaults()
    video = None
    img = None
    if frames:
        dst = work / "frames"
        if not dst.exists():
            shutil.copytree(frames, dst, ignore=shutil.ignore_patterns("prof", "*.json"))
        n = len(list((dst / "plate").glob("*.jpg")))
        video = {"plate": "/work/frames/plate/%05d.jpg", "cut": "/work/frames/cut/%05d.png",
                 "bg": "/work/frames/bg/%05d.jpg" if (dst / "bg").exists() else None, "count": n}
        img = "/work/frames/plate/00030.jpg"
    res = []
    for f in sorted(TPL.glob("*.html")):
        nome = f.stem
        if so and nome not in so:
            continue
        fonte = f.read_text(encoding="utf-8")
        d = {"template": nome, **{k: v for k, v in info["defaults"].get(nome, {}).items() if k in ("layer", "needs_video", "zona")}}
        d["lint"] = [k for k, rx in LINT.items() if re.search(rx, fonte)]
        params = json.loads(json.dumps(AMOSTRA.get(nome, {})).replace('"@img"', json.dumps(img or "")))
        params["format"] = {"w": W, "h": H}
        params.setdefault("cues", {})
        if d.get("needs_video"):
            if not video:
                d["status"] = "pulado (precisa de --frames-dir)"
                res.append(d)
                continue
            params["video"] = video
        if nome == "profundidade" and video:
            sys.path.insert(0, str(SK / "scripts"))
            import motion_dados_profundidade as mdp
            mdp.enriquecer("profundidade", params, {}, work=work)
        opaco = d.get("layer") == "full"
        clip = out / f"{nome}.mov"
        job = {"page": f"/templates/{nome}.html", "out": str(clip), "w": W, "h": H, "fps": FPS, "duration": DUR,
               "params": params, "opaque": opaco, "webgl": nome in info["webgl"],
               "roots": {"/": str(SK / "assets" / "motion"), "/fonts/": str(SK / "assets" / "fonts"), "/work/": str(work)}}
        jf = out / f"job_{nome}.json"
        jf.write_text(json.dumps(job, ensure_ascii=False))
        t0 = time.time()
        p = subprocess.run(["node", str(RENDERER), str(jf)], capture_output=True, text=True)
        d["segundos"] = round(time.time() - t0, 1)
        d["ms_por_quadro"] = round(1000 * d["segundos"] / (DUR * FPS))
        if p.returncode != 0:
            d["status"] = "falhou"
            d["erro"] = (p.stderr or p.stdout)[-400:]
            res.append(d)
            continue
        d["status"] = "ok"
        # alfa de 4 instantes: quanto da tela ocupa e quanto cai na zona típica do rosto (centro-alto)
        cob, rosto = [], []
        for t in INSTANTES:
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", str(clip), "-frames:v", "1", "-vf",
                                "scale=108:192,format=rgba,alphaextract,format=gray", "-f", "rawvideo", "-"],
                               capture_output=True)
            a = np.frombuffer(r.stdout, np.uint8)
            if a.size == 108 * 192:
                a = a.reshape(192, 108) > 127
                cob.append(float(a.mean()))
                rosto.append(float(a[38:96, 27:81].mean()))
        d["cobertura"] = round(max(cob), 3) if cob else None
        d["zona_rosto"] = round(max(rosto), 3) if rosto else None
        # folha: 4 instantes sobre o quadro real (ou cinza)
        fundo = ["-i", str(work / "frames" / "plate" / "00030.jpg")] if frames else ["-f", "lavfi", "-i", f"color=0x3a3a44:s={W}x{H}"]
        partes = []
        for k, t in enumerate(INSTANTES):
            partes.append(f"[{k + 1}:v]scale=216:384[c{k}];[b{k}][c{k}]overlay=0:0[o{k}]")
        ins = []
        for t in INSTANTES:
            ins += ["-ss", f"{t}", "-i", str(clip)]
        filtro = f"[0:v]scale=216:384,split=4" + "".join(f"[b{k}]" for k in range(4)) + ";" + ";".join(partes) \
            + ";" + "".join(f"[o{k}]" for k in range(4)) + f"hstack=4,drawtext=text='{nome}':x=8:y=8:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6[v]"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *fundo, *ins, "-filter_complex", filtro, "-map", "[v]",
                        "-frames:v", "1", str(out / f"tira_{nome}.jpg")])
        clip.unlink(missing_ok=True)
        res.append(d)
        print(f"{nome:<14} {d['status']:<7} {d['ms_por_quadro']:>5} ms/q  cob {d['cobertura']}  rosto {d['zona_rosto']}  lint {d['lint']}")
    (out / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    tiras = sorted(out.glob("tira_*.jpg"))
    for n in range(0, len(tiras), 8):
        grupo = tiras[n:n + 8]
        args = sum((["-i", str(t)] for t in grupo), [])
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex",
                        "".join(f"[{i}:v]" for i in range(len(grupo))) + f"vstack={len(grupo)}" if len(grupo) > 1 else "null",
                        "-frames:v", "1", str(out / f"folha_{n // 8 + 1}.jpg")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
