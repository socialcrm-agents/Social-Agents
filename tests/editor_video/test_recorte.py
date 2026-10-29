"""Recorte de produto (fundo removido, 100% local): o motor OpenCV em fotos sintéticas de estúdio (fundo liso, degradê,
sombra, ruído e JPEG), medido por IoU contra a máscara verdadeira; borda sem halo; PNG justo; CLI; e o template
produto3d registrado.   python -m unittest tests/editor_video/test_recorte.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import recorte  # noqa: E402


def _jpeg(img: np.ndarray, q: int = 88) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def foto_estudio(produto: str, fundo=(236, 236, 238), degrade: float = 18, sombra: float = 0.45, ruido: float = 3,
                 tam=(720, 540), semente: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Foto sintética de produto em estúdio -> (BGR uint8, máscara verdadeira bool). Fundo com degradê vertical e
    vinheta, sombra suave projetada + sombra de contato, ruído de sensor e compressão JPEG."""
    rng = np.random.default_rng(semente)
    h, w = tam
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.array(fundo, np.float32)
    luz = 1 - degrade / 255 * (yy / h) - 0.04 * (((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2)
    img = base[None, None] * luz[..., None]
    m = np.zeros((h, w), np.uint8)
    cx = w // 2
    if produto == "pote":            # pote com tampa (o caso do vídeo): corpo arredondado + tampa + rótulo
        cv2.rectangle(m, (cx - 120, 250), (cx + 120, 600), 1, -1)
        for x in (cx - 80, cx + 80):
            cv2.circle(m, (x, 290), 40, 1, -1)
            cv2.circle(m, (x, 560), 40, 1, -1)
        cv2.rectangle(m, (cx - 100, 160), (cx + 100, 260), 1, -1)
        cor = np.zeros((h, w, 3), np.uint8)
        cor[:] = (200, 120, 40)                                    # azul (BGR)
        cor[:300] = (170, 60, 230)                                 # tampa rosa
        cv2.putText(cor, "UP2U", (cx - 105, 450), cv2.FONT_HERSHEY_DUPLEX, 2.2, (255, 255, 255), 6)
        cv2.rectangle(cor, (cx - 120, 330), (cx + 120, 345), (40, 200, 250), -1)
    elif produto == "frasco":        # frasco escuro com bico (cosmético)
        cv2.ellipse(m, (cx, 420), (110, 200), 0, 0, 360, 1, -1)
        cv2.rectangle(m, (cx - 30, 150), (cx + 30, 240), 1, -1)
        cor = np.zeros((h, w, 3), np.uint8)
        cor[:] = (40, 45, 60)
        cv2.rectangle(cor, (cx - 70, 380), (cx + 70, 470), (210, 210, 215), -1)
    elif produto == "caneca":        # caneca com alça (o buraco da alça tem de continuar transparente)
        cv2.rectangle(m, (cx - 150, 220), (cx + 90, 560), 1, -1)
        cv2.ellipse(m, (cx + 110, 380), (95, 110), 0, 0, 360, 1, 34)
        cor = np.zeros((h, w, 3), np.uint8)
        cor[:] = (60, 170, 240)                                    # laranja
    elif produto == "branco":        # tubo branco em fundo cinza claro (pouco contraste)
        cv2.rectangle(m, (cx - 90, 140), (cx + 90, 600), 1, -1)
        cv2.circle(m, (cx, 600), 90, 1, -1)
        cor = np.zeros((h, w, 3), np.uint8)
        cor[:] = (252, 252, 252)
        cv2.rectangle(cor, (cx - 90, 300), (cx + 90, 330), (80, 60, 200), -1)
        img *= 0.88
    elif produto in ("preto", "cinza"):  # fone/caixinha neutra (preta ou cinza) em fundo branco
        cv2.rectangle(m, (cx - 140, 200), (cx + 140, 520), 1, -1)
        cv2.circle(m, (cx, 200), 60, 1, -1)
        cor = np.zeros((h, w, 3), np.uint8)
        cor[:] = (24, 24, 26) if produto == "preto" else (95, 95, 98)
        cv2.circle(cor, (cx, 360), 60, (70, 70, 72) if produto == "preto" else (200, 200, 200), -1)
    else:
        raise ValueError(produto)
    verdade = m.astype(bool)
    # sombra suave projetada (para baixo e para a direita) + sombra de contato estreita
    sb = np.zeros((h, w), np.float32)
    sb[np.roll(np.roll(verdade, 26, 0), 30, 1)] = 1
    sb = cv2.GaussianBlur(sb, (0, 0), 18) * sombra
    ys = np.nonzero(verdade)[0]
    cont = np.zeros((h, w), np.float32)
    cv2.ellipse(cont, (cx, int(ys.max()) + 4), (130, 12), 0, 0, 360, 1, -1)
    sb = np.maximum(sb, cv2.GaussianBlur(cont, (0, 0), 6) * sombra * 1.2)
    img = img * (1 - np.clip(sb, 0, 0.8))[..., None]
    # sombreamento do próprio produto (volume) e borda anti-serrilhada
    sh = 0.78 + 0.32 * np.cos((xx - cx) / 260)
    prod = np.clip(cor.astype(np.float32) * sh[..., None], 0, 255)
    a = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 0.8)[..., None]
    img = img * (1 - a) + prod * a
    img = img + rng.normal(0, ruido, img.shape)
    return _jpeg(np.clip(img, 0, 255).astype(np.uint8)), verdade


def iou(a: np.ndarray, b: np.ndarray) -> float:
    return float((a & b).sum() / max((a | b).sum(), 1))


class MotorOpenCV(unittest.TestCase):
    """Sem rede e sem modelo: o fallback próprio tem de recortar foto de estúdio com precisão."""

    def checa(self, produto: str, minimo: float, **kw):
        img, verdade = foto_estudio(produto, **kw)
        a, motor = recorte.alfa(img, "opencv")
        self.assertEqual(motor, "opencv")
        v = iou(a > 0.5, verdade)
        self.assertGreater(v, minimo, f"{produto}: IoU {v:.3f}")
        return a, img, verdade

    def test_pote_com_sombra_e_degrade(self):
        self.checa("pote", 0.97)

    def test_frasco_escuro_em_fundo_bege(self):
        self.checa("frasco", 0.97, fundo=(190, 215, 232), degrade=30)

    def test_caneca_mantem_o_buraco_da_alca(self):
        a, _, verdade = self.checa("caneca", 0.95)
        cx = 540 // 2
        self.assertLess(a[380, cx + 110], 0.1, "o buraco da alça foi preenchido")

    def test_produto_branco_em_fundo_claro(self):
        self.checa("branco", 0.93, sombra=0.3)

    def test_produto_preto_e_cinza_neutros_em_fundo_branco(self):
        """Neutro escuro parece "sombra" pela cor: tem de continuar sendo produto."""
        self.checa("preto", 0.97)
        self.checa("cinza", 0.95)

    def test_sombra_forte_nao_entra_no_recorte(self):
        a, _, verdade = self.checa("pote", 0.96, sombra=0.7)
        sombra = np.roll(np.roll(verdade, 26, 0), 30, 1) & ~cv2.dilate(verdade.astype(np.uint8), np.ones((9, 9))).astype(bool)
        self.assertLess(float((a[sombra] > 0.5).mean()), 0.03, "a sombra foi recortada junto")

    def test_borda_sem_halo_do_fundo(self):
        """Na borda (alfa intermediário) a cor tem de ser a do produto, não um rosa lavado de branco."""
        img, verdade = foto_estudio("caneca", fundo=(250, 250, 250), sombra=0.0)
        a, _ = recorte.alfa(img, "opencv")
        cor = recorte.descontamina(img, a).astype(np.float32)
        borda = (a > 0.15) & (a < 0.85)
        self.assertGreater(borda.sum(), 50)
        laranja = np.array((60, 170, 240), np.float32)
        d_cor = np.linalg.norm(cor[borda] - laranja, axis=1).mean()
        d_orig = np.linalg.norm(img[borda].astype(np.float32) - laranja, axis=1).mean()
        self.assertLess(d_cor, d_orig * 0.75, f"halo: {d_cor:.1f} vs foto {d_orig:.1f}")

    def test_borda_suave_mas_curta(self):
        a, _, _ = self.checa("pote", 0.97)
        meio = ((a > 0.05) & (a < 0.95)).sum()
        contorno = cv2.findContours((a > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
        perim = sum(len(c) for c in contorno)
        self.assertGreater(meio, perim * 0.3, "borda serrilhada (sem anti-serrilhado)")
        self.assertLess(meio, perim * 4.5, "borda borrada demais")

    def test_caixa_limita_a_busca(self):
        """Produto num canto de uma cena maior: com --caixa só ele sai."""
        img, verdade = foto_estudio("pote")
        cena = np.full((900, 1100, 3), 120, np.uint8)
        cv2.circle(cena, (150, 150), 90, (20, 200, 20), -1)       # outro objeto fora da caixa
        cena[100:820, 500:1040] = img
        a, _ = recorte.alfa(cena, "opencv", caixa=(500, 100, 1040, 820))
        self.assertLess(a[150, 150], 0.01)
        self.assertGreater(iou(a[100:820, 500:1040] > 0.5, verdade), 0.96)


class Arquivo(unittest.TestCase):
    def test_png_rgba_justo_e_cli(self):
        img, verdade = foto_estudio("pote")
        with tempfile.TemporaryDirectory() as tmp:
            foto = Path(tmp) / "foto produto ç.jpg"                 # acento no caminho (Windows)
            cv2.imencode(".jpg", img)[1].tofile(str(foto))
            saida = Path(tmp) / "saída.png"
            proc = subprocess.run([sys.executable, str(util.SCRIPTS / "recorte.py"), str(foto), str(saida),
                                   "--motor", "opencv", "--margem", "4"],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            info = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(info["motor"], "opencv")
            png = cv2.imdecode(np.fromfile(str(saida), np.uint8), cv2.IMREAD_UNCHANGED)
            self.assertEqual(png.shape[2], 4)
            ys, xs = np.nonzero(verdade)
            esperado = (xs.max() - xs.min() + 1 + 8, ys.max() - ys.min() + 1 + 8)
            self.assertLessEqual(abs(png.shape[1] - esperado[0]), 8, (png.shape, esperado))
            self.assertLessEqual(abs(png.shape[0] - esperado[1]), 8, (png.shape, esperado))
            self.assertEqual(int(png[0, 0, 3]), 0)                  # canto transparente
            self.assertEqual(int(png[png.shape[0] // 2, png.shape[1] // 2, 3]), 255)
            self.assertRegex(info["cor_borda"], r"^#[0-9a-f]{6}$")

    def test_motor_ausente_cai_no_proximo(self):
        """auto nunca falha por falta de rembg/modelo: o OpenCV está sempre lá."""
        self.assertIn("opencv", recorte.disponiveis())
        img, verdade = foto_estudio("frasco")
        with self.assertRaises(ValueError):
            recorte.alfa(img, "inexistente")


class DadosProduto3D(unittest.TestCase):
    """O motor passa ao template onde está o rosto e a legenda (o objeto não cobre nenhum dos dois)."""

    def test_caixa_do_rosto_ignora_quadros_isolados_e_inclui_a_cabeca(self):
        import motion_dados_produto3d as m
        q = [[0.3, 0.2, 0.6, 0.45] + [0] * 6] * 20 + [None] * 5 + [[0.0, 0.6, 0.2, 0.9] + [0] * 6]
        c = m.caixa_rosto(q)
        self.assertLess(c[1], 0.2)                       # sobe até o topo da cabeça
        self.assertAlmostEqual(c[0], 0.3 - 0.08 * 0.3, places=3)
        self.assertLess(c[3], 0.5)                       # o quadro fora da curva não estica a caixa
        self.assertIsNone(m.caixa_rosto([None, None]))

    def test_enriquecer_poe_rosto_por_quadro_e_legenda(self):
        import motion_dados_produto3d as m
        import motion_dados_visao as mv
        quadros = [[0.3, 0.2, 0.6, 0.45] + [0] * 6] * 6
        orig = mv._cached
        mv._cached = lambda work, key, fn: quadros
        mv_key = mv._key
        mv._key = lambda *a, **k: "x"
        try:
            tl = {"captions": {"cfg": {"y": 1150, "size": 70, "emph_size": 90}, "pages": [{"t0": 0, "t1": 1}]},
                  "motion": [], "graphics": [], "shots": []}
            params: dict = {}
            m.enriquecer("produto3d", params, {}, work=Path("."), tl=tl, aroll=Path("x"), mask=None, t0=0, t1=1,
                         w=1080, h=1920, fps=30, project=Path("."))
            self.assertEqual(len(params["rostos"]), 6)
            self.assertEqual(len(params["rosto"]), 4)
            y0, y1 = params["legenda"]
            self.assertTrue(0.4 < y0 < 1150 / 1920 < y1 < 0.65, params["legenda"])
            outro: dict = {}
            m.enriquecer("objeto3d", outro, {}, work=Path("."), tl=tl, aroll=Path("x"), mask=None, t0=0, t1=1,
                         w=1080, h=1920, fps=30, project=Path("."))
            self.assertEqual(outro, {})
        finally:
            mv._cached, mv._key = orig, mv_key


class Template(unittest.TestCase):
    def test_produto3d_registrado(self):
        import motion
        import plan
        self.assertTrue((util.SK / "assets" / "motion" / "templates" / "produto3d.html").exists())
        self.assertIn("produto3d", motion.WEBGL)
        self.assertEqual(plan.MOTION_DEFAULTS["produto3d"]["layer"], "front")
        html = (util.SK / "assets" / "motion" / "templates" / "produto3d.html").read_text(encoding="utf-8")
        for proibido in ("setTimeout", "requestAnimationFrame", "Math.random", "Date.now"):
            self.assertNotIn(proibido, html, f"{proibido}: o render tem de ser determinístico em t")
        self.assertIn("preserveDrawingBuffer", html)


if __name__ == "__main__":
    unittest.main()
