#!/usr/bin/env python3
"""Mapa de profundidade e placa limpa (cenário sem a pessoa) — 100% local e gratuito.

Usa o Depth Anything V2 Small (Apache-2.0, ~100 MB, ONNX na CPU) quando ele está instalado; sem ele, cai num modo
heurístico (pessoa na frente + cenário em degradê) que já dá o efeito 2.5D num vídeo de pessoa falando.

  python profundidade.py --status                      qual modo está ativo
  python profundidade.py --baixar                      baixa o modelo (uma vez; Hugging Face, sem conta)
  python profundidade.py imagem.jpg saida.png          mapa de uma imagem (branco = perto)

Modelo: <MODELS_DIR>/depth_anything_v2_small.onnx (baixado pelo setup.py --models) ou a variável EDITOR_DEPTH_MODEL.
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx"
MEDIA = np.array([0.485, 0.456, 0.406], np.float32)
DESVIO = np.array([0.229, 0.224, 0.225], np.float32)
_SESSAO = None


def caminho_modelo() -> Path:
    if os.environ.get("EDITOR_DEPTH_MODEL"):
        return Path(os.environ["EDITOR_DEPTH_MODEL"])
    from common import MODELS_DIR
    return Path(MODELS_DIR) / "depth_anything_v2_small.onnx"


def baixar() -> Path:
    destino = caminho_modelo()
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".part")
    print(f"Baixando o modelo de profundidade (~100 MB) de {URL}")
    urllib.request.urlretrieve(URL, tmp)
    os.replace(tmp, destino)
    return destino


def _sessao():
    global _SESSAO
    if _SESSAO is None and caminho_modelo().exists():
        try:
            import onnxruntime as ort
            _SESSAO = ort.InferenceSession(str(caminho_modelo()), providers=["CPUExecutionProvider"])
        except Exception as exc:  # modelo corrompido ou onnxruntime ausente: segue no modo heurístico
            print(f"aviso: modelo de profundidade não carregou ({exc}); usando modo heurístico", file=sys.stderr)
            _SESSAO = False
    return _SESSAO or None


def modo() -> str:
    return "modelo" if _sessao() else "heuristica"


def _pelo_modelo(img: np.ndarray, lado: int = 518) -> np.ndarray:
    """Depth Anything: entrada múltipla de 14, normalizada ImageNet; saída = profundidade inversa (maior = perto)."""
    h, w = img.shape[:2]
    escala = lado / max(h, w)
    nh, nw = (max(14, int(round(h * escala / 14)) * 14), max(14, int(round(w * escala / 14)) * 14))
    x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (nw, nh), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    x = ((x - MEDIA) / DESVIO).transpose(2, 0, 1)[None]
    s = _sessao()
    y = s.run(None, {s.get_inputs()[0].name: x})[0]
    d = np.squeeze(y).astype(np.float32)
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)


def _heuristica(img: np.ndarray, pessoa: np.ndarray | None) -> np.ndarray:
    """Sem modelo: chão perto (embaixo), parede longe (em cima), detalhes nítidos um pouco mais perto, pessoa na frente."""
    h, w = img.shape[:2]
    d = np.tile(np.linspace(0.15, 0.55, h, dtype=np.float32)[:, None], (1, w))
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    nitidez = cv2.GaussianBlur(np.abs(cv2.Laplacian(cinza, cv2.CV_32F)), (0, 0), 25)
    d += 0.15 * nitidez / max(float(np.percentile(nitidez, 99)), 1e-6)
    if pessoa is not None:
        d = np.maximum(d, cv2.GaussianBlur(pessoa.astype(np.float32), (0, 0), 6) * 1.0)
    return np.clip(cv2.GaussianBlur(d, (0, 0), 3), 0, 1)


def heuristica_retrato(img: np.ndarray, pessoa: np.ndarray) -> np.ndarray:
    """Sem modelo, para pessoa falando com a câmera: a pessoa e uma faixa larga em volta dela (mão, produto que ela
    segura, ombro fora da máscara) ficam perto e quase não se mexem; o cenário fica longe, em degradê. A transição
    é suave para a paralaxe não rasgar a imagem na borda."""
    h, w = pessoa.shape
    r = max(3, int(w * 0.14))
    perto = cv2.dilate((pessoa > 0.3).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    perto = cv2.GaussianBlur(perto.astype(np.float32), (0, 0), r * 0.6)
    fundo = np.tile(np.linspace(0.1, 0.4, h, dtype=np.float32)[:, None], (1, w))
    return np.clip(np.maximum(np.maximum(fundo, perto * 0.95), pessoa), 0, 1)


def mapa(img: np.ndarray, pessoa: np.ndarray | None = None) -> tuple[np.ndarray, str]:
    """Profundidade 0..1 (1 = perto) do tamanho da imagem e o modo usado."""
    if _sessao():
        try:
            return _pelo_modelo(img), "modelo"
        except Exception as exc:
            print(f"aviso: modelo de profundidade falhou ({exc}); usando modo heurístico", file=sys.stderr)
    return _heuristica(img, pessoa), "heuristica"


def placa_limpa(quadros: list[np.ndarray], alfas: list[np.ndarray]) -> np.ndarray:
    """Cenário sem a pessoa: mediana de cada pixel nos quadros em que a pessoa não está ali; o que ela cobriu o
    tempo todo é preenchido (inpaint). Câmera parada = cenário perfeito; câmera na mão = levemente suave."""
    pilha = np.stack(quadros).astype(np.float32)                         # n, h, w, 3
    livre = np.stack([a < 0.1 for a in alfas])                           # n, h, w
    soma_livre = livre.sum(0)
    com_nan = np.where(livre[..., None], pilha, np.nan)
    import warnings
    with warnings.catch_warnings():                                      # pixel sempre coberto = NaN (vira buraco)
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(com_nan, axis=0)
    buraco = (soma_livre == 0).astype(np.uint8)
    med = np.where(np.isnan(med), 0, med).astype(np.uint8)
    if buraco.any():
        # inpaint em resolução menor (rápido) e só nos buracos; a borda é dilatada para não sobrar contorno
        h, w = buraco.shape
        f = 0.5
        peq = cv2.resize(med, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
        bpeq = cv2.dilate(cv2.resize(buraco, (int(w * f), int(h * f)), interpolation=cv2.INTER_NEAREST),
                          np.ones((9, 9), np.uint8))
        cheio = cv2.resize(cv2.inpaint(peq, bpeq, 12, cv2.INPAINT_TELEA), (w, h), interpolation=cv2.INTER_CUBIC)
        borda = cv2.GaussianBlur(cv2.dilate(buraco, np.ones((15, 15), np.uint8)).astype(np.float32), (0, 0), 6)[..., None]
        med = (cheio * borda + med * (1 - borda)).astype(np.uint8)
    return med


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if a[0] == "--baixar":
        print(f"OK: {baixar()} ({modo()})")
        return 0
    if a[0] == "--status":
        print(f"modo: {modo()}  modelo: {caminho_modelo()} ({'instalado' if caminho_modelo().exists() else 'ausente'})")
        return 0
    img = cv2.imread(a[0])
    if img is None:
        print(f"não consegui abrir {a[0]}")
        return 1
    d, m = mapa(img)
    cv2.imwrite(a[1], (d * 255).astype(np.uint8))
    print(f"OK ({m}): {a[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
