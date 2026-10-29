"""Fábrica de variações (fabrica.py) e espionagem de vencedores (vencedores.py).
python -m unittest tests/editor_video/test_fabrica_vencedores.py -v     (render real: EDITOR_TESTES_RENDER=1)
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import fabrica  # noqa: E402
import vencedores  # noqa: E402


class Desenho(unittest.TestCase):
    NIV = {"gancho": [{"rotulo": x} for x in "OABCD"], "trilha": [{"rotulo": x} for x in ("sem", "e", "i")],
           "cta": [{"rotulo": "p"}, {"rotulo": "b"}]}

    def test_controle_primeiro_sem_repetir_e_equilibrado(self):
        cs = fabrica.desenhar(self.NIV, 10)
        self.assertEqual(len(cs), 10)
        self.assertEqual([c[f]["rotulo"] for c in cs[:1] for f in self.NIV], ["O", "sem", "p"])
        chaves = [tuple(c[f]["rotulo"] for f in self.NIV) for c in cs]
        self.assertEqual(len(set(chaves)), 10)
        for f, lv in self.NIV.items():
            usos = [sum(1 for c in cs if c[f]["rotulo"] == x["rotulo"]) for x in lv]
            self.assertLessEqual(max(usos) - min(usos), 1, f"{f} desequilibrado: {usos}")

    def test_pares_misturados(self):
        cs = fabrica.desenhar(self.NIV, 10)
        for a, b in itertools.combinations(self.NIV, 2):
            pares = {(c[a]["rotulo"], c[b]["rotulo"]) for c in cs}
            self.assertGreaterEqual(len(pares), min(10, len(self.NIV[a]) * len(self.NIV[b])) - 2)

    def test_n_maior_que_o_possivel(self):
        self.assertEqual(len(fabrica.desenhar({"cta": self.NIV["cta"]}, 10)), 2)


class FabricaPlano(unittest.TestCase):
    def test_so_plano_no_projeto_real_volta_ao_original(self):
        proj = util.preparar("semcortes")
        try:
            antes = hashlib.md5((proj / "project.json").read_bytes()).hexdigest()
            r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "fabrica", str(proj), "--n", "6",
                                "--so-plano"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
            res = json.loads((proj / "qa" / "fabrica.json").read_text(encoding="utf-8"))
            self.assertEqual(len(res), 6)
            self.assertEqual(res[0]["trechos_diferentes"], [], "V01 = controle, nada muda")
            self.assertFalse(res[0]["audio_muda"])
            so_trilha = [x for x in res if x["fatores"].get("gancho") == "original" and x["fatores"].get("cta") in
                         ("pilula", None) and x["fatores"].get("trilha") != res[0]["fatores"].get("trilha")]
            for x in so_trilha:   # trocar só a trilha não refaz vídeo
                self.assertEqual(x["trechos_diferentes"], [])
                self.assertTrue(x["audio_muda"])
            self.assertEqual(hashlib.md5((proj / "project.json").read_bytes()).hexdigest(), antes)
            self.assertIn("CONTROLE", (proj / "qa" / "fabrica.md").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(proj, ignore_errors=True)


class Vencedores(unittest.TestCase):
    AGORA = time.time()

    def busca(self):
        def ad(i, dias, versoes, video=True, colecao=None, texto=None):
            return {"ad_archive_id": str(i), "page_name": f"P{i}", "is_active": True, "collation_count": versoes,
                    "collation_id": colecao, "start_date": int(self.AGORA - dias * 86400), "end_date": int(self.AGORA),
                    "snapshot": {"body": {"text": texto or f"texto {i}"}, "cta_text": "Saiba mais",
                                 "videos": [{"video_sd_url": f"https://x/{i}.mp4"}] if video else [],
                                 "cards": []}}
        return {"searchResults": [ad(1, 10, 1), ad(2, 300, 1), ad(3, 90, 8), ad(4, 400, 1, video=False),
                                  ad(5, 300, 1, colecao="c9"), ad(6, 299, 2, colecao="c9")]}

    def test_le_formato_do_conector_e_ranqueia(self):
        ads = vencedores.ler_anuncios(self.busca())
        self.assertAlmostEqual(next(a for a in ads if a["id"] == "2")["dias"], 300, delta=0.1)
        rk = vencedores.ranquear(ads, 10)
        ids = [a["id"] for a in rk]
        self.assertNotIn("4", ids, "sem vídeo não entra")
        self.assertEqual(sum(1 for i in ids if i in ("5", "6")), 1, "mesma coleção = um anúncio só")
        self.assertEqual(ids[-1], "1", "10 dias no ar é o mais fraco")
        self.assertEqual(rk[0]["cta"], "Saiba mais")

    def test_formato_meta_ads_mcp(self):
        ads = vencedores.ler_anuncios({"data": [{"id": "77", "page_name": "X", "ad_delivery_start_time": "2026-01-01",
                                                  "ad_creative_bodies": ["Olha isso"], "video_url": "https://v/77.mp4"}]})
        self.assertEqual((ads[0]["id"], ads[0]["texto"], ads[0]["video"]), ("77", "Olha isso", "https://v/77.mp4"))
        self.assertGreater(ads[0]["dias"], 100)

    def test_gancho_e_tipo(self):
        self.assertEqual(vencedores.gancho_da_transcricao({"transcript": "Você sabia disso? O resto."}), "Você sabia disso?")
        self.assertEqual(vencedores.tipo_gancho("Você sabia disso?"), "pergunta")
        self.assertEqual(vencedores.tipo_gancho("Ganhei 300 reais em uma semana"), "numero")
        self.assertEqual(vencedores.tipo_gancho(""), "sem_fala")


LIGADO = os.environ.get("EDITOR_TESTES_RENDER") == "1" and shutil.which("ffmpeg") and shutil.which("node")


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de ffmpeg, Node/Playwright e OpenCV)")
class Real(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="ev_fabv_"))

    def tearDown(self):
        if not os.environ.get("EDITOR_TESTES_MANTER"):
            shutil.rmtree(self.d, ignore_errors=True)

    def test_vencedores_analisa_videos_e_gera_perfil_aplicavel(self):
        from test_render_revisao import video_sintetico
        vids = []
        for i in range(3):
            v = self.d / f"c{i}.mp4"
            video_sintetico(v)
            vids.append(v)
        busca = {"searchResults": [{"ad_archive_id": str(i), "page_name": f"C{i}", "is_active": True,
                                    "start_date": int(time.time() - (100 + i) * 86400), "collation_count": 1,
                                    "snapshot": {"videos": [{"video_sd_url": v.resolve().as_uri()}]}}
                                   for i, v in enumerate(vids)]}
        (self.d / "busca.json").write_text(json.dumps(busca))
        with mock.patch.object(vencedores, "PASTA", self.d / "nichos"):
            ads = vencedores.ler_anuncios(busca)
            (self.d / "nichos" / "x").mkdir(parents=True)
            (self.d / "nichos" / "x" / "ranking.json").write_text(json.dumps(vencedores.ranquear(ads)))
            r = vencedores.analisar("x", 3, {"0": "Você sabia disso? Resto."})
        self.assertEqual(len([a for a in r["analisados"] if a.get("medidas")]), 3)
        self.assertIsNotNone(r["medianas"]["cortes_por_min"])
        self.assertEqual(r["ganchos"], {"pergunta": 1})
        perfil = json.loads((self.d / "nichos" / "x" / "perfil_nicho.json").read_text())
        self.assertIn("traducao", perfil, "perfil do nicho tem o formato que o referencia.py aplicar aceita")

    def test_fabrica_renderiza_versoes_com_codigo_e_manifesto(self):
        from test_render_revisao import video_sintetico
        clip = self.d / "s.mp4"
        video_sintetico(clip)
        proj = self.d / "proj"
        subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "new", str(proj), "--clips", str(clip),
                        "--style", "pro_clean", "--sem-cortes", "--sem-receita"], check=True, capture_output=True)
        words = [{"w": f"palavra{i}" + ("." if i % 6 == 5 else ""), "t0": round(0.2 + i * 0.5, 3),
                  "t1": round(0.55 + i * 0.5, 3), "clip": "c1"} for i in range(30)]
        (proj / "transcript.json").write_text(json.dumps({"backend": "teste", "words": words, "silences": {}}))
        p = json.loads((proj / "project.json").read_text())
        p["overrides"]["triggers"] = False
        (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False))
        r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "fabrica", str(proj), "--n", "3",
                            "--fatores", "trilha,cta", "--trilhas", "energia", "--draft"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        arqs = sorted((proj / "renders" / "fabrica").glob("V*_EV-*.mp4"))
        self.assertEqual(len(arqs), 3)
        with (proj / "renders" / "fabrica" / "manifesto.csv").open(encoding="utf-8") as fh:
            linhas = list(csv.DictReader(fh, delimiter=";"))
        self.assertEqual([x["arquivo"] for x in linhas], [a.name for a in arqs])
        res = json.loads((proj / "qa" / "fabrica.json").read_text())
        so_audio = [x for x in res[1:] if x["fatores"]["cta"] == "pilula"]
        for x in so_audio:
            self.assertEqual(x["trechos_diferentes"], [], "trocar só a trilha não refaz vídeo")
        import aprender
        fs = aprender.fichas()
        cod = linhas[1]["codigo"]
        self.assertIn(cod, fs)
        self.assertIn("fabrica_trilha", fs[cod]["caracteristicas"])
        self.assertNotIn("botao_cta", json.dumps(json.loads((proj / "project.json").read_text())["overrides"]))


if __name__ == "__main__":
    unittest.main()
