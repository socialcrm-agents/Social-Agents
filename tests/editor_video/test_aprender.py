"""Aprendizado com as vendas (aprender.py): ficha + código de cada render, importação no formato real dos
conectores (Meta Ads e Vturb), comparação com certeza, quedas de retenção e receita "aprendida".
python -m unittest tests/editor_video/test_aprender.py -v
"""

from __future__ import annotations

import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import aprender  # noqa: E402
import receitas  # noqa: E402


class Pasta(unittest.TestCase):
    """Cada teste com o seu ~/.editor-viral."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="ev_apr_"))
        self.patches = [mock.patch.object(aprender, n, self.d / f) for n, f in
                        (("CRIATIVOS", "criativos.jsonl"), ("RESULTADOS", "resultados.jsonl"),
                         ("APRENDIZADO", "aprendizado.json"), ("RELATORIO", "aprendizado.md"))]
        self.patches += [mock.patch.object(aprender, "PASTA", self.d),
                         mock.patch.object(receitas, "APRENDIDA", self.d / "aprendizado.json")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.d, ignore_errors=True)


def ficha_falsa(cod: str, **car) -> dict:
    base = {"gancho_tipo": "afirmacao", "abertura": "nada", "composicoes": "nenhuma", "direcao": "premium",
            "estilo": "reels_viral", "trilha": "lofi", "voz": "padrao", "legenda": "grande", "ritmo_cortes": "medio",
            "densidade": "media", "fala": "normal", "duracao": "20_40s", "correcao_imagem": "sim", "cta_na_tela": "nao"}
    base.update(car)
    return {"codigo": cod, "projeto": "/x", "versao": 1, "arquivo": f"v1_reels_viral_{cod}.mp4", "duracao": 30.0,
            "gancho_texto": f"gancho {cod}", "caracteristicas": base, "numeros": {}, "eventos": [], "buracos": []}


class Ficha(Pasta):
    def test_ficha_do_projeto_real_e_codigo_estavel(self):
        proj = util.preparar("semcortes")
        try:
            tl = util.planejar(proj)
            p = json.loads((proj / "project.json").read_text(encoding="utf-8"))
            f = aprender.registrar(proj, 3, tl, p, "v3.mp4")
            self.assertRegex(f["codigo"], r"^EV-[0-9A-F]{6}$")
            self.assertEqual(f["codigo"], aprender.codigo(proj, 3))
            self.assertNotEqual(f["codigo"], aprender.codigo(proj, 4))
            self.assertIn(f["caracteristicas"]["gancho_tipo"],
                          {"pergunta", "dor", "numero", "prova", "virada", "lista", "produto", "cta", "afirmacao", "sem_fala"})
            self.assertTrue(set(aprender.NOMES) <= set(f["caracteristicas"]))
            self.assertIn(f["codigo"], aprender.fichas())
        finally:
            shutil.rmtree(proj, ignore_errors=True)


class Importacao(Pasta):
    META = {"ad_entities": json.dumps([
        {"id": "1", "name": "Anúncio EV-AAAAAA teste", "amount_spent": {"value": "100", "unit": "BRL"},
         "impressions": "10000", "video_play_actions": 4000, "video_p25_watched_actions": 2000,
         "video_p100_watched_actions": 400, "video_thruplay_watched_actions": 900, "ctr": 1.5, "purchase_roas": 2.0},
        {"id": "2", "name": "outro vídeo v2_reels_viral_ev-aaaaaa.mp4", "amount_spent": {"value": "50"},
         "impressions": "30000", "video_play_actions": None, "ctr": 0.5, "purchase_roas": [{"value": "1.0"}]},
        {"id": "3", "name": "Anúncio sem código", "amount_spent": {"value": "999"}, "impressions": "1"}])}

    def test_meta_no_formato_do_conector_soma_anuncios_do_mesmo_video(self):
        linhas = aprender.normalizar_meta(self.META)
        self.assertEqual([r["codigo"] for r in linhas], ["EV-AAAAAA", "EV-AAAAAA"])
        self.assertAlmostEqual(linhas[0]["p25"], 0.5)
        f = self.d / "meta.json"
        f.write_text(json.dumps(self.META), encoding="utf-8")
        aprender.importar("meta", f)
        r = aprender.resultados()["EV-AAAAAA"]
        self.assertEqual(r["gasto"], 150)
        self.assertAlmostEqual(r["ctr"], (1.5 * 10000 + 0.5 * 30000) / 40000)   # ponderado por impressões
        self.assertAlmostEqual(r["roas"], (2.0 * 10000 + 1.0 * 30000) / 40000)

    def test_vturb_curva_e_nome_pelo_list_players(self):
        stats = {"player_id": "p1", "plays": 776, "play_rate": 64.0, "engagement": 39.1, "conversion_rate": 1.2,
                 "pitch_retention": 36.0, "retention_curve": [{"second": 0, "retention": 100}, {"second": 5, "retention": 88.58},
                                                              {"second": 10, "retention": 80.56}]}
        linhas = aprender.normalizar_vturb([stats], {"p1": "VSL v3_reels_viral_EV-BBBBBB"})
        self.assertEqual(linhas[0]["codigo"], "EV-BBBBBB")
        self.assertAlmostEqual(linhas[0]["ret_5s"], 88.58)
        self.assertAlmostEqual(linhas[0]["ret_3s"], 100 - 11.42 * 3 / 5, places=2)
        self.assertEqual(aprender.normalizar_vturb([stats], {}), [], "sem código no nome não entra")


class Analise(Pasta):
    def popular(self, n: int = 12, efeito: float = 1.0, semente: int = 3):
        rnd = random.Random(semente)
        for i in range(n):
            cod = f"EV-{i:06X}"
            trilha = "energia" if i % 2 else "lofi"
            gancho = rnd.choice(["pergunta", "afirmacao", "dor"])
            aprender._anexar(aprender.CRIATIVOS, ficha_falsa(cod, trilha=trilha, gancho_tipo=gancho))
            roas = 1.0 + (efeito if trilha == "energia" else 0) + rnd.uniform(-0.25, 0.25)
            aprender._anexar(aprender.RESULTADOS, {"codigo": cod, "fonte": "meta", "id": str(i), "gasto": 80.0,
                                                   "impressoes": 20000, "plays": 9000, "roas": roas, "ctr": 1.0})

    def test_acha_o_que_vence_e_vira_receita(self):
        self.popular()
        res = aprender.analisar()
        self.assertEqual(res["metrica"], "roas")
        top = res["achados"][0]
        self.assertEqual((top["caracteristica"], top["valor"]), ("trilha", "energia"))
        self.assertEqual(top["certeza"], "alta")
        self.assertGreater(top["t"], 0)
        self.assertEqual(len(res["ranking"]), 12)
        ap = aprender.aplicar(res)
        i = ap["receita"].index("--music")
        self.assertEqual(ap["receita"][i + 1], "auto:energia")
        self.assertEqual(ap["receita"].count("--music"), 1, "opção trocada, não duplicada")
        self.assertEqual(ap["receita"].count("--composicao"), receitas.RECEITAS["premium"].count("--composicao"))
        exp = receitas.expandir(["proj", "--receita", "aprendida"])
        self.assertIn("auto:energia", exp)
        self.assertIn("Receita aprendida", aprender.relatorio(res, ap))

    def test_sem_diferenca_real_nao_vira_regra(self):
        self.popular(efeito=0.0)
        res = aprender.analisar()
        self.assertFalse([a for a in res["achados"] if a["certeza"] != "baixa"], res["achados"])
        ap = aprender.aplicar(res)
        self.assertEqual(ap["porque"], [])

    def test_poucos_dados_avisa(self):
        self.popular(n=3)
        res = aprender.analisar()
        self.assertIsNone(res["metrica"])
        self.assertIn("Ainda não dá para aprender", aprender.relatorio(res, None))

    def test_queda_de_retencao_no_trecho_parado(self):
        eventos = [[0.5, "animação palavra_chave"], [3.0, "corte"], [16.0, "efeito whip"]]
        curva = [[0, 100], [5, 90], [10, 60], [15, 55], [20, 50]]
        normal = {0: 10.0, 5: 8.0, 10: 9.0, 15: 9.0}
        q = aprender.quedas(curva, eventos, [[3.0, 16.0]], 20.0, normal)
        self.assertEqual(len(q), 1)
        self.assertEqual((q[0]["de"], q[0]["ate"]), (5, 10))
        self.assertTrue(q[0]["parado"])
        self.assertEqual(q[0]["na_tela"], ["nada muda na tela"])


class Sobrepor(unittest.TestCase):
    def test_troca_opcao_unica_e_mantem_repetiveis(self):
        base = ["--direcao", "premium", "--music", "auto:energia", "--composicao", "a@auto", "--composicao", "b@auto"]
        out = receitas.sobrepor(base, ["--music", "off", "--composicao", "c@auto", "--voz", "estudio"])
        self.assertEqual(out.count("--music"), 1)
        self.assertEqual(out[out.index("--music") + 1], "off")
        self.assertEqual(out.count("--composicao"), 3)
        self.assertIn("estudio", out)


if __name__ == "__main__":
    unittest.main()
