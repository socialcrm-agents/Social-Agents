"""Receitas (jeito de editar salvo) e padrão para todo vídeo novo.  python -m unittest tests/editor_video/test_receitas.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import composicoes  # noqa: E402
import receitas  # noqa: E402
from test_seletor import falas  # noqa: E402


class Receitas(unittest.TestCase):
    def test_expande_e_opcao_escrita_depois_vale_por_cima(self):
        args = receitas.expandir(["proj", "--receita", "premium", "--music", "off"])
        self.assertIn("--direcao", args)
        self.assertEqual(args[-2:], ["--music", "off"])
        with self.assertRaises(ValueError):
            receitas.expandir(["--receita", "inventada"])

    def test_padrao_fica_fora_da_skill_e_sobrevive(self):
        arq = Path(tempfile.mkdtemp()) / "padrao.json"
        with mock.patch.object(receitas, "ARQUIVO", arq):
            self.assertIsNone(receitas.padrao())
            receitas.definir_padrao("premium")
            self.assertEqual(receitas.padrao(), "premium")
            receitas.definir_padrao(None)
            self.assertIsNone(receitas.padrao())

    def test_composicoes_automaticas_acham_gancho_e_frase_forte(self):
        w = falas("Se eu fosse um corredor, um maratonista, um cara especialista em bike,",
                  "eu jamais venderia um curso gravado ou uma planilhazinha barata,",
                  "um e-bookzinho, porque isso vai estragar a sua audiência.", "Quando você traz as pessoas para o seu funil,")
        mo, *_ = composicoes.expandir([{"nome": "revelacao", "at": "auto"}, {"nome": "impacto", "at": "auto"}], w, 20.0, {})
        textos = {m["composicao"]: m["params"].get("texto") or m["params"].get("text") for m in mo}
        self.assertEqual(textos["revelacao"], "CORREDOR")
        self.assertEqual(textos["impacto"], "ESTRAGAR")

    def test_projeto_novo_nasce_com_a_receita_do_padrao(self):
        proj = util.preparar("semcortes")
        util.rodar("edit.py", proj, "--receita", "premium", "--no-render")
        ov = json.loads((proj / "project.json").read_text(encoding="utf-8"))["overrides"]
        self.assertEqual(ov.get("direcao"), "premium")
        self.assertEqual([c["at"] for c in ov.get("composicoes", [])], ["auto", "auto"])
        self.assertEqual(ov["imagem"], {"correcao": "auto", "estabilizar": "auto"})


if __name__ == "__main__":
    unittest.main()
