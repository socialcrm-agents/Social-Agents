#!/usr/bin/env python3
"""Espionagem dos anúncios vencedores do seu nicho: quem paga anúncio por meses é porque o anúncio dá lucro.

  1. O Claude busca na Biblioteca de Anúncios (conector Scrape Creators ou Meta Ads) e grava o JSON.
  2. `ranquear` dá nota a cada anúncio de vídeo: dias no ar (o sinal mais forte), quantas versões ele tem
     (escalar = duplicar) e se continua ativo. Junta duplicados (mesmo texto/coleção).
  3. `analisar` baixa os vídeos dos melhores, mede ritmo, cortes, texto na tela, legenda, zoom e áudio
     (referencia.py) e lê o gancho (transcrição do conector, quando houver). Monta o PERFIL DO NICHO: as medianas,
     os tipos de gancho que mais aparecem e o vídeo que melhor representa os vencedores.
  4. `aplicar` leva o ritmo/estilo desse perfil para o seu projeto (via referencia.py: nunca copia conteúdo).

  vencedores.py ranquear busca.json --nicho renda-extra [--top 10]
  vencedores.py analisar --nicho renda-extra [--top 8] [--transcricoes transcricoes.json]
  vencedores.py aplicar --nicho renda-extra <projeto> [--dry-run]
Tudo fica em ~/.editor-viral/nichos/<nicho>/ (ranking.json, perfil_nicho.json, nicho.md, videos/).
Os ganchos dos concorrentes aparecem no relatório como INSPIRAÇÃO de formato (pergunta, número, dor...) — o seu
vídeo continua com as suas palavras.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from common import EditorError, load_json, log, main_guard, norm, save_json

HERE = Path(__file__).resolve().parent
PASTA = Path(os.environ.get("EDITOR_VIRAL_DIR") or Path.home() / ".editor-viral") / "nichos"
MEDIDAS = ("duracao_s", "cortes_por_min", "plano_medio_s", "texto_eventos_por_min", "texto_na_tela_frac",
           "zoom_por_s", "fx_por_min", "punch_ins")


def _slug(s: str) -> str:
    palavras = re.split(r"[\s_\-/.,;:]+", s)
    return re.sub(r"[^a-z0-9]+", "-", "-".join(norm(w) for w in palavras if w)).strip("-") or "nicho"


def pasta(nicho: str) -> Path:
    return PASTA / _slug(nicho)


# ---------------------------------------------------------------------------------------------------------------
# leitura dos formatos dos conectores

def _data(v) -> float | None:
    """Unix (s ou ms) ou texto ISO/AAAA-MM-DD -> unix em segundos."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v) / (1000 if v > 1e11 else 1)
    s = str(v).strip()
    if s.isdigit():
        return _data(int(s))
    for fmt, n in (("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return time.mktime(time.strptime(s[:n], fmt))
        except ValueError:
            continue
    return None


def _video(a: dict) -> str | None:
    s = a.get("snapshot") or {}
    for v in (s.get("videos") or []) + (s.get("cards") or []) + (s.get("extra_videos") or []):
        url = v.get("video_hd_url") or v.get("video_sd_url") if isinstance(v, dict) else None
        if url:
            return url
    return a.get("video_url") or a.get("video")


def _texto(a: dict) -> str:
    s = a.get("snapshot") or {}
    b = s.get("body")
    if isinstance(b, dict):
        b = b.get("text")
    if not b:
        b = next((c.get("body") for c in s.get("cards") or [] if c.get("body")), None)
    if not b and a.get("ad_creative_bodies"):
        b = a["ad_creative_bodies"][0]
    return (b or a.get("body") or "").strip()


def ler_anuncios(dados) -> list[dict]:
    """Scrape Creators (searchResults/snapshot), Meta Ads MCP (ads_library_search) ou lista simples."""
    if isinstance(dados, dict):
        for k in ("searchResults", "results", "ads", "data"):
            if k in dados:
                return ler_anuncios(dados[k])
        return [dados]
    out = []
    agora = time.time()
    for a in dados or []:
        ini = _data(a.get("start_date") or a.get("ad_delivery_start_time") or a.get("startDate"))
        fim = _data(a.get("end_date") or a.get("ad_delivery_stop_time") or a.get("endDate"))
        ativo = bool(a.get("is_active", a.get("isActive", fim is None)))
        fim = min(fim, agora) if fim else agora   # no ativo, o fim é a última vez que foi visto no ar
        out.append({
            "id": str(a.get("ad_archive_id") or a.get("id") or a.get("adArchiveID")),
            "pagina": a.get("page_name") or (a.get("snapshot") or {}).get("page_name") or a.get("pageName") or "?",
            "texto": _texto(a), "video": _video(a), "ativo": ativo,
            "dias": round((fim - ini) / 86400, 1) if ini else None,
            "versoes": int(a.get("collation_count") or 1),
            "colecao": a.get("collation_id"),
            "cta": (a.get("snapshot") or {}).get("cta_text") or a.get("cta_text"),
            "url": a.get("url") or a.get("ad_snapshot_url")
                   or f"https://www.facebook.com/ads/library/?id={a.get('ad_archive_id') or a.get('id')}"})
    return out


def nota(a: dict) -> float:
    """Dias no ar pesam mais (log: 90 dias não é 3× melhor que 30), versões = escalando, ativo = ainda dá lucro."""
    return round(math.log1p(a.get("dias") or 0) * 2 + math.log1p(a["versoes"]) + (0.7 if a["ativo"] else 0), 3)


def ranquear(anuncios: list[dict], top: int = 10) -> list[dict]:
    vistos, out = set(), []
    for a in sorted(anuncios, key=nota, reverse=True):
        if not a["video"]:
            continue
        chave = a["colecao"] or (a["pagina"], norm(a["texto"])[:80])
        if chave in vistos:
            continue
        vistos.add(chave)
        out.append({**a, "nota": nota(a)})
    return out[:top]


# ---------------------------------------------------------------------------------------------------------------
# análise dos vídeos

def tipo_gancho(frase: str) -> str:
    import ganchos
    import seletor
    if not frase:
        return "sem_fala"
    t = seletor.intencao({"fala": frase}, 1)
    if t != "respiro":
        return t
    ws = {norm(w) for w in frase.split()}
    if ws & ganchos.PROMESSA:
        return "promessa"
    if ws & ganchos.VOCE:
        return "voce"
    return "afirmacao"


def gancho_da_transcricao(tr: str | dict | None) -> str:
    """Primeira frase (até ~3 s de fala ≈ 12 palavras) do texto da transcrição do conector."""
    if isinstance(tr, dict):
        tr = tr.get("transcript") or tr.get("text") or ""
    tr = (tr or "").strip()
    m = re.split(r"(?<=[.!?])\s", tr, maxsplit=1)
    frase = m[0] if m else tr
    return " ".join(frase.split()[:14])


def baixar(url: str, destino: Path) -> Path | None:
    if destino.exists() and destino.stat().st_size > 1000:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, destino.open("wb") as fh:
            fh.write(r.read())
        return destino
    except Exception as exc:  # noqa: BLE001 — link expirado/bloqueado: segue sem esse vídeo
        log(f"   não baixou {destino.name}: {exc}")
        destino.unlink(missing_ok=True)
        return None


def _mediana(v: list[float]) -> float | None:
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    k = len(v) // 2
    return v[k] if len(v) % 2 else (v[k - 1] + v[k]) / 2


def analisar(nicho: str, top: int = 8, transcricoes: dict | None = None, com_rosto: bool = False) -> dict:
    import referencia
    d = pasta(nicho)
    ranking = load_json(d / "ranking.json")
    if not ranking:
        raise EditorError(f"Sem ranking para '{nicho}' (rode: vencedores.py ranquear busca.json --nicho {nicho})")
    analisados = []
    for a in ranking[:top]:
        log(f"[{a['pagina']}] {a['dias']} dias no ar, {a['versoes']} versões")
        arq = baixar(a["video"], d / "videos" / f"{a['id']}.mp4")
        item = {**a, "gancho": gancho_da_transcricao((transcricoes or {}).get(a["id"]))}
        item["gancho_tipo"] = tipo_gancho(item["gancho"]) if item["gancho"] else None
        if arq:
            try:
                perfil = referencia.analisar(arq, 10.0, com_rosto=com_rosto)
                save_json(d / "videos" / f"{a['id']}.perfil.json", perfil)
                item["perfil"] = str(d / "videos" / f"{a['id']}.perfil.json")
                item["medidas"] = {k: perfil["medidas"].get(k) for k in MEDIDAS}
                leg = perfil["medidas"].get("legenda")
                item["medidas"]["legenda"] = bool(leg)
                item["medidas"]["trilha"] = bool((perfil["medidas"].get("audio") or {}).get("trilha_provavel"))
                item["estilo"] = perfil["traducao"]["estilo"]
            except Exception as exc:  # noqa: BLE001
                log(f"   análise falhou: {exc}")
        analisados.append(item)
    medidos = [x for x in analisados if x.get("medidas")]
    medianas = {k: _mediana([x["medidas"][k] for x in medidos]) for k in MEDIDAS}
    frac = lambda k: round(sum(1 for x in medidos if x["medidas"].get(k)) / len(medidos), 2) if medidos else None
    tipos: dict[str, int] = {}
    for x in analisados:
        if x.get("gancho_tipo"):
            tipos[x["gancho_tipo"]] = tipos.get(x["gancho_tipo"], 0) + 1
    # o vídeo que melhor representa os vencedores (mais perto das medianas, em escala relativa)
    def distancia(x):
        return sum(abs(math.log((x["medidas"][k] or 0) + 0.05) - math.log((medianas[k] or 0) + 0.05))
                   for k in ("cortes_por_min", "plano_medio_s", "texto_eventos_por_min", "zoom_por_s", "fx_por_min"))
    repr_ = min(medidos, key=distancia) if medidos else None
    resumo = {"nicho": nicho, "gerado_em": time.strftime("%Y-%m-%d %H:%M"), "analisados": analisados,
              "medianas": medianas, "com_legenda": frac("legenda"), "com_trilha": frac("trilha"),
              "ganchos": dict(sorted(tipos.items(), key=lambda kv: -kv[1])),
              "ctas": sorted({x["cta"] for x in analisados if x.get("cta")}),
              "representante": repr_ and {"id": repr_["id"], "pagina": repr_["pagina"], "perfil": repr_["perfil"]}}
    if repr_:
        perfil = load_json(Path(repr_["perfil"]))
        perfil["origem_nicho"] = {"nicho": nicho, "representante": repr_["id"], "medianas": medianas}
        save_json(d / "perfil_nicho.json", perfil)
    save_json(d / "nicho.json", resumo)
    (d / "nicho.md").write_text(relatorio(resumo), encoding="utf-8")
    return resumo


def _f(x, casas=1, suf=""):
    return "?" if x is None else f"{x:.{casas}f}{suf}"


def relatorio(r: dict) -> str:
    m = r["medianas"]
    L = [f"# Vencedores do nicho: {r['nicho']}", "",
         f"{len(r['analisados'])} anúncios de vídeo que mais tempo ficaram no ar (quem paga por meses está lucrando).",
         "", "## O padrão dos vencedores", "",
         f"- Duração típica: {_f(m['duracao_s'], 0, ' s')}",
         f"- Cortes: {_f(m['cortes_por_min'], 0)} por minuto (um plano a cada {_f(m['plano_medio_s'], 1, ' s')})",
         f"- Texto na tela além da legenda: {_f(m['texto_eventos_por_min'], 0)} entradas por minuto, presente "
         f"{_f((m['texto_na_tela_frac'] or 0) * 100 if m['texto_na_tela_frac'] is not None else None, 0, '%')} do tempo",
         f"- Zoom/punch-ins: {_f(m['punch_ins'], 0)} por vídeo; efeitos (flash/tremida): {_f(m['fx_por_min'], 1)} por minuto",
         f"- Com legenda: {_f((r['com_legenda'] or 0) * 100 if r['com_legenda'] is not None else None, 0, '%')} | "
         f"com trilha: {_f((r['com_trilha'] or 0) * 100 if r['com_trilha'] is not None else None, 0, '%')}"]
    if r["ganchos"]:
        L.append("- Tipos de gancho: " + ", ".join(f"{k} ({v})" for k, v in r["ganchos"].items()))
    if r["ctas"]:
        L.append("- Chamadas usadas: " + ", ".join(r["ctas"]))
    if r.get("representante"):
        L += ["", f"Vídeo que melhor representa o nicho: {r['representante']['pagina']} "
                  f"(`{r['representante']['id']}`) → vira o perfil de ritmo (`vencedores.py aplicar`)."]
    L += ["", "## Os anúncios", "", "| # | página | dias no ar | versões | cortes/min | texto/min | gancho (formato) |",
          "|---|---|---|---|---|---|---|"]
    for i, x in enumerate(r["analisados"], 1):
        md = x.get("medidas") or {}
        L.append(f"| {i} | [{x['pagina']}]({x['url']}) | {x['dias']} | {x['versoes']} | {_f(md.get('cortes_por_min'), 0)} "
                 f"| {_f(md.get('texto_eventos_por_min'), 0)} | {x.get('gancho_tipo') or '—'}"
                 + (f": \"{x['gancho']}\"" if x.get("gancho") else "") + " |")
    L += ["", "Ganchos dos concorrentes = inspiração de FORMATO. Escreva o seu com as suas palavras."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------------------------
# CLI

def cmd_ranquear(a) -> None:
    anuncios = ler_anuncios(json.loads(Path(a.arquivo).read_text(encoding="utf-8")))
    d = pasta(a.nicho)
    antigo = {x["id"]: x for x in (load_json(d / "ranking.json") or [])}
    for x in anuncios:     # várias buscas do mesmo nicho somam
        antigo[x["id"]] = x
    rk = ranquear(list(antigo.values()), a.top)
    d.mkdir(parents=True, exist_ok=True)
    save_json(d / "ranking.json", rk)
    log(f"{len(anuncios)} anúncios lidos, {sum(1 for x in antigo.values() if x['video'])} com vídeo; top {len(rk)}:")
    for i, x in enumerate(rk, 1):
        log(f"  {i:2d}. {x['pagina'][:28]:28s} {x['dias'] or '?':>6} dias  {x['versoes']} versões  "
            f"{'ativo' if x['ativo'] else 'parado'}  nota {x['nota']}")
    log(f"Ranking: {d / 'ranking.json'}")


def cmd_analisar(a) -> None:
    trs = json.loads(Path(a.transcricoes).read_text(encoding="utf-8")) if a.transcricoes else None
    if isinstance(trs, list):
        trs = {str(t.get("id") or t.get("ad_archive_id")): t for t in trs}
    r = analisar(a.nicho, a.top, trs, com_rosto=a.rosto)
    print(relatorio(r))
    log(f"Relatório: {pasta(a.nicho) / 'nicho.md'}")


def cmd_aplicar(a) -> None:
    perfil = pasta(a.nicho) / "perfil_nicho.json"
    if not perfil.exists():
        raise EditorError(f"Sem perfil do nicho '{a.nicho}' (rode: vencedores.py analisar --nicho {a.nicho})")
    args = [sys.executable, str(HERE / "referencia.py"), "aplicar", str(perfil), a.project]
    sys.exit(subprocess.run(args + (["--dry-run"] if a.dry_run else [])).returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ranquear")
    r.add_argument("arquivo")
    r.add_argument("--nicho", required=True)
    r.add_argument("--top", type=int, default=10)
    an = sub.add_parser("analisar")
    an.add_argument("--nicho", required=True)
    an.add_argument("--top", type=int, default=8)
    an.add_argument("--transcricoes", help="JSON {id: transcrição} ou lista do conector")
    an.add_argument("--rosto", action="store_true", help="mede também o rosto (mais lento)")
    apl = sub.add_parser("aplicar")
    apl.add_argument("project")
    apl.add_argument("--nicho", required=True)
    apl.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    {"ranquear": cmd_ranquear, "analisar": cmd_analisar, "aplicar": cmd_aplicar}[a.cmd](a)


if __name__ == "__main__":
    main_guard(main)
