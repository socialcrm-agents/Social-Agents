"""Utilitários do anúncio de produto: caminhos, ffmpeg, JSON, erros com mensagem em português."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = SKILL_DIR / "assets" / "web"
FONTS_DIR = SKILL_DIR / "assets" / "fonts"
STYLES_DIR = SKILL_DIR / "estilos"
VOICES_FILE = SKILL_DIR / "vozes" / "vozes.json"
# os modelos ficam fora da skill (baixados uma vez); a pasta é a mesma do editor de vídeo, se ele existir
MODELS_DIR = Path(os.environ.get("ANUNCIO_MODELS", os.environ.get(
    "EDITOR_VIDEO_MODELS", Path.home() / ".cache" / "editor-video" / "models")))

W, H, FPS = 1080, 1920, 30
# TikTok/Reels: topo (busca/abas), base (legenda do post, carrinho do TikTok Shop) e coluna de botões à direita
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 200, 1480, 70, 150
DURATIONS = (10, 15, 20, 30, 45, 60)
WORDS_PER_SECOND = 2.3  # voz pronta em pt-BR (medido: Kokoro ~2,2 palavras/s a 1,1x); a voz real é medida depois
LEAD = 0.15       # respiro antes da primeira fala (s)
END_CARD = 1.2    # CTA parado na tela depois da última fala (s)


class AdError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        raise AdError(f"Comando falhou: {' '.join(map(str, cmd[:6]))} ...\n{proc.stderr[-1500:]}")
    return proc.stdout + proc.stderr


def ffmpeg(args: list[str], cwd: Path | None = None) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args], cwd=cwd)


def probe(path: Path | str) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
               "-of", "json", str(path)])
    data = json.loads(out[out.index("{"):])
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"duration": float(data.get("format", {}).get("duration") or 0),
            "width": v.get("width"), "height": v.get("height"),
            "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}


def load_json(path: Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def project_paths(project: Path) -> dict:
    project = Path(project)
    return {"root": project, "project": project / "produto.json", "script": project / "roteiro.json",
            "work": project / "work", "renders": project / "renders", "qa": project / "qa"}


def main_guard(fn) -> None:
    try:
        fn()
    except AdError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
