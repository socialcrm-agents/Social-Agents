"""Imagens por IA: provedores com respostas simuladas (sem rede), troca de provedor, cache e pedidos do projeto.
python -m unittest tests/editor_video/test_imagens.py -v
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

sys.path.insert(0, str(util.SCRIPTS))
import imagens  # noqa: E402

JPG = b"\xff\xd8\xff\xe0" + b"0" * 64


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Provedores(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"EDITOR_IMAGENS_CACHE": str(self.dir / "cache")}, clear=False)
        self.env.start()
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)
        self.urls = []

    def tearDown(self):
        self.env.stop()

    def abrir(self, respostas):
        def fake(req, timeout=None):
            self.urls.append((req.full_url, req.data, dict(req.headers)))
            r = respostas.pop(0)
            if isinstance(r, Exception):
                raise r
            return Resp(r)
        return mock.patch("urllib.request.urlopen", fake)

    def test_sem_chave_usa_o_gratuito_sem_conta(self):
        self.assertEqual(imagens.ordem("auto"), ["pollinations"])
        with self.abrir([JPG]):
            r = imagens.gerar("estúdio bege", self.dir / "a.jpg")
        self.assertEqual(r["provedor"], "pollinations")
        self.assertEqual((self.dir / "a.jpg").read_bytes(), JPG)
        self.assertIn("width=1080&height=1920", self.urls[0][0])
        self.assertIn("sem%20texto", self.urls[0][0], "estilo padrão (sem texto/logo) vai no prompt")

    def test_com_chave_usa_o_gemini_e_le_a_imagem_da_resposta(self):
        os.environ["GEMINI_API_KEY"] = "teste"
        corpo = {"candidates": [{"content": {"parts": [{"text": "ok"}, {"inlineData": {"mimeType": "image/png",
                                                                                         "data": base64.b64encode(JPG).decode()}}]}}]}
        with self.abrir([json.dumps(corpo).encode()]):
            r = imagens.gerar("cozinha clara", self.dir / "b.jpg", "16:9")
        self.assertEqual(r["provedor"], "gemini")
        url, dado, cab = self.urls[0]
        self.assertIn(":generateContent", url)
        self.assertEqual(json.loads(dado)["generationConfig"]["imageConfig"]["aspectRatio"], "16:9")
        self.assertNotIn("teste", url, "a chave vai no cabeçalho, não na URL")
        self.assertEqual(cab.get("X-goog-api-key"), "teste")

    def test_cota_do_gemini_acabou_cai_no_gratuito(self):
        os.environ["GEMINI_API_KEY"] = "teste"
        erro = urllib.error.HTTPError("u", 429, "cota", {}, io.BytesIO(b"RESOURCE_EXHAUSTED"))
        with self.abrir([erro, JPG]):
            r = imagens.gerar("academia", self.dir / "c.jpg")
        self.assertEqual(r["provedor"], "pollinations")

    def test_resposta_que_nao_e_imagem_e_tudo_falhando_vira_erro_claro(self):
        with self.abrir([b"<html>fila cheia</html>"]):
            with self.assertRaises(imagens.SemImagem) as c:
                imagens.gerar("praia", self.dir / "d.jpg")
        self.assertIn("pollinations", str(c.exception))

    def test_mesmo_pedido_vem_do_cache_sem_rede(self):
        with self.abrir([JPG]):
            imagens.gerar("palco com luzes", self.dir / "e.jpg", semente=3)
        with self.abrir([]):                                  # nenhuma resposta disponível: se chamar a rede, quebra
            r = imagens.gerar("palco com luzes", self.dir / "f.jpg", semente=3)
        self.assertTrue(r["cache"])
        self.assertEqual((self.dir / "f.jpg").read_bytes(), JPG)


class AtenderPedidos(unittest.TestCase):
    def test_gera_os_cenarios_do_projeto_e_devolve_o_comando_de_encaixe(self):
        proj = util.preparar("semcortes")
        (proj / "qa").mkdir(exist_ok=True)
        (proj / "qa" / "pedidos-de-midia.json").write_text(json.dumps([
            {"tipo": "cenario", "t": 3.2, "palavra": "escritório", "trecho": "...", "query": "escritório moderno"},
            {"tipo": "ferramenta", "t": 5.0, "palavra": "Canva", "trecho": "...", "nome": "Canva"},
        ]), encoding="utf-8")
        with mock.patch.dict(os.environ, {"EDITOR_IMAGENS_CACHE": tempfile.mkdtemp()}), \
                mock.patch.object(imagens, "_pollinations", return_value=JPG):
            os.environ.pop("GEMINI_API_KEY", None)
            r = imagens.atender(proj)
        self.assertEqual(len(r), 1, "só cenários viram imagem gerada (ferramenta = print/gravação real)")
        self.assertTrue(Path(r[0]["arquivo"]).exists())
        flag, mo = r[0]["encaixe"]
        self.assertEqual(flag, "--motion")
        self.assertEqual(json.loads(mo)["template"], "cenario")
        self.assertTrue((proj / "qa" / "imagens-geradas.json").exists())


if __name__ == "__main__":
    unittest.main()
