#!/usr/bin/env python3
"""Verifica (e opcionalmente instala) tudo que o editor precisa.

  python3 setup.py            só verifica e imprime STATUS de cada item
  python3 setup.py --install  instala pacotes Python que faltam (pip --user)
  python3 setup.py --models   baixa os modelos (~680 MB) para ~/.cache/editor-video/models

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
from common import MODELS_DIR  # noqa: E402

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
    return ok


def check_motion() -> bool:
    """Motion graphics: Node 18+ e Playwright com Chromium (renderizam as composições HTML)."""
    node = shutil.which("node")
    if not node:
        print("STATUS node MISSING -> https://nodejs.org (LTS) ou brew/apt/winget install nodejs")
        return False
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    probe = subprocess.run(["node", "-e", "const path=require('path');for (const p of ['playwright','playwright-core',"
                            "'/opt/node-tools/node_modules/playwright', path.join(process.argv[1],'playwright')])"
                            "{try{require(p);process.exit(0)}catch{}};process.exit(1)", root],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        print("STATUS playwright MISSING -> npm install -g playwright && npx playwright install chromium")
        return False
    print("STATUS motion (node + playwright) OK")
    return True


def main() -> None:
    install, fetch = "--install" in sys.argv, "--models" in sys.argv
    results = [check_ffmpeg(), check_python(install), check_models(fetch), check_motion()]
    print("READY" if all(results) else "NOT READY (veja as linhas STATUS acima)")


if __name__ == "__main__":
    main()
