"""Smart Revision Engine — testes rápidos (sem render; só biblioteca padrão; Windows, Mac e Linux).

  python -m unittest discover -s tests/editor_video -v
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import revisao  # noqa: E402


def ler(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else "-"


class IdsEstaveis(unittest.TestCase):
    def test_todos_os_elementos_tem_id_unico(self):
        tl = util.planejar(util.preparar("pro2"))
        for col in ("shots", "motion", "behind", "broll", "graphics", "fx"):
            ids = [x.get("id") for x in tl[col]]
            self.assertTrue(all(ids), f"{col} sem id")
            self.assertEqual(len(ids), len(set(ids)), f"{col} com id repetido")
        ids = [p["id"] for p in tl["captions"]["pages"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corte_no_meio_nao_muda_ids_nem_zoom_do_resto(self):
        proj = util.preparar("pro2")
        antes = util.planejar(proj)
        util.rodar("edit.py", proj, "--cut", "dá uma olhadinha, um", "--no-render")
        depois = util.planejar(proj)
        a = {s["id"]: (s["zoom0"], s["zoom1"], s["in"], s["out"]) for s in antes["shots"]}
        d = {s["id"]: (s["zoom0"], s["zoom1"], s["in"], s["out"]) for s in depois["shots"]}
        comuns = [i for i in a if i in d and a[i][2:] == d[i][2:]]
        self.assertGreaterEqual(len(comuns), len(a) - 2, "o corte deveria afetar no máximo os planos vizinhos")
        for i in comuns:
            self.assertEqual(a[i][:2], d[i][:2], f"zoom do plano {i} mudou só porque outro trecho foi cortado")
        # pedidos de motion mantêm o id (m1, m2...)
        self.assertEqual({m["id"] for m in antes["motion"] if m["id"].startswith("m")},
                         {m["id"] for m in depois["motion"] if m["id"].startswith("m")})


class Patches(unittest.TestCase):
    def test_patch_sobrevive_ao_replanejamento(self):
        proj = util.preparar("pro2")
        tl = util.planejar(proj)
        alvo = next(m for m in tl["motion"] if m["id"].startswith("m"))["id"]
        util.rodar("edit.py", proj, "--patch", f"{alvo}.params.rotulo=EDITADO", "--no-render")
        util.planejar(proj)
        util.rodar("edit.py", proj, "--caption-size", "+10%", "--cut", "dá uma olhadinha, um", "--no-render")
        tl2 = util.planejar(proj)
        m = next(m for m in tl2["motion"] if m["id"] == alvo)
        self.assertEqual(m["params"]["rotulo"], "EDITADO")
        self.assertEqual(m.get("_patch"), "editado")

    def test_edicao_manual_da_timeline_vira_patch_e_sobrevive(self):
        proj = util.preparar("pro2")
        tl = util.planejar(proj)
        tl["motion"][0]["params"]["EDITADO_A_MAO"] = True
        sid = tl["shots"][2]["id"]
        tl["shots"][2]["zoom0"] = 1.5
        (proj / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
        util.rodar("edit.py", proj, "--caption-size", "+10%", "--no-render")
        tl2 = util.planejar(proj)
        self.assertTrue(tl2["motion"][0]["params"].get("EDITADO_A_MAO"), "edição manual do motion se perdeu")
        self.assertEqual(next(s for s in tl2["shots"] if s["id"] == sid)["zoom0"], 1.5, "zoom manual se perdeu")
        patches = ler(proj / "project.json")["overrides"]["patches"]
        self.assertTrue(any(p.get("origem", "").startswith("timeline.json") for p in patches))
        # replanejar de novo não duplica nem perde
        tl3 = util.planejar(proj)
        self.assertEqual(util.normalizar(tl2), util.normalizar(tl3))

    def test_remover_elemento_automatico_por_patch(self):
        proj = util.preparar("pro2")
        tl = util.planejar(proj)
        alvo = tl["graphics"][0]["id"]
        util.rodar("edit.py", proj, "--patch-remove", alvo, "--no-render")
        self.assertNotIn(alvo, [g["id"] for g in util.planejar(proj)["graphics"]])
        util.rodar("edit.py", proj, "--patch-clear", alvo, "--no-render")
        self.assertIn(alvo, [g["id"] for g in util.planejar(proj)["graphics"]])

    def test_patch_orfao_avisa_e_fica_guardado(self):
        proj = util.preparar("pro2")
        util.planejar(proj)
        util.rodar("edit.py", proj, "--patch", "nao_existe.params.x=1", "--no-render")
        util.rodar("analyze.py", proj)
        r = util.rodar("plan.py", proj)
        self.assertIn("sem elemento correspondente", r.stdout)
        self.assertTrue(any(p.get("id") == "nao_existe" for p in ler(proj / "project.json")["overrides"]["patches"]))


class PedidosIdempotentes(unittest.TestCase):
    REQ = {"template": "luz", "at": 4.0, "dur": 1.5, "params": {"kind": "flash"}}

    def test_mesmo_motion_duas_vezes_nao_duplica(self):
        proj = util.preparar("pro2")
        antes = len(ler(proj / "project.json")["overrides"].get("motion", []))
        for _ in range(2):
            util.rodar("edit.py", proj, "--motion", json.dumps(self.REQ), "--no-render")
        self.assertEqual(len(ler(proj / "project.json")["overrides"]["motion"]), antes + 1)

    def test_motion_com_id_implicito_substitui_sem_duplicar(self):
        proj = util.preparar("pro2")
        tl = util.planejar(proj)
        antes = len(ler(proj / "project.json")["overrides"]["motion"])
        util.rodar("edit.py", proj, "--motion", json.dumps({**self.REQ, "id": "m2"}), "--no-render")
        reqs = ler(proj / "project.json")["overrides"]["motion"]
        self.assertEqual(len(reqs), antes)
        self.assertEqual(reqs[1]["template"], "luz")
        ids = [m["id"] for m in util.planejar(proj)["motion"]]
        self.assertEqual(len(ids), len(set(ids)), f"ids repetidos: {ids}")

    def test_motion_com_id_substitui(self):
        proj = util.preparar("pro2")
        util.rodar("edit.py", proj, "--motion", json.dumps({**self.REQ, "id": "selo"}), "--no-render")
        util.rodar("edit.py", proj, "--motion", json.dumps({**self.REQ, "id": "selo", "params": {"kind": "Y"}}),
                   "--no-render")
        reqs = [r for r in ler(proj / "project.json")["overrides"]["motion"] if r.get("id") == "selo"]
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]["params"]["kind"], "Y")
        tl = util.planejar(proj)
        self.assertIn("selo", [m["id"] for m in tl["motion"]])
        util.rodar("edit.py", proj, "--motion-remove", "selo", "--no-render")
        self.assertNotIn("selo", [m["id"] for m in util.planejar(proj)["motion"]])


class Grafo(unittest.TestCase):
    """Chaves por componente: mudar uma animação só invalida ela e os trechos que ela toca."""

    def _chaves(self, tl):
        w, h, fps = tl["w"], tl["h"], tl["fps"]
        cp = [revisao.chave_plano(s, w, h, fps) for s in tl["shots"]]
        cm = {m["id"]: revisao.chave_motion(m, tl, cp, True, Path("/nao/existe")) for m in tl["motion"]}
        ct = {(a, b): revisao.chave_trecho(tl, a, b, cp, cm, True, "veryfast", "f")
              for a, b, _ in revisao.janelas(tl["duration"], fps)}
        return cp, cm, ct, revisao.chave_audio(tl, cp)

    def test_mudar_animacao_entre_12_e_16_so_invalida_ela_e_o_trecho(self):
        proj = util.preparar("semcortes")
        tl = util.planejar(proj)
        alvo = next(m for m in tl["motion"] if 12 <= m["t0"] < 16 and m["id"].startswith("m"))
        cp1, cm1, ct1, au1 = self._chaves(tl)
        util.rodar("edit.py", proj, "--patch", f"{alvo['id']}.params.text=NOVO", "--no-render")
        tl2 = util.planejar(proj)
        cp2, cm2, ct2, au2 = self._chaves(tl2)
        self.assertEqual(cp1, cp2, "planos não deveriam mudar")
        self.assertEqual(au1, au2, "áudio não deveria mudar")
        self.assertEqual({k for k in cm1 if cm1[k] != cm2.get(k)}, {alvo["id"]})
        mudaram = {k for k in ct1 if ct1[k] != ct2.get(k)}
        esperado = {k for k in ct1 if k[0] < alvo["t1"] and k[1] > alvo["t0"]}
        self.assertEqual(mudaram, esperado)
        self.assertTrue(all(12 <= a < 16 for a, _ in mudaram), mudaram)

    def test_trechos_tem_quadros_inteiros_e_cobrem_o_video(self):
        for total in (17.367, 14.9, 4.0, 3.99, 30.0):
            js = revisao.janelas(total, 30)
            self.assertEqual(sum(n for _, _, n in js), round(total * 30))
            self.assertEqual(js[0][0], 0.0)
            for (a, b, n), (c, _, _) in zip(js, js[1:]):
                self.assertAlmostEqual(b, c)
                self.assertEqual(round((b - a) * 30), n)


class DryRun(unittest.TestCase):
    def test_dry_run_nao_grava_nada(self):
        proj = util.preparar("pro2")
        util.planejar(proj)
        antes = {f: md5(proj / f) for f in ("project.json", "timeline.json", "edl.json")}
        r = util.rodar("edit.py", proj, "--patch", "m1.params.x=1", "--dry-run")
        self.assertIn("dry-run", r.stdout)
        self.assertIn("MISS", r.stdout)
        self.assertEqual(antes, {f: md5(proj / f) for f in antes})
        self.assertFalse((proj / "renders").exists() and any((proj / "renders").iterdir()))


class Windows(unittest.TestCase):
    def test_fontes_sem_link_simbolico_copiam(self):
        import tempfile

        import render
        work = Path(tempfile.mkdtemp())
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("sem privilégio")):
            render.prepare_fonts({"brand": None}, work)
        self.assertTrue(any((work / "fonts").glob("*.ttf")))

    def test_lista_de_concat_usa_barra_normal_e_aspas(self):
        import tempfile

        import render
        d = Path(tempfile.mkdtemp())
        files = [d / "a b.mp4", d / "c'd.mp4"]
        with mock.patch.object(render, "ffmpeg") as ff, mock.patch("os.replace"):
            render._concat(files, d / "out.mp4")
        lista = next(a for a in ff.call_args[0][0] if str(a).endswith(".txt"))
        # a lista é apagada no fim; o comando aponta para ela e usa -safe 0
        self.assertIn("-safe", ff.call_args[0][0])
        self.assertTrue(lista.endswith(".lista.txt"))


if __name__ == "__main__":
    unittest.main()
