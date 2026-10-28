"""Anime.js e Lottie no relógio do render: os templates `cinetico` (4 estilos) e `lottie` desenham, animam e são
determinísticos (o mesmo quadro sai igual). Precisa de Node + Playwright.
EDITOR_TESTES_RENDER=1 python -m unittest tests/editor_video/test_motion_libs.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import util

LIGADO = os.environ.get("EDITOR_TESTES_RENDER") == "1" and shutil.which("node") and shutil.which("ffmpeg")
MOTION = util.SK / "assets" / "motion"

LOTTIE = {"v": "5.7.4", "fr": 30, "ip": 0, "op": 30, "w": 200, "h": 200, "nm": "t", "ddd": 0, "assets": [],
          "layers": [{"ddd": 0, "ind": 1, "ty": 4, "nm": "q", "sr": 1, "ip": 0, "op": 30, "st": 0, "bm": 0, "ao": 0,
                      "ks": {"o": {"a": 0, "k": 100}, "p": {"a": 0, "k": [100, 100, 0]}, "a": {"a": 0, "k": [0, 0, 0]},
                             "s": {"a": 0, "k": [100, 100, 100]},
                             "r": {"a": 1, "k": [{"t": 0, "s": [0], "i": {"x": [0.5], "y": [1]},
                                                  "o": {"x": [0.5], "y": [0]}}, {"t": 30, "s": [90]}]}},
                      "shapes": [{"ty": "gr", "it": [
                          {"ty": "rc", "d": 1, "s": {"a": 0, "k": [120, 120]}, "p": {"a": 0, "k": [0, 0]},
                           "r": {"a": 0, "k": 10}},
                          {"ty": "fl", "c": {"a": 0, "k": [0.1, 0.8, 0.4, 1]}, "o": {"a": 0, "k": 100}, "r": 1},
                          {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
                           "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}}]}]}]}


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de Node/Playwright e ffmpeg)")
class Bibliotecas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp(prefix="ev_libs_"))
        (cls.d / "work").mkdir()
        (cls.d / "work" / "anim.json").write_text(json.dumps(LOTTIE))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def render(self, nome: str, page: str, params: dict, dur: float = 1.6) -> Path:
        out = self.d / f"{nome}.mov"
        job = {"page": page, "out": str(out), "w": 540, "h": 960, "fps": 30, "duration": dur, "params": params,
               "opaque": False, "webgl": False, "roots": {"/": str(MOTION), "/fonts/": str(util.SK / "assets" / "fonts"),
                                                          "/work/": str(self.d / "work")}}
        jf = self.d / f"{nome}.job.json"
        jf.write_text(json.dumps(job))
        r = subprocess.run(["node", str(util.SCRIPTS / "motion_render.mjs"), str(jf)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        return out

    def alfas(self, mov: Path) -> list[float]:
        """Fração de pixels visíveis (alfa > 0) por quadro."""
        raw_a = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mov), "-vf", "scale=54:96,format=rgba,alphaextract",
                                "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        n = 54 * 96
        return [sum(1 for b in raw_a[i:i + n] if b > 10) / n for i in range(0, len(raw_a), n)]

    def test_cinetico_todos_os_estilos_animam_e_somem_no_fim(self):
        for est in ("sobe", "onda", "explode", "maquina"):
            a = self.alfas(self.render(f"cin_{est}", "/templates/cinetico.html",
                                       {"text": "Ninguém te conta esse segredo", "estilo": est, "destaque": "segredo"}))
            self.assertGreater(max(a), 0.01, f"{est}: nada desenhado")
            self.assertLess(a[-1], max(a) * 0.5, f"{est}: não saiu no fim")
            self.assertGreater(len({round(x, 3) for x in a[:20]}), 3, f"{est}: não anima na entrada")

    def test_lottie_toca_no_tempo(self):
        a = self.alfas(self.render("lot", "/templates/lottie.html", {"src": "/work/anim.json", "tamanho": 300}))
        self.assertGreater(max(a), 0.02)

    def test_deterministico(self):
        p = {"text": "Mesmo quadro sempre", "estilo": "explode"}
        h = [hashlib.md5(self.render(f"det{i}", "/templates/cinetico.html", p).read_bytes()).hexdigest() for i in (1, 2)]
        a1 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(self.d / "det1.mov"), "-f", "framemd5", "-"],
                            capture_output=True, text=True).stdout.splitlines()[-10:]
        a2 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(self.d / "det2.mov"), "-f", "framemd5", "-"],
                            capture_output=True, text=True).stdout.splitlines()[-10:]
        self.assertEqual(a1, a2, f"quadros diferentes entre dois renders ({h})")


if __name__ == "__main__":
    unittest.main()
