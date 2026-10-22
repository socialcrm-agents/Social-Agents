#!/usr/bin/env python3
"""Baixa vídeo por link (Google Drive, Dropbox ou link direto). Só biblioteca padrão.

  drive.py <link> [pasta_destino]      baixa e imprime o caminho do arquivo

Uso em Python:
  from drive import baixar, achar_link, eh_link
  arquivo = baixar("https://drive.google.com/file/d/<id>/view?usp=sharing", Path("fontes"))

Vídeo longo (VSL de 30 min, aula, live) não passa no upload do chat nem no WhatsApp: a pessoa sobe no Google
Drive, compartilha como "Qualquer pessoa com o link → Leitor" e manda o link.
"""

from __future__ import annotations

import html
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
DRIVE_DL = "https://drive.usercontent.google.com/download"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}

COMO_LIBERAR = (
    "O link do Google Drive está privado. Para liberar:\n"
    "  • No celular: abra o vídeo no app Drive → ⋮ → Compartilhar → Acesso geral → "
    "\"Qualquer pessoa com o link\" (Leitor) → copie o link.\n"
    "  • No computador: clique com o botão direito no vídeo → Compartilhar → Acesso geral → "
    "\"Qualquer pessoa com o link\" → Leitor → Copiar link.\n"
    "Depois mande o link de novo."
)


class LinkError(RuntimeError):
    """Erro com mensagem pronta para mostrar ao cliente (pt-BR)."""


def eh_link(texto: str) -> bool:
    return bool(re.match(r"https?://", str(texto).strip(), re.I))


def achar_link(texto: str) -> str | None:
    """Primeiro link http(s) de uma mensagem (ex.: texto do WhatsApp)."""
    m = re.search(r"https?://[^\s<>\"']+", texto or "")
    return m.group(0).rstrip(").,;!?") if m else None


def drive_id(url: str) -> str | None:
    u = urllib.parse.urlparse(url)
    if not re.search(r"(^|\.)(drive|docs)\.google\.com$|drive\.usercontent\.google\.com$", u.netloc):
        return None
    if "/folders/" in u.path or "/drive/folders" in u.path:
        raise LinkError("Esse link é de uma PASTA do Drive. Abra a pasta, compartilhe o arquivo do vídeo e mande o "
                        "link dele (Compartilhar → Copiar link).")
    m = re.search(r"/file/d/([A-Za-z0-9_-]{10,})", u.path)
    if m:
        return m.group(1)
    q = urllib.parse.parse_qs(u.query)
    if q.get("id"):
        return q["id"][0]
    return None


def _ssl_ctx() -> ssl.SSLContext:
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "CURL_CA_BUNDLE"):
        f = os.environ.get(var)
        if f and Path(f).exists():
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(f)  # soma ao repositório padrão (proxy corporativo)
            return ctx
    return ssl.create_default_context()


def _abrir(url: str, cookies: dict | None = None):
    headers = {"User-Agent": UA}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = urllib.request.Request(url, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=60, context=_ssl_ctx())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise LinkError(COMO_LIBERAR if "google" in url else f"O link pediu login ou foi negado ({e.code}).")
        if e.code == 404:
            raise LinkError("Link não encontrado (404). Confira se copiou o link inteiro e se o arquivo não foi "
                            "apagado.")
        raise LinkError(f"O servidor do link respondeu erro {e.code}. Tente de novo em alguns minutos.")
    except urllib.error.URLError as e:
        raise LinkError(f"Não consegui acessar o link ({e.reason}).")


def _cookies(resp) -> dict:
    out = {}
    for c in resp.headers.get_all("Set-Cookie") or []:
        k, _, v = c.split(";", 1)[0].partition("=")
        out[k.strip()] = v.strip()
    return out


def form_confirmacao(pagina: str) -> str | None:
    """Página "não foi possível verificar vírus" do Drive (arquivo grande): monta a URL do botão "Fazer download"."""
    m = re.search(r'<form[^>]*id="download-form"[^>]*action="([^"]+)"(.*?)</form>', pagina, re.S)
    if not m:
        m = re.search(r'<form[^>]*action="(https://drive\.usercontent\.google\.com/download[^"]*)"(.*?)</form>',
                      pagina, re.S)
    if m:
        action, corpo = html.unescape(m.group(1)), m.group(2)
        campos = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', corpo))
        campos.update(re.findall(r'<input[^>]*name="([^"]+)"[^>]*type="hidden"[^>]*value="([^"]*)"', corpo))
        return action + ("&" if "?" in action else "?") + urllib.parse.urlencode(
            {k: html.unescape(v) for k, v in campos.items()})
    m = re.search(r'href="(/uc\?export=download[^"]*confirm=[^"]+)"', pagina)  # formato antigo
    if m:
        return "https://drive.google.com" + html.unescape(m.group(1))
    return None


def pagina_privada(pagina: str) -> bool:
    p = pagina.lower()
    return any(s in p for s in ("accounts.google.com/servicelogin", "servicelogin", "you need access",
                                "você precisa de acesso", "solicitar acesso", "request access",
                                "sign in - google accounts", "fazer login - contas do google"))


def _nome_arquivo(resp, padrao: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)"?', cd)
    nome = urllib.parse.unquote(m.group(1)) if m else padrao
    nome = re.sub(r"[^\w.\- ]+", "_", nome).strip() or padrao
    return nome if Path(nome).suffix else nome + ".mp4"


def normalizar(url: str) -> tuple[str, str]:
    """(url de download, nome padrão)."""
    url = url.strip()
    fid = drive_id(url)
    if fid:
        return f"{DRIVE_DL}?id={fid}&export=download&confirm=t", f"drive_{fid[:10]}.mp4"
    u = urllib.parse.urlparse(url)
    if u.netloc.endswith("dropbox.com"):
        q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
        q["dl"] = ["1"]
        url = urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q, doseq=True)))
        return url, Path(u.path).name or "dropbox.mp4"
    return url, Path(u.path).name or "video.mp4"


def baixar(url: str, destino_dir: Path, max_mb: float = 4000, progresso: bool = True) -> Path:
    """Baixa o vídeo do link para destino_dir e devolve o caminho. Levanta LinkError com mensagem para o cliente."""
    if not eh_link(url):
        raise LinkError("Isso não parece um link (tem que começar com http).")
    destino_dir = Path(destino_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)
    dl, padrao = normalizar(url)
    resp = _abrir(dl)
    cookies = _cookies(resp)
    for _ in range(3):  # Drive: até 2 páginas intermediárias (aviso de vírus)
        tipo = resp.headers.get("Content-Type", "")
        if not tipo.startswith("text/html"):
            break
        pagina = resp.read(2_000_000).decode("utf-8", "replace")
        if pagina_privada(pagina) or "accounts.google.com" in resp.geturl():
            raise LinkError(COMO_LIBERAR)
        prox = form_confirmacao(pagina)
        if not prox:
            if "google" in dl:
                raise LinkError(COMO_LIBERAR)
            raise LinkError("Esse link abre uma página, não o arquivo do vídeo. Mande o link do Google Drive "
                            "ou do Dropbox, ou um link que termine em .mp4.")
        resp = _abrir(prox, cookies)
        cookies.update(_cookies(resp))
    else:
        raise LinkError("O Drive não liberou o download. Confira se o link está como \"Qualquer pessoa com o link\".")
    total = int(resp.headers.get("Content-Length") or 0)
    if total and total > max_mb * 1e6:
        raise LinkError(f"O vídeo tem {total / 1e9:.1f} GB; o máximo é {max_mb / 1000:.1f} GB. Exporte em 1080p.")
    nome = _nome_arquivo(resp, padrao)
    if Path(nome).suffix.lower() not in VIDEO_EXT:
        nome = Path(nome).stem + ".mp4"
    alvo = destino_dir / nome
    parcial = alvo.with_suffix(alvo.suffix + ".part")
    feito, marca, t0 = 0, 0.0, time.time()
    with open(parcial, "wb") as f:
        while True:
            bloco = resp.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
            feito += len(bloco)
            if feito > max_mb * 1e6:
                parcial.unlink(missing_ok=True)
                raise LinkError(f"O vídeo passou de {max_mb / 1000:.1f} GB. Exporte em 1080p e mande de novo.")
            if progresso and time.time() - marca > 3:
                marca = time.time()
                pct = f" {100 * feito / total:.0f}%" if total else ""
                print(f"   baixando {nome}:{pct} {feito / 1e6:.0f} MB ({feito / 1e6 / (marca - t0 + 1e-6):.1f} MB/s)",
                      file=sys.stderr, flush=True)
    if feito < 10_000:
        parcial.unlink(missing_ok=True)
        raise LinkError("O arquivo baixado veio vazio. Confira o link e a permissão de compartilhamento.")
    parcial.replace(alvo)
    if progresso:
        print(f"   baixado: {alvo} ({feito / 1e6:.0f} MB em {time.time() - t0:.0f}s)", file=sys.stderr)
    return alvo


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        print(baixar(sys.argv[1], Path(sys.argv[2] if len(sys.argv) > 2 else ".")))
    except LinkError as e:
        sys.exit(f"ERRO: {e}")


if __name__ == "__main__":
    main()
