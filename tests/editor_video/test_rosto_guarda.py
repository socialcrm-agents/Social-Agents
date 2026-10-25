"""Rosto nunca tampado: medida por quadro, escolha da menor mudança, vizinhos como obstáculo, rastreio que não some.
python -m unittest tests/editor_video/test_rosto_guarda.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import rosto_guarda as rg  # noqa: E402

N, H, W = 30, rg.BH, rg.BW
ROSTO = (60, 120, 210, 260)                      # olhos até o queixo, em px de 270x480


def card(y0, y1, x0=20, x1=250, n=N):
    a = np.zeros((n, H, W), np.float32)
    a[:, y0:y1, x0:x1] = 1
    return a


class Decisao(unittest.TestCase):
    def test_card_em_cima_do_rosto_sai_do_rosto_e_continua_inteiro(self):
        a = card(150, 210)
        d = rg.decidir(a, [ROSTO] * N)
        self.assertEqual(d["antes"], N)
        self.assertLessEqual(d["depois"], rg.TOLERA_QUADROS)
        t = rg._transforma(a, d["s"], d["ax"], d["dy"])
        self.assertTrue(rg._cabe(t, a, d["s"]))
        self.assertAlmostEqual(float((t > 0.5).sum()), float((a > 0.5).sum()) * d["s"] ** 2, delta=a[0].size * 0.02)

    def test_sem_rosto_coberto_nao_mexe(self):
        d = rg.decidir(card(300, 360), [ROSTO] * N)
        self.assertEqual((d["s"], d["dy"]), (1.0, 0.0))

    def test_nunca_troca_por_algo_pior_e_reprova_quando_nao_ha_saida(self):
        a = card(10, 470, 2, 268)                # ocupa a tela toda: não há posição livre
        d = rg.decidir(a, [ROSTO] * N)
        self.assertEqual(d["depois"], d["antes"])
        self.assertGreater(d["depois"], rg.TOLERA_QUADROS)

    def test_desvia_de_outra_animacao(self):
        a = card(150, 210)
        obst = card(215, 300)                    # outro card logo abaixo do rosto
        d = rg.decidir(a, [ROSTO] * N, obst)
        t = rg._transforma(a, d["s"], d["ax"], d["dy"])
        self.assertEqual(rg.colisao(t, obst), 0)
        self.assertLessEqual(d["depois"], rg.TOLERA_QUADROS)

    def test_elemento_que_ja_passava_da_zona_segura_pode_se_mover(self):
        a = card(330, 458)                       # botão com sombra até 95% da altura (caso real do botao_cta)
        self.assertTrue(rg._cabe(a, a, 1.0))


class Rastreio(unittest.TestCase):
    def test_detector_falhando_nao_faz_o_rosto_sumir(self):
        f = [0.2, 0.2, 0.5, 0.3]
        stats = [{"face": f if i in (0, 45) else None, "top": 300} for i in range(60)]
        caixas = rg.rostos_por_quadro(stats, 0, 60)
        self.assertTrue(all(c is not None for c in caixas), "buraco de 45 quadros sem rosto")

    def test_interpola_entre_deteccoes_e_segue_o_topo_da_cabeca(self):
        stats = [{"face": None, "top": 300} for _ in range(31)]
        stats[0]["face"], stats[30]["face"] = [0.2, 0.2, 0.4, 0.3], [0.4, 0.2, 0.4, 0.3]
        meio = rg.rostos_por_quadro(stats, 15, 16)[0]
        self.assertAlmostEqual(meio[0], rg.zona_do_rosto([0.3, 0.2, 0.4, 0.3], W, H)[0], delta=1)
        stats2 = [{"face": [0.2, 0.2, 0.4, 0.3] if i == 0 else None, "top": 300 + 4 * i} for i in range(20)]
        c0, c19 = rg.rostos_por_quadro(stats2, 0, 20)[0], rg.rostos_por_quadro(stats2, 0, 20)[19]
        self.assertGreater(c19[1], c0[1], "a cabeça desceu e a zona do rosto não acompanhou")

    def test_recuo_leva_o_rosto_para_baixo(self):
        c = rg.com_recuo(ROSTO, 1.0, [{"t0": 0.0, "t1": 3.0, "s": 0.7}], W, H)
        self.assertGreater(c[1], ROSTO[1])


if __name__ == "__main__":
    unittest.main()
