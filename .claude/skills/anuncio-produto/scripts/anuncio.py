#!/usr/bin/env python3
"""Anúncio de produto: fotos (e vídeos) do produto + roteiro + voz -> vídeo de venda 9:16 pronto.

  anuncio.py novo <projeto> --fotos a.jpg b.jpg [--videos v.mp4] --nome "..." [--preco "R$ 129,90"]
             [--preco-antigo "R$ 199,90"] [--desconto 35%] [--parcelas "ou 3x de R$ 43,30"]
             [--estilo tiktok_shop|premium|oferta] [--plataforma tiktok_shop|reels|shorts] [--cor "#hex"]
  anuncio.py recorte <projeto>                  recorta o produto das fotos e tira as cores
  anuncio.py checar <projeto> [--roteiro r.json] confere o roteiro (tamanho x duração, cenas, fotos, preço)
  anuncio.py voz <projeto> [--roteiro r.json]    gera ou alinha a narração
  anuncio.py render <projeto> [--roteiro r.json] [--rascunho]
  anuncio.py tudo <projeto> [--roteiro r.json] [--rascunho]   recorte + checar + voz + render
  anuncio.py versoes <projeto> --roteiros roteiro_15s.json roteiro_30s.json ...
  anuncio.py vozes [--amostras pasta]            lista as vozes (e gera uma amostra de cada)
  anuncio.py estilos
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from common import (DURATIONS, END_CARD, LEAD, STYLES_DIR, VOICES_FILE, WORDS_PER_SECOND, AdError, load_json, log,
                    main_guard, probe, project_paths, save_json)

IMG = {".jpg", ".jpeg", ".png", ".webp"}
VID = {".mp4", ".mov", ".m4v", ".webm"}
SCENES = {"gancho", "heroi", "foto", "detalhe", "beneficios", "comparacao", "prova", "oferta", "cta", "video",
          "galeria", "continua"}


def script_path(project: Path, name: str | None) -> Path:
    p = Path(name or "roteiro.json")
    return p if p.is_absolute() else project / p


def cmd_novo(a) -> None:
    project = Path(a.projeto).resolve()
    paths = project_paths(project)
    if paths["project"].exists() and not a.force:
        raise AdError(f"{paths['project']} já existe (use --force para recriar)")
    fotos = [str(Path(f).expanduser().resolve()) for f in a.fotos]
    for f in fotos:
        if not Path(f).exists() or Path(f).suffix.lower() not in IMG:
            raise AdError(f"Foto inválida: {f} (aceito: {', '.join(sorted(IMG))})")
    videos = [str(Path(v).expanduser().resolve()) for v in (a.videos or [])]
    for v in videos:
        if not Path(v).exists() or Path(v).suffix.lower() not in VID:
            raise AdError(f"Vídeo inválido: {v}")
    if a.estilo and not (STYLES_DIR / f"{a.estilo}.json").exists():
        raise AdError(f"Estilo '{a.estilo}' não existe. Opções: {', '.join(p.stem for p in STYLES_DIR.glob('*.json'))}")
    project.mkdir(parents=True, exist_ok=True)
    save_json(paths["project"], {
        "nome": a.nome, "nome_curto": a.nome_curto or a.nome.split()[0], "preco": a.preco, "preco_antigo": a.preco_antigo,
        "desconto": ("-" + a.desconto.lstrip("-")) if a.desconto else None, "parcelas": a.parcelas, "estilo": a.estilo or "tiktok_shop",
        "plataforma": a.plataforma, "cor": a.cor, "fotos": fotos, "videos": videos,
        "foto_principal": Path(fotos[0]).stem if fotos else None,
    })
    log(f"Projeto criado: {project} ({len(fotos)} foto(s), {len(videos)} vídeo(s), estilo {a.estilo or 'tiktok_shop'})")


def cmd_recorte(a) -> None:
    import recorte
    sys.argv = ["recorte.py", str(Path(a.projeto).resolve())]
    recorte.main()


def check(project: Path, script: Path) -> list[str]:
    """Problemas que impedem ou pioram o anúncio. Lista vazia = pronto para gravar a voz."""
    proj = load_json(project_paths(project)["project"])
    rot = load_json(script)
    if not rot:
        raise AdError(f"{script} não existe. Escreva o roteiro (ver references/roteiros.md).")
    probs = []
    dur = rot.get("duracao")
    if dur not in DURATIONS:
        probs.append(f"duracao {dur}: use uma de {DURATIONS}")
        dur = dur or 20
    falas = rot.get("falas") or []
    if not falas:
        probs.append("roteiro sem falas")
    words = sum(len(f.get("texto", "").split()) for f in falas)
    own = isinstance(rot.get("voz"), dict)
    budget = int((dur - END_CARD - LEAD) * WORDS_PER_SECOND)
    if not own and words > budget * 1.12:
        probs.append(f"{words} palavras para {dur}s (cabem ~{budget}): corte {words - budget}")
    if not own and words < budget * 0.6:
        probs.append(f"só {words} palavras para {dur}s (ideal ~{budget}): o vídeo vai ficar mais curto que {dur}s")
    fotos = {Path(f).stem for f in proj["fotos"]}
    tipos = []
    for i, f in enumerate(falas):
        c = f.get("cena")
        if not c or c == "continua":
            continue
        t = c.get("tipo")
        tipos.append(t)
        if t not in SCENES:
            probs.append(f"fala {i + 1}: cena '{t}' não existe ({', '.join(sorted(SCENES))})")
        for ref in [c.get("foto")] + list(c.get("fotos") or []):
            if isinstance(ref, str) and Path(ref).stem not in fotos:
                probs.append(f"fala {i + 1}: foto '{ref}' não está no projeto ({', '.join(sorted(fotos))})")
        if t == "oferta" and not (proj.get("preco") or (rot.get("produto") or {}).get("preco")):
            probs.append(f"fala {i + 1}: cena oferta sem preço (anuncio.py novo --preco ...)")
        if t == "prova" and not c.get("nota") and not c.get("texto"):
            probs.append(f"fala {i + 1}: cena prova precisa de nota/texto REAIS fornecidos pelo cliente")
        if t == "video" and not (c.get("video") or proj.get("videos")):
            probs.append(f"fala {i + 1}: cena video sem vídeo do produto")
        for it in c.get("itens", []):
            if len(it.get("texto", "")) > 26:
                probs.append(f"fala {i + 1}: benefício '{it['texto']}' longo demais (máx. ~26 letras)")
    if tipos and tipos[-1] != "cta":
        probs.append("a última cena deve ser 'cta'")
    if not falas or not falas[0].get("cena") or falas[0]["cena"].get("tipo") != "gancho":
        probs.append("a primeira cena deve ser 'gancho' (os 2 primeiros segundos seguram o scroll)")
    texto = " ".join(f.get("texto", "") for f in falas).lower()
    for bad in ("cura", "garantido", "100% eficaz", "milagre", "emagrece", "sem efeitos colaterais"):
        if re.search(rf"\b{re.escape(bad)}\b", texto):
            probs.append(f"promessa arriscada '{bad}': TikTok Shop e Meta reprovam alegação absoluta/saúde sem prova")
    return probs


def cmd_checar(a) -> None:
    project = Path(a.projeto).resolve()
    probs = check(project, script_path(project, a.roteiro))
    if probs:
        for p in probs:
            log(f"   - {p}")
        raise AdError(f"{len(probs)} ajuste(s) no roteiro antes de gerar")
    log("OK: roteiro pronto")


def cmd_voz(a) -> None:
    import voz
    project = Path(a.projeto).resolve()
    voz.narrate(project, script_path(project, a.roteiro))


def cmd_render(a) -> None:
    import montar
    project = Path(a.projeto).resolve()
    montar.render(project, script_path(project, a.roteiro), a.rascunho)


def cmd_tudo(a) -> None:
    t = time.time()
    project = Path(a.projeto).resolve()
    cmd_recorte(a)
    probs = check(project, script_path(project, a.roteiro))
    blocking = [p for p in probs if "não existe" in p or "sem " in p or "não está" in p]
    for p in probs:
        log(f"   aviso: {p}")
    if blocking:
        raise AdError("corrija o roteiro antes de gerar")
    cmd_voz(a)
    cmd_render(a)
    log(f"   (total {time.time() - t:.0f}s)")


def cmd_versoes(a) -> None:
    for r in a.roteiros:
        a.roteiro = r
        log(f"== {r}")
        cmd_tudo(a)


def cmd_vozes(a) -> None:
    data = load_json(VOICES_FILE)
    for k, v in data["vozes"].items():
        log(f"   {k:6s} {v['descricao']}{'  (padrão)' if k == data['padrao'] else ''}")
    if a.amostras:
        import numpy as np
        import voz
        out = Path(a.amostras)
        out.mkdir(parents=True, exist_ok=True)
        txt = "Para tudo! Esse sérum tem dez por cento de vitamina C e deixa a pele iluminada. Toca no carrinho e garante o seu."
        for k, v in data["vozes"].items():
            audio, sr = voz.synth_lines([txt], v, v.get("velocidade", 1.0))
            voz.write_wav(out / f"{k}.wav", np.concatenate(audio), sr)
            log(f"   amostra: {out / (k + '.wav')}")


def cmd_estilos(a) -> None:
    for p in sorted(STYLES_DIR.glob("*.json")):
        log(f"   {p.stem:12s} {load_json(p).get('_doc', '')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Anúncio de produto (foto -> vídeo de venda)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("novo")
    n.add_argument("projeto")
    n.add_argument("--fotos", nargs="+", required=True)
    n.add_argument("--videos", nargs="*")
    n.add_argument("--nome", required=True)
    n.add_argument("--nome-curto")
    n.add_argument("--preco")
    n.add_argument("--preco-antigo")
    n.add_argument("--desconto")
    n.add_argument("--parcelas")
    n.add_argument("--estilo")
    n.add_argument("--plataforma", default="tiktok_shop", choices=["tiktok_shop", "reels", "shorts"])
    n.add_argument("--cor")
    n.add_argument("--force", action="store_true")
    for name in ("recorte", "checar", "voz", "render", "tudo"):
        p = sub.add_parser(name)
        p.add_argument("projeto")
        p.add_argument("--roteiro")
        p.add_argument("--rascunho", action="store_true")
    v = sub.add_parser("versoes")
    v.add_argument("projeto")
    v.add_argument("--roteiros", nargs="+", required=True)
    v.add_argument("--rascunho", action="store_true")
    z = sub.add_parser("vozes")
    z.add_argument("--amostras")
    sub.add_parser("estilos")
    a = ap.parse_args()
    {"novo": cmd_novo, "recorte": cmd_recorte, "checar": cmd_checar, "voz": cmd_voz, "render": cmd_render,
     "tudo": cmd_tudo, "versoes": cmd_versoes, "vozes": cmd_vozes, "estilos": cmd_estilos}[a.cmd](a)


if __name__ == "__main__":
    main_guard(main)
