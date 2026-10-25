#!/usr/bin/env python3
"""Recorte de produto: tira o fundo de uma foto e salva um PNG com transparência, justo no produto.
100% local e grátis.

Motores (o primeiro disponível vence; --motor força um):
  rembg   -> se o pacote estiver instalado (pip install rembg; o modelo baixa do GitHub uma vez)
  isnet   -> o mesmo IS-Net do anuncio-produto, se o .onnx já estiver em <MODELS_DIR>/recorte (onnxruntime)
  opencv  -> sem modelo nenhum: cor do fundo estimada nas bordas (aceita degradê) + GrabCut inicializado por essa
             estimativa + limpeza morfológica. Feito para foto de produto em fundo liso/claro/estúdio (com sombra)
Depois de qualquer motor: só o objeto principal, buracos pequenos fechados, borda refinada pela própria foto
(filtro guiado), cor da borda descontaminada (sem halo do fundo) e recorte justo (bbox + margem).

  python recorte.py foto.jpg saida.png
  python recorte.py foto.jpg saida.png --motor opencv --margem 6
  python recorte.py video.mov saida.png --tempo 5.0 --caixa 0.55,0.25,0.98,0.75   (produto num quadro do vídeo)
  python recorte.py --status                                                     qual motor está disponível

Importável: recortar(entrada, saida, ...) -> dict  |  alfa(imagem_bgr, motor) -> máscara 0..1 do tamanho da foto
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

VIDEOS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
MOTORES = ("rembg", "isnet", "opencv")
LADO_TRABALHO = 640  # GrabCut roda nesta resolução; a borda final é refinada na resolução da foto


# --------------------------------------------------------------------------------------------------------------
# leitura/gravação (np.fromfile + imdecode: funciona com acentos no caminho no Windows, onde cv2.imread falha)
# --------------------------------------------------------------------------------------------------------------

def ler_imagem(caminho: Path) -> np.ndarray:
    """BGR uint8 (fotos com alfa: o fundo transparente vira branco)."""
    dados = np.fromfile(str(caminho), np.uint8)
    img = cv2.imdecode(dados, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"não consegui abrir a imagem: {caminho}")
    if img.dtype != np.uint8:
        img = (img / 257).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        a = img[:, :, 3:4].astype(np.float32) / 255
        img = (img[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return img


def quadro_do_video(video: Path, tempo: float) -> np.ndarray:
    """Um quadro do vídeo (ffmpeg já aplica a rotação do celular)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "quadro.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{tempo:.3f}",
                        "-i", str(video), "-frames:v", "1", str(out)], check=True)
        return ler_imagem(out)


def salvar_png(caminho: Path, rgba_bgra: np.ndarray) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", rgba_bgra, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise ValueError("falha ao gravar o PNG")
    buf.tofile(str(caminho))


# --------------------------------------------------------------------------------------------------------------
# motores
# --------------------------------------------------------------------------------------------------------------

def _pasta_modelos() -> Path:
    try:
        from common import MODELS_DIR
        return Path(MODELS_DIR) / "recorte"
    except ImportError:  # usado fora da pasta scripts (ex.: copiado sozinho)
        return Path(os.environ.get("EDITOR_VIDEO_MODELS", Path.home() / ".cache" / "editor-video" / "models")) / "recorte"


# IS-Net (anuncio-produto/scripts/setup.py baixa os dois); u2netp é o pequeno
ISNET = [("isnet-general-use.onnx", 1024, (0.485, 0.456, 0.406), (1.0, 1.0, 1.0)),
         ("u2netp.onnx", 320, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225))]


def disponiveis() -> list[str]:
    out = []
    try:
        import rembg  # noqa: F401
        out.append("rembg")
    except Exception:
        pass
    try:
        import onnxruntime  # noqa: F401
        if any((_pasta_modelos() / n).exists() for n, *_ in ISNET):
            out.append("isnet")
    except Exception:
        pass
    out.append("opencv")
    return out


def _alfa_rembg(img: np.ndarray) -> np.ndarray:
    from PIL import Image
    from rembg import new_session, remove
    sessao = new_session("isnet-general-use")  # baixa o modelo na 1ª vez; sem rede levanta erro (cai no próximo)
    m = remove(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), session=sessao, only_mask=True)
    return np.asarray(m.convert("L"), np.float32) / 255


def _alfa_isnet(img: np.ndarray) -> np.ndarray:
    import onnxruntime as ort
    for nome, lado, media, desvio in ISNET:
        p = _pasta_modelos() / nome
        if not p.exists():
            continue
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        s = ort.InferenceSession(str(p), opts, providers=["CPUExecutionProvider"])
        x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (lado, lado), interpolation=cv2.INTER_AREA)
        x = ((x.astype(np.float32) / 255 - media) / desvio).transpose(2, 0, 1)[None].astype(np.float32)
        out = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
        out = (out - out.min()) / max(float(out.max() - out.min()), 1e-6)
        out = cv2.resize(out, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
        return np.clip((out - 0.12) / 0.76, 0, 1).astype(np.float32)
    raise FileNotFoundError("modelo IS-Net ausente")


def _ajusta_fundo(lab: np.ndarray, faixa: int) -> tuple[np.ndarray, np.ndarray]:
    """Modelo do fundo: polinômio de 2º grau em (x, y) por canal Lab, ajustado só nas bordas e robusto (o produto
    pode encostar na borda). Devolve (fundo estimado HxWx3, resíduo das bordas)."""
    h, w = lab.shape[:2]
    borda = np.zeros((h, w), bool)
    borda[:faixa], borda[-faixa:], borda[:, :faixa], borda[:, -faixa:] = True, True, True, True
    ys, xs = np.nonzero(borda)
    passo = max(1, len(ys) // 6000)
    ys, xs = ys[::passo], xs[::passo]

    def base(x, y):
        x, y = x / max(w - 1, 1) - 0.5, y / max(h - 1, 1) - 0.5
        return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], -1)

    A, v = base(xs.astype(np.float32), ys.astype(np.float32)), lab[ys, xs].astype(np.float32)
    usa = np.ones(len(v), bool)
    for _ in range(3):  # descarta o que não é fundo (produto na borda, sujeira) e reajusta
        coef, *_ = np.linalg.lstsq(A[usa], v[usa], rcond=None)
        res = np.linalg.norm(A @ coef - v, axis=1)
        lim = max(3.0, 2.5 * float(np.median(res[usa])) * 1.4826)
        novo = res < lim
        if novo.sum() < 0.3 * len(v) or (novo == usa).all():
            break
        usa = novo
    gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
    fundo = (base(gx.ravel(), gy.ravel()) @ coef).reshape(h, w, 3)
    return fundo.astype(np.float32), res[usa]


def _alfa_opencv(img: np.ndarray) -> np.ndarray:
    """Fundo liso/estúdio: estimativa do fundo nas bordas -> sementes -> GrabCut -> limpeza. Máscara 0/1 (a borda
    suave vem depois, no refinamento comum)."""
    h0, w0 = img.shape[:2]
    k = min(1.0, LADO_TRABALHO / max(h0, w0))
    peq = cv2.resize(img, (max(8, round(w0 * k)), max(8, round(h0 * k))), interpolation=cv2.INTER_AREA) if k < 1 else img
    peq = cv2.bilateralFilter(peq, 5, 20, 5)  # tira ruído/JPEG sem borrar o contorno
    h, w = peq.shape[:2]
    lab = cv2.cvtColor(peq, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[:, :, 0] *= 100 / 255  # L em 0..100; a, b em torno de 128
    faixa = max(2, round(min(h, w) * 0.025))
    fundo, res = _ajusta_fundo(lab, faixa)
    d = lab - fundo
    dE = np.sqrt(d[:, :, 0] ** 2 + d[:, :, 1] ** 2 + d[:, :, 2] ** 2)
    ruido = float(np.percentile(res, 95)) if len(res) else 3.0
    baixo, alto = max(4.0, ruido * 1.3), max(12.0, ruido * 2.6)
    # sombra: a cor do fundo multiplicada por um fator k < 1 (mesma cromaticidade, só mais escura; não preta)
    rgb = peq.astype(np.float32)
    fundo_rgb, _ = _ajusta_fundo(rgb, faixa)
    fator = (rgb * fundo_rgb).sum(-1) / np.maximum((fundo_rgb ** 2).sum(-1), 1)
    resto = np.linalg.norm(rgb - fator[..., None] * fundo_rgb, axis=-1) / np.maximum(np.linalg.norm(fundo_rgb, axis=-1), 1)
    parecida = (resto < 0.05 + ruido / 400) & (d[:, :, 0] < -baixo) & (fator > 0.12)
    # sombra x produto escuro da mesma cor (cinza em fundo branco, marrom em fundo bege): a sombra encosta no
    # fundo SEM borda nítida (ela esmaece); o produto é separado do fundo por uma borda forte. Tira as bordas
    # fortes, separa as regiões "parecidas" e só as que tocam o fundo limpo viram sombra.
    gx = cv2.Sobel(lab[:, :, 0], cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(lab[:, :, 0], cv2.CV_32F, 0, 1, ksize=3) / 8
    forte = cv2.dilate((np.hypot(gx, gy) > max(2.2, ruido * 0.9)).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    raio_f = max(3, round(min(h, w) * 0.012))
    regioes = (parecida & ~forte).astype(np.uint8)
    n, rot = cv2.connectedComponents(regioes, connectivity=8)
    limpo = cv2.dilate((dE < baixo).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    toca = np.bincount(rot[limpo & (regioes > 0)], minlength=n)
    eh_sombra = toca >= 3
    eh_sombra[0] = False
    sombra = eh_sombra[rot]
    # a faixa da borda forte entre duas partes da sombra (degrau de JPEG) segue a vizinhança
    sombra |= parecida & forte & (cv2.dilate(sombra.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0) & \
        ~(cv2.dilate((parecida & ~forte & ~sombra).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
    abre = lambda x: cv2.morphologyEx(x.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    com_sombra = abre(dE > alto)
    cand = abre((dE > alto) & ~sombra)
    if cand.sum() < 0.25 * com_sombra.sum():
        # a sombra "vazou" para dentro do produto por uma falha na borda: fecha o contorno das bordas fortes e o
        # que fica dentro dele é produto (o lado de fora da sombra esmaece, não tem borda para fechar)
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * raio_f + 1,) * 2)
        dentro = _preenche_buracos(cv2.morphologyEx(forte.astype(np.uint8), cv2.MORPH_CLOSE, ker)) > 0
        sombra = sombra & ~dentro
        cand = abre((dE > alto) & ~sombra)
    if cand.sum() < 0.25 * com_sombra.sum():  # quase tudo virou "sombra": desconfia e trata como produto
        cand, sombra = com_sombra, np.zeros_like(sombra)
    if cand.sum() < 0.002 * h * w:
        cand = (dE > baixo).astype(np.uint8)
    # buracos do candidato (rótulo claro, reflexo) entram como "provável produto"
    cheio = _preenche_buracos(cand)
    raio = max(2, round(min(h, w) * 0.012))
    nucleo = cv2.erode(cand, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * raio + 1,) * 2))
    perto = cv2.dilate(cheio, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4 * raio + 1,) * 2))

    m = np.full((h, w), cv2.GC_BGD, np.uint8)
    m[perto > 0] = cv2.GC_PR_BGD
    m[(cheio > 0) | ((perto > 0) & (dE > baixo) & ~sombra)] = cv2.GC_PR_FGD
    m[nucleo > 0] = cv2.GC_FGD
    # sombra reconhecida é fundo certo (o GrabCut confunde sombra cinza com produto cinza); perto de borda forte
    # fica "provável", para o contorno do produto ainda poder se ajustar
    perto_borda = cv2.dilate(forte.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    m[sombra & (nucleo == 0)] = cv2.GC_PR_BGD
    m[sombra & (nucleo == 0) & ~perto_borda] = cv2.GC_BGD
    if (m == cv2.GC_FGD).sum() == 0 and (m == cv2.GC_PR_FGD).sum() == 0:
        return np.zeros((h0, w0), np.float32)
    if (m == cv2.GC_BGD).sum() == 0:
        m[:faixa, :] = cv2.GC_BGD
    if ruido > 14:
        # as bordas não são um fundo liso (cena, quadro de vídeo): GrabCut clássico pela caixa. Topo e laterais
        # são fundo; a base fica "provável" (o produto costuma sair pela mão/pela borda de baixo)
        m = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
        m[:faixa], m[:, :faixa], m[:, -faixa:] = cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD
        m[-faixa:][m[-faixa:] != cv2.GC_BGD] = cv2.GC_PR_BGD
    try:
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(peq, m, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        pass  # GMM sem amostras suficientes: fica a semente
    mask = ((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    if k < 1:
        mask = cv2.resize(mask.astype(np.float32), (w0, h0), interpolation=cv2.INTER_LINEAR)
        mask = cv2.GaussianBlur(mask, (0, 0), 0.6 / k)
    return (mask > 0.5).astype(np.float32)


def _preenche_buracos(m: np.ndarray) -> np.ndarray:
    h, w = m.shape
    flood = np.pad((m > 0).astype(np.uint8), 1)
    cv2.floodFill(flood, np.zeros((h + 4, w + 4), np.uint8), (0, 0), 2)
    return ((flood[1:-1, 1:-1] != 2)).astype(np.uint8)


# --------------------------------------------------------------------------------------------------------------
# limpeza e borda (comum a todos os motores)
# --------------------------------------------------------------------------------------------------------------

def objeto_principal(a: np.ndarray, minimo: float = 0.15) -> np.ndarray:
    """Mantém o maior objeto (e pedaços com pelo menos `minimo` da área dele, ex.: kit com 2 itens); fecha buracos
    pequenos (reflexo, letra do rótulo) e preserva os grandes (alça de caneca)."""
    b = (a > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
    if n <= 1:
        return a * 0
    areas = st[1:, cv2.CC_STAT_AREA]
    maior = int(areas.max())
    manter = np.zeros(n, bool)
    manter[1:] = areas >= max(minimo * maior, 1)
    b = manter[lab].astype(np.uint8)
    cheio = _preenche_buracos(b)
    buracos = (cheio > 0) & (b == 0)
    nb, lb, sb, _ = cv2.connectedComponentsWithStats(buracos.astype(np.uint8), connectivity=4)
    pequenos = np.zeros(nb, bool)
    pequenos[1:] = sb[1:, cv2.CC_STAT_AREA] < 0.004 * max(b.sum(), 1)
    fechar = pequenos[lb]
    perto = cv2.dilate(((b > 0) | fechar).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    out = a * perto                      # a borda suave do objeto fica; pedaços soltos longe dele saem
    out[fechar] = 1.0
    return out.astype(np.float32)


def _filtro_guiado(guia: np.ndarray, p: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Filtro guiado (He et al.) só com boxFilter: a borda da máscara passa a seguir o contorno da foto."""
    caixa = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), normalize=True, borderType=cv2.BORDER_REFLECT)
    mI, mp = caixa(guia), caixa(p)
    cov = caixa(guia * p) - mI * mp
    var = caixa(guia * guia) - mI * mI
    a = cov / (var + eps)
    b = mp - a * mI
    return caixa(a) * guia + caixa(b)


def refina_borda(img: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Borda suave e fiel: filtro guiado numa faixa estreita em volta do contorno; dentro e fora ficam 1 e 0."""
    h, w = a.shape
    r = max(2, round(max(h, w) / 500))
    duro = (a > 0.5).astype(np.uint8)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    faixa = (cv2.dilate(duro, ker) - cv2.erode(duro, ker)) > 0
    guia = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    suave = cv2.GaussianBlur(a.astype(np.float32), (0, 0), max(0.8, r * 0.5))
    g = _filtro_guiado(guia, suave, r, 2e-3)
    g = np.clip((g - 0.08) / 0.84, 0, 1)  # contrai a rampa: borda limpa, sem véu
    g = g * g * (3 - 2 * g)
    # desmistura de cor: na faixa, cada pixel é uma mistura da cor do produto ali perto (F) com a do fundo ali
    # perto (B); a projeção de I sobre o segmento B->F dá o alfa com precisão de subpixel (sem anel de 1 px)
    I = img.astype(np.float32)
    dentro = cv2.erode(duro, ker).astype(np.float32)
    fora = 1 - cv2.dilate(duro, ker).astype(np.float32)
    s = 2.0 * r
    F = cv2.GaussianBlur(I * dentro[..., None], (0, 0), s) / np.maximum(cv2.GaussianBlur(dentro, (0, 0), s), 1e-4)[..., None]
    B = cv2.GaussianBlur(I * fora[..., None], (0, 0), s) / np.maximum(cv2.GaussianBlur(fora, (0, 0), s), 1e-4)[..., None]
    FB = F - B
    contraste = np.sqrt((FB ** 2).sum(-1))
    ac = np.clip(((I - B) * FB).sum(-1) / (contraste ** 2 + 1), 0, 1)
    ac = cv2.GaussianBlur(ac, (0, 0), 0.6)
    confia = np.clip((contraste - 18) / 40, 0, 1)        # pouco contraste produto x fundo: fica o filtro guiado
    g = confia * ac + (1 - confia) * g
    out = np.where(faixa, g, duro.astype(np.float32))
    return out.astype(np.float32)


def descontamina(img: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Cor da borda sem o fundo misturado (halo branco/cinza): F = (I - (1-a)B)/a, com B = fundo próximo
    (média ponderada por 1-a) e, onde a é baixo, a cor vem de dentro do produto (sangria)."""
    I = img.astype(np.float32)
    s = max(3.0, max(a.shape) / 250)
    wb = cv2.GaussianBlur((1 - a), (0, 0), s)[..., None]
    B = cv2.GaussianBlur(I * (1 - a)[..., None], (0, 0), s) / np.maximum(wb, 1e-3)
    dentro = (a > 0.96).astype(np.float32)
    wf = cv2.GaussianBlur(dentro, (0, 0), s)[..., None]
    sangria = cv2.GaussianBlur(I * dentro[..., None], (0, 0), s) / np.maximum(wf, 1e-3)
    am = a[..., None]
    F = np.clip((I - (1 - am) * B) / np.maximum(am, 0.2), 0, 255)
    mistura = np.clip((am - 0.15) / 0.6, 0, 1)            # alfa baixo: confia mais na cor de dentro
    F = F * mistura + sangria * (1 - mistura)
    F = np.where(am > 0.98, I, F)
    return F.astype(np.uint8)


# --------------------------------------------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------------------------------------------

def _caixa_px(caixa, w: int, h: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = [float(v) for v in caixa]
    if max(x0, y0, x1, y1) <= 1.0:  # frações da imagem
        x0, x1, y0, y1 = x0 * w, x1 * w, y0 * h, y1 * h
    x0, x1 = sorted((int(max(0, x0)), int(min(w, x1))))
    y0, y1 = sorted((int(max(0, y0)), int(min(h, y1))))
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise ValueError("caixa pequena demais")
    return x0, y0, x1, y1


def alfa(img: np.ndarray, motor: str = "auto", caixa=None) -> tuple[np.ndarray, str]:
    """Máscara 0..1 (float32) do tamanho da foto e o motor usado. `caixa` (x0,y0,x1,y1 em px ou frações) limita a
    busca a uma região: útil para tirar o produto de um quadro de vídeo com pessoa e cenário."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = _caixa_px(caixa, w, h) if caixa else (0, 0, w, h)
    reg = img[y0:y1, x0:x1]
    ordem = [motor] if motor != "auto" else [m for m in MOTORES if m in disponiveis()]
    erros = []
    for m in ordem:
        try:
            a = {"rembg": _alfa_rembg, "isnet": _alfa_isnet, "opencv": _alfa_opencv}[m](reg)
        except KeyError:
            raise ValueError(f"motor desconhecido: {m} (use {', '.join(MOTORES)} ou auto)") from None
        except Exception as exc:  # sem pacote, sem modelo, sem rede: tenta o próximo
            erros.append(f"{m}: {exc}")
            continue
        a = objeto_principal(a)
        if (a > 0.5).sum() < 0.001 * a.size:
            erros.append(f"{m}: não achou produto")
            continue
        a = refina_borda(reg, a)
        out = np.zeros((h, w), np.float32)
        out[y0:y1, x0:x1] = a
        return out, m
    raise ValueError("não consegui recortar o produto (" + "; ".join(erros) + ")")


def recortar(entrada, saida=None, motor: str = "auto", caixa=None, tempo: float | None = None,
             margem: int = 4) -> dict:
    """Recorta e grava o PNG RGBA justo no produto. Devolve {saida, motor, tamanho, caixa, area, cor_borda}."""
    entrada = Path(entrada)
    if entrada.suffix.lower() in VIDEOS:
        img = quadro_do_video(entrada, float(tempo or 0))
    else:
        img = ler_imagem(entrada)
    a, usado = alfa(img, motor, caixa)
    cor = descontamina(img, a)
    ys, xs = np.nonzero(a > 0.02)
    h, w = a.shape
    x0, x1 = max(0, xs.min() - margem), min(w, xs.max() + 1 + margem)
    y0, y1 = max(0, ys.min() - margem), min(h, ys.max() + 1 + margem)
    bgra = np.dstack([cor, np.round(a * 255).astype(np.uint8)])[y0:y1, x0:x1]
    saida = Path(saida) if saida else entrada.with_name(entrada.stem + "_recorte.png")
    salvar_png(saida, bgra)
    # cor média da borda do produto (as laterais do objeto 3D usam algo parecido)
    duro = (a > 0.5).astype(np.uint8)
    anel = (duro - cv2.erode(duro, np.ones((7, 7), np.uint8))) > 0
    b, g, r = [int(v) for v in np.median(cor[anel], axis=0)] if anel.any() else (128, 128, 128)
    return {"saida": str(saida), "motor": usado, "tamanho": [int(x1 - x0), int(y1 - y0)],
            "caixa": [int(x0), int(y0), int(x1), int(y1)], "area": round(float((a > 0.5).mean()), 4),
            "cor_borda": f"#{r:02x}{g:02x}{b:02x}"}


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Tira o fundo da foto do produto (PNG transparente), 100% local")
    ap.add_argument("entrada", nargs="?", help="foto (jpg/png/webp) ou vídeo (com --tempo)")
    ap.add_argument("saida", nargs="?", help="PNG de saída (padrão: <foto>_recorte.png)")
    ap.add_argument("--motor", default="auto", choices=("auto",) + MOTORES)
    ap.add_argument("--caixa", help="região do produto: x0,y0,x1,y1 em px ou frações 0..1")
    ap.add_argument("--tempo", type=float, help="segundo do vídeo de onde tirar o quadro")
    ap.add_argument("--margem", type=int, default=4, help="px em volta do produto no PNG final")
    ap.add_argument("--status", action="store_true", help="mostra os motores disponíveis")
    args = ap.parse_args()
    if args.status or not args.entrada:
        print("motores disponíveis: " + ", ".join(disponiveis()))
        if "rembg" not in disponiveis():
            print("  (melhor qualidade em foto difícil: pip install rembg  — o modelo baixa uma vez do GitHub)")
        return 0
    try:
        caixa = [float(v) for v in args.caixa.split(",")] if args.caixa else None
        info = recortar(args.entrada, args.saida, args.motor, caixa, args.tempo, args.margem)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
