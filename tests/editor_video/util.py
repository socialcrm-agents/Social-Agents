"""Utilitários dos testes do editor-video (só biblioteca padrão; roda em Windows, Mac e Linux)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SK = REPO / ".claude" / "skills" / "editor-video"
SCRIPTS = SK / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
# vídeo de referência (opcional): testes de render só rodam se ele existir ou se a variável apontar para ele
REF_VIDEO = Path(os.environ.get("EDITOR_REF_VIDEO", "")) if os.environ.get("EDITOR_REF_VIDEO") else None


def preparar(fixture: str, clip: Path | None = None) -> Path:
    """Copia a fixture para uma pasta temporária e aponta os clipes para `clip` (ou um caminho fictício)."""
    tmp = Path(tempfile.mkdtemp(prefix=f"ev_{fixture}_"))
    for f in (FIXTURES / fixture).glob("*.json"):
        if not f.name.startswith("golden_"):
            shutil.copy2(f, tmp / f.name)
    p = json.loads((tmp / "project.json").read_text(encoding="utf-8"))
    for c in p["clips"]:
        c["path"] = str(clip) if clip else c["path"]
    (tmp / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return tmp


def rodar(script: str, project: Path, *extra: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), str(project), *extra],
                          capture_output=True, text=True, encoding="utf-8", env=env)
    if check and proc.returncode != 0:
        raise AssertionError(f"{script} falhou:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return proc


def planejar(project: Path) -> dict:
    rodar("analyze.py", project)
    rodar("plan.py", project)
    return json.loads((project / "timeline.json").read_text(encoding="utf-8"))


# campos que o motor de revisão acrescenta (ids, origem de patch) e que não mudam o resultado do vídeo
CAMPOS_NOVOS = {"id", "i", "_patch", "_gerado"}


def normalizar(obj):
    """Tira campos de identificação e o caminho do clipe para comparar com o baseline."""
    if isinstance(obj, dict):
        return {k: normalizar(v) for k, v in obj.items() if k not in CAMPOS_NOVOS and k != "src"}
    if isinstance(obj, list):
        return [normalizar(x) for x in obj]
    return obj
