"""Creative Studio — testes do contrato (agentes, schemas, skill) e do fluxo com ferramentas reais numa fixture.

  python -m unittest tests/creative_studio/test_creative_studio.py -v        (só biblioteca padrão)
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
AGENTS = REPO / ".claude" / "agents"
CREATIVE = REPO / "creative"
SKILL = REPO / ".claude" / "skills" / "creative-studio" / "SKILL.md"
sys.path.insert(0, str(CREATIVE))
sys.path.insert(0, str(REPO / "tests" / "editor_video"))
import util  # noqa: E402
import validar  # noqa: E402

ESPERADOS = {"conversion-strategist", "art-director", "senior-editor", "motion-3d-artist", "sound-designer",
             "render-engineer", "quality-director"}
CAMPOS_SUPORTADOS = {"name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
                     "skills", "effort", "color", "isolation", "mcpServers", "hooks", "memory", "background"}
FERRAMENTAS = {"Read", "Grep", "Glob", "Bash", "Edit", "Write", "NotebookEdit", "Agent", "WebFetch", "WebSearch"}
# quem pode alterar arquivos (e o quê) — o resto é só leitura
ESCRITA = {"senior-editor": {"Write"}, "motion-3d-artist": {"Edit", "Write"}, "render-engineer": {"Edit"}}
SCHEMAS = ["brief", "decision-plan", "shot-plan", "revision-plan", "qa-report"]


def frontmatter(path: Path) -> tuple[dict, str]:
    """Parser mínimo do frontmatter (chave: valor; valor entre aspas = JSON) sem depender de PyYAML."""
    texto = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    assert m, f"{path.name}: frontmatter ausente"
    d = {}
    for linha in m.group(1).splitlines():
        k, _, v = linha.partition(":")
        v = v.strip()
        d[k.strip()] = json.loads(v) if v.startswith('"') else v
    return d, m.group(2)


def lista(v: str) -> set[str]:
    return {x.strip() for x in v.split(",") if x.strip()}


class Agentes(unittest.TestCase):
    def test_existem_exatamente_os_sete(self):
        self.assertEqual({p.stem for p in AGENTS.glob("*.md")}, ESPERADOS)

    def test_frontmatter_suportado_e_consistente(self):
        for p in AGENTS.glob("*.md"):
            fm, corpo = frontmatter(p)
            self.assertEqual(fm["name"], p.stem)
            self.assertTrue(set(fm) <= CAMPOS_SUPORTADOS, f"{p.name}: campo não suportado {set(fm) - CAMPOS_SUPORTADOS}")
            self.assertGreater(len(fm["description"]), 80, f"{p.name}: descrição curta demais para delegação")
            self.assertIn("Convoque", fm["description"], f"{p.name}: descrição não diz quando convocar")
            self.assertTrue(lista(fm["tools"]) <= FERRAMENTAS)
            self.assertIn("Agent", lista(fm["disallowedTools"]), f"{p.name}: especialista não pode convocar outros")
            self.assertTrue(int(fm["maxTurns"]) <= 30)

    def test_permissoes_por_funcao(self):
        for p in AGENTS.glob("*.md"):
            fm, _ = frontmatter(p)
            efetivas = lista(fm["tools"]) - lista(fm["disallowedTools"])
            escrita = efetivas & {"Edit", "Write", "NotebookEdit"}
            self.assertEqual(escrita, ESCRITA.get(p.stem, set()), f"{p.name}: ferramentas de escrita {escrita}")

    def test_corpo_tem_obrigacoes(self):
        for p in AGENTS.glob("*.md"):
            _, corpo = frontmatter(p)
            for trecho in ("approved-decisions.json", "Sem render completo", "Saída", "Critérios de qualidade",
                           "suportado\": false", "creative/"):
                self.assertIn(trecho, corpo, f"{p.name}: falta '{trecho}'")
            self.assertTrue(any(f"creative/{s}.schema.json" in corpo for s in SCHEMAS), f"{p.name}: sem schema de saída")


class Contratos(unittest.TestCase):
    def test_schemas_sao_json_schema_validos(self):
        for s in SCHEMAS:
            sc = json.loads((CREATIVE / f"{s}.schema.json").read_text(encoding="utf-8"))
            self.assertIn("$schema", sc)
            try:
                import jsonschema
                jsonschema.Draft202012Validator.check_schema(sc)
            except ImportError:
                pass

    def test_exemplos_passam_e_erros_sao_pegos_nos_dois_validadores(self):
        for s in SCHEMAS:
            ok = json.loads((CREATIVE / "exemplos" / f"{s}.json").read_text(encoding="utf-8"))
            self.assertEqual(validar.validar(ok, s), [], s)
            ruim = copy.deepcopy(ok)
            ruim.pop(next(iter(json.loads((CREATIVE / f"{s}.schema.json").read_text())["required"])))
            ruim["campo_inventado"] = 1
            self.assertTrue(validar.validar(ruim, s), f"{s}: erro não detectado (jsonschema)")
            with mock.patch.dict(sys.modules, {"jsonschema": None}):
                self.assertEqual(validar.validar(ok, s), [], f"{s}: validador próprio rejeitou exemplo bom")
                self.assertGreaterEqual(len(validar.validar(ruim, s)), 2, f"{s}: validador próprio não pegou erros")

    def test_decisoes_aprovadas_tem_ids_unicos(self):
        d = json.loads((CREATIVE / "approved-decisions.json").read_text(encoding="utf-8"))["decisoes"]
        ids = [x["id"] for x in d]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(x["decisao"] and x["origem"] for x in d))

    def test_skill_do_diretor(self):
        fm, corpo = frontmatter(SKILL)
        self.assertEqual(fm["name"], "creative-studio")
        for etapa in ("**1.", "**2.", "**3.", "**4.", "**5.", "**6.", "**7.", "**8."):
            self.assertIn(etapa, corpo)
        for nome in ESPERADOS:
            self.assertIn(f"`{nome}`", corpo, f"skill não diz quando convocar {nome}")
        self.assertIn("Gaps conhecidos", corpo)


class FluxoComFerramentasReais(unittest.TestCase):
    """Passos 1-5 na fixture real (Mentos sem cortes): brief → plano → comandos do shot-plan aplicados com edit.py →
    dry-run → revision-plan validado. Garante que os comandos que os especialistas propõem existem de verdade."""

    def test_fluxo_na_fixture(self):
        proj = util.preparar("semcortes")
        tl = util.planejar(proj)
        # 1. brief
        brief = json.loads((CREATIVE / "exemplos" / "brief.json").read_text(encoding="utf-8"))
        brief["projeto"] = str(proj)
        self.assertEqual(validar.validar(brief, "brief"), [])
        # 2-4. plano aprovado com ids reais da timeline
        alvo = next(m for m in tl["motion"] if 12 <= m["t0"] < 16 and m["id"].startswith("m"))
        shot = {"agente": "art-director", "cenas": [{"cena": "c4", "t0": alvo["t0"], "t1": alvo["t1"], "acoes": [
            {"tipo": "patch", "comando": ["--patch", f"{alvo['id']}.params.text=VICIANTE."], "alvo_id": alvo["id"],
             "justificativa": "palavra mais forte", "suportado": True},
            {"tipo": "fx", "comando": ["--fx", "tremida@gostoso"], "justificativa": "impacto", "suportado": True}]}]}
        self.assertEqual(validar.validar(shot, "shot-plan"), [])
        # 5. editor sênior: aplica exatamente os comandos (sem render) e mede o custo com dry-run
        ops = [a["comando"] for c in shot["cenas"] for a in c["acoes"] if a.get("suportado")]
        args = [x for op in ops for x in op]
        dry = util.rodar("edit.py", proj, *args, "--dry-run")
        miss = re.findall(r"MISS\s+(\w+)\s+(\S+)", dry.stdout)
        util.rodar("edit.py", proj, *args, "--no-render", "--note", "teste do fluxo creative-studio")
        tl2 = util.planejar(proj)
        self.assertEqual(next(m for m in tl2["motion"] if m["id"] == alvo["id"])["params"]["text"], "VICIANTE.")
        self.assertTrue(any(f["type"] == "tremida" for f in tl2["fx"]))
        rev = {"pedido": "troca a palavra gigante e dá impacto", "operacoes": [{"comando": o} for o in ops],
               "dry_run": {"resumo": dry.stdout.strip().splitlines()[-2], "miss": [f"{a}:{b}" for a, b in miss]},
               "preset": "draft", "conflita_com_aprovadas": []}
        self.assertEqual(validar.validar(rev, "revision-plan"), [])
        self.assertTrue(rev["dry_run"]["miss"])


if __name__ == "__main__":
    unittest.main()
