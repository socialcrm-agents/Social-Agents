#!/usr/bin/env python3
"""Referência do concorrente: mede ritmo, densidade e estilo de um vídeo pronto e traduz para o nosso editor.

  referencia.py analisar <video> [--saida perfil.json] [--fps 15]
  referencia.py aplicar <perfil.json> <projeto> [--dry-run]

100% local (ffmpeg + numpy + OpenCV; MediaPipe para rosto quando o modelo existe). Nada é enviado para fora.

O que é medido (tudo número; nenhum texto, imagem ou áudio do concorrente é guardado):
- cortes por minuto e duração média de plano (troca de cena = salto de histograma, ou quadro que o fluxo
  óptico não explica, ou salto de zoom de um quadro para o outro = punch-in);
- movimento de câmera e zoom (fluxo óptico Farneback: escala e translação globais por segundo);
- texto/gráficos na tela (proxy sem OCR: regiões de alto gradiente com forma de linha de texto, paradas na tela
  enquanto o fundo mexe; o que fica parado no mesmo lugar o vídeo inteiro é cenário e não conta);
- legenda: faixa da tela onde texto sobreposto aparece com frequência (posição da base e altura da linha);
- paleta: k-means das cores do quadro e das cores dentro dos textos/gráficos (cor de destaque);
- brilho, contraste e saturação médios; flashes (picos de luma curtos) e tremidas (translação que vai e volta);
- áudio: loudness integrado (EBU R128), trilha provável (energia fora da faixa de voz e fundo contínuo nas
  pausas), ritmo da fala (sílabas por segundo estimadas pelo envelope da voz) e pausas por minuto;
- rosto na tela (fração de tempo): o resto é tela cheia (gráfico, B-roll, tela gravada).

`aplicar` traduz o perfil para operações do edit.py (estilo, zoom, legenda, cor de destaque, ícones/gatilhos,
efeitos por minuto nas NOSSAS palavras fortes, velocidade da fala) e roda com --no-render. Copia ritmo,
densidade e estilo; o conteúdo (texto, imagem, áudio) continua sendo só o do nosso vídeo.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from common import STYLES_DIR, EditorError, load_json, log, main_guard, norm, probe, project_paths, save_json

HERE = Path(__file__).resolve().parent
LADO_MAIOR = 480                 # resolução de análise (lado maior, px)
PLANO_ESTILO = {"alternate": 2.6, "keyword": 3.4, "push": 5.0}   # mesmo alvo de plano do plan.py
DENSIDADE_ESTILO = {"editorial_premium": 0, "pro_clean": 1, "anuncio_conversao": 2, "reels_viral": 3}


# ---------------------------------------------------------------------------------------------------------------
# leitura

def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise EditorError("OpenCV não instalado (pip install opencv-python). Rode scripts/setup.py.") from exc
    return cv2


def _dimensoes(info: dict) -> tuple[int, int]:
    w, h = info.get("width") or 1080, info.get("height") or 1920
    k = LADO_MAIOR / max(w, h)
    return max(int(w * k) // 2 * 2, 2), max(int(h * k) // 2 * 2, 2)


def _quadros(path: Path, w: int, h: int, fps: float):
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h}",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
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


def _mediana_local(x: np.ndarray, raio: int) -> np.ndarray:
    out = np.empty_like(x, dtype=float)
    for i in range(len(x)):
        out[i] = np.median(x[max(0, i - raio):i + raio + 1])
    return out


def _hex(bgr) -> str:
    b, g, r = (int(round(v)) for v in bgr)
    return f"#{r:02X}{g:02X}{b:02X}"


def _hsv(bgr) -> tuple[float, float, float]:
    import colorsys
    b, g, r = (v / 255 for v in bgr)
    return colorsys.rgb_to_hsv(r, g, b)


# ---------------------------------------------------------------------------------------------------------------
# texto sobreposto (proxy sem OCR)

def _componentes_texto(cv2, g: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Caixas (x, y, w, h) com cara de linha de texto: muito gradiente, mais larga que alta, altura de letra."""
    H, W = g.shape
    grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    _, bw = cv2.threshold(grad, 70, 255, cv2.THRESH_BINARY)
    # linhas longas (borda de tela dividida, barra de progresso) grudariam na legenda: saem antes
    linhas = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (W // 2, 1)))
    bw = cv2.subtract(bw, cv2.dilate(linhas, np.ones((3, 1), np.uint8)))
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(W // 40, 3), 3)))
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(bw, connectivity=8)
    out = []
    for x, y, w, h, area in stats[1:]:
        if not (0.022 * H <= h <= 0.14 * H) or w < 1.3 * h or w > 0.97 * W:
            continue
        fill = area / float(w * h)
        if fill >= 0.3:
            out.append((int(x), int(y), int(w), int(h)))
    return out


def _parado(g: np.ndarray, g_ant: np.ndarray | None, caixa) -> bool:
    """Texto sobreposto fica parado na tela (pixel a pixel) enquanto a câmera/fundo mexe."""
    if g_ant is None:
        return False
    x, y, w, h = caixa
    a = g[y:y + h, x:x + w].astype(np.int16)
    b = g_ant[y:y + h, x:x + w].astype(np.int16)
    return float(np.abs(a - b).mean()) < 7.0


def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / float(aw * ah + bw * bh - inter) if inter else 0.0


# ---------------------------------------------------------------------------------------------------------------
# áudio

def _audio(path: Path, sr: int = 22050) -> np.ndarray | None:
    proc = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr),
                           "-f", "f32le", "-"], capture_output=True)
    if proc.returncode or not proc.stdout:
        return None
    return np.frombuffer(proc.stdout, np.float32)


def _lufs(path: Path) -> float | None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", "ebur128",
                           "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    achados = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", proc.stderr or "")
    return float(achados[-1]) if achados else None


def medir_audio(path: Path, sr: int = 22050) -> dict | None:
    """Loudness, trilha provável e ritmo da fala (envelope da faixa de voz)."""
    x = _audio(path, sr)
    if x is None or len(x) < sr:
        return None
    hop, win = sr // 100, sr // 25               # 10 ms de passo, 40 ms de janela
    n = (len(x) - win) // hop
    if n <= 10:
        return None
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    quadros = x[idx] * np.hanning(win)[None, :]
    esp = np.abs(np.fft.rfft(quadros, axis=1)) ** 2
    freqs = np.fft.rfftfreq(win, 1 / sr)
    voz = esp[:, (freqs >= 250) & (freqs <= 3500)].sum(1)
    fora = esp[:, ((freqs >= 40) & (freqs < 150)) | (freqs > 5000)].sum(1)
    total = esp.sum(1) + 1e-12
    db = 10 * np.log10(total / win + 1e-12)
    voz_db = 10 * np.log10(voz / win + 1e-12)
    # fala ativa: voz bem acima do fundo (piso = percentil 10)
    piso = np.percentile(voz_db, 10)
    ativo = voz_db > max(piso + 12, np.percentile(voz_db, 95) - 30)
    # sílabas: picos do envelope da voz (suavizado ~40 ms), mínimo 90 ms entre picos, só onde há fala
    env = np.convolve(voz_db, np.ones(4) / 4, mode="same")
    picos = 0
    ultimo = -99
    for i in range(1, len(env) - 1):
        if ativo[i] and env[i] >= env[i - 1] and env[i] > env[i + 1] and i - ultimo >= 9:
            vale = env[max(0, i - 12):i].min()
            if env[i] - vale >= 4.0:
                picos += 1
                ultimo = i
    seg_fala = ativo.sum() / 100.0
    # pausas (≥ 0,35 s sem fala, entre trechos de fala)
    pausas, run = 0, 0
    for a in ativo:
        if not a:
            run += 1
        else:
            if run >= 35:
                pausas += 1
            run = 0
    dur = len(x) / sr
    fundo = float(np.percentile(db, 10))
    meio = float(np.percentile(db, 60))
    razao_fora = float(np.median(fora / total))
    gap = meio - fundo
    return {
        "lufs": _lufs(path),
        "fala_ativa_frac": round(float(ativo.mean()), 3),
        "silabas_por_s": round(picos / seg_fala, 2) if seg_fala > 1 else None,
        "pausas_por_min": round(pausas / dur * 60, 1),
        "energia_fora_da_voz": round(razao_fora, 3),
        "fundo_nas_pausas_db": round(gap, 1),
        # música preenche as pausas (fundo perto do nível médio) e tem grave/agudo fora da faixa de voz
        "trilha_provavel": bool(gap < 16 and razao_fora > 0.12) or bool(gap < 9),
    }


# ---------------------------------------------------------------------------------------------------------------
# análise de vídeo

def _rosto(path: Path, dur: float, w: int, h: int) -> float | None:
    """Fração do tempo com rosto (2 quadros/s). MediaPipe se o modelo existir; senão Haar do OpenCV."""
    cv2 = _cv2()
    detector = None
    try:
        from vision import FACE_MODEL, _mp
        mp, BaseOptions, vision_ = _mp()
        detector = vision_.FaceDetector.create_from_options(vision_.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(FACE_MODEL)), min_detection_confidence=0.5))
    except Exception:  # noqa: BLE001 — sem MediaPipe/modelo: cai para o Haar
        detector = None
    haar = None if detector else cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    com, tot = 0, 0
    for f in _quadros(path, w, h, 2):
        tot += 1
        if detector is not None:
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(f[:, :, ::-1]))
            com += bool(detector.detect(img).detections)
        else:
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            com += len(haar.detectMultiScale(g, 1.15, 5, minSize=(int(0.08 * w), int(0.08 * w)))) > 0
    if detector is not None:
        detector.close()
    return round(com / tot, 3) if tot else None


def analisar(video: Path, fps: float = 15.0, com_rosto: bool = True) -> dict:
    cv2 = _cv2()
    video = Path(video).resolve()
    if not video.exists():
        raise EditorError(f"Vídeo não encontrado: {video}")
    info = probe(video)
    dur = info["duration"]
    if dur <= 0.5:
        raise EditorError("Vídeo curto demais para medir ritmo.")
    W, H = _dimensoes(info)
    ws, hs = W // 2, H // 2
    passo_txt = max(int(round(fps / 5)), 1)       # texto e cor a ~5 quadros/s
    luma, contraste, sat, hist_d, resid, escala, trans = [], [], [], [], [], [], []
    txt_amostras: list[tuple[float, list, list]] = []   # (t, caixas paradas, todas)
    amostras_cor, amostras_txt = [], []
    g_ant = gs_ant = h_ant = None
    soma = soma2 = None                              # média e desvio de cada pixel nas amostras de texto
    yy, xx = np.mgrid[0:hs, 0:ws].astype(np.float32)
    cx, cy = (ws - 1) / 2, (hs - 1) / 2
    rx, ry = xx - cx, yy - cy
    den = float((rx ** 2 + ry ** 2).sum())
    for i, f in enumerate(_quadros(video, W, H, fps)):
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        luma.append(float(g.mean()))
        contraste.append(float(g.std()))
        sat.append(float(hsv[:, :, 1].mean()) / 255)
        pequeno = cv2.resize(hsv, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        hist = cv2.calcHist([pequeno], [0, 1], None, [16, 8], [0, 180, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        gs = cv2.resize(g, (ws, hs), interpolation=cv2.INTER_AREA)
        if gs_ant is None:
            hist_d.append(0.0)
            resid.append(0.0)
            escala.append(0.0)
            trans.append((0.0, 0.0))
        else:
            hist_d.append(float(cv2.compareHist(h_ant, hist, cv2.HISTCMP_BHATTACHARYYA)))
            flow = cv2.calcOpticalFlowFarneback(gs_ant, gs, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            fx, fy = flow[:, :, 0], flow[:, :, 1]
            tx, ty = float(np.median(fx)), float(np.median(fy))
            s = float(((fx - tx) * rx + (fy - ty) * ry).sum() / den)
            escala.append(s)
            trans.append((tx / ws, ty / hs))
            # o quadro atual reconstruído a partir do anterior pelo fluxo: se não bate, é corte
            mapa_x = (xx - fx).astype(np.float32)
            mapa_y = (yy - fy).astype(np.float32)
            prev_w = cv2.remap(gs_ant, mapa_x, mapa_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            resid.append(float(np.abs(prev_w.astype(np.int16) - gs.astype(np.int16)).mean()))
        if i % passo_txt == 0:
            caixas = _componentes_texto(cv2, g)
            paradas = [c for c in caixas if _parado(g, g_ant, c)]
            txt_amostras.append((i / fps, paradas, caixas))
            gf = g.astype(np.float32)
            soma = gf if soma is None else soma + gf
            soma2 = gf * gf if soma2 is None else soma2 + gf * gf
            amostras_cor.append(f[::8, ::8].reshape(-1, 3))
            for x, y, w, h in paradas:
                amostras_txt.append(f[y:y + h, x:x + w][::2, ::2].reshape(-1, 3))
        g_ant, gs_ant, h_ant = g, gs, hist
    n = len(luma)
    if n < 3:
        raise EditorError("Não consegui ler quadros do vídeo (ffmpeg).")
    dur_v = n / fps
    luma_a, hist_a, resid_a, esc_a = map(np.array, (luma, hist_d, resid, escala))

    # flashes: luma acima da mediana de 1 s por até 0,35 s
    base = _mediana_local(luma_a, int(fps // 2))
    alto = (luma_a - base) > 18
    flashes, quadros_flash, k = [], set(), 0
    while k < n:
        if alto[k]:
            j = k
            while j + 1 < n and alto[j + 1]:
                j += 1
            if (j - k + 1) / fps <= 0.35:
                flashes.append(round(k / fps, 2))
                quadros_flash.update(range(k, j + 3))
            k = j + 1
        else:
            k += 1

    # cortes: evento de UM quadro (o seguinte volta a ser explicado pelo fluxo). Troca de cena = histograma salta;
    # corte seco no mesmo cenário = o fluxo não reconstrói o quadro novo; punch-in = zoom salta de uma vez.
    # Câmera na mão chicoteando borra 2+ quadros seguidos e não conta.
    raio = int(fps)
    med_r = _mediana_local(resid_a, raio)
    med_h = _mediana_local(hist_a, raio)
    mov = np.array([math.hypot(*t) for t in trans])
    cortes, punch = [], 0
    ultimo = -1e9
    for i in range(1, n):
        if i in quadros_flash:
            continue
        r_viz = max(resid_a[i - 1], resid_a[i + 1] if i + 1 < n else 0.0)
        e_viz = max(abs(esc_a[i - 1]), abs(esc_a[i + 1]) if i + 1 < n else 0.0)
        camera_mexendo = min(mov[i - 1], mov[i + 1] if i + 1 < n else 0.0) >= 0.012
        troca_cena = hist_a[i] > 0.35 and hist_a[i] > 3 * med_h[i] + 0.05 and resid_a[i] > 6
        nao_explica = resid_a[i] > max(12.0, 4 * med_r[i]) and r_viz < 0.5 * resid_a[i] and not camera_mexendo
        salto_zoom = abs(esc_a[i]) > 0.05 and e_viz < 0.5 * abs(esc_a[i])
        if (troca_cena or nao_explica or salto_zoom) and (i - ultimo) / fps >= 0.25:
            cortes.append(round(i / fps, 2))
            ultimo = i
            punch += bool(salto_zoom and not troca_cena)
    planos = np.diff([0.0] + cortes + [dur_v])
    corte_set = {int(round(c * fps)) for c in cortes}
    dentro = [i for i in range(1, n) if i not in corte_set and i not in quadros_flash]
    # zoom contínuo: escala somada em janelas de 1 s (o tremor da mão vai e volta e se cancela; o push-in soma)
    esc_d = np.where(np.isin(np.arange(n), dentro), esc_a, 0.0)
    jan = max(int(fps), 1)
    zoom_s = float(np.mean([abs(esc_d[k:k + jan].sum()) for k in range(0, n, jan)])) if n else 0.0
    tr = np.array([trans[i] for i in dentro]) if dentro else np.zeros((1, 2))
    mov_s = float(np.mean(np.hypot(tr[:, 0], tr[:, 1]))) * fps

    # tremidas: translação forte que vai e volta 2+ vezes em ~0,4 s (a mão chicoteando vai para um lado só)
    tremidas, ultimo = [], -1e9
    lim = 0.02
    dentro_set = set(dentro)
    for i in dentro:
        if (i - ultimo) / fps <= 0.5:
            continue
        janela = [np.array(trans[j]) for j in range(i, min(i + int(0.4 * fps) + 1, n)) if j in dentro_set]
        fortes = [v for v in janela if np.hypot(*v) >= lim]
        viradas = sum(float(a @ b) < 0 for a, b in zip(fortes, fortes[1:]))
        if viradas >= 2:
            tremidas.append(round(i / fps, 2))
            ultimo = i

    # texto sobreposto: parado na tela. O que fica no mesmo lugar em > 70% das amostras SEM mudar de conteúdo
    # (desvio baixo do pixel ao longo do vídeo) é cenário (placa, logo fixo da parede); legenda troca de palavra.
    Hh = H
    presenca = np.zeros((H, W), np.float32)
    for _t, paradas, _todas in txt_amostras:
        m = np.zeros((H, W), np.uint8)
        for x, y, w, h in paradas:
            m[y:y + h, x:x + w] = 1
        presenca += m
    na = max(len(txt_amostras), 1)
    desvio = np.sqrt(np.maximum(soma2 / na - (soma / na) ** 2, 0)) if soma is not None else np.zeros((H, W))
    cenario = (presenca / na > 0.7) & (desvio < 12)

    def sobreposto(c):
        x, y, w, h = c
        return cenario[y:y + h, x:x + w].mean() < 0.5

    amostras = [(t, [c for c in p if sobreposto(c)]) for t, p, _ in txt_amostras]
    # faixa da legenda: faixa horizontal onde há linha de texto em boa parte do tempo E bem mais do que nas faixas
    # vizinhas (tela gravada/cenário com texto espalhado não forma pico). A legenda anima (pop, palavra ativa
    # mudando de cor), então aqui contam todas as linhas de texto, não só as paradas.
    legenda = None
    bins = np.zeros(50)
    for _t, _p, todas in txt_amostras:
        for b in {min(int((y + h / 2) / Hh * 50), 49) for x, y, w, h in todas}:
            bins[b] += 1
    if bins.any():
        suave = np.convolve(bins, [1, 1, 1], mode="same")
        pico = int(np.argmax(suave))
        viz = [suave[j] for j in range(50) if 4 <= abs(j - pico) <= 10]
        destaque_pico = suave[pico] / (np.median(viz) + 1.0) if viz else 0.0
        faixa = (max(pico - 2, 0) / 50 * Hh, min(pico + 3, 50) / 50 * Hh)
        na_faixa = [[c for c in todas if faixa[0] <= c[1] + c[3] / 2 <= faixa[1]] for _t, _p, todas in txt_amostras]
        frac = sum(bool(x) for x in na_faixa) / na
        # e parte do tempo ela fica parada na tela enquanto o fundo mexe (texto da tela gravada mexe junto)
        frac_parada = sum(any(faixa[0] <= c[1] + c[3] / 2 <= faixa[1] for c in cs) for _t, cs in amostras) / na
        if frac >= 0.25 and destaque_pico >= 1.5 and frac_parada >= 0.1:
            alturas = [c[3] for cs in na_faixa for c in cs]
            bases = [c[1] + c[3] for cs in na_faixa for c in cs]
            legenda = {"frac_tempo": round(frac, 3), "base_rel": round(float(np.median(bases)) / Hh, 3),
                       "altura_linha_rel": round(float(np.median(alturas)) / Hh, 4), "faixa_rel": [round(faixa[0] / Hh, 3),
                                                                                                round(faixa[1] / Hh, 3)]}
    fora = [[c for c in cs if not legenda or not (legenda["faixa_rel"][0] * Hh <= c[1] + c[3] / 2 <= legenda["faixa_rel"][1] * Hh)]
            for _t, cs in amostras]
    # entrada de texto/gráfico: caixa parada onde, 0,2 s antes, não havia linha de texto nenhuma
    # (texto da tela gravada que só mudou de lugar com a câmera continua sobreposto à posição anterior)
    eventos_txt, ultimo = [], -1e9
    mx, my = int(0.06 * W), int(0.04 * H)

    def vizinha(c, d) -> bool:
        x, y, w, h = d
        return _iou(c, (x - mx, y - my, w + 2 * mx, h + 2 * my)) > 0 and abs((c[1] + c[3] / 2) - (y + h / 2)) <= my

    for k, ((t, _p, _todas), cs) in enumerate(zip(txt_amostras, fora)):
        # compara com ~0,6 s antes: a entrada animada (pop, desfoque) já terminou e o texto está parado
        ant = txt_amostras[k - 3][2] if k >= 3 else []
        novo = any(c[3] >= 0.03 * H and not any(vizinha(c, d) for d in ant) for c in cs)
        if novo and t - ultimo >= 0.5:
            eventos_txt.append(round(t, 2))
            ultimo = t
    texto_fora_frac = sum(bool(cs) for cs in fora) / na

    # paleta (k-means): quadro inteiro e dentro dos textos/gráficos
    def kmeans(px: np.ndarray, k: int):
        if px is None or len(px) < k * 10:
            return []
        px = px.astype(np.float32)
        if len(px) > 60000:
            px = px[np.random.default_rng(7).choice(len(px), 60000, replace=False)]
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
        _c, lab, cen = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        cont = np.bincount(lab.flatten(), minlength=k) / len(lab)
        ordem = np.argsort(-cont)
        return [{"cor": _hex(cen[j]), "fatia": round(float(cont[j]), 3)} for j in ordem]

    cv2.setRNGSeed(7)
    paleta_video = kmeans(np.concatenate(amostras_cor) if amostras_cor else None, 5)
    paleta_graf = kmeans(np.concatenate(amostras_txt) if amostras_txt else None, 4)
    destaque = None
    for c in paleta_graf:
        rgb = [int(c["cor"][i:i + 2], 16) for i in (5, 3, 1)]
        hh, ss, vv = _hsv(rgb)
        if c["fatia"] >= 0.06 and ss >= 0.45 and vv >= 0.45:
            destaque = c["cor"]
            break

    rosto = _rosto(video, dur, W, H) if com_rosto else None
    audio = medir_audio(video) if info.get("has_audio") else None
    minuto = dur_v / 60
    medidas = {
        "duracao_s": round(dur_v, 2), "largura": info.get("width"), "altura": info.get("height"),
        "cortes": len(cortes), "cortes_por_min": round(len(cortes) / minuto, 1),
        "plano_medio_s": round(float(planos.mean()), 2), "plano_mediano_s": round(float(np.median(planos)), 2),
        "punch_ins": punch, "zoom_por_s": round(zoom_s, 4), "movimento_camera_por_s": round(mov_s, 4),
        "flashes": len(flashes), "tremidas": len(tremidas),
        "fx_por_min": round((len(flashes) + len(tremidas)) / minuto, 1),
        "texto_eventos_por_min": round(len(eventos_txt) / minuto, 1),
        "texto_fora_legenda_frac": round(texto_fora_frac, 3),
        "texto_na_tela_frac": round(sum(bool(cs) for _t, cs in amostras) / na, 3),
        "legenda": legenda,
        "brilho": round(float(np.mean(luma_a)) / 255, 3), "contraste": round(float(np.mean(contraste)) / 255, 3),
        "saturacao": round(float(np.mean(sat)), 3),
        "paleta_video": paleta_video, "paleta_graficos": paleta_graf, "cor_destaque": destaque,
        "rosto_frac": rosto, "audio": audio,
        "tempos": {"cortes": cortes, "flashes": flashes, "tremidas": tremidas, "texto": eventos_txt},
    }
    return {"arquivo": video.name, "medidas": medidas, "traducao": traduzir(medidas),
            "aviso": "Só números (ritmo, densidade, estilo). Nenhum texto, imagem ou áudio do vídeo de referência "
                     "foi guardado; o conteúdo do nosso vídeo não muda."}


# ---------------------------------------------------------------------------------------------------------------
# tradução para o nosso editor

def _estilos() -> dict:
    out = {}
    for p in sorted(STYLES_DIR.glob("*.json")):
        s = load_json(p)
        out[p.stem] = {"plano": PLANO_ESTILO.get(s["zoom"]["mode"], 3.0), "cap_size": s["captions"]["size"],
                       "cap_y": s["captions"]["y"], "accent": s["graphics"]["accent"],
                       "densidade": DENSIDADE_ESTILO.get(p.stem, 1)}
    return out


def _nivel_densidade(m: dict) -> int:
    """0 = calmo ... 3 = muito denso (eventos visuais por minuto, sem contar a legenda)."""
    ev = m["cortes_por_min"] + m["texto_eventos_por_min"] + m["fx_por_min"]
    return 0 if ev < 8 else 1 if ev < 18 else 2 if ev < 32 else 3


def traduzir(m: dict) -> dict:
    eventos = m["cortes"] + len(m["tempos"]["texto"]) + m["flashes"] + m["tremidas"]
    leg = m.get("legenda")
    cap_size = cap_y = None
    if leg:
        # altura da linha detectada (com contorno) ~ 0,85 do corpo da fonte das nossas legendas (Anton/Inter)
        cap_size = int(min(max(leg["altura_linha_rel"] * 1920 / 0.85, 50), 140))
        cap_y = int(min(max(leg["base_rel"] * 1920, 900), 1470))
    dens = _nivel_densidade(m)
    punch_min = m["punch_ins"] / (m["duracao_s"] / 60)
    z = m["zoom_por_s"]
    # punch-ins mandam; zoom contínuo só sobe um nível quando é claro (câmera na mão também "respira")
    zoom = ("forte" if punch_min >= 10 else "on" if punch_min >= 4 else "suave" if punch_min >= 1 else "off")
    if z >= 0.06 and zoom in ("off", "suave"):
        zoom = "suave" if zoom == "off" else "on"
    distancias = {}
    for nome, s in _estilos().items():
        d = abs(math.log(max(m["plano_medio_s"], 0.3) / s["plano"])) * 2.0 + abs(dens - s["densidade"]) * 1.0
        if leg:
            d += abs(cap_size - s["cap_size"]) / 40 + abs(cap_y - s["cap_y"]) / 250
        if m.get("cor_destaque"):
            h1 = _hsv([int(m["cor_destaque"][i:i + 2], 16) for i in (5, 3, 1)])[0]
            h2 = _hsv([int(s["accent"][i:i + 2], 16) for i in (5, 3, 1)])[0]
            d += min(abs(h1 - h2), 1 - abs(h1 - h2)) * 4
        distancias[nome] = round(d, 3)
    estilo = min(distancias, key=distancias.get)
    audio = m.get("audio") or {}
    return {
        "estilo": estilo, "distancias_estilo": distancias,
        "algo_muda_a_cada_s": round(m["duracao_s"] / eventos, 2) if eventos else None,
        "zoom": zoom, "caption_size": cap_size, "caption_y": cap_y, "cor_destaque": m.get("cor_destaque"),
        "fx_por_min": m["fx_por_min"], "fx_tipo": "clarao" if m["flashes"] >= m["tremidas"] else "tremida",
        "densidade_motion": ["baixa", "media", "alta", "muito alta"][dens],
        "icons": "on" if dens >= 2 else "off", "gatilhos": "on" if dens >= 1 else "off",
        "silabas_por_s": audio.get("silabas_por_s"), "trilha": audio.get("trilha_provavel"),
    }


# ---------------------------------------------------------------------------------------------------------------
# aplicar no projeto

def _palavras_fortes(tl: dict, n: int) -> list[str]:
    """Palavras do NOSSO vídeo para os efeitos: destaques da legenda, espaçados ≥ 4 s, cada uma na 1ª ocorrência."""
    from plan import score_word
    vistos, primeira = set(), {}
    for w in tl.get("words", []):
        k = norm(w["w"])
        if k and k not in primeira:
            primeira[k] = w
    cands = sorted((w for k, w in primeira.items() if w.get("emph") or score_word(w["w"]) >= 4),
                   key=lambda w: -score_word(w["w"]))
    out, tempos = [], []
    for w in cands:
        k = norm(w["w"])
        if k in vistos or w["t0"] < 1.0 or any(abs(w["t0"] - t) < 4.0 for t in tempos):
            continue
        vistos.add(k)
        out.append(w["w"].strip(".,!?:;"))
        tempos.append(w["t0"])
        if len(out) >= n:
            break
    return out


def operacoes(perfil: dict, proj: dict, tl: dict | None, fala_nossa: float | None) -> tuple[list[str], list[str]]:
    """Operações do edit.py que copiam ritmo/densidade/estilo do perfil (e a explicação de cada uma)."""
    tr = perfil["traducao"]
    ops, porque = [], []
    if tr["estilo"] != proj.get("style"):
        ops += ["--style", tr["estilo"]]
        porque.append(f"estilo {proj.get('style')} -> {tr['estilo']} (mais próximo do ritmo/legenda/cor da referência)")
    ops += ["--zoom", tr["zoom"]]
    porque.append(f"zoom {tr['zoom']} (punch-ins e zoom contínuo medidos)")
    if tr.get("caption_size"):
        ops += ["--caption-size", str(tr["caption_size"]), "--caption-y", str(tr["caption_y"])]
        porque.append(f"legenda {tr['caption_size']} px, base em y={tr['caption_y']} (faixa medida na referência)")
    if tr.get("cor_destaque"):
        ops += ["--cor-destaque", tr["cor_destaque"]]
        porque.append(f"cor de destaque {tr['cor_destaque']} (cor dominante dos textos/gráficos da referência)")
    ops += ["--icons", tr["icons"], "--gatilhos", tr["gatilhos"]]
    porque.append(f"densidade {tr['densidade_motion']}: ícones {tr['icons']}, gatilhos {tr['gatilhos']}")
    dur = (tl or {}).get("duration") or 0
    n_fx = min(int(round(tr["fx_por_min"] * dur / 60)), 6) if tr["fx_por_min"] >= 1.5 else 0
    if n_fx and tl:
        ja = {norm(r.get("at", "")) for r in proj.get("overrides", {}).get("fx_requests", [])}
        palavras = [p for p in _palavras_fortes(tl, n_fx) if norm(p) not in ja]
        for p in palavras:
            ops += ["--fx", f"{tr['fx_tipo']}@{p}"]
        if palavras:
            porque.append(f"{len(palavras)} efeito(s) {tr['fx_tipo']} nas nossas palavras fortes "
                          f"({tr['fx_por_min']}/min na referência): {', '.join(palavras)}")
    ov = proj.get("overrides", {})
    if tr.get("silabas_por_s") and fala_nossa and not ov.get("sem_cortes") and not proj.get("ja_editado"):
        razao = tr["silabas_por_s"] / fala_nossa
        if razao > 1.05:
            vel = round(min(razao, 1.2), 2)
            ops += ["--velocidade", str(vel)]
            porque.append(f"fala ×{vel} (referência {tr['silabas_por_s']} sílabas/s, nossa {fala_nossa})")
    return ops, porque


def cmd_analisar(a) -> None:
    perfil = analisar(Path(a.video), a.fps, com_rosto=not a.sem_rosto)
    saida = Path(a.saida) if a.saida else Path(a.video).with_suffix(".perfil.json")
    save_json(saida, perfil)
    m, t = perfil["medidas"], perfil["traducao"]
    leg = m["legenda"]
    log(f"Perfil: {saida}")
    log(f"  {m['duracao_s']}s | {m['cortes']} cortes ({m['cortes_por_min']}/min, plano médio {m['plano_medio_s']}s, "
        f"{m['punch_ins']} punch-ins) | zoom {m['zoom_por_s']}/s | câmera {m['movimento_camera_por_s']}/s")
    log(f"  texto: {m['texto_eventos_por_min']} entradas/min fora da legenda, na tela {m['texto_na_tela_frac'] * 100:.0f}% "
        f"do tempo | legenda: " + (f"{leg['frac_tempo'] * 100:.0f}% do tempo, base em {leg['base_rel'] * 100:.0f}% da altura"
                                     if leg else "não detectada"))
    log(f"  flashes {m['flashes']}, tremidas {m['tremidas']} ({m['fx_por_min']}/min) | brilho {m['brilho']} "
        f"contraste {m['contraste']} saturação {m['saturacao']} | destaque {m['cor_destaque']}")
    au = m["audio"] or {}
    log(f"  áudio: {au.get('lufs')} LUFS, trilha {'provável' if au.get('trilha_provavel') else 'não'}, "
        f"{au.get('silabas_por_s')} sílabas/s, {au.get('pausas_por_min')} pausas/min | rosto {m['rosto_frac']}")
    log(f"  -> estilo {t['estilo']}, algo muda a cada {t['algo_muda_a_cada_s']}s, zoom {t['zoom']}, legenda "
        f"{t['caption_size']}/{t['caption_y']}, densidade {t['densidade_motion']}")


def cmd_aplicar(a) -> None:
    perfil = load_json(Path(a.perfil))
    if not perfil or "traducao" not in perfil:
        raise EditorError(f"Perfil inválido: {a.perfil} (gere com: referencia.py analisar <video>)")
    project = Path(a.project).resolve()
    paths = project_paths(project)
    proj = load_json(paths["project"])
    if not proj:
        raise EditorError("project.json não encontrado.")
    if not paths["timeline"].exists() and paths["transcript"].exists():
        for script in ("analyze.py", "plan.py"):
            subprocess.run([sys.executable, str(HERE / script), str(project)], capture_output=True)
    tl = load_json(paths["timeline"])
    fala = None
    if proj.get("clips"):
        au = medir_audio(Path(proj["clips"][0]["path"])) if Path(proj["clips"][0]["path"]).exists() else None
        fala = (au or {}).get("silabas_por_s")
    ops, porque = operacoes(perfil, proj, tl, fala)
    log(f"Referência {perfil.get('arquivo')} -> {project.name}:")
    for p in porque:
        log(f"  - {p}")
    if a.dry_run:
        log("edit.py " + " ".join(ops) + " --no-render   (dry-run: nada aplicado)")
        return
    nota = f"referência: ritmo/estilo de {perfil.get('arquivo')} (sem copiar conteúdo)"
    proc = subprocess.run([sys.executable, str(HERE / "edit.py"), str(project), *ops, "--note", nota, "--no-render"])
    if proc.returncode:
        raise EditorError("edit.py falhou; nada aplicado.")
    log("Aplicado sem renderizar. Para ver: python scripts/run.py render " + str(project))


def main() -> None:
    ap = argparse.ArgumentParser(description="Copia ritmo, densidade e estilo de um vídeo de referência (sem conteúdo).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analisar", help="mede o vídeo e grava perfil.json")
    an.add_argument("video")
    an.add_argument("--saida")
    an.add_argument("--fps", type=float, default=15.0)
    an.add_argument("--sem-rosto", action="store_true", help="pula a detecção de rosto (mais rápido)")
    ap_ = sub.add_parser("aplicar", help="aplica o perfil no projeto via edit.py (sem renderizar)")
    ap_.add_argument("perfil")
    ap_.add_argument("project")
    ap_.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    {"analisar": cmd_analisar, "aplicar": cmd_aplicar}[a.cmd](a)


if __name__ == "__main__":
    main_guard(main)
