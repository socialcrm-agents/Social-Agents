"""Trilha por IA (musica_ia.py) contra um servidor ACE-Step de mentira (mesmo protocolo da API real:
release_task -> query_result -> /v1/audio): pedido certo, acabamento (duração, loudness, pico, final suave),
cache, e volta para a trilha sintetizada quando o servidor está fora do ar ou falha.
python -m unittest tests/editor_video/test_musica_ia.py -v
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import dsp  # noqa: E402
import musica_ia  # noqa: E402
import trilha  # noqa: E402


def wav_bytes(dur: float, sr: int = 44100) -> bytes:
    t = np.arange(int(sr * dur)) / sr
    x = 0.5 * np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 2 * t))
    st = np.round(np.stack([x, x]).T * 32767).astype("<i2")
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(st.tobytes())
    return b.getvalue()


class Falso(BaseHTTPRequestHandler):
    pedidos: list = []
    falhar = False
    consultas = 0

    def log_message(self, *a):
        pass

    def _json(self, obj):
        corpo = json.dumps({"data": obj, "code": 200, "error": None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            return self._json({"models": ["acestep-v15-turbo"]})
        if self.path.startswith("/v1/audio"):
            dur = Falso.pedidos[-1]["audio_duration"]
            corpo = wav_bytes(dur)
            self.send_response(200)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return None
        self.send_error(404)

    def do_POST(self):
        dados = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/release_task":
            Falso.pedidos.append(dados)
            return self._json({"task_id": "t1", "status": "queued"})
        if self.path == "/query_result":
            Falso.consultas += 1
            if Falso.falhar:
                return self._json([{"task_id": "t1", "status": 2, "result": "sem memória"}])
            if Falso.consultas % 2:   # primeira consulta: ainda gerando
                return self._json([{"task_id": "t1", "status": 0}])
            res = [{"file": "/v1/audio?path=/tmp/x.wav", "status": 1, "metas": {"bpm": 128}}]
            return self._json([{"task_id": "t1", "status": 1, "result": json.dumps(res)}])
        self.send_error(404)


class MusicaIA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Falso)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url_ok = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.time_sleep = musica_ia.time.sleep
        musica_ia.time.sleep = lambda s: None

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        musica_ia.time.sleep = cls.time_sleep

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="ev_mia_"))
        Falso.pedidos.clear()
        Falso.falhar = False
        musica_ia.URL = self.url_ok

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_pedido_e_acabamento(self):
        info = musica_ia.gerar_arquivo("energia", self.work / "t.wav", 12.4, 130, 7)
        p = Falso.pedidos[-1]
        self.assertEqual((p["bpm"], p["seed"], p["use_random_seed"], p["lyrics"]), (130, 7, False, "[Instrumental]"))
        self.assertGreaterEqual(p["audio_duration"], 12.4)
        self.assertIn("no vocals", p["prompt"])
        x = dsp.le_wav(self.work / "t.wav")
        self.assertEqual(x.shape[1], dsp.seg(12.4))
        self.assertAlmostEqual(dsp.loudness(x), trilha.ALVO_LUFS, delta=1.0)
        self.assertLessEqual(dsp.pico_verdadeiro(x), trilha.TETO_DBTP + 0.05)
        self.assertLess(np.max(np.abs(x[:, -dsp.seg(0.05):])), 0.01, "final sem fade")
        self.assertEqual(info["motor"], "ia")

    def test_projeto_usa_ia_e_reaproveita_o_cache(self):
        words = [{"w": "oi", "t0": 1.0, "t1": 1.4}, {"w": "gente", "t0": 1.5, "t1": 2.0},
                 {"w": "olha", "t0": 2.1, "t1": 2.4}, {"w": "isso.", "t0": 2.5, "t1": 3.0}]
        m = trilha.trilha_do_projeto(self.work, {"auto": True, "clima": "lofi"}, 10.0, words)
        self.assertEqual(m["auto"]["motor"], "ia")
        self.assertIn("trilha_ia_", m["path"])
        n = len(Falso.pedidos)
        m2 = trilha.trilha_do_projeto(self.work, {"auto": True, "clima": "lofi"}, 10.0, words)
        self.assertEqual((m2["path"], len(Falso.pedidos)), (m["path"], n), "segunda vez veio do cache")

    def test_fora_do_ar_usa_sintetizada_e_timeline_nao_muda(self):
        musica_ia.URL = "http://127.0.0.1:9"     # porta fechada
        m = trilha.trilha_do_projeto(self.work, {"auto": True, "clima": "lofi"}, 6.0, [])
        self.assertNotIn("motor", m["auto"], "pedido antigo (motor auto) sem IA: timeline idêntica à de antes")
        self.assertNotIn("trilha_ia_", m["path"])
        m = trilha.trilha_do_projeto(self.work, {"auto": True, "clima": "lofi", "motor": "ia"}, 6.0, [])
        self.assertEqual(m["auto"]["motor"], "sintetizada")

    def test_ia_falha_volta_para_sintetizada(self):
        Falso.falhar = True
        m = trilha.trilha_do_projeto(self.work, {"auto": True, "clima": "energia"}, 6.0, [])
        self.assertNotIn("trilha_ia_", m["path"])

    def test_motor_sintetizada_nem_consulta_o_servidor(self):
        m = trilha.trilha_do_projeto(self.work, {"auto": True, "clima": "energia", "motor": "sintetizada"}, 6.0, [])
        self.assertEqual((m["auto"]["motor"], Falso.pedidos), ("sintetizada", []))


if __name__ == "__main__":
    unittest.main()
