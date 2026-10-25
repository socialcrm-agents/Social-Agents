"""Referência do concorrente (referencia.py): mede ritmo/densidade/estilo de um vídeo sintético com números conhecidos.

O vídeo é gerado pelo ffmpeg (sem arquivo externo): 6 planos de 2 s com cores/texturas diferentes (5 cortes),
2 flashes brancos de 2 quadros, legenda trocando de palavra a cada 1 s sempre na mesma faixa (base em ~62% da
altura) e 2 "adesivos" de texto no alto. O perfil tem que achar esses números (com tolerância) e a tradução
para o editor tem que ser coerente; aplicar no projeto muda só estilo/ritmo, nunca texto do vídeo de referência.

  python -m unittest tests/editor_video/test_referencia.py -v
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

W, H, FPS, DUR = 540, 960, 30, 12.0
CORTES = [2.0, 4.0, 6.0, 8.0, 10.0]
FLASHES = [3.0, 7.0]
CORES = ["0x2E4057", "0x8C2F39", "0x3E7C17", "0xC9A227", "0x5B2A86", "0x1B998B"]
PALAVRAS = ["ESSE", "É", "O", "SEGREDO", "QUE", "NINGUÉM", "TE", "CONTA", "AGORA", "MESMO"]
LEGENDA_BASE = 0.62
TEM_CV = shutil.which("ffmpeg") is not None
try:
    import cv2  # noqa: F401
    import numpy  # noqa: F401
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
except ImportError:
    TEM_CV = False


def _png_texto(path: Path, texto: str, altura: int, base_rel: float, cor=(255, 255, 255)) -> None:
    from PIL import Image, ImageDraw, ImageFont
    fonte = ImageFont.truetype(str(util.SK / "assets" / "fonts" / "Anton-Regular.ttf"), altura)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=fonte, stroke_width=5)
    d.text(((W - (x1 - x0)) / 2 - x0, H * base_rel - y1), texto, font=fonte, fill=cor + (255,),
           stroke_width=5, stroke_fill=(0, 0, 0, 255))
    img.save(path)


def video_sintetico(pasta: Path) -> Path:
    """Planos coloridos com textura fixa + flashes + legenda + adesivos, montados num só comando do ffmpeg."""
    entradas, filtros = [], []
    for k, cor in enumerate(CORES):
        entradas += ["-f", "lavfi", "-i", f"color=c={cor}:s={W}x{H}:r={FPS}:d=2"]
        # textura própria de cada plano (ruído fixo + grade), para o corte ser "troca de cena" de verdade
        filtros.append(f"[{k}:v]noise=alls={8 + 3 * k}:allf=u,drawgrid=w={40 + 15 * k}:h={40 + 15 * k}:"
                       f"t=2:color=white@0.25,format=yuv420p[p{k}]")
    filtros.append("".join(f"[p{k}]" for k in range(len(CORES))) + f"concat=n={len(CORES)}:v=1:a=0[base]")
    cur = "base"
    n = len(CORES)
    for j, palavra in enumerate(PALAVRAS):        # legenda: 1 palavra por segundo, de 1 s a 11 s
        png = pasta / f"leg{j}.png"
        _png_texto(png, palavra, 62, LEGENDA_BASE)
        entradas += ["-loop", "1", "-t", str(DUR), "-i", str(png)]
        t0 = 1.0 + j
        filtros.append(f"[{cur}][{n}:v]overlay=0:0:enable='between(t,{t0},{t0 + 0.999})'[l{j}]")
        cur, n = f"l{j}", n + 1
    for j, (texto, t0, t1) in enumerate([("OFERTA", 5.2, 6.6), ("HOJE", 9.1, 10.4)]):   # adesivos no alto
        png = pasta / f"ad{j}.png"
        _png_texto(png, texto, 80, 0.22, cor=(255, 230, 0))
        entradas += ["-loop", "1", "-t", str(DUR), "-i", str(png)]
        filtros.append(f"[{cur}][{n}:v]overlay=0:0:enable='between(t,{t0},{t1})'[a{j}]")
        cur, n = f"a{j}", n + 1
    flash = "+".join(f"between(t,{t:.3f},{t + 2 / FPS - 0.001:.3f})" for t in FLASHES)
    filtros.append(f"[{cur}]drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{flash}',format=yuv420p[out]")
    out = pasta / "referencia_sintetica.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *entradas, "-filter_complex", ";".join(filtros),
                    "-map", "[out]", "-t", str(DUR), "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "18", str(out)], check=True, capture_output=True)
    return out


def video_parado(pasta: Path) -> Path:
    """'Bruto': um plano só, câmera parada, sem texto nem flash."""
    out = pasta / "bruto_sintetico.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i",
                    f"color=c=0x6B705C:s={W}x{H}:r={FPS}:d={DUR}", "-vf", "noise=alls=10:allf=u,format=yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", str(out)], check=True, capture_output=True)
    return out


@unittest.skipUnless(TEM_CV, "precisa de ffmpeg, numpy, OpenCV e Pillow")
class PerfilSintetico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import referencia
        cls.ref = referencia
        cls.tmp = Path(tempfile.mkdtemp(prefix="ev_ref_"))
        cls.perfil = referencia.analisar(video_sintetico(cls.tmp), com_rosto=False)
        cls.perfil_bruto = referencia.analisar(video_parado(cls.tmp), com_rosto=False)
        cls.m = cls.perfil["medidas"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_cortes_e_planos(self):
        achados = self.m["tempos"]["cortes"]
        self.assertEqual(len(achados), len(CORTES), f"cortes achados: {achados}")
        for c in CORTES:
            self.assertTrue(any(abs(c - a) <= 0.15 for a in achados), f"corte em {c}s não achado: {achados}")
        self.assertAlmostEqual(self.m["plano_medio_s"], DUR / (len(CORTES) + 1), delta=0.2)
        self.assertAlmostEqual(self.m["cortes_por_min"], len(CORTES) / DUR * 60, delta=3)

    def test_flashes_nao_viram_corte(self):
        achados = self.m["tempos"]["flashes"]
        self.assertEqual(len(achados), len(FLASHES), f"flashes: {achados}")
        for f in FLASHES:
            self.assertTrue(any(abs(f - a) <= 0.1 for a in achados), f"flash em {f}s não achado: {achados}")

    def test_legenda_posicao_e_tamanho(self):
        leg = self.m["legenda"]
        self.assertIsNotNone(leg, "legenda não detectada")
        self.assertAlmostEqual(leg["base_rel"], LEGENDA_BASE, delta=0.04)
        self.assertGreater(leg["frac_tempo"], 0.45)   # palavras de 1-2 letras ("É", "O") não têm forma de linha
        tr = self.perfil["traducao"]
        self.assertAlmostEqual(tr["caption_y"], LEGENDA_BASE * 1920, delta=80)
        self.assertTrue(50 <= tr["caption_size"] <= 140)

    def test_texto_fora_da_legenda(self):
        ev = self.m["tempos"]["texto"]
        self.assertTrue(1 <= len(ev) <= 3, f"entradas de texto fora da legenda: {ev}")
        self.assertTrue(any(abs(t - 5.2) <= 0.7 for t in ev), ev)
        self.assertEqual(self.m["cor_destaque"] is not None, True)

    def test_bruto_bem_menos_denso(self):
        b = self.perfil_bruto["medidas"]
        self.assertEqual(b["cortes"], 0)
        self.assertEqual(b["flashes"], 0)
        self.assertIsNone(b["legenda"])
        self.assertGreater(self.m["cortes_por_min"], b["cortes_por_min"] + 15)
        self.assertGreater(self.m["texto_na_tela_frac"], b["texto_na_tela_frac"] + 0.3)
        self.assertEqual(self.perfil_bruto["traducao"]["zoom"], "off")

    def test_perfil_so_tem_numeros(self):
        texto = json.dumps(self.perfil, ensure_ascii=False)
        for palavra in PALAVRAS + ["OFERTA", "HOJE"]:
            if len(palavra) > 2:
                self.assertNotIn(palavra, texto, "o perfil não pode guardar texto do vídeo de referência")

    def test_aplicar_no_projeto_so_muda_estilo(self):
        proj = util.preparar("pro2")
        util.planejar(proj)
        antes = json.loads((proj / "project.json").read_text(encoding="utf-8"))
        perfil_path = self.tmp / "perfil.json"
        perfil_path.write_text(json.dumps(self.perfil, ensure_ascii=False), encoding="utf-8")
        env_proc = subprocess.run([sys.executable, str(util.SCRIPTS / "referencia.py"), "aplicar", str(perfil_path),
                                   str(proj)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(env_proc.returncode, 0, env_proc.stdout + env_proc.stderr)
        depois = json.loads((proj / "project.json").read_text(encoding="utf-8"))
        tr = self.perfil["traducao"]
        self.assertEqual(depois["style"], tr["estilo"])
        self.assertEqual(depois["overrides"]["caption"]["size"], tr["caption_size"])
        self.assertEqual(depois["overrides"]["caption"]["y"], tr["caption_y"])
        self.assertEqual(depois["overrides"]["caption"].get("emph_color"), tr["cor_destaque"])
        # conteúdo intocado: cortes, correções, motions e textos pedidos continuam os mesmos
        for k in ("cuts", "restores", "word_fixes", "motion", "hook", "cta", "patches"):
            self.assertEqual(antes["overrides"].get(k), depois["overrides"].get(k), k)
        self.assertEqual(depois["version"], antes["version"], "aplicar não renderiza")
        # efeitos (se houver) só em palavras ditas no NOSSO vídeo
        from common import norm
        nossas = {norm(w["w"]) for w in json.loads((proj / "transcript.json").read_text(encoding="utf-8"))["words"]}
        for r in depois["overrides"].get("fx_requests", []):
            self.assertIn(norm(r["at"]), nossas)


if __name__ == "__main__":
    unittest.main()
