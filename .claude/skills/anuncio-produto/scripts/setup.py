#!/usr/bin/env python3
"""Verifica (e opcionalmente instala) tudo que o anúncio de produto precisa.

  python3 setup.py                    só verifica e imprime STATUS de cada item
  python3 setup.py --install          instala pacotes Python que faltam (pip --user)
  python3 setup.py --models           baixa voz Kokoro + voz Piper "faber" + recorte (~450 MB)
  python3 setup.py --models --todas-vozes   + vozes Piper "cadu" e "jeff" (~160 MB)
  python3 setup.py --models --voz-propria   + transcrição Parakeet (~640 MB), para usar a voz do cliente

Fontes (todas públicas, uso comercial permitido):
- Kokoro-82M (Apache-2.0) e vozes Piper pt_BR (dataset CC0), empacotados pelo sherpa-onnx (Apache-2.0),
  releases do GitHub k2-fsa/sherpa-onnx.
- IS-Net general use e U2-Net p (Apache-2.0), releases do GitHub danielgatis/rembg.
- Parakeet TDT 0.6B v3 (NVIDIA, CC-BY-4.0: citar a NVIDIA nos créditos), releases do sherpa-onnx.
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

PY_PKGS = {"numpy": "numpy", "PIL": "pillow", "sherpa_onnx": "sherpa-onnx", "onnxruntime": "onnxruntime"}
GH_TTS = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
GH_ASR = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
GH_CUT = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"
ARCHIVES = {  # nome da pasta -> (url, arquivo que prova que está instalado, grupo)
    "tts/kokoro-int8-multi-lang-v1_0": (GH_TTS + "kokoro-int8-multi-lang-v1_0.tar.bz2", "model.int8.onnx", "base"),
    "tts/vits-piper-pt_BR-faber-medium": (GH_TTS + "vits-piper-pt_BR-faber-medium.tar.bz2", "tokens.txt", "base"),
    "tts/vits-piper-pt_BR-cadu-medium": (GH_TTS + "vits-piper-pt_BR-cadu-medium.tar.bz2", "tokens.txt", "vozes"),
    "tts/vits-piper-pt_BR-jeff-medium": (GH_TTS + "vits-piper-pt_BR-jeff-medium.tar.bz2", "tokens.txt", "vozes"),
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8": (GH_ASR + "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2",
                                                   "tokens.txt", "propria"),
}
FILES = {"recorte/isnet-general-use.onnx": GH_CUT + "isnet-general-use.onnx",
         "recorte/u2netp.onnx": GH_CUT + "u2netp.onnx"}


def fix_for(tool: str) -> str:
    table = {"ffmpeg": {"Darwin": "brew install ffmpeg", "Linux": "sudo apt install ffmpeg",
                        "Windows": "winget install --id Gyan.FFmpeg -e"}}
    return table[tool].get(platform.system(), table[tool]["Linux"])


def check_ffmpeg() -> bool:
    ok = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    print(f"STATUS ffmpeg {'OK' if ok else 'MISSING -> ' + fix_for('ffmpeg')}")
    return ok


def check_python(install: bool) -> bool:
    ok = sys.version_info >= (3, 10)
    print(f"STATUS python {'OK' if ok else 'TOO OLD (>=3.10)'} {platform.python_version()}")
    missing = []
    for mod, pkg in PY_PKGS.items():
        try:
            importlib.import_module(mod)
            print(f"STATUS py:{pkg} OK")
        except ImportError:
            missing.append(pkg)
            print(f"STATUS py:{pkg} MISSING")
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


def check_models(fetch: bool, groups: set[str]) -> bool:
    ok = True
    for folder, (url, marker, group) in ARCHIVES.items():
        d = MODELS_DIR / folder
        if not (d / marker).exists() and fetch and group in groups:
            arc = d.parent / (d.name + ".tar.bz2")
            download(url, arc)
            with tarfile.open(arc) as tf:
                tf.extractall(d.parent, filter="data")
            arc.unlink()
        have = (d / marker).exists()
        need = group == "base"
        label = {"base": "", "vozes": " (opcional: --todas-vozes)", "propria": " (opcional: --voz-propria)"}[group]
        print(f"STATUS model:{d.name} {'OK' if have else 'MISSING' + label}")
        ok = ok and (have or not need)
    for rel, url in FILES.items():
        p = MODELS_DIR / rel
        if not p.exists() and fetch:
            download(url, p)
        print(f"STATUS model:{p.name} {'OK' if p.exists() else 'MISSING -> setup.py --models'}")
        ok = ok and p.exists()
    return ok


def check_render() -> bool:
    if not shutil.which("node"):
        print("STATUS node MISSING -> https://nodejs.org (LTS)")
        return False
    root = subprocess.run([shutil.which("npm"), "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""  # npm.cmd no Windows
    probe = subprocess.run(["node", "-e", "const path=require('path');for (const p of ['playwright','playwright-core',"
                            "'/opt/node-tools/node_modules/playwright', path.join(process.argv[1],'playwright')])"
                            "{try{require(p);process.exit(0)}catch{}};process.exit(1)", root], capture_output=True)
    if probe.returncode != 0:
        print("STATUS playwright MISSING -> npm install -g playwright && npx playwright install chromium")
        return False
    print("STATUS render (node + playwright) OK")
    return True


def main() -> None:
    install, fetch = "--install" in sys.argv, "--models" in sys.argv
    groups = {"base"} | ({"vozes"} if "--todas-vozes" in sys.argv else set()) | \
             ({"propria"} if "--voz-propria" in sys.argv else set())
    results = [check_ffmpeg(), check_python(install), check_models(fetch, groups), check_render()]
    print("READY" if all(results) else "NOT READY (veja as linhas STATUS acima)")


if __name__ == "__main__":
    main()
