#!/usr/bin/env python3
"""Worker: pega um job por vez da fila e roda o editor (skill editor-video) de verdade.

  python3 worker.py            roda para sempre (um job por vez: o render já usa todos os núcleos)
  python3 worker.py --uma-vez  processa o que estiver na fila e sai (testes, cron)

Vídeo novo: run.py new -> transcribe -> analyze -> cérebro (Claude) -> edit.py --no-render -> run.py render
            -> comprime para o WhatsApp (< 15 MB) -> envia o vídeo e um resumo.
Link:       Drive/Dropbox/.mp4 no texto -> baixa (drive.py da skill) -> mesmo caminho do vídeo novo; vídeo longo
            (> 3 min) volta por link (PUBLIC_URL) ou como documento (até 100 MB).
Correção:   cérebro (ou regras) -> edit.py (renderiza a próxima versão) -> comprime -> envia.
"""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import cerebro
import config
import fila
import whatsapp_api as wa

PY = sys.executable


def sh(script: str, *args: str) -> str:
    proc = subprocess.run([PY, str(config.SCRIPTS / script), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{script} falhou:\n{(proc.stderr or proc.stdout)[-1500:]}")
    return proc.stdout


def ultimo_render(projeto: Path) -> Path:
    vids = sorted((projeto / "renders").glob("v*_*.mp4"), key=lambda p: p.stat().st_mtime)
    if not vids:
        raise RuntimeError("render não gerou vídeo")
    return vids[-1]


def duracao(arq: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def comprimir(src: Path, dst: Path, max_mb: float = config.MAX_SEND_MB) -> Path:
    """H.264 Main sem B-frames + AAC + faststart (o que o WhatsApp exige). Até 3 tentativas de bitrate."""
    dur = max(duracao(src), 1.0)
    limite = max_mb * 8e6 * 0.94  # bits, com margem para o contêiner
    audio = 128_000
    for k, fator in enumerate((1.0, 0.8, 0.6)):
        video = min(int((limite / dur - audio) * fator), 8_000_000)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(src), "-c:v", "libx264", "-profile:v", "main",
                        "-bf", "0", "-preset", "veryfast", "-b:v", str(video), "-maxrate", str(int(video * 1.3)),
                        "-bufsize", str(video * 2), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", str(audio), "-ac", "2",
                        "-movflags", "+faststart", str(dst)], check=True)
        if dst.stat().st_size <= max_mb * 1e6:
            return dst
    return dst  # ainda grande: o envio cai para link


def entregar(tel: str, arquivo: Path, legenda: str, original: Path | None = None) -> None:
    """Curto: vídeo (16 MB). Longo: link para o arquivo em qualidade cheia (PUBLIC_URL) ou documento (100 MB)."""
    if original is not None:
        if config.PUBLIC_URL:
            wa.enviar_texto(tel, f"{legenda}\n\nSeu vídeo editado (qualidade cheia): "
                                 f"{config.PUBLIC_URL.rstrip('/')}/v/{original.parent.parent.name}/{original.name}")
        elif arquivo.stat().st_size <= config.MAX_DOC_MB * 1e6:
            wa.enviar_documento(tel, arquivo, legenda)
        else:
            raise RuntimeError("vídeo longo passou de 95 MB e PUBLIC_URL não está configurado")
        return
    if arquivo.stat().st_size <= config.MAX_SEND_MB * 1e6:
        wa.enviar_video(tel, arquivo, legenda)
    elif config.PUBLIC_URL:
        wa.enviar_texto(tel, f"{legenda}\n\nO vídeo ficou grande para o WhatsApp, baixe aqui: "
                             f"{config.PUBLIC_URL.rstrip('/')}/v/{arquivo.parent.parent.name}/{arquivo.name}")
    else:
        raise RuntimeError("vídeo passou de 15 MB e PUBLIC_URL não está configurado")


def resumo_takes(projeto: Path) -> str:
    edl = json.loads((projeto / "edl.json").read_text()) if (projeto / "edl.json").exists() else {}
    bruto, final = edl.get("raw_duration"), edl.get("edit_duration")
    return f"{bruto:.0f}s → {final:.0f}s" if bruto and final else ""


def job_novo(job) -> tuple[Path, str]:
    tel = job["telefone"]
    est = fila.cliente(tel)["estilo"] or config.DEFAULT_STYLE
    # nome aleatório: a pasta vira parte do link de download, então não pode expor o telefone do cliente
    projeto = config.DATA / "projetos" / secrets.token_urlsafe(16)
    entrada = job["entrada"]
    if config.achar_link(entrada or "") == entrada:  # veio por link: baixa antes (LinkError avisa o cliente)
        entrada = str(config.baixar(entrada, config.DATA / "entrada" / f"link_{job['id']}",
                                    max_mb=config.MAX_LINK_MB, progresso=False))
    sh("run.py", "new", str(projeto), "--clips", entrada, "--style", est, "--force")
    sh("transcribe.py", str(projeto))
    sh("analyze.py", str(projeto))
    ops = cerebro.decidir((projeto / "transcript.txt").read_text(encoding="utf-8"),
                          (projeto / "qa" / "takes.md").read_text(encoding="utf-8")
                          if (projeto / "qa" / "takes.md").exists() else "", est, job["id"])
    resumo = ""
    if ops:
        args = cerebro.para_argumentos(ops)
        if args:
            sh("edit.py", str(projeto), *args, "--note", "cérebro (Claude API)", "--no-render")
        resumo = ops.get("resumo", "")
    sh("run.py", "render", str(projeto))
    fila.concluir(job["id"], projeto=str(projeto))
    tempo = resumo_takes(projeto)
    legenda = (f"Pronto! ✂️ {tempo}\n{resumo}\n\nQuer mudar algo? Responde aqui em texto: "
               f"\"legenda maior\", \"tira o começo\", \"estilo premium\"...").replace("\n\n\n", "\n\n")
    return ultimo_render(projeto), legenda


def job_correcao(job) -> tuple[Path, str]:
    projeto = Path(job["projeto"])
    proj = json.loads((projeto / "project.json").read_text(encoding="utf-8"))
    ops = cerebro.corrigir(job["pedido"], proj.get("overrides", {}),
                           (projeto / "transcript.txt").read_text(encoding="utf-8"), job["id"])
    if not ops:
        raise PedidoNaoEntendido(job["pedido"])
    sh("edit.py", str(projeto), *cerebro.para_argumentos(ops), "--note", job["pedido"])
    return ultimo_render(projeto), f"Ajustado ✅ {ops.get('resumo', '')}".strip()


class PedidoNaoEntendido(Exception):
    pass


def processar(job) -> None:
    t = time.time()
    tel = job["telefone"]
    try:
        out, legenda = (job_novo if job["tipo"] == "novo" else job_correcao)(job)
        envio = out.with_name(out.stem + "_whatsapp.mp4")
        longo = duracao(out) > config.LONGO_S
        if longo and config.PUBLIC_URL:
            envio = out  # vai por link, sem recomprimir
        else:
            comprimir(out, envio, config.MAX_DOC_MB if longo else config.MAX_SEND_MB)
        entregar(tel, envio, legenda, original=out if longo else None)
        fila.concluir(job["id"], status="ok", saida=str(envio), segundos=round(time.time() - t, 1))
        print(f"OK job {job['id']} ({job['tipo']}) em {time.time() - t:.0f}s: {envio.stat().st_size / 1e6:.1f} MB", flush=True)
    except config.LinkError as exc:  # link privado, de pasta ou quebrado: não adianta tentar de novo
        fila.concluir(job["id"], status="erro", erro=f"link: {exc}")
        fila.add_creditos(tel, 1)
        wa.enviar_texto(tel, f"Não consegui baixar o vídeo do link 😕\n\n{exc}")
    except PedidoNaoEntendido:
        fila.concluir(job["id"], status="erro", erro="pedido não entendido")
        wa.enviar_texto(tel, "Não entendi o ajuste 🤔 Tenta assim: \"legenda maior\", \"sem zoom\", "
                             "\"tira 'então' do começo\", \"estilo premium\" ou \"gancho: 'SEU TEXTO'\".")
    except Exception as exc:  # noqa: BLE001 - qualquer falha do pipeline volta para a fila uma vez
        traceback.print_exc()
        if not fila.falhou(job, f"{exc}"):
            wa.enviar_texto(tel, "Não consegui editar esse vídeo 😕 Seu crédito foi devolvido. "
                                 "Tente um vídeo com você falando para a câmera (até 3 min aqui no chat; "
                                 "mais longo, mande o link do Google Drive).")


def limpar_antigos() -> None:
    """Privacidade: apaga projetos e vídeos com mais de KEEP_DAYS dias."""
    base = config.DATA / "projetos"
    if not base.exists():
        return
    limite = time.time() - config.KEEP_DAYS * 86400
    for p in base.iterdir():
        if p.is_dir() and p.stat().st_mtime < limite:
            shutil.rmtree(p, ignore_errors=True)
    for p in (config.DATA / "entrada").glob("*"):
        if p.stat().st_mtime < limite:
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


def main() -> None:
    uma = "--uma-vez" in sys.argv
    ultima_limpeza = 0.0
    while True:
        if time.time() - ultima_limpeza > 3600:
            limpar_antigos()
            ultima_limpeza = time.time()
        job = fila.pegar_proximo()
        if job:
            processar(job)
            continue
        if uma:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
