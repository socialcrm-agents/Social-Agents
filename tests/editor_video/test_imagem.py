"""Correção de imagem e estabilização (imagem.py) — testes com vídeo sintético pequeno (ffmpeg + OpenCV).

  python -m unittest tests/editor_video/test_imagem.py -v

- tremida conhecida (textura parada recortada com deslocamento senoidal) -> o plano estabilizado treme bem menos;
- vídeo escuro e com cor puxada -> a luma sobe, sem estourar o branco, e o croma volta para perto do neutro;
- opção desligada (ou ausente) -> chave do plano idêntica à de antes (cache e goldens intactos);
- edit.py --correcao/--estabilizar/--pele -> vai para project.json e chega na timeline.
"""

from __future__ import annotations

import json
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
import revisao  # noqa: E402

try:
    import cv2  # noqa: F401
    import numpy  # noqa: F401
    TEM_CV = bool(shutil.which("ffmpeg"))
except ImportError:
    TEM_CV = False

W, H, FPS = 270, 480, 30


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *args], check=True, capture_output=True)


def textura(path: Path, w: int, h: int) -> None:
    """Imagem parada cheia de detalhe (ruído desfocado + grade): cantos de sobra para o fluxo óptico."""
    ff("-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:d=0.04", "-vf",
       "noise=alls=90:allf=0,gblur=sigma=1.6,drawgrid=w=37:h=41:t=2:c=white@0.6,eq=contrast=1.4",
       "-frames:v", "1", str(path))


def video_tremido(path: Path, tex: Path, dur: float = 4.0) -> None:
    """Câmera na mão sintética: recorte 360x640 da textura com tremida de 3 e 5 Hz (amplitude ~12 px)."""
    x = "60+9*sin(2*PI*3.1*t)+5*sin(2*PI*5.3*t+1)"
    y = "80+8*sin(2*PI*2.7*t+0.5)+5*sin(2*PI*4.9*t)"
    ff("-loop", "1", "-framerate", str(FPS), "-i", str(tex), "-t", str(dur), "-vf",
       f"crop=360:640:x='{x}':y='{y}',format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14",
       str(path))


def video_escuro(path: Path, tex: Path, dur: float = 2.0) -> None:
    """Celular no escuro: textura com pouca luz, puxada para o laranja, com ruído de sensor (menor que a saída)."""
    ff("-loop", "1", "-framerate", str(FPS), "-i", str(tex), "-t", str(dur), "-vf",
       "scale=180:320,eq=brightness=-0.12:gamma=0.6:contrast=0.85,"
       "colorbalance=rs=0.08:bs=-0.10:rm=0.06:bm=-0.08,noise=c0s=14:c1s=8:c2s=8:allf=t,format=yuv420p",
       "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", str(path))


def stats_yuv(video: Path) -> dict:
    """Luma (percentis 50/99, fração de branco estourado) e média de Cb/Cr, direto dos planos YUV."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-vf", "format=yuv444p",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                      "stream=width,height", "-of", "json", str(video)],
                                     capture_output=True, text=True).stdout)["streams"][0]
    w, h = info["width"], info["height"]
    a = np.frombuffer(raw, np.uint8).reshape(-1, 3, h, w)
    y = (a[:, 0].astype(np.float32) - 16) / 219
    return {"p50": float(np.percentile(y, 50)), "p99": float(np.percentile(y, 99)),
            "estouro": float((a[:, 0] >= 234).mean()), "cb": float(a[:, 1].mean()), "cr": float(a[:, 2].mean())}


def plano(src: Path, dur: float, **extra) -> dict:
    sh = {"id": "s1", "clip": "c1", "src": str(src), "in": 0.0, "out": dur, "t0": 0.0, "t1": dur,
          "zoom0": 1.0, "zoom1": 1.0, "cx": 0.5, "cy": 0.42, "speed": 1.0}
    sh.update(extra)
    return sh


def renderizar(tl: dict, work: Path) -> Path:
    """Prepara (análise + decisões) e renderiza o plano pelo mesmo caminho do render.py."""
    import imagem
    import render
    render.W, render.H, render.FPS = W, H, FPS
    imagem.preparar_planos(tl, work, {}, {}, W, H)
    chaves = [revisao.chave_plano(sh, W, H, FPS) for sh in tl["shots"]]
    return render.render_shots(tl, work, "ultrafast", None, chaves)


@unittest.skipUnless(TEM_CV, "precisa de ffmpeg, numpy e OpenCV")
class Imagem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="ev_imagem_"))
        cls.tex = cls.dir / "textura.png"
        textura(cls.tex, 520, 860)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_tremida_conhecida_cai_depois_de_estabilizar(self):
        import imagem
        src = self.dir / "tremido.mp4"
        video_tremido(src, self.tex)
        tl = {"shots": [plano(src, 4.0)], "imagem": {"estabilizar": "on"}}
        work = self.dir / "w_trem"
        work.mkdir()
        out = renderizar(tl, work)
        self.assertTrue(tl["shots"][0]["imagem"].get("estab"), "deveria ter decidido estabilizar")
        antes = imagem.analisar_clipe(str(src), self.dir / "m_antes", "a", W / H)["tremida"]
        depois = imagem.analisar_clipe(str(out), self.dir / "m_depois", "d", W / H)["tremida"]
        # movimento global entre quadros: o desvio tem que cair pelo menos à metade (na prática cai ~5x)
        self.assertLess(depois["passo_std"], 0.5 * antes["passo_std"], (antes, depois))
        self.assertLess(depois["jitter"], 0.5 * antes["jitter"], (antes, depois))

    def test_estabilizar_auto_nao_mexe_em_video_parado(self):
        src = self.dir / "parado.mp4"
        ff("-loop", "1", "-framerate", str(FPS), "-i", str(self.tex), "-t", "2", "-vf", "crop=360:640:40:40,format=yuv420p",
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", str(src))
        import imagem
        tl = {"shots": [plano(src, 2.0)], "imagem": {"estabilizar": "auto"}}
        imagem.preparar_planos(tl, self.dir / "w_parado", {}, {}, W, H)
        self.assertNotIn("estab", tl["shots"][0]["imagem"])

    def test_video_escuro_clareia_sem_estourar_e_tira_a_cor_puxada(self):
        src = self.dir / "escuro.mp4"
        video_escuro(src, self.tex)
        tl = {"shots": [plano(src, 2.0)], "imagem": {"correcao": "auto", "pele": 0.5}}
        work = self.dir / "w_escuro"
        work.mkdir()
        out = renderizar(tl, work)
        cor = tl["shots"][0]["imagem"]["cor"]
        self.assertTrue(tl["shots"][0]["imagem"]["no_bruto"], "bruto menor que a saída: filtra na resolução dele")
        self.assertIn("curva", cor)
        self.assertIn("denoise", cor)
        # referência: o mesmo plano sem correção (só a ampliação de sempre)
        tl0 = {"shots": [plano(src, 2.0)]}
        work0 = self.dir / "w_escuro0"
        work0.mkdir()
        ref = renderizar(tl0, work0)
        a, d = stats_yuv(ref), stats_yuv(out)
        self.assertGreater(d["p50"], a["p50"] + 0.05, (a, d))
        self.assertLess(d["estouro"], 0.01, "não pode estourar o branco")
        self.assertLessEqual(d["p99"], 0.99)
        # croma mais perto do neutro (128) que antes
        self.assertLess(abs(d["cb"] - 128) + abs(d["cr"] - 128), abs(a["cb"] - 128) + abs(a["cr"] - 128))

    def test_opcao_desligada_mantem_a_chave_e_o_filtro_de_antes(self):
        import imagem
        sh = plano(Path("/nao/existe.mp4"), 3.0, cx=0.41, cy=0.37, zoom1=1.08)
        antiga = revisao.hk("plano", revisao.arquivo_sig(sh["src"]), sh["in"], sh["out"], round(sh["t1"] - sh["t0"], 4),
                            sh["zoom0"], sh["zoom1"], sh.get("cx"), sh.get("cy"), sh.get("speed", 1.0), W, H, FPS)
        for tl in ({"shots": [dict(sh)]}, {"shots": [dict(sh)], "imagem": {"correcao": "off", "estabilizar": "off"}},
                   {"shots": [dict(sh)], "imagem": {}}):
            self.assertIsNone(imagem.config(tl))
            imagem.preparar_planos(tl, self.dir / "w_off", {}, {}, W, H)
            self.assertNotIn("imagem", tl["shots"][0])
            self.assertEqual(revisao.chave_plano(tl["shots"][0], W, H, FPS), antiga)
        # ligada: a decisão entra na chave (cache não serve plano velho) e muda junto com ela
        a = dict(sh, imagem={"v": 1, "cor": {"pele": 0.3}})
        b = dict(sh, imagem={"v": 1, "cor": {"pele": 0.5}})
        self.assertNotEqual(revisao.chave_plano(a, W, H, FPS), antiga)
        self.assertNotEqual(revisao.chave_plano(a, W, H, FPS), revisao.chave_plano(b, W, H, FPS))

    def test_expressao_por_partes_interpola_e_segura_as_pontas(self):
        import imagem
        expr = imagem._expr_partes([0.0, 1 / 30, 2 / 30], [0.2, 0.4, 0.3], 30)
        # avalia a expressão do jeito do ffmpeg (st/ld/clip/max/abs) para alguns instantes
        def avalia(t):
            mem = {}
            def st(i, v):
                mem[int(i)] = v
                return v
            ctx = {"st": st, "ld": lambda i: mem[int(i)], "clip": lambda v, a, b: min(max(v, a), b),
                   "max": max, "abs": abs, "t": t}
            a, b = expr.split(";", 1)
            eval(a, ctx)
            return eval(b, ctx)
        self.assertAlmostEqual(avalia(0.0), 0.2, 4)
        self.assertAlmostEqual(avalia(0.5 / 30), 0.3, 4)
        self.assertAlmostEqual(avalia(1.5 / 30), 0.35, 4)
        self.assertAlmostEqual(avalia(5.0), 0.3, 4)      # depois do fim: segura o último valor
        self.assertAlmostEqual(avalia(-1.0), 0.2, 4)     # antes do começo: segura o primeiro


class Opcoes(unittest.TestCase):
    def test_edit_grava_as_opcoes_e_o_plan_leva_para_a_timeline(self):
        proj = util.preparar("pro2")
        tl = util.planejar(proj)
        self.assertNotIn("imagem", tl, "sem a opção a timeline não muda")
        util.rodar("edit.py", proj, "--correcao", "auto", "--estabilizar", "on", "--pele", "0.6", "--no-render")
        p = json.loads((proj / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(p["overrides"]["imagem"], {"correcao": "auto", "estabilizar": "on", "pele": 0.6})
        tl = util.planejar(proj)
        self.assertEqual(tl["imagem"], {"correcao": "auto", "estabilizar": "on", "pele": 0.6})
        util.rodar("edit.py", proj, "--correcao", "off", "--estabilizar", "off", "--pele", "0", "--no-render")
        tl = util.planejar(proj)
        sys.path.insert(0, str(util.SCRIPTS))
        import imagem
        self.assertIsNone(imagem.config(tl))
        shutil.rmtree(proj, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
