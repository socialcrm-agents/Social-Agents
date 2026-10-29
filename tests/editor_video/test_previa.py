"""Prévia rápida de um trecho (run.py previa --de A --ate B): só a janela é composta, duração exata, nada vira versão.
EDITOR_TESTES_RENDER=1 python -m unittest tests/editor_video/test_previa.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402
from test_render_revisao import DUR, LIGADO, video_sintetico  # noqa: E402


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de ffmpeg, Node/Playwright e MediaPipe)")
class Previa(unittest.TestCase):
    def test_previa_so_da_janela(self):
        d = Path(tempfile.mkdtemp(prefix="ev_previa_"))
        try:
            clip = d / "s.mp4"
            video_sintetico(clip)
            proj = d / "proj"
            subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "new", str(proj), "--clips", str(clip),
                            "--style", "pro_clean", "--sem-cortes"], check=True, capture_output=True)
            words = [{"w": f"palavra{i}" + ("." if i % 6 == 5 else ""), "t0": round(0.2 + i * 0.5, 3),
                      "t1": round(0.55 + i * 0.5, 3), "clip": "c1"} for i in range(int((DUR - 0.8) / 0.5))]
            (proj / "transcript.json").write_text(json.dumps({"backend": "teste", "words": words, "silences": {}}))
            p = json.loads((proj / "project.json").read_text())
            p["overrides"]["motion"] = [{"template": "etiqueta", "at": 1.0, "dur": 2.0, "params": {"text": "LONGE"}},
                                        {"template": "palavra", "at": 13.0, "dur": 1.6, "params": {"text": "PERTO."}}]
            p["overrides"]["triggers"] = False
            (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False))
            r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "previa", str(proj), "--de", "12",
                                "--ate", "15.5"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
            out = proj / "renders" / "previa_012.0-015.5.mp4"
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                        str(out)], capture_output=True, text=True).stdout)
            self.assertAlmostEqual(dur, 3.5, delta=0.1)
            self.assertNotIn("etiqueta", r.stdout, "animação fora da janela foi renderizada")
            self.assertFalse((proj / "versions").exists() and any((proj / "versions").iterdir()), "prévia virou versão")
            self.assertEqual(json.loads((proj / "project.json").read_text()).get("version", 0), 0)
        finally:
            if not os.environ.get("EDITOR_TESTES_MANTER"):
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
