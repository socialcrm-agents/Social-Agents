#!/usr/bin/env python3
"""Teste ponta a ponta sem credenciais: Graph API falsa + webhook + worker de verdade.

  python3 teste_local.py <video.mp4> [pasta_de_dados]

1. sobe uma Graph API falsa (serve o vídeo, aceita upload e registra as mensagens enviadas);
2. simula a Meta chamando o webhook com o vídeo -> job na fila;
3. roda o worker (pipeline real do editor-video; sem ANTHROPIC_API_KEY o cérebro fica de fora);
4. confere que o vídeo enviado tem < 15 MB;
5. simula a correção por texto "legenda maior" e confere a segunda entrega.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VIDEO = Path(sys.argv[1]).resolve()
DATA = Path(sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="wa-teste-"))
ENVIADOS: list[dict] = []
UPLOADS: list[int] = []


class FakeGraph(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, ctype="application/json"):
        data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        assert self.headers.get("Authorization") == "Bearer token-teste", "sem token"
        if self.path.startswith("/download/"):
            return self._send(VIDEO.read_bytes(), "video/mp4")
        mid = self.path.rsplit("/", 1)[-1]
        port = self.server.server_address[1]
        self._send({"url": f"http://127.0.0.1:{port}/download/{mid}", "file_size": VIDEO.stat().st_size,
                    "mime_type": "video/mp4", "id": mid})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path.endswith("/media"):
            UPLOADS.append(len(body))
            return self._send({"id": f"midia-{len(UPLOADS)}"})
        ENVIADOS.append(json.loads(body))
        self._send({"messages": [{"id": f"wamid.{len(ENVIADOS)}"}]})


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeGraph)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ.update(WA_TOKEN="token-teste", WA_PHONE_NUMBER_ID="123", WA_VERIFY_TOKEN="verifica",
                      WA_API_BASE=f"http://127.0.0.1:{srv.server_address[1]}", EDITOR_DATA_DIR=str(DATA))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fastapi.testclient import TestClient

    import app as webapp
    import worker

    cli = TestClient(webapp.app)
    r = cli.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "42"})
    assert r.text == "42", r.text
    tel = "5511999990000"

    def webhook(msg):
        payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [
            {"from": tel, "id": "wamid.in", "timestamp": str(int(time.time())), **msg}]}}]}]}
        assert cli.post("/webhook", json=payload).status_code == 200

    def tipos():
        return [m["type"] for m in ENVIADOS]

    # 1) vídeo novo
    t = time.time()
    webhook({"type": "video", "video": {"id": "MID1", "mime_type": "video/mp4"}})
    assert tipos() == ["text"], tipos()  # "Recebi! Editando..."
    worker.main.__globals__["sys"].argv = ["worker.py", "--uma-vez"]
    worker.main()
    t1 = time.time() - t
    assert "video" in tipos(), f"vídeo não enviado: {ENVIADOS}"
    import fila
    job = fila.job()
    saida = Path(job["saida"])
    mb = saida.stat().st_size / 1e6
    assert mb < 15, f"vídeo com {mb:.1f} MB"
    print(f"[1] vídeo novo: {t1:.0f}s, enviado {mb:.1f} MB, legenda: {ENVIADOS[-1]['video']['caption'][:80]!r}")

    # 2) correção por texto (sem cérebro: regras)
    n = len(ENVIADOS)
    t = time.time()
    webhook({"type": "text", "text": {"body": "deixa a legenda maior"}})
    worker.main()
    t2 = time.time() - t
    novos = [m["type"] for m in ENVIADOS[n:]]
    assert novos == ["text", "video"], novos
    proj = json.loads((Path(job["projeto"]) / "project.json").read_text())
    assert proj["overrides"]["caption"], proj["overrides"]
    job2 = fila.job()
    print(f"[2] correção 'legenda maior': {t2:.0f}s, {Path(job2['saida']).stat().st_size / 1e6:.1f} MB, "
          f"overrides.caption={proj['overrides']['caption']}")

    # 3) comandos e pedido não entendido
    n = len(ENVIADOS)
    webhook({"type": "text", "text": {"body": "saldo"}})
    webhook({"type": "text", "text": {"body": "faz chover confete roxo"}})
    worker.main()
    print(f"[3] saldo -> {ENVIADOS[n]['text']['body']!r}; pedido estranho -> {ENVIADOS[-1]['text']['body'][:60]!r}")
    print("RELATÓRIO", fila.relatorio())
    print("TESTE OK")
    srv.shutdown()


if __name__ == "__main__":
    main()
