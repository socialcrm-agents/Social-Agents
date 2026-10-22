"""Cliente mínimo da WhatsApp Cloud API (Graph API da Meta): baixar mídia, enviar texto e vídeo.

Só biblioteca padrão. Erros viram WhatsAppError com o corpo da resposta da Meta.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import config


class WhatsAppError(RuntimeError):
    pass


def _url(path: str) -> str:
    return f"{config.WA_API}/{config.WA_VERSION}/{path.lstrip('/')}"


def _req(method: str, url: str, body: bytes | None = None, headers: dict | None = None, timeout: int = 60):
    h = {"Authorization": f"Bearer {config.WA_TOKEN}", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers
    except urllib.error.HTTPError as exc:
        raise WhatsAppError(f"{method} {url} -> {exc.code}: {exc.read()[:500]!r}") from exc
    except urllib.error.URLError as exc:
        raise WhatsAppError(f"{method} {url} -> {exc.reason}") from exc


def _json(method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    data, _ = _req(method, _url(path), body, {"Content-Type": "application/json"} if body else None)
    return json.loads(data or b"{}")


def baixar_midia(media_id: str, destino: Path) -> Path:
    """GET /{media-id} devolve a URL temporária; o download também exige o token."""
    info = _json("GET", media_id)
    if int(info.get("file_size") or 0) > config.MAX_RECV_MB * 1e6:
        raise WhatsAppError(f"vídeo de {int(info['file_size']) / 1e6:.0f} MB (máximo {config.MAX_RECV_MB:.0f} MB)")
    data, _ = _req("GET", info["url"], timeout=300)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)
    return destino


def subir_midia(arquivo: Path) -> str:
    """POST /{phone-id}/media (multipart). Devolve o media id para usar no envio."""
    mime = mimetypes.guess_type(arquivo.name)[0] or "video/mp4"
    b = uuid.uuid4().hex
    parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"messaging_product\"\r\n\r\nwhatsapp\r\n".encode(),
             f"--{b}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{mime}\r\n".encode(),
             f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{arquivo.name}\"\r\n"
             f"Content-Type: {mime}\r\n\r\n".encode(), arquivo.read_bytes(), f"\r\n--{b}--\r\n".encode()]
    data, _ = _req("POST", _url(f"{config.WA_PHONE_ID}/media"), b"".join(parts),
                   {"Content-Type": f"multipart/form-data; boundary={b}"}, timeout=300)
    return json.loads(data)["id"]


def enviar_texto(tel: str, texto: str) -> dict:
    return _json("POST", f"{config.WA_PHONE_ID}/messages", {
        "messaging_product": "whatsapp", "to": tel, "type": "text", "text": {"body": texto[:4096]}})


def enviar_video(tel: str, arquivo: Path, legenda: str = "") -> dict:
    mid = subir_midia(arquivo)
    return _json("POST", f"{config.WA_PHONE_ID}/messages", {
        "messaging_product": "whatsapp", "to": tel, "type": "video",
        "video": {"id": mid, "caption": legenda[:1024]}})
