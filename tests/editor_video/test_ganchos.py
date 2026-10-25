"""Gancho testado (ganchos.py / run.py ganchos): 3 aberturas diferentes que só mudam o começo do vídeo.

Rápido (sem render): planeja as variações nas fixtures e confere que
  - as 3 variações são diferentes entre si e só diferem do vídeo principal nos primeiros ~3 s (trecho 0-4 s);
  - os textos na tela são palavras ditas no vídeo (nada inventado);
  - vídeo com cortes ganha corte de gancho (frase forte antes do começo); sem cortes, não (vira 2.5D);
  - project.json, edl.json e timeline.json voltam byte a byte ao estado original.
Render de verdade (opcional): EDITOR_TESTES_RENDER=1 -> só os trechos do começo são refeitos (MISS).

  python -m unittest tests/editor_video/test_ganchos.py -v
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

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
from common import norm  # noqa: E402

LIGADO = os.environ.get("EDITOR_TESTES_RENDER") == "1" and shutil.which("ffmpeg") and shutil.which("node")
ARQS = ("project.json", "edl.json", "timeline.json", "work/timeline_gerada.json")


def ler(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def textos_motion(m: dict) -> list[str]:
    p = m.get("params", {})
    out = [p.get("text"), p.get("texto")] + list(p.get("linhas") or [])
    return [x for x in out if isinstance(x, str) and x]


class GanchosPlano(unittest.TestCase):
    def rodar(self, fixture: str, n: int = 3):
        proj = util.preparar(fixture)
        self.addCleanup(shutil.rmtree, proj, True)
        util.planejar(proj)
        antes = {a: (proj / a).read_bytes() for a in ARQS}
        r = subprocess.run(
            [sys.executable, str(util.SCRIPTS / "run.py"), "ganchos", str(proj), "--so-plano", "--n", str(n)],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        for a in ARQS:
            self.assertEqual((proj / a).read_bytes(), antes[a], f"{a} não voltou ao estado original")
        res = ler(proj / "qa" / "ganchos.json")
        tls = {x["letra"]: ler(proj / "work" / "ganchos" / f"timeline_{x['letra']}.json") for x in res}
        self.assertTrue((proj / "qa" / "ganchos.md").exists())
        return proj, ler(proj / "timeline.json"), res, tls

    def checa_so_o_comeco(self, base: dict, tl: dict) -> None:
        def depois(itens, chave="t0"):
            return [{k: v for k, v in x.items() if k != "_patch"} for x in itens if x.get(chave, 0) >= 4.0]
        self.assertEqual(tl["duration"], base["duration"])
        self.assertEqual(depois(tl["shots"]), depois(base["shots"]))
        self.assertEqual(depois(tl["motion"]), depois(base["motion"]))
        self.assertEqual(depois(tl["captions"]["pages"]), depois(base["captions"]["pages"]))
        self.assertEqual(depois(tl["behind"]), depois(base["behind"]))
        self.assertEqual([f for f in tl["fx"] if f["t"] >= 4.0], [f for f in base["fx"] if f["t"] >= 4.0])

    def checa_texto_dito(self, proj: Path, tl: dict) -> None:
        ditas = {norm(w["w"]) for w in ler(proj / "transcript.json")["words"]}
        ditas |= {norm(w["w"]) for w in tl["words"]}          # com as correções de palavra do projeto
        for m in tl["motion"]:
            if str(m.get("id", "")).startswith("gancho_"):
                for t in textos_motion(m):
                    for palavra in t.split():
                        self.assertIn(norm(palavra), ditas, f"'{palavra}' em {m['id']} não foi dito no vídeo")

    def test_sem_cortes_tres_aberturas_so_no_comeco(self):
        proj, base, res, tls = self.rodar("semcortes")
        self.assertEqual([x["letra"] for x in res], ["A", "B", "C"])
        gmot = {k: [m for m in tl["motion"] if str(m.get("id", "")).startswith("gancho_")] for k, tl in tls.items()}
        self.assertEqual(gmot["A"][0]["template"], "pergunta")
        self.assertEqual(gmot["B"][0]["template"], "manchete")
        self.assertEqual(gmot["C"][0]["template"], "profundidade", "sem cortes: C não pode ser corte de gancho")
        for k, tl in tls.items():
            self.assertTrue(all(m["t1"] <= 3.05 for m in gmot[k]), "gancho passou de ~3 s")
            self.checa_so_o_comeco(base, tl)
            self.checa_texto_dito(proj, tl)
            self.assertNotEqual(tl, base)
        for x in res:
            self.assertEqual(x["trechos_diferentes"], [[0.0, 4.0]], f"gancho {x['letra']}: {x['trechos_diferentes']}")
        # as três são diferentes entre si
        cab = [json.dumps([m for m in tl["motion"] if m["t0"] < 3.0], sort_keys=True) for tl in tls.values()]
        self.assertEqual(len(set(cab)), 3)
        # B: zoom de impacto no 1º plano + tremida
        self.assertGreater(tls["B"]["shots"][0]["zoom0"], base["shots"][0]["zoom0"])
        self.assertTrue(any(f.get("id") == "gancho_fx_b" for f in tls["B"]["fx"]))
        # a abertura antiga (motion no começo) saiu de todas
        velhas = [m["id"] for m in base["motion"] if m["t0"] < 3.0]
        for tl in tls.values():
            self.assertFalse([m for m in tl["motion"] if m["id"] in velhas])

    def test_com_cortes_corte_de_gancho(self):
        proj, base, res, tls = self.rodar("pro2")
        c = tls["C"]
        self.assertEqual(res[2]["nome"], "corte de gancho")
        primeiro = c["shots"][0]
        self.assertTrue(primeiro.get("gancho") and primeiro["id"].startswith("g"))
        dur_g = round(primeiro["t1"], 3)
        self.assertTrue(1.4 <= dur_g <= 3.3, dur_g)
        # o resto do vídeo é o mesmo, empurrado pela duração do gancho (mesmos planos, mesma ordem)
        resto = [s for s in c["shots"] if not s.get("gancho")]
        self.assertEqual([(s["id"], s["in"], s["out"]) for s in resto], [(s["id"], s["in"], s["out"]) for s in base["shots"]])
        self.assertAlmostEqual(c["duration"], base["duration"] + sum(s["t1"] - s["t0"] for s in c["shots"]
                                                                      if s.get("gancho")), delta=0.01)
        # as palavras do gancho foram ditas mais tarde no vídeo e não disparam animação de novo
        gw = [w for w in c["words"] if w.get("gancho")]
        self.assertTrue(gw)
        self.assertGreater(min(w["i"] for w in gw), min(w["i"] for w in c["words"] if not w.get("gancho")))
        self.assertEqual(sorted(m["id"] for m in c["motion"]), sorted(m["id"] for m in base["motion"]))
        for k in ("A", "B"):
            self.checa_so_o_comeco(base, tls[k])

    def test_variacao_d_com_n4(self):
        proj, base, res, tls = self.rodar("semcortes", 4)
        self.assertEqual(len(res), 4)
        d = [m for m in tls["D"]["motion"] if m.get("id") == "gancho_d"]
        self.assertEqual(d[0]["template"], "palavra")
        self.checa_so_o_comeco(base, tls["D"])


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de ffmpeg, Node/Playwright e MediaPipe)")
class GanchosRender(unittest.TestCase):
    """Render de verdade: o gancho só refaz o começo; o resto é HIT do cache do vídeo principal."""

    def test_so_o_comeco_e_refeito(self):
        d = Path(tempfile.mkdtemp(prefix="ev_ganchos_"))
        self.addCleanup(shutil.rmtree, d, True)
        clip = d / "sintetico.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", "testsrc2=s=540x960:r=30:d=12",
                        "-f", "lavfi", "-i", "sine=f=220:d=12", "-c:v", "libx264", "-preset", "ultrafast",
                        "-c:a", "aac", "-shortest", str(clip)], check=True, capture_output=True)
        proj = d / "proj"
        r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "new", str(proj), "--clips", str(clip),
                            "--style", "pro_clean", "--sem-cortes"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        fala = ("Você já perdeu vendas por causa disso? O segredo é simples, custa só 15 reais. "
                "Funciona hoje mesmo e eu te mostro como. Clica e confere agora mesmo.").split()
        words = [{"w": w, "t0": round(0.3 + i * 0.4, 3), "t1": round(0.62 + i * 0.4, 3), "clip": "c1"}
                 for i, w in enumerate(fala)]
        (proj / "transcript.json").write_text(json.dumps({"words": words, "silences": {}}), encoding="utf-8")
        p = ler(proj / "project.json")
        p["overrides"]["triggers"] = False
        # o vídeo principal já usa a máscara da pessoa (palavra atrás em 8 s), como num vídeo real com rosto:
        # sem isso, o primeiro elemento de zona "topo" liga a máscara e TODOS os trechos mudam (limite conhecido)
        p["overrides"]["motion"] = [{"template": "palavra", "at": 8.0, "dur": 1.6, "params": {"text": "SIM."}}]
        (proj / "project.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "render", str(proj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        antes = (proj / "project.json").read_text(encoding="utf-8")
        r = subprocess.run([sys.executable, str(util.SCRIPTS / "run.py"), "ganchos", str(proj), "--n", "2"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        for x in ler(proj / "qa" / "ganchos.json"):
            self.assertTrue(Path(x["arquivo"]).exists())
            trechos = [m["id"] for m in x["miss"] if m["tipo"] == "trecho"]
            self.assertEqual(trechos, ["000.0-004.0"], f"gancho {x['letra']} refez {trechos}")
            self.assertEqual(x["resumo"]["plano"]["MISS"], 0 if x["letra"] == "A" else 1)
        depois = ler(proj / "project.json")
        orig = json.loads(antes)
        self.assertEqual({k: v for k, v in depois.items() if k != "version"}, {k: v for k, v in orig.items() if k != "version"})


if __name__ == "__main__":
    unittest.main()
