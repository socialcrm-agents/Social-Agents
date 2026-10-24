"""Profundidade / 2.5D: mapa heurístico, placa limpa, caminho do modelo ONNX (com um modelo falso) e o gancho que
prepara os dados do template.  python -m unittest tests/editor_video/test_profundidade.py -v
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import profundidade  # noqa: E402


def pessoa(h=192, w=108, cx=54):
    m = np.zeros((h, w), np.float32)
    cv2.ellipse(m, (cx, 70), (22, 30), 0, 0, 360, 1, -1)       # cabeça
    cv2.rectangle(m, (cx - 35, 100), (cx + 35, h), 1, -1)      # tronco
    return m


class Heuristica(unittest.TestCase):
    def test_pessoa_e_o_que_esta_em_volta_ficam_perto_e_o_fundo_longe(self):
        img = np.full((192, 108, 3), 120, np.uint8)
        d = profundidade.heuristica_retrato(img, pessoa())
        self.assertGreater(d[70, 54], 0.95)            # rosto
        self.assertGreater(d[70, 54 + 30], 0.6)        # ao lado do rosto (mão / produto que ela segura)
        self.assertLess(d[5, 3], 0.2)                  # canto de cima: parede longe
        self.assertTrue(0 <= d.min() and d.max() <= 1)


class PlacaLimpa(unittest.TestCase):
    def test_recupera_o_cenario_onde_a_pessoa_passou_e_preenche_o_que_ela_sempre_cobriu(self):
        fundo = np.zeros((96, 96, 3), np.uint8)
        fundo[:, :48] = (40, 160, 40)
        fundo[:, 48:] = (160, 40, 40)
        quadros, alfas = [], []
        for cx in (30, 40, 50, 60):                    # a pessoa anda: o centro (45-50) fica sempre coberto
            q, a = fundo.copy(), np.zeros((96, 96), np.float32)
            cv2.rectangle(a, (cx - 15, 20), (cx + 15, 96), 1, -1)
            q[a > 0] = (255, 255, 255)
            quadros.append(q)
            alfas.append(a)
        placa = profundidade.placa_limpa(quadros, alfas)
        self.assertLess(np.abs(placa[50, 20].astype(int) - fundo[50, 20]).max(), 6)   # coberto às vezes: recuperado
        self.assertLess(np.abs(placa[50, 75].astype(int) - fundo[50, 75]).max(), 6)
        self.assertLess(int(placa[60, 47].max()), 230, "sobrou a pessoa (branco) na placa")
        self.assertGreater(int(placa[60, 47].max()), 20, "buraco preto na placa")


class Modelo(unittest.TestCase):
    """O caminho do Depth Anything com um ONNX falso de mesma interface (pixel_values -> predicted_depth)."""

    def setUp(self):
        try:
            import onnx
            from onnx import TensorProto, helper
        except ImportError:
            self.skipTest("pacote onnx não instalado (só para montar o modelo falso)")
        g = helper.make_graph(
            [helper.make_node("ReduceMean", ["pixel_values", "eixos"], ["predicted_depth"], keepdims=0)], "falso",
            [helper.make_tensor_value_info("pixel_values", TensorProto.FLOAT, [1, 3, "h", "w"])],
            [helper.make_tensor_value_info("predicted_depth", TensorProto.FLOAT, [1, "h", "w"])],
            [helper.make_tensor("eixos", TensorProto.INT64, [1], [1])])
        m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 18)])
        m.ir_version = 9
        self.dir = Path(tempfile.mkdtemp())
        onnx.save(m, self.dir / "falso.onnx")
        os.environ["EDITOR_DEPTH_MODEL"] = str(self.dir / "falso.onnx")
        profundidade._SESSAO = None

    def tearDown(self):
        os.environ.pop("EDITOR_DEPTH_MODEL", None)
        profundidade._SESSAO = None

    def test_usa_o_modelo_quando_instalado_e_devolve_mapa_do_tamanho_da_imagem(self):
        self.assertEqual(profundidade.modo(), "modelo")
        img = np.zeros((300, 170, 3), np.uint8)
        img[:, 85:] = 255                                  # lado claro = "perto" no modelo falso
        d, modo = profundidade.mapa(img)
        self.assertEqual(modo, "modelo")
        self.assertEqual(d.shape, (300, 170))
        self.assertGreater(d[150, 160], 0.9)
        self.assertLess(d[150, 10], 0.1)

    def test_modelo_quebrado_cai_no_heuristico_sem_derrubar_o_render(self):
        (self.dir / "falso.onnx").write_bytes(b"lixo")
        profundidade._SESSAO = None
        d, modo = profundidade.mapa(np.zeros((64, 36, 3), np.uint8))
        self.assertEqual(modo, "heuristica")
        self.assertEqual(d.shape, (64, 36))


class GanchoDoTemplate(unittest.TestCase):
    def test_prepara_mapas_por_quadro_e_reaproveita(self):
        work = Path(tempfile.mkdtemp())
        rel = "motion/frames_teste"
        fdir = work / rel
        for sub in ("plate", "cut"):
            (fdir / sub).mkdir(parents=True)
        for i in range(1, 7):
            q = np.full((192, 108, 3), 90, np.uint8)
            a = (pessoa(cx=40 + i * 3) * 255).astype(np.uint8)
            cv2.imwrite(str(fdir / "plate" / f"{i:05d}.jpg"), q)
            cv2.imwrite(str(fdir / "cut" / f"{i:05d}.png"), np.dstack([q, a]))
        mod = importlib.import_module("motion_dados_profundidade")
        params = {"video": {"plate": f"/work/{rel}/plate/%05d.jpg", "cut": f"/work/{rel}/cut/%05d.png", "count": 6},
                  "fundo": "limpo"}
        mod.enriquecer("profundidade", params, {}, work=work)
        self.assertEqual(len(list((fdir / "prof").glob("*.png"))), 6)
        self.assertTrue((fdir / "placa.jpg").exists())
        self.assertEqual(params["prof_seq"], f"/work/{rel}/prof/%05d.png")
        self.assertIn(params["profundidade_modo"], ("modelo", "heuristica"))
        antes = (fdir / "prof" / "00001.png").stat().st_mtime_ns
        mod.enriquecer("profundidade", dict(params), {}, work=work)
        self.assertEqual((fdir / "prof" / "00001.png").stat().st_mtime_ns, antes, "refez os mapas sem precisar")
        outro = {"video": params["video"]}
        mod.enriquecer("palavra", outro, {}, work=work)
        self.assertNotIn("prof_seq", outro)

    def test_template_registrado_no_plano_e_no_catalogo(self):
        tl = json.loads(json.dumps(__import__("plan").MOTION_DEFAULTS["profundidade"]))
        self.assertEqual((tl["layer"], tl["needs_video"]), ("full", True))
        self.assertIn("profundidade", __import__("motion").WEBGL)
        self.assertTrue((util.SK / "assets" / "motion" / "templates" / "profundidade.html").exists())


if __name__ == "__main__":
    unittest.main()
