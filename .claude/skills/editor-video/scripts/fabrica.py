#!/usr/bin/env python3
"""Fábrica de variações: 1 vídeo vira N versões para o teste A/B do anúncio (Meta ou Vturb).

Cada versão muda só fatores baratos de renderizar e fáceis de comparar depois:
  gancho  original | A, B, C, D do ganchos.py (só os primeiros ~3 s mudam; o resto vem do cache)
  trilha  a do projeto | outros climas | sem trilha (só o áudio é refeito)
  cta     pílula do estilo | botão animado clicando (`botao_cta`) | textos que você passar em --ctas
As combinações são escolhidas para equilibrar os fatores (cada nível aparece quase o mesmo número de vezes e os
pares se misturam): assim o aprender.py consegue separar o que fez a diferença. A V01 é sempre o CONTROLE
(o vídeo como está). Os textos na tela continuam sendo palavras ditas no vídeo; nada é inventado.

  fabrica.py <projeto> [--n 10] [--fatores gancho,trilha,cta] [--trilhas energia,inspirador,sem]
             [--ctas "COMPRE AGORA|LINK NA BIO"] [--draft] [--so-plano]      (ou: run.py fabrica ...)

Saída: renders/fabrica/V01_EV-XXXXXX.mp4 ... (o código no nome liga o vídeo ao resultado do anúncio),
renders/fabrica/manifesto.csv (para subir no Meta/Vturb) e qa/fabrica.md (o que muda e o custo de cada uma).
O project.json volta exatamente ao estado original no fim.
"""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
import json
import shutil
from pathlib import Path

import ganchos
import revisao
from common import EditorError, load_json, log, main_guard, project_paths, save_json

CLIMAS = ("energia", "inspirador", "suspense", "lofi", "corporativo")


# ---------------------------------------------------------------------------------------------------------------
# níveis e desenho do teste

def niveis(base: dict, proj: dict, fatores: list[str], trilhas: list[str] | None, ctas: list[str] | None) -> dict:
    """{fator: [nível, ...]} — o primeiro nível de cada fator é o do vídeo original (controle)."""
    ov = proj.get("overrides", {})
    out: dict[str, list[dict]] = {}
    if "gancho" in fatores:
        vs = ganchos.montar(base, proj, 4)
        out["gancho"] = [{"rotulo": "original"}] + [{"rotulo": f"{v['letra']} {v['nome']}", "variacao": v} for v in vs]
    if "trilha" in fatores:
        m = ov.get("music") or {}
        atual = (m.get("clima") or "auto") if m.get("auto") else ("arquivo" if m else "sem")
        pedidas = trilhas or [c for c in ("energia", "inspirador", "sem") if c != atual][:2]
        lv = [{"rotulo": atual}]
        for t in pedidas:
            if t != atual and t not in [x["rotulo"] for x in lv]:
                if t != "sem" and t not in CLIMAS:
                    raise EditorError(f"trilha '{t}' não existe ({', '.join(CLIMAS)}, sem)")
                lv.append({"rotulo": t})
        out["trilha"] = lv
    if "cta" in fatores:
        cta_txt = next((g["text"] for g in base.get("graphics", []) if g["type"] == "cta"), None) or ov.get("cta")
        if ctas:
            out["cta"] = [{"rotulo": "original"}] + [{"rotulo": c.strip(), "texto": c.strip()} for c in ctas if c.strip()]
        else:
            out["cta"] = [{"rotulo": "pilula"}, {"rotulo": "botao", "botao": cta_txt or "Saiba Mais"}]
    return {k: v for k, v in out.items() if len(v) > 1}


def desenhar(niv: dict, n: int) -> list[dict]:
    """N combinações: a 1ª é o controle (todos no nível 0); as outras, escolhidas uma a uma, maximizam pares de
    níveis ainda não vistos juntos e equilibram quantas vezes cada nível aparece."""
    fatores = list(niv)
    if not fatores:
        return [{}]
    todas = [dict(zip(fatores, c)) for c in itertools.product(*(range(len(niv[f])) for f in fatores))]
    escolhidas = [todas[0]]
    while len(escolhidas) < min(n, len(todas)):
        vistos = {(a, c[a], b, c[b]) for c in escolhidas for a, b in itertools.combinations(fatores, 2)}
        uso = {(f, i): sum(1 for c in escolhidas if c[f] == i) for f in fatores for i in range(len(niv[f]))}

        def nota(c):
            novos = sum((a, c[a], b, c[b]) not in vistos for a, b in itertools.combinations(fatores, 2))
            return (novos if len(fatores) > 1 else 0) * 10 - sum(uso[(f, c[f])] for f in fatores)
        resto = [c for c in todas if c not in escolhidas]
        escolhidas.append(max(resto, key=nota))
    return [{f: niv[f][c[f]] for f in fatores} for c in escolhidas]


def aplicar(combo: dict, proj: dict, transcript: dict, dur_base: float) -> dict:
    p = copy.deepcopy(proj)
    ov = p.setdefault("overrides", {})
    g = combo.get("gancho") or {}
    if g.get("variacao"):
        p = ganchos.aplicar(g["variacao"], p, transcript)
        ov = p["overrides"]
    t = combo.get("trilha") or {}
    if t and t["rotulo"] not in ("auto", "arquivo") and t is not None:
        if t["rotulo"] == "sem":
            ov.pop("music", None)
        elif t["rotulo"] in CLIMAS:
            ov["music"] = {**{k: v for k, v in (ov.get("music") or {}).items() if k in ("auto", "volume", "motor")},
                           "auto": True, "clima": t["rotulo"]}
    c = combo.get("cta") or {}
    if c.get("texto"):
        ov["cta"] = c["texto"]
    if c.get("botao"):
        ov.setdefault("motion", []).append({"id": "fab_cta", "template": "botao_cta", "at": round(max(dur_base - 2.8, 0), 2),
                                            "dur": 2.6, "params": {"text": c["botao"]}})
    return p


# ---------------------------------------------------------------------------------------------------------------
# execução

def gerar(project: Path, n: int = 10, fatores: list[str] | None = None, trilhas: list[str] | None = None,
          ctas: list[str] | None = None, draft: bool = False, so_plano: bool = False) -> list[dict]:
    import aprender
    project = Path(project).resolve()
    paths = project_paths(project)
    proj = load_json(paths["project"])
    tr = load_json(paths["transcript"])
    if not proj or not tr:
        raise EditorError("Projeto sem project.json/transcript.json (rode run.py all antes).")
    fatores = fatores or ["gancho", "trilha", "cta"]
    gerada = paths["work"] / "timeline_gerada.json"
    guardados = {p: p.read_bytes() for p in (paths["project"], paths["edl"], paths["timeline"], gerada,
                                             paths["qa"] / "takes.md") if p.exists()}
    ausentes = [p for p in (paths["edl"], paths["timeline"], gerada) if not p.exists()]
    fdir = paths["renders"] / "fabrica"
    logs = paths["work"] / "fabrica"
    logs.mkdir(parents=True, exist_ok=True)
    versao = proj.get("version", 0)
    resultados = []

    def restaura():
        for p, data in guardados.items():
            p.write_bytes(data)
        for p in ausentes:
            p.unlink(missing_ok=True)
        if not so_plano:   # o contador de versões continua subindo (cada variação é uma versão em versions/)
            atual = json.loads(guardados[paths["project"]].decode("utf-8"))
            atual["version"] = max(versao, atual.get("version", 0))
            save_json(paths["project"], atual)

    try:
        log("Fábrica: planejando o vídeo principal ...")
        ganchos._rodar("analyze.py", project)
        ganchos._rodar("plan.py", project)
        base = load_json(paths["timeline"])
        proj_base = load_json(paths["project"])
        niv = niveis(base, proj_base, fatores, trilhas, ctas)
        combos = desenhar(niv, n)
        log(f"   fatores: " + " | ".join(f"{f}: {', '.join(x['rotulo'] for x in v)}" for f, v in niv.items()))
        log(f"   {len(combos)} versões (de {max(1, len(list(itertools.product(*niv.values()))))} combinações possíveis)")
        for i, combo in enumerate(combos, 1):
            nome = f"V{i:02d}"
            desc = {f: combo[f]["rotulo"] for f in combo}
            log(f"\n[{nome}] " + ("CONTROLE (o vídeo como está)" if i == 1 else
                                   " | ".join(f"{f}: {r}" for f, r in desc.items())))
            p = aplicar(combo, proj_base, tr, base["duration"])
            p["version"] = versao
            save_json(paths["project"], p)
            lg = logs / f"log_{nome}.txt"
            lg.write_text("", encoding="utf-8")
            ganchos._rodar("analyze.py", project, saida=lg)
            ganchos._rodar("plan.py", project, saida=lg)
            tl = load_json(paths["timeline"])
            if combo.get("cta", {}).get("botao") and abs(tl["duration"] - base["duration"]) > 0.05:
                p = aplicar(combo, proj_base, tr, tl["duration"])   # corte de gancho mudou a duração: botão no fim
                p["version"] = versao
                save_json(paths["project"], p)
                ganchos._rodar("plan.py", project, saida=lg)
                tl = load_json(paths["timeline"])
            mudou = ganchos.trechos_alterados(base, tl, paths["work"])
            audio_muda = revisao.chave_audio(tl, ["-"]) != revisao.chave_audio(base, ["-"])
            r = {"versao_fabrica": nome, "fatores": desc, "duracao": tl["duration"],
                 "trechos_diferentes": [list(j) for j in mudou], "audio_muda": audio_muda}
            if not so_plano:
                ganchos._rodar("render.py", project, *(["--draft"] if draft else []), saida=lg)
                vv = load_json(paths["project"])["version"]
                versao = vv
                src = next(paths["renders"].glob(f"v{vv}_*.mp4"))
                cod = aprender.codigo(project, vv)
                fdir.mkdir(parents=True, exist_ok=True)
                dst = fdir / f"{nome}_{cod}.mp4"
                shutil.move(str(src), dst)
                rev = load_json(paths["versions"] / f"v{vv}" / "revisao.json") or {}
                aprender.registrar(project, vv, tl, p, str(dst),
                                   extra={"fabrica_" + f: rot for f, rot in desc.items()})
                r.update(arquivo=str(dst), codigo=cod, versao=vv, segundos=rev.get("segundos"),
                         resumo=rev.get("resumo"))
                log(f"   -> {dst.name} | {ganchos._resumo(rev)} | render {rev.get('segundos')}s")
            else:
                log("   muda: " + (", ".join(f"{a:.1f}-{b:.1f}s" for a, b in mudou) or "nenhum trecho de vídeo")
                    + (" + áudio" if audio_muda else ""))
            resultados.append(r)
            restaura()
    finally:
        restaura()
    relatorio(project, resultados, base, niv, so_plano)
    return resultados


def relatorio(project: Path, res: list[dict], base: dict, niv: dict, so_plano: bool) -> None:
    paths = project_paths(project)
    paths["qa"].mkdir(parents=True, exist_ok=True)
    save_json(paths["qa"] / "fabrica.json", res)
    if not so_plano and res:
        fdir = paths["renders"] / "fabrica"
        with (fdir / "manifesto.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["versao", "codigo", "arquivo", *niv.keys(), "duracao_s"])
            for r in res:
                w.writerow([r["versao_fabrica"], r["codigo"], Path(r["arquivo"]).name,
                            *(r["fatores"].get(f, "") for f in niv), f"{r['duracao']:.2f}"])
    total_trechos = len(revisao.janelas(base["duration"], base["fps"]))
    L = ["# Fábrica de variações", "",
         f"Vídeo principal: {base['duration']:.1f}s. {len(res)} versões; a V01 é o CONTROLE (o vídeo como está).",
         "Fatores: " + " | ".join(f"**{f}**: {', '.join(x['rotulo'] for x in v)}" for f, v in niv.items()), "",
         "Como testar: suba TODAS no mesmo conjunto de anúncios (Meta) ou num teste A/B do Vturb, com o nome do "
         "arquivo (o código EV-... é o que liga o vídeo ao resultado). Depois de uns dias: `aprender.py importar` "
         "e `aprender.py analisar` mostram qual fator ganhou.", "",
         "| versão | " + " | ".join(niv) + " | trechos de vídeo refeitos | áudio | arquivo |",
         "|---|" + "---|" * len(niv) + "---|---|---|"]
    for r in res:
        L.append(f"| {r['versao_fabrica']} | " + " | ".join(r["fatores"].get(f, "") for f in niv)
                 + f" | {len(r['trechos_diferentes'])}/{total_trechos} | {'refeito' if r['audio_muda'] else 'igual'} | "
                 + (f"`{Path(r['arquivo']).name}`" if r.get("arquivo") else "(só plano)") + " |")
    (paths["qa"] / "fabrica.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"\nRelatório: {paths['qa'] / 'fabrica.md'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="1 vídeo -> N versões equilibradas para o teste A/B do anúncio.")
    ap.add_argument("project")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--fatores", default="gancho,trilha,cta", help="gancho,trilha,cta (qualquer subconjunto)")
    ap.add_argument("--trilhas", help="climas a testar, ex.: energia,inspirador,sem")
    ap.add_argument("--ctas", help="textos de chamada a testar, separados por |")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--so-plano", action="store_true", help="não renderiza: mostra as versões e o que cada uma refaz")
    a = ap.parse_args()
    fat = [f.strip() for f in a.fatores.split(",") if f.strip()]
    if set(fat) - {"gancho", "trilha", "cta"}:
        raise EditorError("--fatores aceita: gancho, trilha, cta")
    gerar(Path(a.project), a.n, fat, [t.strip() for t in a.trilhas.split(",")] if a.trilhas else None,
          a.ctas.split("|") if a.ctas else None, a.draft, a.so_plano)


if __name__ == "__main__":
    main_guard(main)
