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


def lugar_do_texto(alfas: list[np.ndarray], texto: str, W: int, H: int, fator: float = 0.47) -> dict | None:
    """Onde a palavra cabe MAIOR no cenário: ocupação MÉDIA da pessoa no trecho (quem se mexe muito ainda deixa parede
    livre a maior parte do tempo) até 18% da caixa do texto. Sem lugar livre, o de menor ocupação no tamanho que cabe
    em 88% da largura. Busca em 108x192 com imagem integral. Devolve x, y (topo) e tamanho em px."""
    if not texto or not alfas:
        return None
    import cv2
    w, h = 108, 192
    media = np.mean([cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA) for a in alfas], axis=0)
    ocupa = cv2.dilate(media, np.ones((3, 3), np.uint8))
    ii = np.pad(ocupa.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    n = max(len(texto), 1)

    def busca(fs: int, limite: float | None):
        tw, th = int(n * fs * fator * w / W) + 2, int(fs * 0.95 * h / H) + 1
        if tw >= w - 2:
            return None
        melhor = None
        for y in range(int(h * 0.06), int(h * 0.58) - th):
            for x in range(2, w - tw - 2, 2):
                ocup = (ii[y + th, x + tw] - ii[y, x + tw] - ii[y + th, x] + ii[y, x]) / (tw * th)
                if limite is not None and ocup > limite:
                    continue
                custo = ocup * 4 + abs((x + tw / 2) - w / 2) / w * 0.6 + y / h * 0.4   # livre, centrado, alto
                if melhor is None or custo < melhor[0]:
                    melhor = (custo, x, y)
        return melhor

    for fs in range(380, 96, -12):
        m = busca(fs, 0.18)
        if m:
            return {"texto_x": round(m[1] * W / w), "texto_y": round(m[2] * H / h), "texto_tam": fs}
    fs = max(96, min(300, int(W * 0.88 / (n * fator))))
    m = busca(fs, None)
    return {"texto_x": round(m[1] * W / w), "texto_y": round(m[2] * H / h), "texto_tam": fs} if m else None


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
    if params.get("texto") and "texto_tam" not in params:
        import hashlib
        lugar = fdir / f"lugar_{hashlib.sha1((params['texto'] + Path(__file__).read_text(encoding='utf-8')).encode()).hexdigest()[:10]}.json"
        if not lugar.exists():
            n = params["video"]["count"]
            idx = sorted({round(k * (n - 1) / 15) + 1 for k in range(min(16, n))})
            forma = cv2.imread(str(fdir / "plate" / "00001.jpg")).shape[:2]
            al = [_alfa(fdir, i, forma) for i in idx]
            lugar.write_text(json.dumps(lugar_do_texto(al, params["texto"], forma[1], forma[0])))
        params.update(json.loads(lugar.read_text()) or {})
    params["prof_seq"] = f"/work/{rel}/prof/%05d.png"
    if limpo:
        params["placa"] = f"/work/{rel}/placa.jpg"
    params["profundidade_modo"] = json.loads(feito.read_text())["modo"]
