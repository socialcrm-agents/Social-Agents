"""Biblioteca de objetos 3D: índice de sinônimos, busca na fala e arquivo-modelo de objeto novo."""
from __future__ import annotations

import sys
import unittest

import util

sys.path.insert(0, str(util.SCRIPTS))
import objetos  # noqa: E402


class Objetos(unittest.TestCase):
    def test_acha_objetos_falados_com_acento_e_plural(self):
        achados = {o["arquivo"] for o in objetos.achar("Comprei um sofá, dois lápis e ganhei muito dinheiro no celular")}
        self.assertTrue({"sofa", "lapis", "moedas", "celular"} <= achados, achados)

    def test_indice_tem_sinonimos(self):
        ind = objetos.indice()
        self.assertEqual(ind["cerebro"], "cerebro")
        self.assertEqual(ind["ideia"], "lampada")

    def test_todo_objeto_tem_info_e_criar(self):
        for arq in objetos.PASTA.glob("*.js"):
            txt = arq.read_text(encoding="utf-8")
            self.assertIn("export const info", txt, arq.name)
            self.assertIn("export default function criar", txt, arq.name)


if __name__ == "__main__":
    unittest.main()
