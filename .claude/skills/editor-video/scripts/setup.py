#!/usr/bin/env python3
"""Verifica (e opcionalmente instala) tudo que o editor precisa.

  python3 setup.py            só verifica e imprime STATUS de cada item
  python3 setup.py --install  instala pacotes Python que faltam (pip --user)
  python3 setup.py --models   baixa os modelos (~680 MB) para ~/.cache/editor-video/models
  python3 setup.py --voz-ia   instala a voz limpa por IA (Resemble Enhance, MIT; ~1 GB com o PyTorch)

Opcionais (o editor funciona sem eles, com as versões locais):
- Voz limpa por IA: Resemble Enhance (--voz-ia). Sem ele, voz.py usa a limpeza local.
- Música por IA: ACE-Step 1.5 (MIT), instalado à parte e rodando como servidor no seu PC:
    Windows: baixe https://files.acemusic.ai/acemusic/win/ACE-Step-1.5.7z, extraia e rode start_api_server.bat
    Mac/Linux: git clone https://github.com/ace-step/ACE-Step-1.5 && ./start_api_server.sh (macOS: _macos.sh)
  Com o servidor no ar (porta 8001), "--music auto:CLIMA" usa música de verdade; fora do ar, a sintetizada.

Fontes de download dos modelos (todas públicas):
- Parakeet TDT 0.6B v3 int8 (NVIDIA, CC-BY-4.0) empacotado pelo projeto sherpa-onnx (Apache-2.0),
  release do GitHub k2-fsa/sherpa-onnx.
- MediaPipe face detector + selfie segmenter (Apache-2.0), storage.googleapis.com.
"""

from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MODELS_DIR, perfil  # noqa: E402

PY_PKGS = {"numpy": "numpy", "PIL": "pillow", "sherpa_onnx": "sherpa-onnx", "mediapipe": "mediapipe"}
PARAKEET_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
                "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2")
MP_MODELS = {
    "blaze_face_short_range.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/"
                                     "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
                               "selfie_segmenter/float16/latest/selfie_segmenter.tflite",
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                            "hand_landmarker/float16/latest/hand_landmarker.task",
}


def fix_for(tool: str) -> str:
    osname = platform.system()
    table = {
        "ffmpeg": {"Darwin": "brew install ffmpeg", "Linux": "sudo apt install ffmpeg",
                   "Windows": "winget install --id Gyan.FFmpeg -e"},
        "python": {"Darwin": "brew install python@3.12", "Linux": "sudo apt install python3 python3-pip",
                   "Windows": "winget install --id Python.Python.3.12 -e"},
    }
    return table[tool].get(osname, table[tool]["Linux"])


def check_ffmpeg() -> bool:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print(f"STATUS ffmpeg MISSING -> {fix_for('ffmpeg')}")
        return False
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    need = ["ass", "alphamerge", "loudnorm", "drawbox", "sidechaincompress"]
    miss = [f for f in need if f" {f} " not in filters]
    if miss:
        print(f"STATUS ffmpeg INCOMPLETE (sem {', '.join(miss)}; precisa de build com libass) -> {fix_for('ffmpeg')}")
        return False
    print("STATUS ffmpeg OK")
    return True


def check_python(install: bool) -> bool:
    ok = sys.version_info >= (3, 10)
    print(f"STATUS python {'OK' if ok else 'TOO OLD (>=3.10) -> ' + fix_for('python')} {platform.python_version()}")
    missing = []
    for mod, pkg in PY_PKGS.items():
        try:
            importlib.import_module(mod)
            print(f"STATUS py:{pkg} OK")
        except ImportError:
            missing.append(pkg)
            print(f"STATUS py:{pkg} MISSING")
        except OSError as exc:
            print(f"STATUS py:{pkg} BROKEN ({exc}) -> Linux: sudo apt install libegl1 libgles2 libgl1")
            ok = False
    if missing and install:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", *missing], check=False)
    return ok and not missing


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"baixando {url} ...")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh, length=1 << 20)
    tmp.rename(dest)


def check_models(fetch: bool) -> bool:
    ok = True
    parakeet = MODELS_DIR / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
    if not (parakeet / "tokens.txt").exists():
        if fetch:
            arc = MODELS_DIR / "parakeet.tar.bz2"
            download(PARAKEET_URL, arc)
            with tarfile.open(arc) as tf:
                tf.extractall(MODELS_DIR, filter="data")
            arc.unlink()
        else:
            ok = False
    print(f"STATUS model:parakeet {'OK' if (parakeet / 'tokens.txt').exists() else 'MISSING -> setup.py --models'}")
    for name, url in MP_MODELS.items():
        p = MODELS_DIR / "mediapipe" / name
        if not p.exists() and fetch:
            download(url, p)
        print(f"STATUS model:{name} {'OK' if p.exists() else 'MISSING -> setup.py --models'}")
        ok = ok and p.exists()
    # profundidade (efeito 2.5D): opcional — sem ele o template profundidade usa o modo heurístico
    import profundidade
    if fetch and not profundidade.caminho_modelo().exists():
        try:
            profundidade.baixar()
        except Exception as exc:  # rede bloqueada etc.: segue sem, não reprova a instalação
            print(f"aviso: modelo de profundidade não baixou ({exc}); o 2.5D usa o modo heurístico")
    print(f"STATUS model:depth_anything_v2_small {'OK' if profundidade.caminho_modelo().exists() else 'OPCIONAL -> setup.py --models'}")
    return ok


def check_motion() -> bool:
    """Motion graphics: Node 18+ e Playwright com Chromium (renderizam as composições HTML)."""
    node = shutil.which("node")
    if not node:
        print("STATUS node MISSING -> https://nodejs.org (LTS) ou brew/apt/winget install nodejs")
        return False
    root = subprocess.run([shutil.which("npm"), "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""  # npm.cmd no Windows
    probe = subprocess.run(["node", "-e", "const path=require('path');for (const p of ['playwright','playwright-core',"
                            "'/opt/node-tools/node_modules/playwright', path.join(process.argv[1],'playwright')])"
                            "{try{require(p);process.exit(0)}catch{}};process.exit(1)", root],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        print("STATUS playwright MISSING -> npm install -g playwright && npx playwright install chromium")
        return False
    print("STATUS motion (node + playwright) OK")
    return True


def check_opcionais(voz_ia: bool) -> None:
    """Extras de qualidade (nunca bloqueiam o READY)."""
    import importlib.util
    if voz_ia and importlib.util.find_spec("resemble_enhance") is None:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "resemble-enhance"], check=False)
    tem = importlib.util.find_spec("resemble_enhance") is not None
    print(f"STATUS voz_ia (Resemble Enhance) {'OK' if tem else 'OPCIONAL -> setup.py --voz-ia (sem ele: limpeza local)'}")
    tem_ydl = importlib.util.find_spec("yt_dlp") is not None
    print(f"STATUS yt-dlp (referência por link) {'OK' if tem_ydl else 'OPCIONAL -> pip install yt-dlp'}")
    import musica_ia
    print(f"STATUS musica_ia (ACE-Step em {musica_ia.URL}) "
          f"{'OK' if musica_ia.disponivel() else 'OPCIONAL -> veja o topo do setup.py (sem ele: trilha sintetizada)'}")


def main() -> None:
    install, fetch = "--install" in sys.argv, "--models" in sys.argv
    p = perfil()
    print(f"STATUS pacote {p['perfil']}{'' if p['motion'] else ' (sem Pacote Motion 3D: animações desligadas)'}")
    results = [check_ffmpeg(), check_python(install), check_models(fetch)]
    if p["motion"]:
        results.append(check_motion())  # Node + Chromium só são necessários para as animações
    check_opcionais("--voz-ia" in sys.argv)
    print("READY" if all(results) else "NOT READY (veja as linhas STATUS acima)")


if __name__ == "__main__":
    main()
