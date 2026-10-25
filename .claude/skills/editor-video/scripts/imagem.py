"""Correção de imagem e estabilização com reenquadramento no rosto — 100% local (OpenCV + filtros padrão do ffmpeg).

Uma análise por clipe (cache em work/imagem_<clipe>.json):
  - luz: luma média e percentis; balanço de branco (desvio do cinza nos pixels neutros); ruído (Immerkær, só nas
    áreas lisas); nitidez (variância do Laplaciano numa resolução fixa); luma do rosto quando há rastreio;
  - tremida: movimento global entre quadros (cantos + fluxo óptico + estimateAffinePartial2D/RANSAC em baixa
    resolução, ignorando o rosto e o corpo), acumulado numa trajetória da câmera.

Decisões (tudo moderado, nunca estoura):
  - correção ("correcao": "auto"): denoise proporcional ao ruído e ao quanto a sombra vai ser clareada (hqdn3d;
    nlmeans só em vídeo muito escuro e pequeno), balanço de branco por ganhos de canal (cinza-mundo parcial),
    curva de luma (ponto de preto, ponto de branco e gamma) e nitidez (cas) só quando falta;
  - pele ("pele": 0..1): suavização só nos tons de pele (máscara por Cb/Cr, borda suave) com filtro bilateral só na
    luma, misturado no máximo a ~55%: tira poro/ruído sem cara de plástico;
  - estabilização ("estabilizar": auto|on|off): recorte dinâmico por quadro = rosto suavizado (fica no centro/terço)
    + tremida da câmera (trajetória menos a trajetória suavizada), com zoom mínimo 1,06 (até 1,10 se a tremida for
    grande). Vira expressões por partes (interpolação linear entre quadros) no crop do ffmpeg de cada plano.

O "grade" do estilo continua sendo aplicado depois, na composição: aqui só se normaliza o bruto.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from common import EditorError, load_json, log, probe, save_json

VERSAO = 2                 # muda quando a análise ou as decisões mudam (entra na chave dos planos)
ZOOM_MIN, ZOOM_MAX = 1.06, 1.10
SIGMA_CAMERA = 0.8         # s: o que é mais rápido que isso na trajetória da câmera é tremida (compensada)
SIGMA_ROSTO = 1.0          # s: o enquadramento segue o rosto devagar (sem "nadar")
LIMIAR_TREMIDA = 0.0025    # "auto": estabiliza se a tremida (desvio, fração do quadro) passar disso
LIMIAR_DESVIO_ROSTO = 0.04  # ... ou se o rosto andar mais que isso em volta do centro


# ---------------------------------------------------------------------------------------------------------------
# configuração

def config(tl: dict) -> dict | None:
    """Opções de imagem da timeline normalizadas; None quando tudo está desligado (vídeo igual ao de antes)."""
    c = tl.get("imagem") or {}
    cfg = {"correcao": str(c.get("correcao", "off")), "estabilizar": str(c.get("estabilizar", "off")),
           "pele": float(c.get("pele", 0.35 if c.get("correcao") == "auto" else 0.0) or 0.0)}
    cfg["pele"] = round(min(max(cfg["pele"], 0.0), 1.0), 2)
    if cfg["correcao"] != "auto" and cfg["estabilizar"] not in ("auto", "on") and cfg["pele"] <= 0:
        return None
    return cfg


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError as exc:  # vem com o MediaPipe; sem ele não há análise
        raise EditorError(f"OpenCV indisponível ({exc}): pip install opencv-python-headless") from exc


# ---------------------------------------------------------------------------------------------------------------
# análise por clipe

def _dims_analise(src_w: int, src_h: int, aspect: float) -> tuple[int, int]:
    """Quadro 'cover' no formato do projeto, na resolução do bruto (máx. 540 de largura no vertical)."""
    if src_w / src_h > aspect:
        ch, cw = src_h, src_h * aspect
    else:
        cw, ch = src_w, src_w / aspect
    k = min(1.0, (540 if aspect < 1 else 960) / cw)
    return int(cw * k) // 2 * 2, int(ch * k) // 2 * 2


def _quadros(src: str, w: int, h: int, fps: float):
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", src, "-an",
           "-vf", f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase:flags=area,crop={w}:{h}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = w * h * 3
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def ruido(gray: np.ndarray) -> float:
    """Desvio do ruído (0-255) pelo método de Immerkær, só nos pixels lisos (borda não conta como ruído)."""
    cv2 = _cv2()
    g = gray.astype(np.float32)
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    r = np.abs(cv2.filter2D(g, -1, k))[1:-1, 1:-1]
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0)[1:-1, 1:-1]
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)[1:-1, 1:-1]
    mag = np.abs(gx) + np.abs(gy)
    liso = mag < np.percentile(mag, 50)
    if liso.sum() < 100:
        return 0.0
    return float(math.sqrt(math.pi / 2) * r[liso].mean() / 6)


def nitidez(gray: np.ndarray) -> float:
    """Variância do Laplaciano numa resolução fixa (270x480 ou 480x270): comparável entre clipes."""
    cv2 = _cv2()
    h, w = gray.shape
    alvo = (270, 480) if h > w else (480, 270)
    g = cv2.resize(gray, alvo, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(cv2.GaussianBlur(g, (3, 3), 0.7), cv2.CV_32F).var())


def _mascara_rosto(face: dict | None, w: int, h: int) -> np.ndarray | None:
    """Fora do rosto e do corpo (abaixo dele): onde a tremida da câmera aparece sem o movimento da pessoa."""
    if not face:
        return None
    m = np.full((h, w), 255, np.uint8)
    fh = face["h"] * h
    fw = fh * 0.85
    x0, x1 = int(face["cx"] * w - 1.4 * fw), int(face["cx"] * w + 1.4 * fw)
    y0 = int(face["cy"] * h - 1.1 * fh)
    m[max(y0, 0):, max(x0, 0):max(min(x1, w), 0)] = 0
    return m if (m > 0).mean() > 0.12 else None


def _rosto_em(face_pts: list[dict], t: float) -> dict | None:
    if not face_pts:
        return None
    p = min(face_pts, key=lambda q: abs(q["t"] - t))
    return p if abs(p["t"] - t) <= 0.6 else None


def movimento(frames_gray: list[np.ndarray], fps: float, face_pts: list[dict] | None = None) -> np.ndarray:
    """Movimento global entre quadros consecutivos: (dx, dy, ângulo) por quadro, dx/dy em fração do quadro."""
    cv2 = _cv2()
    out = [(0.0, 0.0, 0.0)]
    prev = None
    for n, g in enumerate(frames_gray):
        if prev is not None:
            h, w = g.shape
            mask = _mascara_rosto(_rosto_em(face_pts or [], n / fps), w, h)
            pts = cv2.goodFeaturesToTrack(prev, maxCorners=220, qualityLevel=0.01, minDistance=7, mask=mask)
            if pts is None or len(pts) < 12:
                pts = cv2.goodFeaturesToTrack(prev, maxCorners=220, qualityLevel=0.01, minDistance=7)
            dx = dy = da = 0.0
            if pts is not None and len(pts) >= 8:
                nxt, st, _err = cv2.calcOpticalFlowPyrLK(prev, g, pts, None, winSize=(21, 21), maxLevel=3)
                ok = st.reshape(-1) == 1
                if ok.sum() >= 8:
                    m, _inl = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC,
                                                          ransacReprojThreshold=1.5)
                    if m is not None:
                        dx, dy = float(m[0, 2]) / w, float(m[1, 2]) / h
                        da = float(math.atan2(m[1, 0], m[0, 0]))
            out.append((dx, dy, da))
        prev = g
    return np.array(out, np.float64)


def _suaviza(x: np.ndarray, sigma_q: float) -> np.ndarray:
    """Gaussiana com borda refletida (sem puxar o começo/fim para zero)."""
    if sigma_q <= 0 or len(x) < 2:
        return x.copy()
    r = int(3 * sigma_q)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_q) ** 2)
    k /= k.sum()
    pad = np.pad(x, (r, r), mode="reflect" if len(x) > r else "edge")
    return np.convolve(pad, k, mode="valid")


def tremida(mov: np.ndarray, fps: float) -> dict:
    """Números da tremida: desvio do movimento entre quadros e da trajetória menos a suavizada (fração do quadro)."""
    if len(mov) < 3:
        return {"passo": 0.0, "jitter": 0.0, "rot_graus": 0.0}
    c = np.cumsum(mov, axis=0)
    j = np.stack([c[:, i] - _suaviza(c[:, i], SIGMA_CAMERA * fps) for i in range(3)], 1)
    return {"passo": round(float(np.hypot(mov[1:, 0], mov[1:, 1]).std() + 0), 5),
            "passo_std": round(float(math.hypot(mov[1:, 0].std(), mov[1:, 1].std())), 5),
            "jitter": round(float(math.hypot(j[:, 0].std(), j[:, 1].std())), 5),
            "rot_graus": round(float(np.degrees(j[:, 2]).std()), 3)}


def analisar_clipe(src: str, work: Path, clip: str, aspect: float, face_pts: list[dict] | None = None,
                   so_cache: bool = False) -> dict | None:
    """Análise do clipe inteiro (uma vez; cache em work/imagem_<clipe>.json, invalidado se o arquivo mudar)."""
    p = Path(src)
    try:
        st = p.stat()
        assin = [str(p), st.st_size, int(st.st_mtime), VERSAO, round(aspect, 4)]
    except OSError:
        assin = [str(p), None, None, VERSAO, round(aspect, 4)]
    cache = work / f"imagem_{clip}.json"
    dado = load_json(cache)
    if dado and dado.get("assinatura") == assin:
        return dado
    if so_cache:
        return None
    cv2 = _cv2()
    info = probe(p)
    fps = min(float(info.get("fps") or 30), 30.0)
    w, h = _dims_analise(info["width"], info["height"], aspect)
    k_m = min(1.0, 300 / min(w, h))                    # movimento com o lado menor em até 300 px (precisão subpixel)
    mw, mh = int(w * k_m) // 2 * 2, int(h * k_m) // 2 * 2
    grays, lum, rgb_med, neutros, ruidos, nits, rosto_l = [], [], [], [], [], [], []
    passo_cor = max(int(fps // 2), 1)                  # cor/ruído/nitidez a ~2 quadros por segundo
    for n, fr in enumerate(_quadros(str(p), w, h, fps)):
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        grays.append(cv2.resize(g, (mw, mh), interpolation=cv2.INTER_AREA))
        if n % passo_cor:
            continue
        f = fr.astype(np.float32) / 255
        y = 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]
        lum.append(np.percentile(y, [1, 5, 50, 95, 99]).tolist() + [float(y.mean())])
        # candidatos a cinza: os 15% menos saturados entre os tons médios (com cor puxada, eles mostram o desvio)
        mx, mn = f.max(axis=2), f.min(axis=2)
        sat = (mx - mn) / np.maximum(mx, 1e-3)
        meio = (y > 0.10) & (y < 0.92)
        rgb_med.append(f.reshape(-1, 3).mean(axis=0).tolist())
        if meio.mean() > 0.05:
            corte = np.percentile(sat[meio], 15)
            neutro = meio & (sat <= corte) & (sat < 0.35)
            if neutro.mean() > 0.01:
                neutros.append(f[neutro].mean(axis=0).tolist())
        ruidos.append(ruido(g))
        nits.append(nitidez(g))
        rf = _rosto_em(face_pts or [], n / fps)
        if rf:
            fh = rf["h"] * h
            x0, x1 = int(rf["cx"] * w - 0.3 * fh), int(rf["cx"] * w + 0.3 * fh)
            y0, y1 = int(rf["cy"] * h - 0.3 * fh), int(rf["cy"] * h + 0.3 * fh)
            reg = y[max(y0, 0):max(y1, 1), max(x0, 0):max(x1, 1)]
            if reg.size > 20:
                rosto_l.append(float(np.median(reg)))
    if not grays:
        raise EditorError(f"não consegui ler quadros de {p.name} para analisar a imagem")
    mov = movimento(grays, fps, face_pts)
    lum_a = np.array(lum)
    dado = {
        "assinatura": assin, "fps": fps, "w": w, "h": h, "src_w": info["width"], "src_h": info["height"],
        "luma": {k: round(float(np.median(lum_a[:, i])), 4) for i, k in enumerate(["p1", "p5", "p50", "p95", "p99", "media"])},
        "rgb": [round(float(x), 4) for x in np.mean(rgb_med, axis=0)],
        "neutro": [round(float(x), 4) for x in np.mean(neutros, axis=0)] if len(neutros) >= max(2, len(lum) // 3) else None,
        "ruido": round(float(np.median(ruidos)), 3), "nitidez": round(float(np.median(nits)), 1),
        "rosto_luma": round(float(np.median(rosto_l)), 4) if rosto_l else None,
        "tremida": tremida(mov, fps),
        "mov": [[round(float(a), 6), round(float(b), 6), round(float(c), 6)] for a, b, c in mov],
    }
    save_json(cache, dado)
    t = dado["tremida"]
    log(f"   imagem {clip}: luma {dado['luma']['p50']:.2f} | ruído {dado['ruido']:.1f} | nitidez {dado['nitidez']:.0f}"
        f" | tremida {t['jitter'] * 1000:.1f}‰")
    return dado


# ---------------------------------------------------------------------------------------------------------------
# decisões de correção

def decidir_correcao(a: dict, cfg: dict, proc_w: int) -> dict:
    """Parâmetros da correção (números; o filtro sai de filtros_correcao). proc_w = largura onde o filtro roda."""
    d: dict = {}
    L = a["luma"]
    if cfg["correcao"] == "auto":
        # exposição: clareia só o que está escuro; referência = rosto (se houver) ou a mediana do quadro
        ref = a.get("rosto_luma") or L["p50"]
        ref = min(max(ref, 0.03), 0.97)
        alvo = 0.46 if a.get("rosto_luma") else 0.42
        bp = round(min(max(L["p1"] - 0.03, 0.0), 0.05), 3)            # preto lavado (névoa/compressão)
        wp = round(max(L["p99"] + 0.04, 0.82), 3) if L["p99"] < 0.86 else 1.0  # branco apagado
        # clareamento: curva racional f(x) = (1+k)x/(x+k) — sobe os tons médios sem lavar o preto (inclinação na
        # origem limitada, ao contrário do gamma) e comprime o alto suavemente (não estoura)
        k = None
        r_ = (ref - bp) / (wp - bp)
        if ref < alvo - 0.03:
            alvo_mod = ref + 0.75 * (alvo - ref)          # chega perto, sem igualar (natural)
            if r_ < alvo_mod:
                k = round(max(r_ * (1 - alvo_mod) / (alvo_mod - r_), 0.3), 3)
        if k is not None or bp > 0.005 or wp < 0.995:
            ganho = (alvo_mod / max(r_, 0.02)) if k is not None else 1.0
            d["curva"] = {"preto": bp, "branco": wp, "k": k,
                          "sat": round(min(1 + 0.15 * (ganho - 1), 1.12), 3)}
        # balanço de branco: o que deveria ser cinza (pixels neutros; sem eles, o quadro todo com metade do peso)
        # volta 70% do caminho até Cb=Cr=128, no máximo 10 níveis (cinza-mundo parcial, direto no croma)
        r, g_, b = a.get("neutro") or a["rgb"]
        peso = 0.7 if a.get("neutro") else 0.3
        cb = 224 * (-0.168736 * r - 0.331264 * g_ + 0.5 * b)
        cr = 224 * (0.5 * r - 0.418688 * g_ - 0.081312 * b)
        du, dv = (round(min(max(-peso * x, -10.0), 10.0), 1) for x in (cb, cr))
        if abs(du) >= 1 or abs(dv) >= 1:
            d["wb"] = [du, dv]
        # ruído na resolução onde o filtro roda (reduzir a imagem também reduz o ruído) x o quanto a sombra clareia
        sig = a["ruido"] * min(max(proc_w / a["w"], 0.5), 2.0)
        inclin = 1.0
        if "curva" in d:
            c = d["curva"]
            x = max(min(r_, 0.9), 0.02)
            inclin = 1 / max(c["branco"] - c["preto"], 0.5)
            if c["k"]:
                inclin *= (1 + c["k"]) * c["k"] / (x + c["k"]) ** 2
        sig_ef = sig * max(inclin, 1.0)
        if sig_ef >= 1.4:
            ls = round(min(max(0.75 * sig_ef, 1.5), 4.5), 2)
            d["denoise"] = {"tipo": "hqdn3d", "ls": ls, "cs": round(ls * 1.2, 2), "lt": round(ls * 1.5, 2),
                            "ct": round(ls * 1.8, 2)}
            # nlmeans (melhor no escuro, ~1,6 s por segundo de vídeo mesmo em 360x480): só muito escuro, muito
            # ruidoso e pequeno
            if L["p50"] < 0.22 and sig_ef >= 6 and proc_w * proc_w * 16 / 9 <= 300_000:
                d["denoise"] = {"tipo": "nlmeans", "s": round(min(max(0.45 * sig_ef, 2.0), 5.0), 2)}
        # nitidez: só quando falta (o grade do estilo já tem um unsharp leve); denoise forte pede um pouco de volta
        nt = a["nitidez"]
        forca = 0.0 if nt >= 300 else 0.35 * (300 - max(nt, 40)) / 260
        if a["src_w"] < 0.8 * proc_w or a["src_h"] < 0.8 * proc_w * 16 / 9:
            forca += 0.1                                    # bruto pequeno ampliado: devolve um pouco de borda
        if "denoise" in d:
            forca += 0.08
        if forca >= 0.08:
            d["nitidez"] = round(min(forca, 0.45), 2)
    if cfg["pele"] > 0:
        d["pele"] = cfg["pele"]
    return d


def filtros_correcao(d: dict, proc_h: int) -> tuple[str, str]:
    """(antes, depois): `antes` roda na resolução de processamento, `depois` no quadro final (nitidez)."""
    # tudo em YUV com tabelas (lutyuv): converter para RGB num quadro 1080x1920 custaria ~1 s por segundo de vídeo
    pre = ["format=yuv420p"]
    dn = d.get("denoise")
    if dn and dn["tipo"] == "hqdn3d":
        pre.append(f"hqdn3d={dn['ls']}:{dn['cs']}:{dn['lt']}:{dn['ct']}")
    elif dn:
        pre.append(f"nlmeans=s={dn['s']}:p=5:r=9")
    lut = []
    c = d.get("curva")
    if c:
        x = "clip((val-minval)/(maxval-minval),0,1)"
        n = f"clip(({x}-{c['preto']})/{c['branco'] - c['preto']:.4f},0,1)"
        f = f"{1 + c['k']:.4f}*{n}/({n}+{c['k']})" if c.get("k") else n
        lut.append(f"y='minval+(maxval-minval)*{f}'")
    sat = c["sat"] if c else 1.0
    du, dv = d.get("wb", [0.0, 0.0])
    if sat > 1.005 or du or dv:  # tira a cor puxada antes de saturar (senão o desvio também satura)
        lut.append(f"u='clip(128+(val-128{du:+.1f})*{sat},minval,maxval)'")
        lut.append(f"v='clip(128+(val-128{dv:+.1f})*{sat},minval,maxval)'")
    if lut:
        pre.append("lutyuv=" + ":".join(lut))
    grafo = ",".join(pre)
    if d.get("pele"):
        # pele: bilateral só na luma, misturado onde Cb/Cr são de pele (máscara na resolução do croma, ampliada
        # e desfocada: borda suave). Mistura máx. ~55%: sem cara de plástico
        amt = round(0.55 * d["pele"], 3)
        ss = round(max(1.5, 5.0 * proc_h / 1920), 2)
        suave = f"bilateral=sigmaS={ss}:sigmaR=0.06:planes=1"
        if proc_h > 1000:  # quadro grande: suaviza em meia resolução (1/4 do custo; a pele lisa não perde nada)
            suave = (f"scale=w=iw/2:h=ih/2:flags=area,bilateral=sigmaS={round(ss / 2, 2)}:sigmaR=0.06:planes=1,"
                     f"scale=w=iw*2:h=ih*2:flags=bicubic")
        trap = lambda lo, hi: f"'255*clip(min((val-{lo - 6})/6,({hi + 6}-val)/6),0,1)'"
        mk = (f"[pm]extractplanes=u+v[pu][pv];"
              f"[pu]lut=c0={trap(80, 125)}[pu2];[pv]lut=c0={trap(136, 172)}[pv2];"
              f"[pu2][pv2]blend=all_mode=multiply,scale=w=iw*2:h=ih*2:flags=bilinear,"
              f"gblur=sigma={round(max(1.0, 3 * proc_h / 1920), 2)},lut=c0='val*{amt}',format=yuv420p[pk]")
        grafo = (f"{grafo},split=3[po][ps][pm];"
                 f"[ps]{suave}[pb];{mk};[po][pb][pk]maskedmerge=planes=1")
    # nitidez só na luma (unsharp custa ~1/4 do cas no quadro 1080x1920)
    pos = f"unsharp=lx=5:ly=5:la={d['nitidez']}:cx=5:cy=5:ca=0" if d.get("nitidez") else ""
    return grafo, pos


# ---------------------------------------------------------------------------------------------------------------
# estabilização + reenquadramento

def _interp_rosto(face_pts: list[dict], tempos: np.ndarray, campo: str) -> np.ndarray | None:
    pts = sorted(face_pts, key=lambda p: p["t"])
    if not pts:
        return None
    return np.interp(tempos, [p["t"] for p in pts], [p[campo] for p in pts])


def caminho_plano(a: dict, sh: dict, face_pts: list[dict], target_y: float, cfg: dict) -> dict | None:
    """Centro da janela de recorte por quadro do bruto (fração do quadro 'cover'), no tempo relativo ao plano.

    janela = rosto suavizado (rosto no centro na horizontal e em target_y na vertical) + tremida da câmera.
    Devolve None quando "auto" decide que não precisa (pouca tremida e rosto parado)."""
    fps = a["fps"]
    mov = np.array(a["mov"], np.float64)
    if len(mov) < 3:
        return None
    dur = (sh["t1"] - sh["t0"]) * sh.get("speed", 1.0)
    traj = np.cumsum(mov[:, :2], axis=0)
    q0 = max(int(math.floor(sh["in"] * fps)) - 1, 0)
    q1 = min(int(math.ceil((sh["in"] + dur) * fps)) + 2, len(mov))
    if q1 - q0 < 3:
        return None
    tq = np.arange(q0, q1) / fps                        # tempo do quadro no clipe
    sig_c = SIGMA_CAMERA * fps
    w0, w1 = max(q0 - int(3 * sig_c), 0), min(q1 + int(3 * sig_c), len(mov))
    tr = traj[w0:w1]
    j_livre = np.stack([tr[:, i] - _suaviza(tr[:, i], sig_c) for i in range(2)], 1)[q0 - w0:q1 - w0]
    zs = min(max(1 + 2 * float(np.percentile(np.abs(j_livre), 90)) + 0.02, ZOOM_MIN), ZOOM_MAX)
    z_plano = max(zs, min(sh["zoom0"], sh["zoom1"]))
    marg = 0.5 - 0.5 / z_plano
    mj = 0.65 * marg                                    # o resto da margem fica para o rosto
    # duas faixas: o tremor fino (mais rápido que ~0,15 s, amplitude pequena) é compensado sempre e inteiro; a
    # oscilação lenta usa o que sobra da margem, com uma trajetória suavizada que nunca se afasta mais que isso da
    # real (balanços grandes de verdade são seguidos com suavidade, sem bater na borda do zoom)
    fina = np.stack([_suaviza(tr[:, i], 0.15 * fps) for i in range(2)], 1)
    tremor = np.clip(tr - fina, -0.8 * mj, 0.8 * mj)
    banda = max(mj - float(np.percentile(np.abs(tremor), 99)), 0.2 * mj)
    lisa = np.stack([_suaviza(fina[:, i], sig_c) for i in range(2)], 1)
    for _ in range(25):
        lisa = np.stack([_suaviza(fina[:, i] - np.clip(fina[:, i] - lisa[:, i], -banda, banda), sig_c)
                         for i in range(2)], 1)
    jq = np.clip(tremor + np.clip(fina - lisa, -banda, banda), -mj, mj)[q0 - w0:q1 - w0]
    fixo = sh.get("enquadramento_fixo")
    perto = [p for p in face_pts if sh["in"] - 1.5 <= p["t"] <= sh["in"] + dur + 1.5] if not fixo else []
    if len(perto) >= 2:
        zf = max((sh["zoom0"] + sh["zoom1"]) / 2, z_plano)
        sig = SIGMA_ROSTO * fps
        # base do rosto no tempo do clipe inteiro (suaviza além das bordas do plano: sem tranco no corte)
        fx = _suaviza(_interp_rosto(perto, np.arange(len(mov)) / fps, "cx"), sig)[q0:q1]
        fy = _suaviza(_interp_rosto(perto, np.arange(len(mov)) / fps, "cy"), sig)[q0:q1]
        ux = fx - 0.0
        uy = fy - (target_y - 0.5) / zf
        desvio = float(np.hypot(fx - fx.mean(), fy - fy.mean()).std() + np.hypot(fx - fx.mean(), fy - fy.mean()).mean())
    else:
        z = max((sh["zoom0"] + sh["zoom1"]) / 2, z_plano)
        cx, cy = sh.get("cx", 0.5), sh.get("cy", 0.42)
        ux = np.full(q1 - q0, cx * (z - 1) / z + 0.5 / z)
        uy = np.full(q1 - q0, cy * (z - 1) / z + 0.5 / z)
        desvio = 0.0
    trem = float(math.hypot(j_livre[:, 0].std(), j_livre[:, 1].std()))
    if cfg["estabilizar"] == "auto" and trem < LIMIAR_TREMIDA and desvio < LIMIAR_DESVIO_ROSTO:
        return None
    lim = marg - mj
    # o rosto só usa a margem que sobra da tremida; o corte no limite é suavizado de novo (sem quina)
    ux = 0.5 + _suaviza(np.clip(ux - 0.5, -lim, lim), 0.25 * fps)
    uy = 0.5 + _suaviza(np.clip(uy - 0.5, -lim, lim), 0.25 * fps)
    ux = ux + jq[:, 0]
    uy = uy + jq[:, 1]
    return {"t": [round(float(t - sh["in"]), 4) for t in tq], "ux": [round(float(v), 5) for v in ux],
            "uy": [round(float(v), 5) for v in uy], "zoom_min": round(zs, 3), "fps": fps,
            "tremida": round(trem, 5), "desvio_rosto": round(desvio, 4)}


def _expr_partes(ts: list[float], vs: list[float], fps: float) -> str:
    """Interpolação linear entre pontos igualmente espaçados (1/fps) como soma de 'chapéus': sem if aninhado."""
    t0 = ts[0]
    termos = [f"{v:.5f}*max(0,1-abs(ld(0)-{k}))" for k, v in enumerate(vs)]
    # antes do primeiro / depois do último ponto: segura o valor da ponta
    return (f"st(0,clip((t{-t0:+.4f})*{fps:.4f},0,{len(vs) - 1}));" + "+".join(termos))


def filtro_recorte(caminho: dict | None, W: int, H: int, z_expr: str, cx: float, cy: float) -> str:
    """scale (zoom) + crop. Sem caminho: o recorte estático de sempre."""
    if not caminho:
        return (f"scale=w='2*trunc({W}*{z_expr}/2)':h='2*trunc({H}*{z_expr}/2)':eval=frame:flags=bicubic,"
                f"crop={W}:{H}:x='(in_w-{W})*{cx}':y='(in_h-{H})*{cy}'")
    z = f"max({z_expr},{caminho['zoom_min']})"
    ex = _expr_partes(caminho["t"], caminho["ux"], caminho["fps"])
    ey = _expr_partes(caminho["t"], caminho["uy"], caminho["fps"])
    return (f"scale=w='2*trunc({W}*{z}/2)':h='2*trunc({H}*{z}/2)':eval=frame:flags=bicubic,"
            f"crop={W}:{H}:x='clip(({ex})*in_w-{W}/2,0,in_w-{W})':y='clip(({ey})*in_h-{H}/2,0,in_h-{H})':exact=1")


# ---------------------------------------------------------------------------------------------------------------
# preparo dos planos (chamado pelo face_for_shots) e cadeia de filtros (render_shots)

def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def preparar_planos(tl: dict, work: Path, tracks: dict, alvos_y: dict, W: int, H: int, so_cache: bool = False) -> None:
    """Decide correção e estabilização de cada plano e grava sh['imagem'] (entra na chave do plano).

    O caminho de recorte vai para work/cache/estab/<hash>.json (a timeline guarda só o hash)."""
    cfg = config(tl)
    if not cfg:
        for sh in tl["shots"]:
            sh.pop("imagem", None)
        return
    analises: dict = {}
    for sh in tl["shots"]:
        if sh["clip"] not in analises:
            try:
                analises[sh["clip"]] = analisar_clipe(sh["src"], work, sh["clip"], W / H, tracks.get(sh["clip"]) or [],
                                                      so_cache=so_cache)
            except EditorError as exc:
                log(f"   (sem análise de imagem de {sh['clip']}: {exc})")
                analises[sh["clip"]] = None
        a = analises[sh["clip"]]
        if a is None:
            sh["imagem"] = {"v": VERSAO, "cfg": cfg, "pendente": True}
            continue
        # filtros rodam no bruto quando ele é menor que a saída (mais barato e o ruído ainda está "fino")
        proc_w = min(a["w"], W) if a["src_w"] * a["src_h"] < W * H else W
        corr = decidir_correcao(a, cfg, proc_w)
        item: dict = {"v": VERSAO, "cfg": cfg, "cor": corr, "no_bruto": a["src_w"] * a["src_h"] < W * H}
        if cfg["estabilizar"] in ("auto", "on"):
            cam = caminho_plano(a, sh, tracks.get(sh["clip"]) or [], alvos_y.get(sh.get("id"), 0.40), cfg)
            if cam:
                k = _hash([cam, VERSAO])
                arq = work / "cache" / "estab" / f"{k}.json"
                if not arq.exists() and not so_cache:  # dry-run não grava nada
                    save_json(arq, cam)
                item["estab"] = k
                item["zoom_min"] = cam["zoom_min"]
        sh["imagem"] = item


def cadeia(sh: dict, work: Path, W: int, H: int, z_expr: str) -> str:
    """Filtro de vídeo do plano (antes do setpts/fps), com correção e recorte dinâmico conforme sh['imagem']."""
    im = sh.get("imagem") or {}
    caminho = load_json(work / "cache" / "estab" / f"{im['estab']}.json") if im.get("estab") else None
    corr = im.get("cor") or {}
    proc_h = H
    if im.get("no_bruto"):
        a = load_json(work / f"imagem_{sh['clip']}.json") or {}
        proc_h = a.get("src_h", H)
    antes, depois = filtros_correcao(corr, proc_h)
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
    partes = [antes, cover] if im.get("no_bruto") else [cover, antes]
    partes.append(filtro_recorte(caminho, W, H, z_expr, sh["cx"], sh["cy"]))
    if depois:
        partes.append(depois)
    # partes com rótulos (pele) precisam ser a primeira cadeia ou fechar a cadeia: junta tudo numa só sequência
    return ",".join(p for p in partes if p)
