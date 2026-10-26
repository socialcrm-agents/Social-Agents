"""Voz limpa de estúdio (voz.py): tira ruído sem estragar a fala, baixa as pausas, segura o S, liga no projeto
(--voz estudio) e, no render real, a voz continua sincronizada com a imagem.
python -m unittest tests/editor_video/test_voz.py -v      (render real: EDITOR_TESTES_RENDER=1)
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

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import dsp  # noqa: E402
import voz  # noqa: E402

SR = dsp.SR
FALA = [[0.5, 1.7], [2.2, 3.6], [4.1, 5.4]]


def voz_sintetica(dur: float = 6.0) -> np.ndarray:
    """Frases "faladas" (harmônicos com vibrato) nos trechos de FALA."""
    t = np.arange(int(SR * dur)) / SR
    x = np.zeros_like(t)
    for k, (a, b) in enumerate(FALA):
        m = (t >= a) & (t < b)
        f0 = 140 + 30 * k + 20 * np.sin(2 * np.pi * 3 * t[m])
        fase = 2 * np.pi * np.cumsum(f0) / SR
        x[m] = 0.2 * sum(np.sin(h * fase) / h for h in range(1, 25)) * np.hanning(m.sum())
    return x


def snr(limpo: np.ndarray, outro: np.ndarray, m: np.ndarray) -> float:
    return 10 * np.log10(np.sum(limpo[m] ** 2) / np.sum((outro - limpo)[m] ** 2))


class Limpeza(unittest.TestCase):
    def setUp(self):
        self.limpo = voz_sintetica()
        r = dsp.ruido(np.random.default_rng(2), len(self.limpo), "rosa")
        self.sujo = self.limpo + r * 0.02 / np.sqrt(np.mean(r ** 2))
        self.m = voz.mascara_fala(len(self.limpo), FALA, 0)

    def test_tira_ruido_durante_a_fala_sem_estragar_a_voz(self):
        y = voz.tirar_ruido(self.sujo, FALA)
        ganho = snr(self.limpo, y, self.m) - snr(self.limpo, self.sujo, self.m)
        self.assertGreater(ganho, 4.0, f"melhora de SNR na fala só {ganho:.1f} dB")

    def test_pausas_bem_mais_baixas_e_sem_estourar(self):
        y = voz.limpar_local(self.sujo, FALA)
        pausa = ~voz.mascara_fala(len(y), FALA, 0.15)
        self.assertLess(dsp.rms_db(y[pausa]) - dsp.rms_db(self.sujo[pausa]), -15)
        self.assertLessEqual(np.max(np.abs(y)), 0.9)

    def test_sem_transcricao_aprende_o_ruido_nos_trechos_mais_baixos(self):
        y = voz.tirar_ruido(self.sujo, None)
        self.assertGreater(snr(self.limpo, y, self.m), snr(self.limpo, self.sujo, self.m) + 2)

    def test_deesser_segura_so_o_s(self):
        t = np.arange(SR) / SR
        vogal = 0.3 * np.sin(2 * np.pi * 220 * t)
        s = np.zeros_like(t)
        s[SR // 2:SR // 2 + SR // 5] = 0.5 * dsp.passa_banda(dsp.ruido(np.random.default_rng(1), SR // 5), 7000, 2.0)
        y = voz.deesser(vogal + s)
        banda = lambda z: dsp.rms_db(dsp.filtro_fft(z, dsp.r_passa_banda(7000, 2.0))[SR // 2:SR // 2 + SR // 5])
        self.assertLess(banda(y), banda(vogal + s) - 2.0)
        self.assertAlmostEqual(dsp.rms_db(y[:SR // 3]), dsp.rms_db(vogal[:SR // 3]), delta=0.5)

    def test_cli_mede_antes_e_depois(self):
        d = Path(tempfile.mkdtemp(prefix="ev_voz_"))
        try:
            dsp.grava_wav(d / "sujo.wav", self.sujo)
            r = subprocess.run([sys.executable, str(util.SCRIPTS / "voz.py"), "limpar", str(d / "sujo.wav"),
                                str(d / "limpo.wav"), "--fala", ",".join(f"{a}-{b}" for a, b in FALA), "--modo", "local"],
                               capture_output=True, text=True, check=True)
            res = json.loads(r.stdout.strip().splitlines()[-1])
            self.assertEqual(res["rota"], "local")
            self.assertLess(res["depois"]["ruido_pausas_db"], res["antes"]["ruido_pausas_db"] - 12)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class Projeto(unittest.TestCase):
    def test_pedido_vai_para_a_timeline_e_muda_so_a_chave_do_audio(self):
        import revisao
        proj = util.preparar("semcortes")
        try:
            tl0 = util.planejar(proj)
            self.assertNotIn("voz", tl0["audio"], "sem pedido a timeline não muda (goldens)")
            util.rodar("edit.py", proj, "--voz", "estudio", "--no-render")
            tl = util.planejar(proj)
            self.assertEqual(tl["audio"]["voz"], "estudio")
            cp = ["x"]
            self.assertNotEqual(revisao.chave_audio(tl0, cp), revisao.chave_audio(tl, cp))
            self.assertEqual(revisao.chave_trecho(tl0, 0, 4, cp, {}, False, "p", "f"),
                             revisao.chave_trecho(tl, 0, 4, cp, {}, False, "p", "f"), "vídeo não precisa ser refeito")
            util.rodar("edit.py", proj, "--voz", "off", "--no-render")
            self.assertNotIn("voz", util.planejar(proj)["audio"])
        finally:
            shutil.rmtree(proj, ignore_errors=True)


LIGADO = os.environ.get("EDITOR_TESTES_RENDER") == "1" and shutil.which("ffmpeg") and shutil.which("node")


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de ffmpeg e Node/Playwright)")
class Render(unittest.TestCase):
    def test_render_com_voz_de_estudio_mantem_sincronia(self):
        from test_render_revisao import EVENTOS, bipes, video_sintetico
        d = Path(tempfile.mkdtemp(prefix="ev_vozr_"))
        try:
            clip = d / "s.mp4"
            video_sintetico(clip)
            proj = d / "proj"
            subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "new", str(proj), "--clips", str(clip),
                            "--style", "pro_clean", "--sem-cortes", "--sem-receita"], check=True, capture_output=True)
            words = [{"w": f"bipe{i}.", "t0": round(t - 0.05, 3), "t1": round(t + 0.15, 3), "clip": "c1"}
                     for i, t in enumerate(EVENTOS)]
            (proj / "transcript.json").write_text(json.dumps({"backend": "teste", "words": words, "silences": {}}))
            p = json.loads((proj / "project.json").read_text())
            p["overrides"].update(triggers=False, voz="estudio")
            (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False))
            r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "render", str(proj), "--draft"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
            self.assertIn("voz de estúdio", r.stdout)
            com = bipes(next((proj / "renders").glob("v1_*.mp4")))
            # o mesmo projeto com a voz padrão: a voz de estúdio não pode mudar o sincronismo (latência 0 vs 25 ms
            # compensados na cadeia padrão)
            p = json.loads((proj / "project.json").read_text())
            p["overrides"].pop("voz")
            (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False))
            subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "render", str(proj), "--draft"],
                           check=True, capture_output=True)
            sem = bipes(next((proj / "renders").glob("v2_*.mp4")))
            self.assertEqual(len(com), len(EVENTOS))
            for a, b in zip(com, sem):
                self.assertAlmostEqual(a, b, delta=0.006, msg=f"voz de estúdio fora de sincronia: {a}s vs {b}s")
        finally:
            if not os.environ.get("EDITOR_TESTES_MANTER"):
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
