#!/usr/bin/env python3
"""Imagens geradas por IA para o vídeo (fundos, cenários, ilustrações de B-roll) — sem custo por padrão.

Provedores (o primeiro disponível vence com --provedor auto):
  gemini        Nano Banana (modelo de imagem do Gemini) pela API do Google AI Studio. Precisa de uma chave grátis
                em aistudio.google.com (variável GEMINI_API_KEY). A cota grátis é do Google e muda; se acabar ou não
                cobrir imagem, o auto passa para o próximo.
  pollinations  Flux pelo pollinations.ai: grátis e sem conta (tem fila e limite de uso). Padrão sem chave.

  python imagens.py gerar "<prompt>" saida.jpg [--formato 9:16] [--provedor auto|gemini|pollinations] [--semente 7]
  python imagens.py atender <projeto> [--provedor ...]   gera as imagens de qa/pedidos-de-midia.json (cenário,
                                                         cena da profissão) em <projeto>/midia/ e escreve
                                                         qa/imagens-geradas.json com o comando de encaixe
  python imagens.py status                               qual provedor está ativo

Mesma imagem pedida de novo (prompt + formato + semente) vem do cache (~/.cache/editor-video/imagens).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TAMANHOS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
ESTILO = ("foto realista, luz natural suave, profundidade de campo, cores ricas, alta definição, "
          "sem texto, sem letras, sem logotipos, sem marca d'água")
GEMINI_MODELO = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
TIMEOUT = 120


class SemImagem(Exception):
    pass


def cache_dir() -> Path:
    return Path(os.environ.get("EDITOR_IMAGENS_CACHE", Path.home() / ".cache" / "editor-video" / "imagens"))


def _http(req: urllib.request.Request) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        raise SemImagem(f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SemImagem(f"sem conexão: {exc}") from exc


def _gemini(prompt: str, formato: str, semente: int | None) -> bytes:
    chave = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not chave:
        raise SemImagem("GEMINI_API_KEY não definida")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODELO}:generateContent"
    corpo = {"contents": [{"parts": [{"text": f"{prompt}. Formato {formato}."}]}],
             "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": formato}}}
    if semente is not None:
        corpo["generationConfig"]["seed"] = semente
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": chave})
    d = json.loads(_http(req))
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            dado = p.get("inlineData") or p.get("inline_data")
            if dado and dado.get("data"):
                return base64.b64decode(dado["data"])
    raise SemImagem(f"o Gemini não devolveu imagem: {json.dumps(d)[:300]}")


def _pollinations(prompt: str, formato: str, semente: int | None) -> bytes:
    w, h = TAMANHOS.get(formato, TAMANHOS["9:16"])
    q = {"width": w, "height": h, "nologo": "true", "model": "flux", "seed": semente if semente is not None else 7}
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?{urllib.parse.urlencode(q)}"
    dado = _http(urllib.request.Request(url, headers={"User-Agent": "editor-viral/1.0"}))
    if not dado.startswith((b"\xff\xd8", b"\x89PNG", b"RIFF")):
        raise SemImagem(f"resposta não é imagem: {dado[:120]!r}")
    return dado


PROVEDORES = ("gemini", "pollinations")


def ordem(provedor: str) -> list[str]:
    if provedor != "auto":
        return [provedor]
    return (["gemini"] if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") else []) + ["pollinations"]


def gerar(prompt: str, saida: Path, formato: str = "9:16", provedor: str = "auto", semente: int | None = None,
          estilo: bool = True) -> dict:
    """Gera (ou pega do cache) e grava em `saida`. Devolve {arquivo, provedor, cache, prompt}."""
    texto = f"{prompt}, {ESTILO}" if estilo else prompt
    chave = hashlib.sha1(json.dumps([texto, formato, semente]).encode()).hexdigest()[:16]
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    for c in sorted(cache_dir().glob(f"{chave}.*")):
        shutil.copy2(c, saida)
        return {"arquivo": str(saida), "provedor": c.suffix.lstrip(".").split("_")[0] or "cache", "cache": True, "prompt": texto}
    erros = []
    for nome in ordem(provedor):
        try:
            dado = globals()[f"_{nome}"](texto, formato, semente)
        except SemImagem as exc:
            erros.append(f"{nome}: {exc}")
            continue
        saida.write_bytes(dado)
        cache_dir().mkdir(parents=True, exist_ok=True)
        (cache_dir() / f"{chave}.{nome}").write_bytes(dado)
        return {"arquivo": str(saida), "provedor": nome, "cache": False, "prompt": texto}
    raise SemImagem("nenhum provedor gerou a imagem — " + " | ".join(erros))


def atender(projeto: Path, provedor: str = "auto") -> list[dict]:
    """Gera as imagens dos pedidos de cenário do projeto e diz como encaixar (o diretor decide se encaixa)."""
    pedidos = json.loads((projeto / "qa" / "pedidos-de-midia.json").read_text(encoding="utf-8"))
    pj = json.loads((projeto / "project.json").read_text(encoding="utf-8"))
    formato = (pj.get("overrides") or {}).get("format") or pj.get("format") or "9:16"
    feitos = []
    for r in pedidos:
        if r["tipo"] not in ("cenario", "cena_profissao") or not r.get("query") or r["query"] == "cenário citado na fala":
            continue
        nome = f"{r['tipo']}_{r['t']:05.1f}s.jpg".replace(" ", "")
        try:
            g = gerar(f"{r['query']}, ambiente vazio sem pessoas, enquadramento vertical para fundo de vídeo",
                      projeto / "midia" / nome, formato, provedor)
        except SemImagem as exc:
            feitos.append({**r, "erro": str(exc)})
            continue
        cena = {"template": "cenario", "at": r["palavra"], "dur": 4,
                "params": {"scenes": [{"image": g["arquivo"], "label": ""}]}}
        feitos.append({**r, **g, "encaixe": ["--motion", json.dumps(cena, ensure_ascii=False)]})
    (projeto / "qa" / "imagens-geradas.json").write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
    return feitos


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Imagens por IA para o vídeo (grátis por padrão)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("gerar"); s.add_argument("prompt"); s.add_argument("saida")
    s.add_argument("--formato", default="9:16", choices=list(TAMANHOS)); s.add_argument("--semente", type=int)
    s.add_argument("--provedor", default="auto", choices=["auto", *PROVEDORES]); s.add_argument("--sem-estilo", action="store_true")
    s = sub.add_parser("atender"); s.add_argument("projeto"); s.add_argument("--provedor", default="auto", choices=["auto", *PROVEDORES])
    sub.add_parser("status")
    a = ap.parse_args()
    try:
        if a.cmd == "gerar":
            print(json.dumps(gerar(a.prompt, Path(a.saida), a.formato, a.provedor, a.semente, not a.sem_estilo), ensure_ascii=False))
        elif a.cmd == "atender":
            r = atender(Path(a.projeto), a.provedor)
            print(json.dumps([{k: x.get(k) for k in ("t", "tipo", "arquivo", "provedor", "erro")} for x in r], ensure_ascii=False, indent=1))
        else:
            print(f"provedores na ordem: {' -> '.join(ordem('auto'))}  cache: {cache_dir()}")
    except SemImagem as exc:
        print(f"ERRO: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
