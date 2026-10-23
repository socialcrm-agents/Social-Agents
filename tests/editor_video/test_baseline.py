"""Baseline do Editor Viral (editor-video): o planejamento atual não pode mudar sem querer.

Roda só com a biblioteca padrão:   python -m unittest discover -s tests/editor_video -v

Os goldens (fixtures/*/golden_*.json) foram gerados com o código do commit eb5f2e9, antes do motor de revisão.
Comparamos sem os campos de identificação que o motor acrescenta (id, i, origem de patch) e sem o caminho do clipe.
"""

from __future__ import annotations

import json
import unittest

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
import util  # noqa: E402


class BaselinePlanejamento(unittest.TestCase):
    def _checa(self, nome: str) -> None:
        tmp = util.preparar(nome)
        tl = util.planejar(tmp)
        edl = json.loads((tmp / "edl.json").read_text(encoding="utf-8"))
        gold_tl = json.loads((util.FIXTURES / nome / "golden_timeline.json").read_text(encoding="utf-8"))
        gold_edl = json.loads((util.FIXTURES / nome / "golden_edl.json").read_text(encoding="utf-8"))
        self.assertEqual(util.normalizar(edl), gold_edl, "edl.json mudou em relação ao baseline")
        atual = util.normalizar(tl)
        for chave in gold_tl:  # mensagem por bloco, para achar rápido o que mudou
            self.assertEqual(atual.get(chave), gold_tl[chave], f"timeline['{chave}'] mudou em relação ao baseline")

    def test_sem_cortes_igual_ao_baseline(self):
        self._checa("semcortes")

    def test_com_cortes_igual_ao_baseline(self):
        self._checa("pro2")

    def test_planejamento_deterministico(self):
        a = util.planejar(util.preparar("pro2"))
        b = util.planejar(util.preparar("pro2"))
        self.assertEqual(util.normalizar(a), util.normalizar(b))


if __name__ == "__main__":
    unittest.main()
