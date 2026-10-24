"""Dados do template profundidade (2.5D): mapas de profundidade por quadro (e placa limpa opcional), 100% local.

Chamado por motion.render_clip via enriquecer(...). Usa os quadros que o render_clip já extraiu da janela
(plate = imagem inteira, cut = pessoa com transparência) e grava, na mesma pasta:
  prof/%05d.png      profundidade de cada quadro, 540 px de largura (branco = perto). Com o Depth Anything
                     instalado: o modelo roda a cada PASSO quadros (o mapa vale para os seguintes); sem ele, o
                     modo heurístico usa a máscara da pessoa do próprio quadro, alargada para incluir mão e o que
                     ela segura (produto), e o cenário em degradê.
  placa.jpg          só com params.fundo = "limpo": cenário sem a pessoa (câmera em tripé, nada na mão)
params["prof_seq"], params["placa"] e params["profundidade_modo"] ("modelo" | "heuristica") chegam ao template.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from common import log

PASSO = 4          # com o modelo: 1 inferência a cada 4 quadros (~0,4 s cada na CPU)
LARGURA = 540


def _alfa(fdir: Path, i: int, forma) -> np.ndarray:
    c = cv2.imread(str(fdir / "cut" / f"{i:05d}.png"), cv2.IMREAD_UNCHANGED)
    if c is None or c.ndim < 3 or c.shape[-1] != 4:
        return np.zeros(forma, np.float32)
    return c[..., 3].astype(np.float32) / 255


def enriquecer(tpl, params, item, work: Path, **_):
    if tpl != "profundidade" or not params.get("video"):
        return
    import profundidade
    rel = params["video"]["plate"].split("/work/", 1)[1].rsplit("/plate/", 1)[0]
    fdir = work / rel
    limpo = params.get("fundo") == "limpo"
    feito = fdir / f"profundidade{'_limpo' if limpo else ''}.json"
    if not feito.exists():
        n = params["video"]["count"]
        pdir = fdir / "prof"
        pdir.mkdir(exist_ok=True)
        modo, ultimo = profundidade.modo(), None
        for i in range(1, n + 1):
            q = cv2.imread(str(fdir / "plate" / f"{i:05d}.jpg"))
            if q is None:
                continue
            h, w = q.shape[:2]
            pq = cv2.resize(q, (LARGURA, round(h * LARGURA / w)), interpolation=cv2.INTER_AREA)
            a = cv2.resize(_alfa(fdir, i, (h, w)), (pq.shape[1], pq.shape[0]), interpolation=cv2.INTER_AREA)
            if modo == "modelo":
                if ultimo is None or (i - 1) % PASSO == 0:
                    ultimo, modo = profundidade.mapa(pq)
                d = ultimo
            else:
                d = profundidade.heuristica_retrato(pq, a)
            cv2.imwrite(str(pdir / f"{i:05d}.png"), (d * 255).astype(np.uint8))
        if limpo:
            idx = sorted({round(k * (n - 1) / 23) + 1 for k in range(min(24, n))})
            qs = [cv2.imread(str(fdir / "plate" / f"{i:05d}.jpg")) for i in idx]
            al = [_alfa(fdir, i, qs[0].shape[:2]) for i in idx]
            cv2.imwrite(str(fdir / "placa.jpg"), profundidade.placa_limpa(qs, al), [cv2.IMWRITE_JPEG_QUALITY, 93])
        feito.write_text(json.dumps({"modo": modo}))
        log(f"   profundidade: {n} mapas ({modo}){' + placa limpa' if limpo else ''}")
    params["prof_seq"] = f"/work/{rel}/prof/%05d.png"
    if limpo:
        params["placa"] = f"/work/{rel}/placa.jpg"
    params["profundidade_modo"] = json.loads(feito.read_text())["modo"]
