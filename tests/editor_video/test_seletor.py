"""Seletor de efeitos por intenção (direção premium): batidas, intenção, palavra-chave dita (nada inventado),
orçamento de densidade, sem repetição, decisões existentes vencem, e QA de densidade/legibilidade.
python -m unittest tests/editor_video/test_seletor.py -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import emocao  # noqa: E402
import seletor  # noqa: E402
from common import norm  # noqa: E402


def falas(*frases, passo=0.32, pausa=0.7):
    """Transcrição sintética: cada palavra 0,32 s; pausa entre frases."""
    out, t = [], 0.3
    for f in frases:
        for w in f.split():
            out.append({"w": w, "t0": round(t, 3), "t1": round(t + passo - 0.04, 3), "emph": False})
            t += passo
        t += pausa
    return out


class Emocao(unittest.TestCase):
    def test_lexico(self):
        self.assertEqual(emocao.da_palavra("dinheiro")[0], "dinheiro")
        self.assertEqual(emocao.da_palavra("Gostoso.")[1], "😋")
        self.assertEqual(emocao.da_palavra("vendas")[0], "dinheiro")          # prefixo venda*
        self.assertEqual(emocao.da_palavra("mesa"), ("neutro", None))
        self.assertEqual(emocao.da_frase(["Você", "sabia", "disso?"]), "curiosidade")


class Batidas(unittest.TestCase):
    def test_frase_longa_quebra_na_virgula_e_marca_troca_de_cena(self):
        w = falas("Gente, eu tô aqui com esse chiclete da Mentos, dá uma olhadinha aqui como ele é.", "Custa 15 reais.")
        cs = seletor.cenas(w)
        self.assertGreaterEqual(len(cs), 3)
        self.assertTrue(cs[0]["nova"])
        self.assertFalse(cs[1]["nova"], "continuação da mesma frase não é troca de cena")
        self.assertTrue(cs[-1]["nova"])
        self.assertTrue(all(c["t1"] - c["t0"] >= 1.2 or c is cs[-1] for c in cs))

    def test_intencao(self):
        c = lambda f: {"fala": f}
        self.assertEqual(seletor.intencao(c("Qualquer coisa."), 0), "gancho")
        self.assertEqual(seletor.intencao(c("Comenta EU QUERO aqui embaixo."), 3), "cta")
        self.assertEqual(seletor.intencao(c("Você sabia disso?"), 2), "pergunta")
        self.assertEqual(seletor.intencao(c("Mas o segredo é outro."), 2), "virada")
        self.assertEqual(seletor.intencao(c("Custa só 15 reais."), 2), "numero")
        self.assertEqual(seletor.intencao(c("O problema é que ninguém consegue."), 2), "dor")


class Direcao(unittest.TestCase):
    FRASES = ("Gente, olha esse chiclete gostoso da Mentos agora.", "Mas o segredo é outro, presta atenção.",
              "Custa só 15 reais na promoção de hoje.", "O problema é que acaba rápido demais.",
              "Ele tem dois sabores incríveis, menta e tutti-frutti.", "Comenta EU QUERO aqui embaixo.")

    def setUp(self):
        self.w = falas(*self.FRASES)
        self.total = self.w[-1]["t1"] + 0.5
        self.r = seletor.direcionar(self.w, [], "anuncio_conversao", self.total, {})

    def test_palavra_chave_e_sempre_uma_palavra_dita(self):
        ditas = {norm(x["w"]) for x in self.w}
        textos = [m["params"].get("text") or m["params"].get("texto") for m in self.r["motion"]
                  if m["template"] in ("palavra_chave", "profundidade")]
        self.assertTrue(textos)
        self.assertTrue(all(norm(t) in ditas for t in textos), textos)

    def test_orcamento_de_densidade_e_sem_repeticao(self):
        herois = sorted(m["t0"] for m in self.r["motion"] if m["template"] != "passa_mao")
        self.assertTrue(all(b - a >= seletor.HEROI_GAP - 0.2 for a, b in zip(herois, herois[1:])), herois)
        trans = sorted((f["t"], f["type"]) for f in self.r["fx"])
        trans += [(m["t0"], "swipe") for m in self.r["motion"] if m["template"] == "passa_mao"]
        trans.sort()
        self.assertTrue(all(b[0] - a[0] >= seletor.TRANS_GAP - 0.3 for a, b in zip(trans, trans[1:])), trans)
        self.assertTrue(all(a[1] != b[1] for a, b in zip(trans, trans[1:])), "mesma transição duas vezes seguidas")
        fulls = [m for m in self.r["motion"] if m.get("layer") == "full"]
        self.assertLessEqual(len(fulls), 1 + int(self.total // seletor.FULL_GAP))

    def test_paleta_consistente_no_maximo_duas_cores(self):
        cores = {m["params"]["cor"] for m in self.r["motion"] if m["template"] == "palavra_chave"}
        self.assertLessEqual(len(cores), 2)
        self.assertLessEqual(len(self.r["paleta"]), 2)

    def test_cta_e_pergunta_nao_ganham_heroi_e_cada_cena_explica_a_escolha(self):
        cta = next(c for c in self.r["relatorio"] if c["intencao"] == "cta")
        self.assertFalse(any(e.startswith("herói") for e in cta["escolha"]))
        self.assertTrue(all(c["escolha"] or c["descartado"] for c in self.r["relatorio"]))

    def test_linguagem_editorial_so_usa_a_familia_dela(self):
        r = seletor.direcionar(self.w, [], "editorial_premium", self.total, {})
        self.assertTrue({f["type"] for f in r["fx"]} <= {"whip"})
        self.assertFalse(any(m["template"] == "passa_mao" for m in r["motion"]))

    def test_decisao_existente_vence(self):
        manual = [{"template": "infografico", "t0": 0.0, "t1": self.total, "layer": "front"}]
        r = seletor.direcionar(self.w, manual, "anuncio_conversao", self.total, {})
        self.assertFalse([m for m in r["motion"] if m["template"] in ("palavra_chave", "profundidade")])


class SemRepeticao(unittest.TestCase):
    def test_mesma_palavra_nao_vira_destaque_duas_vezes_em_6s(self):
        w = falas("Custa só quinze reais hoje.", "Na promoção, reais de verdade.")
        manual = [{"template": "palavra_chave", "t0": 0.2, "t1": 1.4, "layer": "front", "params": {"text": "QUINZE REAIS"}}]
        r = seletor.direcionar(w, manual, "anuncio_conversao", w[-1]["t1"] + 0.5, {})
        textos = [m["params"].get("text") for m in r["motion"] if m["template"] == "palavra_chave"]
        self.assertNotIn("REAIS", textos)


class Composicoes(unittest.TestCase):
    def test_revelacao_mostra_uma_palavra_mesmo_sem_peso_emocional(self):
        import composicoes
        w = falas("Se eu fosse um corredor, um maratonista.")
        mo, *_ = composicoes.expandir([{"nome": "revelacao", "at": "Se eu fosse um corredor"}], w, 5.0, {})
        self.assertEqual(mo[0]["params"]["texto"], "CORREDOR")


class Integracao(unittest.TestCase):
    def test_plano_com_direcao_premium_e_sem_ela(self):
        proj = util.preparar("semcortes")
        tl0 = util.planejar(proj)
        self.assertNotIn("direcao", tl0, "desligada: a timeline não muda (goldens)")
        p = json.loads((proj / "project.json").read_text(encoding="utf-8"))
        p["overrides"]["direcao"] = "premium"
        for k in ("motion", "patches"):            # projeto sem animações pedidas: o seletor decide sozinho
            p["overrides"].pop(k, None)
        (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        tl = util.planejar(proj)
        self.assertIn("direcao", tl)
        novos = [m for m in tl["motion"] if m.get("origem") == "seletor"]
        self.assertTrue(novos)
        self.assertTrue(all(m["id"].startswith("s_") for m in novos))
        sys.path.insert(0, str(util.SCRIPTS))
        import render
        self.assertTrue({f["type"] for f in tl["fx"]} <= set(render.DUR_FX))
        for m in novos:
            self.assertTrue((util.SK / "assets" / "motion" / "templates" / f"{m['template']}.html").exists())


class QADensidade(unittest.TestCase):
    def base(self, **kw):
        tl = {"duration": 12.0, "w": 1080, "motion": [], "fx": [], "behind": [], "broll": [], "shots": [{"t0": 0}],
              "captions": {"cfg": {"size": 58}}}
        tl.update(kw)
        return tl

    def test_buraco_monotono_e_dois_herois_juntos(self):
        tl = self.base(motion=[{"id": "a", "template": "palavra_chave", "t0": 1.0, "t1": 3.0, "layer": "front"},
                               {"id": "b", "template": "infografico", "t0": 2.0, "t1": 4.0, "layer": "front"}])
        d = seletor.densidade(tl)
        self.assertTrue(d["buracos"])
        self.assertTrue(d["herois_juntos"])

    def test_legenda_pequena_reprova_leitura(self):
        tl = self.base(captions={"cfg": {"size": 30}})
        self.assertTrue(seletor.legibilidade(tl)["alertas"])


if __name__ == "__main__":
    unittest.main()
