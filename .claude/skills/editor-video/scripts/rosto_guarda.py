"""Rosto nunca tampado: mede, quadro a quadro, quanto cada animação cobre olhos e boca, e escolhe sozinho a menor
mudança (descer, subir, ir para o lado, diminuir) que libera o rosto. O QA mede de novo depois e reprova o que
ainda cobrir.

Entrada: clipe RGBA da animação (work/motion/clip_*.mov), rosto por quadro (mask_stats: caixa do MediaPipe a cada 3
quadros) e o recuo (a cena encolhe e desce quando há card no topo — o rosto vai junto).
Saída por animação: {"s": escala, "x": px, "y": px} para o overlay (0,0,1 = sem mudança) + medidas antes/depois.
Tudo em baixa resolução (270x480) para custar frações de segundo por animação.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

BW, BH = 270, 480          # resolução de medida (9:16); 16:9 inverte
VERSAO = 13                 # muda quando a regra de decisão muda (invalida o cache das decisões)
LIMITE = 0.04              # fração da zona do rosto coberta que já conta como "tampou"
VISIVEL = 0.25             # alfa a partir do qual já se vê (letra entrando meio transparente também tampa)
TOLERA_QUADROS = 1         # rosto sagrado: só 1 quadro de passagem (entrada/saída) é tolerado
# candidatos: (escala, âncora x 0..1, deslocamento y em fração da altura); ordem = preferência (menos mudança)
_PASSOS = sorted({round(k * 0.02, 2) for k in range(-18, 19)} - {0.0}, key=lambda d: (abs(d), -d))
CANDIDATOS = [(1.0, 0.5, dy) for dy in _PASSOS] + \
             [(s, ax, dy) for s in (0.85, 0.72, 0.6) for ax in (0.5, 0.0, 1.0) for dy in (0.0, *_PASSOS[::2])]


def zona_do_rosto(face: list[float] | None, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Caixa do MediaPipe (x, y, largura, altura normalizados) -> olhos até o queixo, em px."""
    if not face:
        return None
    x, y, fw, fh = face
    return (int((x + 0.1 * fw) * w), int((y + 0.22 * fh) * h), int((x + 0.9 * fw) * w), int((y + 1.02 * fh) * h))


def zona_por_pontos(p: dict, face: list[float], w: int, h: int) -> tuple:
    """Olhos e boca de verdade (pontos do detector) -> (zona do rosto, faixa dos olhos, caixa da boca) em px."""
    lx, ly, rx, ry = p["olhos"]
    mx, my = p["boca"]
    fw = max(face[2] if face else abs(rx - lx) * 2.5, abs(rx - lx) * 1.6)
    olho_y, dist = (ly + ry) / 2, max(my - (ly + ry) / 2, 0.02)
    olhos = (int((min(lx, rx) - 0.22 * fw) * w), int((olho_y - 0.45 * dist) * h),
             int((max(lx, rx) + 0.22 * fw) * w), int((olho_y + 0.4 * dist) * h))
    boca = (int((mx - 0.2 * fw) * w), int((my - 0.3 * dist) * h), int((mx + 0.2 * fw) * w), int((my + 0.45 * dist) * h))
    zona = (min(olhos[0], boca[0]), olhos[1], max(olhos[2], boca[2]), boca[3])
    return zona, olhos, boca


def _partes_da_caixa(c: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    """Sem os pontos do detector: olhos e boca estimados dentro da zona (proporções de rosto de frente)."""
    x0, y0, x1, y1 = c
    fw, fh = x1 - x0, y1 - y0
    return [(x0 + int(0.04 * fw), y0 + int(0.08 * fh), x1 - int(0.04 * fw), y0 + int(0.36 * fh)),   # olhos
            (x0 + int(0.25 * fw), y0 + int(0.58 * fh), x1 - int(0.25 * fw), y0 + int(0.86 * fh))]   # boca


def _uniao(caixas: list) -> tuple:
    return (min(c[0] for c in caixas), min(c[1] for c in caixas), max(c[2] for c in caixas), max(c[3] for c in caixas))


def rostos_por_quadro(stats: list[dict], a: int, b: int, w: int = BW, h: int = BH, alcance: int = 60) -> list:
    """Rosto de cada quadro [a, b). O detector roda a cada 3 quadros e falha com rosto muito perto/cortado na borda;
    rosto não teletransporta: entre duas detecções (até `alcance` quadros = 2 s) interpola, e na ponta segura a mais
    próxima. A altura acompanha o topo da cabeça (máscara da pessoa, que não falha) quando ele é conhecido."""
    n = len(stats)
    det = [i for i in range(max(a - alcance, 0), min(b + alcance, n)) if stats[i].get("face")]
    out = []
    for i in range(a, b):
        ant = max((d for d in det if d <= i), default=None)
        pos = min((d for d in det if d >= i), default=None)
        ant = ant if ant is not None and i - ant <= alcance else None
        pos = pos if pos is not None and pos - i <= alcance else None
        if ant is None and pos is None:
            out.append(None)
            continue
        if ant is not None and pos is not None and pos != ant:
            k = (i - ant) / (pos - ant)
            f = [x + (y - x) * k for x, y in zip(stats[ant]["face"], stats[pos]["face"])]
            ref = None
        else:
            ref = ant if ant is not None else pos
            f = list(stats[ref]["face"])
        topo_i = stats[i].get("top") if i < n else None
        topo_r = stats[ref].get("top") if ref is not None else None
        dy = 0.0
        if ref is not None and topo_i is not None and topo_r is not None:
            dy = (topo_i - topo_r) / 1920              # a cabeça subiu/desceu desde a detecção (top em px de 1920)
            f[1] += dy
        perto = ref if ref is not None else (ant if ant is not None and (pos is None or i - ant <= pos - i) else pos)
        pts = stats[perto].get("pontos") if perto is not None else None
        if pts:  # olhos/boca de verdade da detecção mais próxima, deslocados como a caixa
            dx = f[0] - stats[perto]["face"][0]
            dyy = f[1] - stats[perto]["face"][1]
            p2 = {"olhos": [pts["olhos"][0] + dx, pts["olhos"][1] + dyy, pts["olhos"][2] + dx, pts["olhos"][3] + dyy],
                  "boca": [pts["boca"][0] + dx, pts["boca"][1] + dyy]}
            out.append(zona_por_pontos(p2, f, w, h))
        else:
            z = zona_do_rosto(f, w, h)
            out.append((z, *_partes_da_caixa(z)))
    return out


def folga_temporal(rostos: list, r: int = 3) -> list:
    """O detector atrasa um pouco quando a pessoa se mexe rápido (inclina para a câmera): zona, olhos e boca de cada
    quadro viram a união dos 3 quadros antes e depois. Melhor desviar um pouco a mais do que encostar no olho."""
    out = []
    for i in range(len(rostos)):
        viz = [c for c in rostos[max(i - r, 0): i + r + 1] if c]
        out.append(tuple(_uniao([c[k] for c in viz]) for k in range(3)) if viz else None)
    return out


def com_recuo(rosto, t: float, recuo: list[dict], w: int, h: int):
    """O recuo encolhe a cena (âncora embaixo, centro em x): o rosto (zona, olhos, boca) encolhe e desce junto."""
    if not rosto or not recuo:
        return rosto
    k = 0.0
    for r in recuo:
        k += (1 - r["s"]) * min(max((t - r["t0"]) / 0.35, 0), 1) * min(max((r["t1"] - t) / 0.35, 0), 1)
    sc = 1 - k

    def um(c):
        x0, y0, x1, y1 = c
        return (int(w / 2 + (x0 - w / 2) * sc), int(h - (h - y0) * sc), int(w / 2 + (x1 - w / 2) * sc), int(h - (h - y1) * sc))
    return tuple(um(c) for c in rosto)


def alfas(clip: Path, w: int = BW, h: int = BH, fps: int = 30) -> np.ndarray:
    """Canal alfa do clipe da animação, quadro a quadro, em baixa resolução (n, h, w) 0..1."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(clip),
                           "-vf", f"fps={fps},scale={w}:{h}:flags=area,format=rgba,alphaextract,format=gray",
                           "-f", "rawvideo", "-"], capture_output=True, check=True)
    a = np.frombuffer(proc.stdout, np.uint8)
    return (a[: len(a) // (w * h) * w * h].reshape(-1, h, w).astype(np.float32) / 255)


def _transforma(a: np.ndarray, s: float, ax: float, dy: float) -> np.ndarray:
    """Aplica escala s (âncora x em ax, centro em y) e deslocamento vertical dy*h a todas as máscaras."""
    import cv2
    n, h, w = a.shape
    x = (w - w * s) * ax
    y = (h - h * s) / 2 + dy * h
    m = np.float32([[s, 0, x], [0, s, y]])
    return np.stack([cv2.warpAffine(q, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=0) for q in a])


def cobertura(a: np.ndarray, caixas: list) -> np.ndarray:
    """Por quadro: fração coberta (alfa > 0,5) da zona do rosto — e olhos/boca contam 2x mais rígido (qualquer
    toque de 2% neles já vale como o limite). Sem rosto = 0."""
    out = np.zeros(len(a), np.float32)
    for i, (q, c) in enumerate(zip(a, caixas)):
        if c is None:
            continue
        v = 0.0
        for k, (x0, y0, x1, y1) in enumerate(c):         # zona, olhos, boca
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, q.shape[1]), min(y1, q.shape[0])
            if x1 > x0 and y1 > y0:
                f = float((q[y0:y1, x0:x1] > VISIVEL).mean())
                v = max(v, f if k == 0 else f * LIMITE / 0.02)
        out[i] = v
    return out


def _cabe(a: np.ndarray, original: np.ndarray, s: float) -> bool:
    """O elemento continua INTEIRO e dentro da zona segura: nada saiu do quadro (a área visível é a original × s²)
    nem caiu na barra do app embaixo."""
    vis = a.max(axis=0) > 0.5
    area0 = float((original.max(axis=0) > 0.5).sum())
    if not vis.any():
        return area0 == 0
    if vis.sum() < area0 * s * s * 0.97:
        return False
    ys, xs = np.where(vis)
    h, w = vis.shape
    # zona segura (6% em cima, 86% embaixo) — ou o que o próprio elemento já ocupava (sombra, cursor, brilho)
    oy = np.where(original.max(axis=0) > 0.5)[0]
    cima, baixo = min(int(h * 0.06), int(oy.min())), max(int(h * 0.86), int(oy.max()))
    return xs.min() >= 2 and xs.max() <= w - 3 and ys.min() >= cima and ys.max() <= baixo


def colisao(a: np.ndarray, obst: np.ndarray | None) -> int:
    """Quadros em que o elemento encosta em outro (mais de 8% da área dele em cima de outra animação)."""
    if obst is None:
        return 0
    el = a > VISIVEL
    area = el.reshape(len(a), -1).sum(1)
    sobre = (el & (obst[: len(a)] > 0.5)).reshape(len(a), -1).sum(1)
    return int(((area > 0) & (sobre > 0.08 * np.maximum(area, 1))).sum())


def decidir(a: np.ndarray, caixas: list, obst: np.ndarray | None = None) -> dict:
    """Menor mudança que deixa o rosto livre sem bater em outro elemento. Se nenhuma resolve, a que mais reduz (e o
    QA reprova)."""
    antes = cobertura(a, caixas)
    ruins = int((antes > LIMITE).sum())
    base = {"s": 1.0, "ax": 0.5, "dy": 0.0, "antes": ruins, "depois": ruins, "max_antes": round(float(antes.max(initial=0)), 3)}
    if ruins <= TOLERA_QUADROS:
        return base
    # custo = quadros com rosto coberto + quadros batendo em outra animação; nunca pior que o original
    melhor = (ruins + colisao(a, obst), ruins, 1.0, 0.5, 0.0)
    for s, ax, dy in CANDIDATOS:
        t = _transforma(a, s, ax, dy)
        if not _cabe(t, a, s):
            continue
        c = int((cobertura(t, caixas) > LIMITE).sum())
        custo = c + colisao(t, obst)
        if custo < melhor[0]:
            melhor = (custo, c, s, ax, dy)
        if custo <= TOLERA_QUADROS:
            break
    _, c, s, ax, dy = melhor
    return {"s": s, "ax": ax, "dy": dy, "antes": ruins, "depois": c, "max_antes": base["max_antes"]}


def fixos_da_timeline(tl: dict, gfx: list, W: int, H: int) -> list[dict]:
    """Obstáculos que não são animações: a faixa da legenda de cada página e os gráficos (CTA, gancho, título)."""
    from PIL import Image
    from assets import caption_y
    w, h = (BW, BH) if H >= W else (BH, BW)
    out = []
    size = tl["captions"]["cfg"]["size"]
    for pg in tl["captions"]["pages"]:
        y = caption_y(tl, pg["t0"])
        # faixa da legenda com respiro (0,8 da altura da letra) em cima e embaixo: nada encosta nela
        out.append({"t0": pg["t0"], "t1": pg["t1"],
                    "ret": [int(w * 0.1), int((y - 3.2 * size) * h / H), int(w * 0.9), int((y + 1.0 * size) * h / H)]})
    for png, g in gfx:
        try:
            a = np.asarray(Image.open(png).convert("RGBA").resize((w, h)), np.float32)[..., 3] / 255
        except OSError:
            continue
        out.append({"t0": g["t0"], "t1": g["t1"], "alfa": a})
    return out


def obstaculos(outros: list[tuple[dict, Path]], t0: float, n: int, W: int, H: int, fps: int,
               fixos: list[dict] | None = None) -> np.ndarray | None:
    """União do que já ocupa a tela durante a janela [t0, t0 + n quadros): outras animações na frente (já com a
    guarda delas), a faixa da legenda e os gráficos."""
    w, h = (BW, BH) if H >= W else (BH, BW)
    acc = None
    for fx_ in fixos or []:
        ini, fim = int(round((fx_["t0"] - t0) * fps)), int(round((fx_["t1"] - t0) * fps))
        if fim <= 0 or ini >= n:
            continue
        mask = np.zeros((h, w), np.float32)
        if "ret" in fx_:
            x0, y0, x1, y1 = fx_["ret"]
            mask[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)] = 1
        else:
            mask = fx_["alfa"]
        buf = np.zeros((n, h, w), np.float32)
        buf[max(ini, 0):min(fim, n)] = mask
        acc = buf if acc is None else np.maximum(acc, buf)
    for m, clip in outros:
        a = alfas(Path(clip), w, h, fps)
        g = m.get("guarda")
        if g:
            a = _transforma(a, g["s"], g.get("ax", 0.5), g.get("dy", 0.0))
        ini = int(round((m["t0"] - t0) * fps))
        buf = np.zeros((n, h, w), np.float32)
        for i in range(n):
            j = i - ini
            if 0 <= j < len(a):
                buf[i] = a[j]
        acc = buf if acc is None else np.maximum(acc, buf)
    return acc


def guarda(clip: Path, m: dict, stats: list[dict], recuo: list[dict], W: int, H: int, fps: int, cache_dir: Path,
           outros: list[tuple[dict, Path]] | None = None, fixos: list[dict] | None = None) -> dict:
    """Decisão para uma animação (com cache: mesmo clipe + mesmos rostos + mesmo recuo + mesmos vizinhos)."""
    a_, b_ = int(round(m["t0"] * fps)), int(round(m["t1"] * fps))
    w, h = (BW, BH) if H >= W else (BH, BW)
    caixas = [com_recuo(c, (a_ + i) / fps, recuo, w, h) for i, c in enumerate(rostos_por_quadro(stats, a_, b_, w, h))]
    caixas = folga_temporal(caixas)
    viz = [[Path(p).name, o["t0"], o.get("guarda")] for o, p in (outros or [])]
    fixos = [f_ for f_ in (fixos or []) if f_["t0"] < m["t1"] and f_["t1"] > m["t0"]]
    viz.append([[f_["t0"], f_["t1"], f_.get("ret") or float(f_["alfa"].sum())] for f_ in fixos])
    chave = hashlib.sha1(json.dumps([VERSAO, clip.name, clip.stat().st_size, caixas, recuo, m["t0"], m["t1"], viz],
                                    default=str).encode()).hexdigest()[:16]
    f = cache_dir / f"guarda_{chave}.json"
    if f.exists():
        return json.loads(f.read_text())
    a = alfas(clip, w, h, fps)[: len(caixas)]
    caixas = caixas[: len(a)]
    obst = obstaculos(outros or [], m["t0"], len(a), W, H, fps, fixos) if (outros or fixos) else None
    d = decidir(a, caixas, obst)
    s = d["s"]
    # em px do quadro final, para o overlay do clipe já escalado
    d.update(x=round((W - W * s) * d["ax"]), y=round((H - H * s) / 2 + d["dy"] * H), quadros=len(a))
    cache_dir.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d))
    return d
