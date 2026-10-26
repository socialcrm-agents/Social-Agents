#!/usr/bin/env python3
"""O editor aprende com as suas vendas: cruza o que tem em cada vídeo com o resultado real dele no anúncio.

Como funciona
  1. Todo render ganha uma FICHA (o que tem no vídeo: tipo de gancho, abertura, composições, trilha, voz,
     legenda, ritmo, densidade, duração...) e um CÓDIGO (ex.: EV-7F3A2C) que vai no nome do arquivo. Suba o
     vídeo com esse nome no Meta/Vturb (ou ponha o código no nome do anúncio) e o editor reconhece qual é qual.
  2. Os números chegam pelos conectores (o Claude busca no Meta Ads e no Vturb e grava o JSON) e entram com
     `importar`. Nada de copiar planilha.
  3. `analisar` compara os vídeos: o que os vencedores têm em comum, com quanta certeza (poucos dados = avisa),
     e onde as pessoas saem do vídeo acima do normal (curva de retenção do Vturb) e o que estava na tela ali.
  4. Com certeza suficiente, grava a receita "aprendida" (run.py padrao aprendida) e a ordem de ganchos
     preferida da fábrica de variações. O que não tem certeza vira teste sugerido, não regra.

  aprender.py ficha <projeto> [--versao N]       (re)gera a ficha da versão e mostra o código
  aprender.py importar meta|vturb arquivo.json   resultados exportados pelos conectores
  aprender.py analisar [--metrica auto|roas|ctr|segurou|retencao|conversao] [--min-gasto 30] [--aplicar]
  aprender.py status                             quantos vídeos, quantos já com resultado, códigos sem dono
Tudo fica em ~/.editor-viral/ (criativos.jsonl, resultados.jsonl, aprendizado.json, aprendizado.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

from common import EditorError, load_json, log, main_guard, norm, project_paths, save_json

PASTA = Path(os.environ.get("EDITOR_VIRAL_DIR") or Path.home() / ".editor-viral")   # testes usam outra pasta
CRIATIVOS = PASTA / "criativos.jsonl"
RESULTADOS = PASTA / "resultados.jsonl"
APRENDIZADO = PASTA / "aprendizado.json"
RELATORIO = PASTA / "aprendizado.md"
CODIGO_RE = re.compile(r"EV-?([0-9A-F]{6})", re.I)
GANCHO_S = 3.0


# ---------------------------------------------------------------------------------------------------------------
# ficha do criativo

def codigo(project: Path, versao: int) -> str:
    return "EV-" + hashlib.sha1(f"{Path(project).resolve()}|v{versao}".encode()).hexdigest()[:6].upper()


def _num(v) -> float | None:
    """Número de qualquer formato dos conectores: 12, "12", {"value": "12"}, [{"value": 3.1}], None."""
    if v is None:
        return None
    if isinstance(v, dict):
        return _num(v.get("value"))
    if isinstance(v, list):
        vals = [_num(x) for x in v]
        vals = [x for x in vals if x is not None]
        return sum(vals) if vals else None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _faixa(x: float, cortes: list[float], nomes: list[str]) -> str:
    for c, n in zip(cortes, nomes):
        if x < c:
            return n
    return nomes[-1]


def montar_ficha(tl: dict, proj: dict, project: Path, versao: int, arquivo: str | None = None,
                 extra: dict | None = None) -> dict:
    """O que tem no vídeo, em características comparáveis entre vídeos (todas simples e legíveis)."""
    import seletor
    words = tl.get("words", [])
    total = float(tl["duration"])
    ov = proj.get("overrides", {})
    cs = seletor.cenas(words) if words else []
    gancho_txt = " ".join(w["w"] for w in words if w["t0"] < GANCHO_S) if words else ""
    tipo = seletor.intencao(cs[0], 1) if cs else "sem_fala"
    if tipo in ("gancho", "respiro"):   # sem marca forte: "afirmação"
        tipo = "afirmacao"
    if "?" in gancho_txt:
        tipo = "pergunta"
    motion = tl.get("motion", [])
    abre = sorted({m.get("template") for m in motion if m.get("t0", 99) < GANCHO_S} |
                  {f["type"] for f in tl.get("fx", []) if f.get("t", 99) < GANCHO_S})
    comps = sorted({m.get("composicao") for m in motion if m.get("composicao")})
    musica = tl.get("music") or {}
    auto = musica.get("auto") or {}
    trilha = (f"{auto.get('clima')}{'_ia' if auto.get('motor') == 'ia' else ''}" if auto else
              ("arquivo" if musica else "sem"))
    dens = seletor.densidade(tl)
    cortes_min = 60 * max(len(tl.get("shots", [])) - 1, 0) / max(total, 1)
    falando = [w for w in words if w["t1"] - w["t0"] < 2]
    pps = len(falando) / max(sum(w["t1"] - w["t0"] for w in falando), 0.1) if falando else 0
    cap = (tl.get("captions") or {}).get("cfg", {})
    img = tl.get("imagem") or {}
    caracteristicas = {
        "gancho_tipo": tipo,
        "abertura": "+".join(abre) if abre else "nada",
        "composicoes": "+".join(comps) if comps else "nenhuma",
        "direcao": "premium" if tl.get("direcao") else "padrao",
        "estilo": tl.get("style"),
        "trilha": trilha,
        "voz": (tl.get("audio") or {}).get("voz", "padrao"),
        "legenda": _faixa(float(cap.get("size") or 0), [70, 90], ["pequena", "media", "grande"]),
        "ritmo_cortes": _faixa(cortes_min, [8, 20], ["calmo", "medio", "rapido"]),
        "densidade": _faixa(dens["media"], [1.0, 2.0], ["baixa", "media", "alta"]),
        "fala": _faixa(pps, [2.6, 3.4], ["devagar", "normal", "rapida"]),
        "duracao": _faixa(total, [20, 40, 70], ["ate_20s", "20_40s", "40_70s", "mais_70s"]),
        "correcao_imagem": "sim" if img.get("correcao") in ("auto", "on") else "nao",
        "cta_na_tela": "sim" if any(m.get("template") in ("botao_cta", "final", "cta") for m in motion) else "nao",
    }
    if extra:
        caracteristicas.update(extra)
    eventos = sorted([[round(m["t0"], 2), f"animação {m.get('template')}"] for m in motion]
                     + [[round(f["t"], 2), f"efeito {f['type']}"] for f in tl.get("fx", [])]
                     + [[round(s["t0"], 2), "corte"] for s in tl.get("shots", [])[1:]])
    return {"codigo": codigo(project, versao), "projeto": str(Path(project).resolve()), "versao": versao,
            "arquivo": arquivo, "criado_em": time.strftime("%Y-%m-%d %H:%M"), "duracao": round(total, 2),
            "gancho_texto": gancho_txt[:160], "caracteristicas": caracteristicas,
            "numeros": {"cortes_por_min": round(cortes_min, 1), "mudancas_por_3s": dens["media"],
                        "palavras_por_s": round(pps, 2), "animacoes": len(motion)},
            "eventos": eventos, "buracos": dens["buracos"]}


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for linha in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(linha))
        except ValueError:
            continue
    return out


def _anexar(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def registrar(project: Path, versao: int, tl: dict, proj: dict, arquivo: str | None, extra: dict | None = None) -> dict:
    """Grava a ficha em versions/vN/ficha.json e no registro geral (~/.editor-viral/criativos.jsonl)."""
    f = montar_ficha(tl, proj, project, versao, arquivo, extra)
    paths = project_paths(Path(project))
    vdir = paths["versions"] / f"v{versao}"
    if vdir.exists():
        save_json(vdir / "ficha.json", f)
    _anexar(CRIATIVOS, f)
    return f


def fichas() -> dict[str, dict]:
    """Última ficha de cada código."""
    return {f["codigo"]: f for f in _jsonl(CRIATIVOS)}


# ---------------------------------------------------------------------------------------------------------------
# importação dos resultados (formatos dos conectores Meta Ads e Vturb)

def _codigo_em(*textos) -> str | None:
    for t in textos:
        m = CODIGO_RE.search(str(t or ""))
        if m:
            return "EV-" + m.group(1).upper()
    return None


def _lista(dados, *chaves) -> list:
    """Acha a lista de itens em respostas embrulhadas ({"data": ...}, {"ad_entities": "<json>"}, lista pura)."""
    if isinstance(dados, str):
        try:
            dados = json.loads(dados)
        except ValueError:
            return []
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for k in (*chaves, "data", "ad_entities", "videos", "players", "items", "results"):
            if k in dados:
                return _lista(dados[k], *chaves)
        return [dados]
    return []


def normalizar_meta(dados) -> list[dict]:
    out = []
    for ad in _lista(dados):
        cod = _codigo_em(ad.get("name"), ad.get("video_title"), ad.get("title"), ad.get("creative_name"),
                         ad.get("ad_name"))
        if not cod:
            continue
        plays = _num(ad.get("video_play_actions"))
        imp = _num(ad.get("impressions"))
        r = {"codigo": cod, "fonte": "meta", "id": ad.get("id"), "gasto": _num(ad.get("amount_spent") or ad.get("spend")),
             "impressoes": imp, "plays": plays, "ctr": _num(ad.get("ctr")),
             "roas": _num(ad.get("purchase_roas")), "cpa": _num(ad.get("cost_per_omni_purchase") or ad.get("cost_per_purchase")),
             "compras": _num(ad.get("purchases") or ad.get("omni_purchase")),
             "tempo_medio": _num(ad.get("video_avg_time_watched_actions"))}
        if plays:
            for p in (25, 50, 75, 100):
                v = _num(ad.get(f"video_p{p}_watched_actions"))
                r[f"p{p}"] = round(v / plays, 4) if v is not None else None
        if imp:
            th = _num(ad.get("video_thruplay_watched_actions"))
            r["thruplay_taxa"] = round(th / imp, 4) if th is not None else None
        out.append(r)
    return out


def _retencao_em(curva: list, seg: float) -> float | None:
    pts = sorted((_num(p.get("second")), _num(p.get("retention"))) for p in curva or [] if _num(p.get("second")) is not None)
    if not pts:
        return None
    ant = pts[0]
    for s, r in pts:
        if s >= seg:
            if s == ant[0]:
                return r
            return ant[1] + (r - ant[1]) * (seg - ant[0]) / (s - ant[0])
        ant = (s, r)
    return pts[-1][1]


def normalizar_vturb(dados, nomes: dict | None = None) -> list[dict]:
    """get_player_stats (um ou vários). O código vem do nome do vídeo: `nomes` {player_id: nome} (list_players)
    ou campos name/title no próprio item."""
    out = []
    for it in _lista(dados, "stats"):
        pid = it.get("player_id") or it.get("id")
        cod = _codigo_em(it.get("name"), it.get("title"), (nomes or {}).get(pid), it.get("codigo"))
        if not cod:
            continue
        curva = it.get("retention_curve") or []
        out.append({"codigo": cod, "fonte": "vturb", "id": pid, "plays": _num(it.get("plays")),
                    "play_rate": _num(it.get("play_rate")), "engajamento": _num(it.get("engagement")),
                    "conversao": _num(it.get("conversion_rate")), "receita": _num(it.get("revenue")),
                    "conversoes": _num(it.get("conversions")), "pitch_retencao": _num(it.get("pitch_retention")),
                    "ret_3s": _retencao_em(curva, 3), "ret_5s": _retencao_em(curva, 5),
                    "ret_10s": _retencao_em(curva, 10),
                    "curva": [[_num(p.get("second")), _num(p.get("retention"))] for p in curva]})
    return out


def importar(fonte: str, arquivo: Path, nomes: Path | None = None) -> list[dict]:
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    if fonte == "meta":
        linhas = normalizar_meta(dados)
    else:
        mapa = {}
        if nomes:
            for p in _lista(json.loads(Path(nomes).read_text(encoding="utf-8")), "players"):
                mapa[p.get("id") or p.get("player_id")] = p.get("name") or p.get("title")
        linhas = normalizar_vturb(dados, mapa)
    agora = time.strftime("%Y-%m-%d %H:%M")
    for r in linhas:
        r["importado_em"] = agora
        _anexar(RESULTADOS, r)
    return linhas


def resultados() -> dict[str, dict]:
    """Por código: o último resultado de cada (fonte, id) somado (vários anúncios do mesmo vídeo somam gasto)."""
    ultimo: dict[tuple, dict] = {}
    for r in _jsonl(RESULTADOS):
        ultimo[(r["codigo"], r["fonte"], r.get("id"))] = r
    por: dict[str, dict] = {}
    for (cod, fonte, _id), r in ultimo.items():
        a = por.setdefault(cod, {"codigo": cod})
        if fonte == "meta":
            peso_ant, peso = a.get("_imp_meta", 0.0), r.get("impressoes") or 0.0
            for k in ("ctr", "roas", "p25", "p50", "p75", "p100", "thruplay_taxa", "tempo_medio"):
                if r.get(k) is not None:
                    a[k] = (a[k] * peso_ant + r[k] * peso) / (peso_ant + peso) if a.get(k) is not None and peso_ant + peso \
                        else r[k]
            for k in ("gasto", "impressoes", "plays", "compras"):
                if r.get(k) is not None:
                    a[k] = (a.get(k) or 0) + r[k]
            a["_imp_meta"] = peso_ant + peso
        else:
            for k, v in r.items():
                if k not in ("codigo", "fonte", "id", "importado_em") and v is not None:
                    a[k if k != "plays" else "plays_vturb"] = v
    for a in por.values():
        a.pop("_imp_meta", None)
    return por


# ---------------------------------------------------------------------------------------------------------------
# análise

METRICAS = {  # nome -> (campo, rótulo para pessoas, mínimo de volume por vídeo)
    "roas": ("roas", "retorno (ROAS)", "gasto"),
    "conversao": ("conversao", "conversão no Vturb (%)", "plays_vturb"),
    "ctr": ("ctr", "cliques (CTR %)", "impressoes"),
    "segurou": ("p25", "quem passou de 25% do vídeo", "plays"),
    "retencao": ("ret_5s", "quem ficou depois de 5 s (Vturb, %)", "plays_vturb"),
}
ORDEM_AUTO = ["roas", "conversao", "ctr", "segurou", "retencao"]
NOMES = {"gancho_tipo": "tipo de gancho", "abertura": "o que abre o vídeo", "composicoes": "composições",
         "direcao": "direção", "estilo": "estilo", "trilha": "trilha", "voz": "voz", "legenda": "tamanho da legenda",
         "ritmo_cortes": "ritmo de cortes", "densidade": "quantidade de efeitos", "fala": "velocidade da fala",
         "duracao": "duração", "correcao_imagem": "correção de imagem", "cta_na_tela": "botão de ação na tela"}


def _media_var(v: list[float]) -> tuple[float, float]:
    m = sum(v) / len(v)
    return m, (sum((x - m) ** 2 for x in v) / (len(v) - 1) if len(v) > 1 else 0.0)


def comparar(linhas: list[tuple[dict, float]], minimo: int = 2) -> list[dict]:
    """Para cada característica: o valor de melhor média contra o resto, com tamanho da diferença e certeza.
    Certeza (teste t de Welch + tamanho das amostras): alta (t ≥ 2,5 e ≥ 4 vídeos de cada lado), média (t ≥ 1,7 e
    ≥ 3), baixa (o resto: vira sugestão de teste, não regra)."""
    if len(linhas) < 2 * minimo:
        return []
    achados = []
    chaves = sorted({k for f, _ in linhas for k in f["caracteristicas"]})
    for k in chaves:
        grupos: dict[str, list[float]] = {}
        for f, y in linhas:
            grupos.setdefault(str(f["caracteristicas"].get(k)), []).append(y)
        if len(grupos) < 2:
            continue
        for valor, ys in grupos.items():
            resto = [y for v, yy in grupos.items() if v != valor for y in yy]
            if len(ys) < minimo or len(resto) < minimo:
                continue
            m1, v1 = _media_var(ys)
            m2, v2 = _media_var(resto)
            ep = math.sqrt(v1 / len(ys) + v2 / len(resto)) or 1e-9
            t = (m1 - m2) / ep
            n = min(len(ys), len(resto))
            certeza = "alta" if abs(t) >= 2.5 and n >= 4 else "media" if abs(t) >= 1.7 and n >= 3 else "baixa"
            achados.append({"caracteristica": k, "valor": valor, "media": m1, "media_resto": m2,
                            "dif_rel": (m1 - m2) / abs(m2) if m2 else None, "t": round(t, 2), "n": len(ys),
                            "n_resto": len(resto), "certeza": certeza})
    # por característica, só o valor mais forte (o mesmo efeito visto pelos dois lados não conta duas vezes)
    melhor: dict[str, dict] = {}
    for a in achados:
        forca = abs(a["t"]) + (1e-6 if a["t"] > 0 else 0)   # empate (2 valores = o mesmo efeito): o lado que ganha
        atual = melhor.get(a["caracteristica"])
        if atual is None or forca > abs(atual["t"]) + (1e-6 if atual["t"] > 0 else 0):
            melhor[a["caracteristica"]] = a
    return sorted(melhor.values(), key=lambda a: -abs(a["t"]))


def quedas(curva: list, eventos: list, buracos: list, duracao: float, esperado: dict[int, float]) -> list[dict]:
    """Trechos de 5 s onde saiu gente acima do normal desta conta, e o que estava na tela ali."""
    pts = sorted((s, r) for s, r in curva if s is not None and r is not None and s <= duracao + 1)
    out = []
    for (s0, r0), (s1, r1) in zip(pts, pts[1:]):
        if s1 <= s0 or r0 <= 0:
            continue
        perda = 100 * (r0 - r1) / r0 / (s1 - s0) * 5      # % de quem ainda assistia que saiu, por 5 s
        base = esperado.get(int(s0 // 5) * 5)
        if base is None or perda < max(base * 1.6, base + 3):
            continue
        tela = [e[1] for e in eventos if s0 - 0.5 <= e[0] < s1]
        parado = [b for b in buracos if b[0] < s1 and b[1] > s0]
        out.append({"de": s0, "ate": s1, "saiu_pct": round(perda, 1), "normal_pct": round(base, 1),
                    "na_tela": tela or ["nada muda na tela"], "parado": bool(parado) or not tela})
    return out


def analisar(metrica: str = "auto", min_volume: float = 30.0) -> dict:
    fs, rs = fichas(), resultados()
    juntos = [(fs[c], rs[c]) for c in rs if c in fs]
    escolhida = None
    for nome in ([metrica] if metrica != "auto" else ORDEM_AUTO):
        campo, _rot, vol = METRICAS[nome]
        lim = min_volume if vol == "gasto" else 100 if vol in ("plays", "plays_vturb") else 1000
        ok = [(f, r[campo]) for f, r in juntos if r.get(campo) is not None and (r.get(vol) or 0) >= lim]
        if len(ok) >= 4 or (metrica != "auto" and ok):
            escolhida, linhas = nome, ok
            break
    res = {"criativos": len(fs), "com_resultado": len(juntos), "sem_ficha": sorted(c for c in rs if c not in fs),
           "metrica": escolhida, "achados": [], "quedas": [], "ranking": []}
    if not escolhida:
        return res
    campo, rotulo, _ = METRICAS[escolhida]
    res["rotulo"] = rotulo
    res["achados"] = comparar(linhas)
    res["ranking"] = [{"codigo": f["codigo"], "valor": y, "gancho": f["gancho_texto"][:60], "arquivo": f.get("arquivo")}
                      for f, y in sorted(linhas, key=lambda x: -x[1])]
    # quedas de retenção (Vturb): o normal desta conta em cada janela de 5 s = mediana entre os vídeos
    curvas = [(f, r["curva"]) for f, r in juntos if r.get("curva")]
    perdas: dict[int, list[float]] = {}
    for _f, cv in curvas:
        pts = sorted((s, r_) for s, r_ in cv if s is not None and r_ is not None)
        for (s0, r0), (s1, r1) in zip(pts, pts[1:]):
            if s1 > s0 and r0 > 0:
                perdas.setdefault(int(s0 // 5) * 5, []).append(100 * (r0 - r1) / r0 / (s1 - s0) * 5)
    esperado = {k: sorted(v)[len(v) // 2] for k, v in perdas.items() if len(v) >= 2}
    for f, cv in curvas:
        for q in quedas(cv, f.get("eventos", []), f.get("buracos", []), f["duracao"], esperado):
            res["quedas"].append({"codigo": f["codigo"], **q})
    return res


# ---------------------------------------------------------------------------------------------------------------
# virar receita

# característica -> opções do edit.py quando o valor vence com certeza (o que não tem tradução fica só no relatório)
ACOES = {
    "trilha": lambda v: ["--music", "off"] if v == "sem" else (["--music", f"auto:{v.removesuffix('_ia')}"]
                                                               if v.removesuffix("_ia") in
                                                               ("energia", "inspirador", "suspense", "lofi", "corporativo")
                                                               else []),
    "voz": lambda v: ["--voz", "estudio" if v == "estudio" else "off"],
    "legenda": lambda v: ["--caption-size", {"pequena": "64", "media": "78", "grande": "92"}[v]] if v in
    ("pequena", "media", "grande") else [],
    "direcao": lambda v: ["--direcao", "premium" if v == "premium" else "off"],
    "correcao_imagem": lambda v: ["--correcao", "auto" if v == "sim" else "off"],
}


def receita_aprendida(achados: list[dict], base: list[str]) -> tuple[list[str], list[str]]:
    """Base (premium) + o que venceu com certeza média/alta. Só valores que GANHAM (t > 0) viram regra."""
    import receitas
    ops = list(base)
    porque = []
    for a in achados:
        if a["certeza"] == "baixa" or a["t"] <= 0 or a["caracteristica"] not in ACOES:
            continue
        extra = ACOES[a["caracteristica"]](a["valor"])
        if extra:
            ops = receitas.sobrepor(ops, extra)
            porque.append(f"{NOMES.get(a['caracteristica'], a['caracteristica'])} = {a['valor']} "
                          f"(certeza {a['certeza']})")
    return ops, porque


def _pct(x: float | None) -> str:
    return "?" if x is None else f"{x * 100:+.0f}%"


def _fmt(x: float, metrica: str) -> str:
    if metrica in ("segurou",):
        return f"{x * 100:.0f}%"
    return f"{x:.2f}" if metrica == "roas" else f"{x:.1f}"


def relatorio(res: dict, aplicado: dict | None) -> str:
    L = ["# O que o editor aprendeu com as suas vendas", "",
         f"{res['criativos']} vídeos com ficha; {res['com_resultado']} já com resultado no Meta/Vturb.", ""]
    if res["sem_ficha"]:
        L += [f"Códigos com resultado mas sem ficha neste computador: {', '.join(res['sem_ficha'])}", ""]
    if not res["metrica"]:
        L += ["**Ainda não dá para aprender:** preciso de pelo menos 4 vídeos com resultado e volume mínimo "
              "(R$ 30 de gasto ou 100 plays cada). Continue subindo os vídeos com o código no nome.", ""]
        return "\n".join(L)
    m = res["metrica"]
    L += [f"Medida usada: **{res['rotulo']}**.", "", "## Ranking", ""]
    for i, r in enumerate(res["ranking"], 1):
        L.append(f"{i}. `{r['codigo']}` {_fmt(r['valor'], m)} — \"{r['gancho']}\"")
    L += ["", "## O que os vencedores têm em comum", ""]
    if not res["achados"]:
        L.append("Nenhuma diferença clara ainda (os vídeos são parecidos demais ou são poucos).")
    for a in res["achados"]:
        nome = NOMES.get(a["caracteristica"], a["caracteristica"])
        lado = "melhor" if a["t"] > 0 else "pior"
        L.append(f"- **{nome} = {a['valor']}** foi {lado}: {_fmt(a['media'], m)} contra {_fmt(a['media_resto'], m)} "
                 f"({_pct(a['dif_rel'])}; {a['n']} vídeos contra {a['n_resto']}) — certeza **{a['certeza']}**"
                 + (" → vale testar de propósito" if a["certeza"] == "baixa" else ""))
    if res["quedas"]:
        L += ["", "## Onde as pessoas saem acima do normal (Vturb)", ""]
        parados = sum(1 for q in res["quedas"] if q["parado"])
        for q in res["quedas"][:15]:
            L.append(f"- `{q['codigo']}` {q['de']:.0f}–{q['ate']:.0f} s: saíram {q['saiu_pct']}% (normal "
                     f"{q['normal_pct']}%) — na tela: {', '.join(q['na_tela'][:4])}")
        if parados:
            L += ["", f"Em {parados} de {len(res['quedas'])} quedas nada mudava na tela: a fábrica e a direção "
                      f"premium devem ter algo novo a cada 3-4 s nesses pontos."]
    if aplicado:
        L += ["", "## Receita aprendida", "", "Aplicada como `aprendida` (use: run.py padrao aprendida):", "",
              "`" + " ".join(aplicado["receita"]) + "`", ""]
        L += [f"- {p}" for p in aplicado["porque"]] or ["- (igual à premium: nada com certeza suficiente ainda)"]
        if aplicado.get("ganchos"):
            L += ["", "Ordem de ganchos preferida da fábrica: " + " > ".join(aplicado["ganchos"])]
    return "\n".join(L) + "\n"


def aplicar(res: dict) -> dict:
    import receitas
    ops, porque = receita_aprendida(res["achados"], receitas.RECEITAS["premium"])
    ganchos = [a["valor"] for a in res["achados"] if a["caracteristica"] == "gancho_tipo" and a["t"] > 0
               and a["certeza"] != "baixa"]
    dados = {"receita": ops, "porque": porque, "ganchos": ganchos, "metrica": res["metrica"],
             "gerado_em": time.strftime("%Y-%m-%d %H:%M"), "videos": res["com_resultado"]}
    save_json(APRENDIZADO, dados)
    return dados


# ---------------------------------------------------------------------------------------------------------------
# CLI

def cmd_ficha(a) -> None:
    project = Path(a.project).resolve()
    paths = project_paths(project)
    proj = load_json(paths["project"])
    if not proj:
        raise EditorError("project.json não encontrado")
    v = a.versao or proj.get("version", 0)
    tl = load_json(paths["versions"] / f"v{v}" / "timeline.json") or load_json(paths["timeline"])
    if not tl:
        raise EditorError("timeline não encontrada (rode run.py all/plan antes)")
    arq = next((str(p) for p in paths["renders"].glob(f"v{v}_*.mp4")), None) if paths["renders"].exists() else None
    f = registrar(project, v, tl, proj, arq)
    log(f"Código do criativo: {f['codigo']}  (v{v}) — use no nome do vídeo/anúncio")
    for k, val in f["caracteristicas"].items():
        log(f"  {NOMES.get(k, k)}: {val}")


def cmd_importar(a) -> None:
    linhas = importar(a.fonte, Path(a.arquivo), Path(a.nomes) if a.nomes else None)
    fs = fichas()
    log(f"{len(linhas)} resultado(s) com código importado(s) de {a.fonte}")
    for r in linhas:
        log(f"  {r['codigo']} {'(ficha OK)' if r['codigo'] in fs else '(sem ficha neste computador)'}")
    if not linhas:
        log("Nenhum anúncio/vídeo com código EV-XXXXXX no nome. Suba os vídeos com o nome do arquivo do editor.")


def cmd_analisar(a) -> None:
    res = analisar(a.metrica, a.min_gasto)
    aplicado = aplicar(res) if a.aplicar and res["metrica"] else None
    txt = relatorio(res, aplicado)
    PASTA.mkdir(parents=True, exist_ok=True)
    RELATORIO.write_text(txt, encoding="utf-8")
    save_json(PASTA / "analise.json", res)
    print(txt)
    log(f"Relatório: {RELATORIO}")


def cmd_status(_a) -> None:
    fs, rs = fichas(), resultados()
    log(f"{len(fs)} vídeos com ficha | {sum(1 for c in rs if c in fs)} com resultado | "
        f"{len([c for c in rs if c not in fs])} códigos sem ficha")
    ap = load_json(APRENDIZADO)
    if ap:
        log(f"Receita aprendida em {ap['gerado_em']} com {ap['videos']} vídeos ({ap['metrica']})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    fi = sub.add_parser("ficha")
    fi.add_argument("project")
    fi.add_argument("--versao", type=int)
    im = sub.add_parser("importar")
    im.add_argument("fonte", choices=["meta", "vturb"])
    im.add_argument("arquivo")
    im.add_argument("--nomes", help="Vturb: JSON do list_players (nome de cada player_id)")
    an = sub.add_parser("analisar")
    an.add_argument("--metrica", default="auto", choices=["auto", *METRICAS])
    an.add_argument("--min-gasto", type=float, default=30.0)
    an.add_argument("--aplicar", action="store_true", help="grava a receita 'aprendida' e a ordem de ganchos")
    sub.add_parser("status")
    a = ap.parse_args()
    {"ficha": cmd_ficha, "importar": cmd_importar, "analisar": cmd_analisar, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main_guard(main)
