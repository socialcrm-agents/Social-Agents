"""Utilidades compartilhadas pelo editor de vídeo (ffmpeg, json, caminhos)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = SKILL_DIR / "assets" / "fonts"
STYLES_DIR = SKILL_DIR / "styles"
BRANDS_DIR = SKILL_DIR / "brands"
MODELS_DIR = Path(os.environ.get("EDITOR_VIDEO_MODELS", Path.home() / ".cache" / "editor-video" / "models"))

W, H, FPS = 1080, 1920, 30
# Zona segura do Reels/TikTok: nada importante acima de 220px nem abaixo de 1470px.
SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE = 220, 1470, 60
FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def safe_zone(w: int, h: int) -> tuple[int, int, int]:
    """(topo, base, lateral) seguros. Vertical: interface do Reels/TikTok. Horizontal: margem de TV/YouTube."""
    if h > w:
        return int(h * 0.115), int(h * 0.765), 60
    return int(h * 0.07), int(h * 0.92), int(w * 0.05)


def perfil() -> dict:
    """Pacote instalado: "completo" (padrão, este repositório), "corte-viral" (front, sem animações 3D) ou
    "corte-viral" + Pacote Motion por cima (volta a "completo"). Vem de perfil.json, gerado pelo empacotador."""
    data = {"perfil": "completo", "motion": True}
    p = SKILL_DIR / "perfil.json"
    if p.exists():
        data.update(json.loads(p.read_text(encoding="utf-8")))
    # sem os arquivos do motor de animação, o motion fica desligado mesmo que o perfil diga o contrário
    data["motion"] = bool(data["motion"]) and (SKILL_DIR / "assets" / "motion").is_dir()
    return data


class EditorError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], cwd: Path | None = None, quiet: bool = True) -> str:
    """Executa um comando e devolve o stderr+stdout. Falha com a cauda do log."""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        tail = "\n".join(out.strip().splitlines()[-25:])
        raise EditorError(f"Falhou: {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    if not quiet:
        log(out)
    return out


def ffmpeg(args: list[str], cwd: Path | None = None) -> str:
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args], cwd=cwd)


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    data = json.loads(out)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    info = {"path": str(path), "duration": float(data["format"].get("duration", 0)), "has_audio": a is not None}
    if v:
        num, den = (v.get("avg_frame_rate") or "30/1").split("/")
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        w, h = int(v["width"]), int(v["height"])
        if abs(rot) in (90, 270):
            w, h = h, w
        info.update(width=w, height=h, fps=round(float(num) / float(den or 1), 3))
    return info


def load_json(path: Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_brand(slug: str | None) -> dict:
    """Kit de marca (brands/<slug>/brand.json): cores, fontes, logo, voz, CTAs, correções de palavras."""
    if not slug:
        return {}
    path = BRANDS_DIR / slug / "brand.json"
    if not path.exists():
        names = ", ".join(p.name for p in BRANDS_DIR.iterdir() if (p / "brand.json").exists()) if BRANDS_DIR.exists() else ""
        raise EditorError(f"Marca '{slug}' não existe em brands/. Disponíveis: {names or 'nenhuma'}")
    brand = load_json(path)
    brand["_dir"] = str(path.parent)
    return brand


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_style(name: str, brand: str | dict | None = None) -> dict:
    """Estilo base + identidade da marca (cores de destaque, fontes e ajustes por estilo definidos no brand.json)."""
    path = STYLES_DIR / f"{name}.json"
    if not path.exists():
        names = ", ".join(p.stem for p in STYLES_DIR.glob("*.json"))
        raise EditorError(f"Estilo '{name}' não existe. Disponíveis: {names}")
    style = load_json(path)
    b = load_brand(brand) if isinstance(brand, str) else (brand or {})
    if not b:
        return style
    accent = (b.get("colors") or {}).get("accent")
    if accent:
        style["graphics"]["accent"] = accent
        style["captions"]["emph_color"] = accent
        if style["captions"].get("highlight", "none") != "none":
            style["captions"]["highlight"] = accent
    return _deep_merge(style, (b.get("styles") or {}).get(name, {}))


def norm(word: str) -> str:
    """Palavra minúscula, sem acento e sem pontuação (para comparar tomadas)."""
    word = unicodedata.normalize("NFKD", word.lower())
    word = "".join(c for c in word if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9%$]", "", word)


def project_paths(project: Path) -> dict[str, Path]:
    project = Path(project)
    return {
        "project": project / "project.json",
        "transcript": project / "transcript.json",
        "edl": project / "edl.json",
        "timeline": project / "timeline.json",
        "work": project / "work",
        "renders": project / "renders",
        "versions": project / "versions",
        "qa": project / "qa",
    }


def require_tools() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        raise EditorError(f"Faltando: {', '.join(missing)}. Rode scripts/setup.py para instruções.")


def main_guard(fn):
    try:
        fn()
    except EditorError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
