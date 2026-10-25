"""Sons e trilha (trilha.py, sfx.py, dsp.py) — só biblioteca padrão + numpy/ffmpeg do editor; Windows, Mac e Linux.

  python -m unittest discover -s tests/editor_video -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import numpy as np  # noqa: E402

import dsp  # noqa: E402
import revisao  # noqa: E402
import sfx  # noqa: E402
import trilha  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tmpdir(caso: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="ev_trilha_"))
    caso.addCleanup(shutil.rmtree, d, True)
    return d


def ffmpeg_loudness(path: Path) -> tuple[float, float]:
    """(LUFS integrado, pico verdadeiro dBTP) medidos pelo ffmpeg, para conferir a medição em numpy."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    resumo = r[r.rfind("Summary:"):]
    i = float(resumo.split("I:")[1].split()[0])
    pk = float(resumo.split("Peak:")[1].split()[0])
    return i, pk


def voz_sintetica(dur: float, fala: list[tuple[float, float]], semente: int = 7) -> np.ndarray:
    """Sinal com cara de voz (formantes + sílabas a ~4 Hz) só dentro das regiões de fala."""
    rng = np.random.default_rng(semente)
    n = dsp.seg(dur)
    t = dsp.tempo(n)
    f0 = 140 + 25 * np.sin(2 * np.pi * 0.7 * t)
    tab = dsp.tabela_onda(dsp.serra_limitada(140, 0.6))
    x = dsp.osc_tabela(tab, f0, n) + 0.08 * rng.standard_normal(n)
    x = dsp.filtro_fft(x, dsp.combina(dsp.r_sino(700, 9, 2), dsp.r_sino(1200, 7, 2), dsp.r_sino(2600, 5, 2),
                                      dsp.r_passa_alta(90, 2)))
    silabas = 0.5 + 0.5 * np.sin(2 * np.pi * 4.2 * t) ** 2
    mascara = np.zeros(n)
    for a, b in fala:
        mascara[dsp.seg(a):dsp.seg(b)] = 1
    mascara = dsp.filtro_fft(mascara, dsp.r_passa_baixa(30, 2))
    x = x * silabas * np.clip(mascara, 0, 1)
    return x / (np.max(np.abs(x)) + 1e-9) * 0.5


class Trilha(unittest.TestCase):
    def test_duracao_exata_em_amostras(self):
        d = tmpdir(self)
        for dur in (4.37, 11.0):
            info = trilha.gerar_arquivo("lofi", d / f"t{dur}.wav", dur, 84, 3)
            x = dsp.le_wav(d / f"t{dur}.wav")
            self.assertEqual(x.shape, (2, round(dur * 48000)))
            self.assertEqual(info["dur"], round(round(dur * 48000) / 48000, 3))
        # termina em silêncio (resolução + fade): nada de corte seco no último quadro
        self.assertLess(float(np.max(np.abs(x[:, -48:]))), 1e-3)

    def test_deterministico_mesma_semente_mesmos_bytes(self):
        d = tmpdir(self)
        trilha.gerar_arquivo("energia", d / "a.wav", 6.0, 140, 5)
        trilha.gerar_arquivo("energia", d / "b.wav", 6.0, 140, 5)
        trilha.gerar_arquivo("energia", d / "c.wav", 6.0, 140, 6)
        self.assertEqual(sha(d / "a.wav"), sha(d / "b.wav"))
        self.assertNotEqual(sha(d / "a.wav"), sha(d / "c.wav"))

    def test_todos_os_climas_sem_clip_e_masterizados(self):
        d = tmpdir(self)
        for clima in trilha.CLIMAS:
            info = trilha.gerar_arquivo(clima, d / f"{clima}.wav", 9.0, None, 1)
            self.assertLessEqual(info["pico_dbtp"], -1.0, clima)
            self.assertAlmostEqual(info["lufs"], -18.0, delta=0.5, msg=clima)
            self.assertEqual(dsp.le_wav(d / f"{clima}.wav").shape[0], 2)
        # a medição em numpy bate com a do ffmpeg (EBU R128)
        i, pk = ffmpeg_loudness(d / "energia.wav")
        self.assertAlmostEqual(i, -18.0, delta=0.5)
        self.assertLessEqual(pk, -1.0)

    def test_bpm_segue_o_ritmo_da_fala(self):
        lento = trilha.bpm_sugerido("energia", 2.0)
        rapido = trilha.bpm_sugerido("energia", 4.0)
        self.assertLess(lento, rapido)
        self.assertEqual((lento, rapido), trilha.CLIMAS["energia"]["bpm"])
        words = [{"t0": i * 0.33, "t1": i * 0.33 + 0.28} for i in range(30)]
        self.assertAlmostEqual(trilha.ritmo_da_fala(words), 3.0, delta=0.2)

    def test_video_longo_repete_o_corpo_sem_estourar_memoria(self):
        x = trilha.gerar("corporativo", trilha.MAX_DIRETO + 13.7, 112, 2)
        self.assertEqual(x.shape[1], dsp.seg(trilha.MAX_DIRETO + 13.7))
        self.assertLessEqual(dsp.pico_verdadeiro(x[:, -dsp.seg(20):]), -1.0)
        self.assertLess(float(np.max(np.abs(x[:, -48:]))), 1e-3)


class CacheEIntegracao(unittest.TestCase):
    def test_cache_por_pedido_e_chave_do_audio(self):
        d = tmpdir(self)
        words = [{"t0": 1.0 + i * 0.4, "t1": 1.3 + i * 0.4} for i in range(10)]
        m1 = trilha.trilha_do_projeto(d, {"auto": True, "clima": "lofi"}, 8.0, words)
        mtime = Path(m1["path"]).stat().st_mtime_ns
        m2 = trilha.trilha_do_projeto(d, {"auto": True, "clima": "lofi"}, 8.0, words)
        self.assertEqual(m1, m2)
        self.assertEqual(Path(m2["path"]).stat().st_mtime_ns, mtime, "mesmo pedido não pode regerar")
        self.assertTrue(Path(m1["path"]).name.startswith("trilha_"))
        m3 = trilha.trilha_do_projeto(d, {"auto": True, "clima": "suspense"}, 8.0, words)
        m4 = trilha.trilha_do_projeto(d, {"auto": True, "clima": "lofi", "semente": 2}, 8.0, words)
        self.assertEqual(len({m1["path"], m3["path"], m4["path"]}), 3)
        # chave do componente "audio" do motor de revisão: muda com a trilha, não com a pasta (dry-run)
        tl = {"sfx": [], "audio": {"lufs": -14}, "duration": 8.0}
        k1 = revisao.chave_audio({**tl, "music": m1}, ["p"])
        self.assertNotEqual(k1, revisao.chave_audio({**tl, "music": m3}, ["p"]))
        self.assertNotEqual(k1, revisao.chave_audio({**tl, "music": {**m1, "volume": 0.2}}, ["p"]))
        outra = trilha.trilha_do_projeto(tmpdir(self), {"auto": True, "clima": "lofi"}, 8.0, words)
        self.assertEqual(k1, revisao.chave_audio({**tl, "music": outra}, ["p"]))

    def test_ducking_no_mix_do_render_abaixa_pelo_menos_6_db(self):
        d = tmpdir(self)
        dur = 16.0
        fala = [(2.0, 6.0), (9.0, 13.0)]
        voz = voz_sintetica(dur, fala)
        dsp.grava_wav(d / "voz.wav", voz, 16)
        words = [{"w": "x", "t0": round(a + k * 0.25, 2), "t1": round(a + k * 0.25 + 0.2, 2)}
                 for a, b in fala for k in range(int((b - a) / 0.25))]
        musica = trilha.trilha_do_projeto(d, {"auto": True, "clima": "energia"}, dur, words)
        tl = {"duration": dur, "sfx": [], "audio": {"lufs": -14}, "music": musica, "words": words}
        res = trilha.medir_ducking(tl, d / "voz.wav", {}, d / "med")
        self.assertGreaterEqual(res["diferenca_db"], 6.0, res)   # nível da trilha: sem fala x com fala
        self.assertGreaterEqual(res["ducking_db"], 6.0, res)     # só o sidechain do render
        self.assertGreater(res["segundos_sem_fala"], 4)

    def test_edit_music_auto_grava_pedido_e_plano_padrao_nao_muda(self):
        proj = util.preparar("semcortes")
        self.addCleanup(shutil.rmtree, proj, True)
        tl0 = util.planejar(proj)
        self.assertIsNone(tl0["music"])
        util.rodar("edit.py", proj, "--music", "auto:lofi:0.4", "--trilha-bpm", "82", "--no-render")
        ov = json.loads((proj / "project.json").read_text(encoding="utf-8"))["overrides"]
        self.assertEqual(ov["music"], {"auto": True, "clima": "lofi", "volume": 0.4, "bpm": 82})
        tl = util.planejar(proj)
        m = tl["music"]
        self.assertTrue(Path(m["path"]).exists())
        self.assertEqual((m["auto"]["clima"], m["auto"]["bpm"], m["volume"]), ("lofi", 82.0, 0.4))
        self.assertEqual(m["auto"]["dur"], round(tl["duration"], 3))
        self.assertEqual(Path(m["path"]).parent, proj / "work")
        # o resto do plano é idêntico ao sem trilha
        self.assertEqual({k: v for k, v in tl.items() if k != "music"}, {k: v for k, v in tl0.items() if k != "music"})
        proc = util.rodar("edit.py", proj, "--music", "auto:rock", "--no-render", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("energia", proc.stdout + proc.stderr)
        util.rodar("edit.py", proj, "--music", "off", "--no-render")
        self.assertNotIn("music", json.loads((proj / "project.json").read_text(encoding="utf-8"))["overrides"])


class Efeitos(unittest.TestCase):
    def test_biblioteca_completa_normalizada_sem_clique(self):
        d = tmpdir(self)
        sons = sfx.biblioteca(d)
        antigos = {"whoosh", "pop", "boom", "ding", "tick", "click", "glitch", "venda", "riser"}
        novos = {"hit", "swoosh", "swipe", "camera_shutter", "notification", "cash", "plim", "pop_bolha"}
        self.assertTrue(antigos | novos <= set(sons))
        for nome, p in sons.items():
            x = dsp.le_wav(p)
            self.assertEqual(x.shape[0], 2, nome)
            self.assertLessEqual(dsp.pico_verdadeiro(x), -1.0, nome)
            self.assertLess(float(np.max(np.abs(x[:, 0]))), 2e-3, f"{nome}: começa com degrau")
            self.assertLess(float(np.max(np.abs(x[:, -1]))), 2e-3, f"{nome}: termina com degrau")
            self.assertAlmostEqual(sfx.loud_max(x), sfx.SONS[nome][1], delta=3.0, msg=nome)
        # versão gravada: não refaz à toa; os bytes são determinísticos
        h = sha(sons["whoosh"])
        mt = sons["whoosh"].stat().st_mtime_ns
        sons2 = sfx.biblioteca(d)
        self.assertEqual(sons2["whoosh"].stat().st_mtime_ns, mt)
        d2 = tmpdir(self)
        self.assertEqual(sha(sfx.biblioteca(d2)["whoosh"]), h)

    def test_render_usa_a_biblioteca(self):
        import assets
        d = tmpdir(self)
        self.assertEqual(set(assets.make_sfx(d)), set(sfx.SONS))


if __name__ == "__main__":
    unittest.main()
