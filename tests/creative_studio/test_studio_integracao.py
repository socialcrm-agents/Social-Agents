"""Creative Studio x editor-video — integração do fluxo executável (creative/studio.py) com as ferramentas reais.

  python -m unittest tests/creative_studio/test_studio_integracao.py -v                    (planejamento + edit.py)
  EDITOR_TESTES_RENDER=1 python -m unittest tests/creative_studio/test_studio_integracao.py -v   (+ render real)

Sem render: fixture real (Mentos, sem cortes) — iniciar, cenas, equipe mínima, rascunho, verificação contra
templates/ids/comandos/decisões, conflito aberto recusado, aprovação, aplicação com edit.py (dry-run + --no-render),
travas e histórico. Com render: vídeo sintético, os 8 passos até o relatório com HIT/MISS da versão.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CREATIVE = REPO / "creative"
sys.path.insert(0, str(CREATIVE))
sys.path.insert(0, str(REPO / "tests" / "editor_video"))
import studio  # noqa: E402
import util  # noqa: E402
import validar  # noqa: E402


def cli(*args: str, ok: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(CREATIVE / "studio.py"), *args], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    if ok and r.returncode != 0:
        raise AssertionError(f"studio.py {args[0]} falhou:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def shot(agente: str, cena: str, t0: float, t1: float, *acoes: dict) -> dict:
    return {"agente": agente, "cenas": [{"cena": cena, "t0": t0, "t1": t1, "acoes": list(acoes)}]}


def acao(tipo: str, comando: list[str] | None, alvo: str | None = None, suportado: bool = True) -> dict:
    a = {"tipo": tipo, "justificativa": "teste", "suportado": suportado}
    if comando:
        a["comando"] = comando
    if alvo:
        a["alvo_id"] = alvo
    return a


class FluxoExecutavel(unittest.TestCase):
    def setUp(self):
        self.proj = util.preparar("semcortes")
        self.tl = util.planejar(self.proj)
        self.p = str(self.proj)
        cli("iniciar", self.p, "--pedido", "edita esse criativo de venda no nível dos concorrentes", "--tipo", "produto")

    def gravar(self, nome: str, dado: dict) -> str:
        f = self.proj / "creative" / nome
        f.write_text(json.dumps(dado, ensure_ascii=False), encoding="utf-8")
        return str(f)

    def alvo(self, a: float, b: float) -> dict:
        return next(m for m in self.tl["motion"] if a <= m["t0"] < b and m["id"].startswith("m"))

    # --- passo 1-2
    def test_iniciar_le_o_projeto_e_respeita_d02(self):
        brief = json.loads((self.proj / "creative" / "brief.json").read_text(encoding="utf-8"))
        self.assertEqual(validar.validar(brief, "brief"), [])
        self.assertTrue(brief["ja_editado"], "projeto sem cortes tem de virar ja_editado (D02)")
        self.assertEqual((brief["objetivo"], brief["nivel"]), ("venda", "maximo"))

    def test_cenas_tem_ids_reais_da_timeline(self):
        cs = json.loads(cli("cenas", self.p, "--de", "12", "--ate", "16").stdout)
        ids = studio.ids_da_timeline(self.tl)
        self.assertTrue(cs)
        self.assertTrue(all(12 - 4 <= c["t1"] and c["t0"] <= 16 for c in cs))
        self.assertTrue(all(e["id"] in ids for c in cs for e in c["elementos"]))

    def test_equipe_minima_por_pedido(self):
        def eq(pedido):
            return [c["agente"] for c in json.loads(cli("equipe", self.p, "--pedido", pedido).stdout)]
        completa = eq("edita esse criativo de venda no nível dos concorrentes")
        self.assertEqual(completa, ["conversion-strategist", "art-director", "senior-editor", "quality-director"])
        self.assertEqual(eq("melhora o visual de 12 a 16s"), ["art-director", "senior-editor"])
        self.assertEqual(eq("troca o texto do CTA"), [], "ajuste pontual: o diretor aplica sozinho")
        self.assertEqual(eq("põe uma trilha e sobe o volume da voz"), ["senior-editor", "sound-designer"])
        self.assertEqual(eq("o render ficou lento"), ["render-engineer"])
        self.assertIn("motion-3d-artist", eq("quero um efeito 3D novo no gancho"))
        for p in ("edita tudo", "melhora", "faz um anúncio completo com 3d e trilha"):
            self.assertLess(len(eq(p)), 7, "nunca a equipe inteira")

    def test_rascunho_aproveita_templates_existentes(self):
        cli("rascunho", self.p, "--pedido", "edita esse criativo de venda")
        dp = json.loads((self.proj / "creative" / "decision-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(validar.validar(dp, "decision-plan"), [])
        self.assertFalse(dp["aprovado"])
        usados = {m["elemento"].get("template") for m in dp["mapa"]} - {None}
        self.assertTrue(usados and usados <= set(studio.catalogo()["templates"]))

    # --- passo 3: verificação das propostas
    def test_verificar_recusa_executor_inventado_template_inexistente_id_fantasma_e_d02(self):
        ruins = {
            "operação": acao("fx", ["--particulas", "ouro"]),
            "template": acao("motion", ["--motion", json.dumps({"template": "holograma", "at": 13.0, "dur": 1})]),
            "id": acao("patch", ["--patch", "m99.params.text=X"], "m99"),
            "fx": acao("fx", ["--fx", "explosao@gostoso"]),
            "D02": acao("cut", ["--cut", "3.0-4.0"]),
            "sem comando": acao("motion", None),
        }
        for nome, a in ruins.items():
            r = cli("verificar", self.p, self.gravar("x.json", shot("art-director", "c3", 12, 16, a)), "shot-plan", ok=False)
            self.assertEqual(r.returncode, 1, f"{nome} passou: {r.stdout}")
        bom = shot("art-director", "c3", 12, 16, acao("fx", ["--fx", "tremida@gostoso"]),
                   acao("broll", None, suportado=False))
        r = cli("verificar", self.p, self.gravar("x.json", bom), "shot-plan")
        self.assertIn("OK", r.stdout)

    def test_ancora_ambigua_e_recusada(self):
        """Achado do senior-editor real: 'dá uma olhadinha' é falado 2x e o editor ancora na 1ª (outra cena)."""
        def mo(at):
            return acao("motion", ["--motion", json.dumps({"template": "objeto3d", "at": at, "dur": 1.0, "id": "m8",
                                                            "params": {"text": "MENTOS"}}, ensure_ascii=False)])
        ruim = self.gravar("a.json", shot("art-director", "c3", 10.48, 14.13, mo("dá uma olhadinha")))
        r = cli("verificar", self.p, ruim, "shot-plan", ok=False)
        self.assertIn("âncora ambígua", r.stdout)
        self.assertIn("não foi falada", cli("verificar", self.p, self.gravar("b.json", shot(
            "art-director", "c3", 10.48, 14.13, mo("chiclete de morango"))), "shot-plan", ok=False).stdout)
        bom = self.gravar("c.json", shot("art-director", "c3", 10.48, 14.13, mo("dá uma olhadinha, um")))
        self.assertIn("OK", cli("verificar", self.p, bom, "shot-plan").stdout)

    # --- passos 4-5: aprovação, conflito e aplicação real
    def test_conflito_aberto_trava_e_resolvido_aplica_com_edit_py(self):
        m = self.alvo(12, 16)
        cli("rascunho", self.p, "--pedido", "edita esse criativo de venda")
        arte = shot("art-director", "c3", 12, 16,
                    acao("patch", ["--patch", f"{m['id']}.params.text=VICIANTE."], m["id"]),
                    acao("fx", ["--fx", "tremida@gostoso"]))
        conv = shot("conversion-strategist", "c3", 12, 16,
                    acao("patch", ["--patch", f"{m['id']}.params.text=SÓ R$15."], m["id"]))
        fa, fc = self.gravar("sp-arte.json", arte), self.gravar("sp-conv.json", conv)
        r = cli("aprovar", self.p, fa, fc, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflito aberto", r.stdout)
        # diretor resolve: registra o conflito e tira a opção perdedora
        dp_f = self.proj / "creative" / "decision-plan.json"
        dp = json.loads(dp_f.read_text(encoding="utf-8"))
        dp["conflitos"] = [{"descricao": f"texto de {m['id']}", "opcoes": ["VICIANTE.", "SÓ R$15."],
                            "decisao": "SÓ R$15.", "motivo": "conversão > estética em anúncio; preço foi dito"}]
        dp_f.write_text(json.dumps(dp, ensure_ascii=False), encoding="utf-8")
        arte["cenas"][0]["acoes"].pop(0)
        self.gravar("sp-arte.json", arte)
        r = json.loads(cli("aprovar", self.p, fa, fc).stdout)
        self.assertTrue(r["aprovado"])
        # prévia não muda nada; aplicação muda a timeline de verdade
        antes = (self.proj / "project.json").read_text(encoding="utf-8")
        prev = json.loads(cli("aplicar", self.p, "--so-previa").stdout)
        self.assertEqual((self.proj / "project.json").read_text(encoding="utf-8"), antes)
        self.assertTrue(prev["dry_run"]["miss"])
        ap = json.loads(cli("aplicar", self.p).stdout)
        self.assertTrue(ap["aplicado"])
        tl2 = util.planejar(self.proj)
        self.assertEqual(next(x for x in tl2["motion"] if x["id"] == m["id"])["params"]["text"], "SÓ R$15.")
        self.assertTrue(any(f["type"] == "tremida" for f in tl2["fx"]))
        rev = json.loads((self.proj / ap["arquivo"]).read_text(encoding="utf-8"))
        self.assertEqual(validar.validar(rev, "revision-plan"), [])
        eventos = [e["evento"] for e in studio.historico(self.proj)]
        self.assertEqual(eventos, ["inicio", "rascunho", "aprovacao", "previa", "aplicacao"])

    def test_convocado_fora_do_escopo_e_proposta_sem_convocacao_sao_recusados(self):
        cli("rascunho", self.p, "--pedido", "melhora o visual de 12 a 16s")
        intruso = shot("sound-designer", "c3", 12, 16, acao("music", None, suportado=False))
        fora = shot("art-director", "c1", 0, 2.6, acao("fx", ["--fx", "clarao@Gente"]))
        r = cli("aprovar", self.p, self.gravar("a.json", intruso), self.gravar("b.json", fora), ok=False)
        self.assertIn("sem ter sido convocado", r.stdout)
        self.assertIn("fora do escopo", r.stdout)

    def test_decisao_travada_pelo_usuario_e_preservada(self):
        m = self.alvo(0, 3)
        cli("travar", self.p, m["id"], "--motivo", "usuário aprovou o gancho")
        sp = self.gravar("t.json", shot("art-director", "c1", 0, 2.6,
                                        acao("patch", ["--patch", f"{m['id']}.params.rotulo=NOVO"], m["id"])))
        r = cli("verificar", self.p, sp, "shot-plan", ok=False)
        self.assertIn("travado", r.stdout)
        cli("liberar", self.p, m["id"], "--motivo", "usuário pediu para mudar o gancho")
        self.assertIn("OK", cli("verificar", self.p, sp, "shot-plan").stdout)
        self.assertEqual([e["evento"] for e in studio.historico(self.proj)][-2:], ["travar", "liberar"])

    def test_qa_reprovado_devolve_correcoes_e_conta_voltas(self):
        rep = {"versao": 1, "aprovado": False, "checks": [
            {"area": "visual", "item": "card cobre a boca", "status": "falha", "tempo": 13.4, "alvo_id": "m5",
             "correcao": ["--patch", "m5.params.y=0.2"]}]}
        for volta in (1, 2, 3):
            r = json.loads(cli("qa", self.p, self.gravar("qa.json", rep)).stdout)
            self.assertFalse(r["aprovado"])
            self.assertEqual(r["correcoes"], [["--patch", "m5.params.y=0.2"]])
            self.assertEqual(r["volta"], volta)
        self.assertIn("3 voltas", r["proximo"])
        self.assertIn("passo", json.loads(cli("status", self.p).stdout)["proximo"])

    def test_skill_e_agentes_usam_o_fluxo_executavel(self):
        skill = (REPO / ".claude" / "skills" / "creative-studio" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`ST` = `PY creative/studio.py`", skill)
        for cmd in ("iniciar", "equipe", "rascunho", "verificar", "aprovar", "aplicar", "qa", "relatorio", "travar"):
            self.assertIn(f"ST {cmd}", skill)
        editor = (REPO / ".claude" / "agents" / "senior-editor.md").read_text(encoding="utf-8")
        self.assertIn("studio.py aplicar", editor)
        for ag in ("art-director", "conversion-strategist", "motion-3d-artist", "sound-designer"):
            self.assertIn("studio.py", (REPO / ".claude" / "agents" / f"{ag}.md").read_text(encoding="utf-8"), ag)


LIGADO = os.environ.get("EDITOR_TESTES_RENDER") == "1" and shutil.which("ffmpeg") and shutil.which("node")


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de ffmpeg, Node/Playwright e MediaPipe)")
class OitoPassosComRender(unittest.TestCase):
    """Os 8 passos num vídeo real (sintético): prévia, QA medido, revisão que só refaz o trecho, relatório."""

    def test_oito_passos(self):
        from test_render_revisao import DUR, video_sintetico  # noqa: E402  (mesmo vídeo dos testes do motor)
        d = Path(tempfile.mkdtemp(prefix="cs_render_"))
        try:
            clip = d / "sintetico.mp4"
            video_sintetico(clip)
            proj = d / "proj"
            subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "new", str(proj), "--clips", str(clip),
                            "--style", "pro_clean", "--sem-cortes", "--cta", "TESTE"], check=True, capture_output=True)
            words = [{"w": f"palavra{i}" + ("." if i % 6 == 5 else ""), "t0": round(0.2 + i * 0.5, 3),
                      "t1": round(0.55 + i * 0.5, 3), "clip": "c1"} for i in range(int((DUR - 0.8) / 0.5))]
            (proj / "transcript.json").write_text(json.dumps({"backend": "teste", "words": words, "silences": {}}),
                                                  encoding="utf-8")
            p = json.loads((proj / "project.json").read_text(encoding="utf-8"))
            p["overrides"]["motion"] = [{"template": "carimbo", "at": 13.0, "dur": 1.6, "params": {"text": "PROMO"}}]
            p["overrides"]["triggers"] = False
            (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
            tl = util.planejar(proj)
            # 1-2
            cli("iniciar", str(proj), "--pedido", "melhora o visual de 12 a 16s", "--tipo", "anuncio")
            cli("rascunho", str(proj), "--pedido", "melhora o visual de 12 a 16s")
            # 3-4
            m = next(x for x in tl["motion"] if x.get("template") == "carimbo")
            sp = proj / "creative" / "sp-arte.json"
            sp.write_text(json.dumps(shot("art-director", "c5", 12, 16,
                                          acao("patch", ["--patch", f"{m['id']}.params.text=OFERTA"], m["id"]))),
                          encoding="utf-8")
            dp = json.loads((proj / "creative" / "decision-plan.json").read_text(encoding="utf-8"))
            dp["convocados"] = [{"agente": "art-director", "motivo": "12-16 s", "cenas": ["c5"]},
                                {"agente": "senior-editor", "motivo": "aplicar", "cenas": ["todas"]}]
            (proj / "creative" / "decision-plan.json").write_text(json.dumps(dp), encoding="utf-8")
            self.assertTrue(json.loads(cli("aprovar", str(proj), str(sp)).stdout)["aprovado"])
            # render base (antes da revisão) para o cache existir
            subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "render", str(proj), "--draft"],
                           check=True, capture_output=True)
            # 5
            ap = json.loads(cli("aplicar", str(proj)).stdout)
            self.assertNotIn("observacoes", ap, "MISS fora das cenas do plano")
            self.assertTrue(all(not x.startswith("plano:") for x in ap["dry_run"]["miss"]),
                            "mudar texto de animação não pode refazer planos")
            # 6
            subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "render", str(proj), "--draft"],
                           check=True, capture_output=True)
            v = max(int(x.name[1:]) for x in (proj / "versions").glob("v*") if x.name[1:].isdigit())
            rv = json.loads((proj / "versions" / f"v{v}" / "revisao.json").read_text(encoding="utf-8"))
            self.assertEqual(rv["resumo"]["plano"]["MISS"], 0)
            mp4 = sorted((proj / "renders").glob("*.mp4"), key=lambda x: x.stat().st_mtime)[-1]
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                        str(mp4)], capture_output=True, text=True).stdout)
            rep = {"versao": v, "arquivo": str(mp4), "aprovado": abs(dur - DUR) < 0.2,
                   "metricas": {"duracao_s": dur, "miss": sum(x["MISS"] for x in rv["resumo"].values())},
                   "checks": [{"area": "tecnico", "item": "duração", "status": "ok" if abs(dur - DUR) < 0.2 else "falha"}]}
            (proj / "creative" / "qa.json").write_text(json.dumps(rep), encoding="utf-8")
            self.assertTrue(json.loads(cli("qa", str(proj), str(proj / "creative" / "qa.json")).stdout)["aprovado"])
            # 8
            rel = Path(cli("relatorio", str(proj)).stdout.strip()).read_text(encoding="utf-8")
            self.assertIn("HIT", rel)
            self.assertIn("art-director", rel)
            self.assertIn("APROVADO", rel)
        finally:
            if not os.environ.get("EDITOR_TESTES_MANTER"):
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
