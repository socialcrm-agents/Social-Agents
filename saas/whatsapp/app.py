"""Webhook do Editor no WhatsApp (WhatsApp Cloud API -> fila).

  uvicorn app:app --host 0.0.0.0 --port 8000      (e rode worker.py em outro processo)

GET  /webhook   verificação da Meta (hub.mode, hub.verify_token, hub.challenge)
POST /webhook   mensagens: vídeo vira job novo; texto vira comando ou correção do último vídeo
GET  /v/...     baixa o vídeo pronto quando ele passa de 15 MB (link enviado no chat)
GET  /saude     status e custo acumulado de IA
"""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

import config
import fila
import whatsapp_api as wa

app = FastAPI(title="Editor no WhatsApp")
APP_SECRET = os.environ.get("WA_APP_SECRET", "")  # assina o POST da Meta (X-Hub-Signature-256)

AJUDA = ("🎬 *Editor de vídeo*\n"
         "1. Me manda um vídeo seu falando (até 3 min).\n"
         "2. Em ~2 min eu devolvo editado: cortes, legenda animada, zoom e efeitos.\n"
         "3. Quer mudar? Responde em texto: \"legenda maior\", \"sem zoom\", \"tira 'então' do começo\".\n\n"
         "Comandos: *estilo viral* | *estilo premium* | *estilo anuncio* | *saldo* | *ajuda*")
ESTILOS = {"viral": "reels_viral", "premium": "editorial_premium", "anuncio": "anuncio_conversao"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().strip())
    return "".join(c for c in s if not unicodedata.combining(c))


@app.get("/webhook")
def verificar(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and config.WA_VERIFY and q.get("hub.verify_token") == config.WA_VERIFY:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "verify token inválido")


@app.post("/webhook")
async def receber(request: Request, tasks: BackgroundTasks):
    body = await request.body()
    if APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        good = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            raise HTTPException(403, "assinatura inválida")
    data = await request.json()
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                tasks.add_task(tratar, msg)  # responde 200 rápido; a Meta reenvia se demorar
    return {"ok": True}


def tratar(msg: dict) -> None:
    tel = msg.get("from", "")
    tipo = msg.get("type")
    c = fila.cliente(tel)
    if tipo == "video" or (tipo == "document" and str(msg["document"].get("mime_type", "")).startswith("video/")):
        media = msg.get("video") or msg.get("document")
        if c["creditos"] <= 0:
            wa.enviar_texto(tel, "Seus créditos acabaram. Para continuar, escolha um plano: <link do checkout>")
            return
        destino = config.DATA / "entrada" / f"{tel}_{media['id']}.mp4"
        try:
            wa.baixar_midia(media["id"], destino)
        except wa.WhatsAppError as exc:
            wa.enviar_texto(tel, f"Não consegui baixar o vídeo ({exc}). Tenta mandar de novo?")
            return
        job = fila.novo_job(tel, "novo", entrada=str(destino))
        if job is None:
            wa.enviar_texto(tel, "Seus créditos acabaram. Para continuar, escolha um plano: <link do checkout>")
            return
        wa.enviar_texto(tel, "Recebi! ✂️ Editando agora, em ~2 minutos te mando o vídeo pronto.")
        return
    if tipo != "text":
        wa.enviar_texto(tel, AJUDA)
        return
    texto = msg["text"]["body"]
    t = _norm(texto)
    if t in ("ajuda", "oi", "ola", "menu", "help"):
        wa.enviar_texto(tel, AJUDA)
    elif t == "saldo":
        wa.enviar_texto(tel, f"Você tem {c['creditos']} vídeo(s) disponível(is). Estilo atual: {c['estilo']}.")
    elif t.startswith("estilo"):
        nome = next((v for k, v in ESTILOS.items() if k in t), None)
        if nome:
            fila.set_estilo(tel, nome)
            wa.enviar_texto(tel, f"Estilo trocado para *{nome.replace('_', ' ')}*. Vale para os próximos vídeos.")
        else:
            wa.enviar_texto(tel, "Estilos: viral, premium, anuncio. Ex.: \"estilo premium\".")
    else:
        projeto = fila.ultimo_projeto(tel)
        if not projeto:
            wa.enviar_texto(tel, AJUDA)
            return
        job = fila.novo_job(tel, "correcao", pedido=texto, projeto=projeto)
        if job is None:
            wa.enviar_texto(tel, f"Esse vídeo já teve {config.FREE_FIXES} ajustes. Manda um vídeo novo quando quiser!")
            return
        wa.enviar_texto(tel, "Beleza, ajustando! Já te mando a nova versão. 🔁")


@app.get("/v/{projeto}/{arquivo}")
def baixar(projeto: str, arquivo: str):
    base = (config.DATA / "projetos").resolve()
    p = (base / projeto / "renders" / arquivo).resolve()
    if not p.is_relative_to(base) or not p.exists() or p.suffix != ".mp4":
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4")


@app.get("/saude")
def saude():
    return {"ok": True, **fila.relatorio()}
