#!/usr/bin/env python3
"""Gancho testado: N aberturas diferentes do MESMO vídeo para testar no anúncio (A/B/C).

  ganchos.py <projeto> [--n 3] [--draft] [--so-plano]      (ou: run.py ganchos <projeto> ...)

Cada versão só muda os primeiros ~3 s; o resto do vídeo é idêntico e vem do cache (render por trechos de 4 s:
só os trechos do começo são refeitos). Variações:
  A  pergunta na tela (template `pergunta`) com a frase de dor/pergunta dita no vídeo;
  B  manchete gigante com as palavras mais fortes ditas + zoom de impacto no 1º plano + tremida;
  C  corte de gancho: abre com a frase mais forte (1,5-3 s) e depois segue do começo — só em vídeo com cortes.
     Vídeo sem cortes/já editado: C vira profundidade 2.5D (câmera anda no cenário) com a palavra mais forte;
  D  (com --n 4) palavra gigante atrás da pessoa + clarão.
Os textos são sempre palavras DITAS no vídeo (escolhidas pelo transcript: pergunta, número, "você", promessa,
dor); nada é inventado. O project.json, edl.json e timeline.json voltam exatamente ao estado original no fim
(só o contador de versões continua subindo, para os renders das variações não sobrescreverem versões).

Saída: renders/gancho_A.mp4, _B, _C (...) + qa/ganchos.md (o que muda e o custo HIT/MISS de cada uma) + qa/ganchos.json.
--so-plano: não renderiza; planeja cada variação e compara com o vídeo principal (quais trechos de 4 s mudariam).
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import revisao
from common import EditorError, load_json, log, main_guard, norm, project_paths, save_json

HERE = Path(__file__).resolve().parent
GANCHO_S = 3.0          # janela do gancho (s): só o que começa antes disso é trocado
VOCE = {"voce", "voces", "vc", "seu", "sua", "seus", "suas", "te", "contigo"}
PROMESSA = {"segredo", "descubra", "aprenda", "garanto", "garantido", "nunca", "sempre", "melhor", "ninguem",
            "rapido", "rapida", "facil", "simples", "gratis", "resultado", "resultados", "promocao", "apenas", "agora",
            "hoje", "novo", "nova", "jeito", "metodo", "passo", "dinheiro", "lucro", "vender", "vendas", "venda", "mil",
            "reais", "dobro", "economiza", "economizar", "imperdivel", "unico", "unica", "oferta", "desconto"}
DOR = {"problema", "problemas", "dificil", "cansado", "cansada", "erro", "erros", "errando", "perder", "perdendo",
       "medo", "sofre", "sofrendo", "dor", "travado", "travada", "pior", "chato", "caro", "cara", "falta", "ruim",
       "pare", "chega", "nao", "consegue", "consigo", "frustrado", "frustrada", "desistir", "duvida"}
NUM_PALAVRAS = {"dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "cem",
                "mil", "vinte", "trinta", "cinquenta", "metade", "dobro"}


# ---------------------------------------------------------------------------------------------------------------
# escolha das frases (só palavras ditas)

def _fim_de_frase(w: dict) -> bool:
    return w["w"].endswith((".", "!", "?"))


def _fim_de_oracao(w: dict) -> bool:
    return w["w"].endswith((".", "!", "?", ",", ";", ":"))


def candidatas(words: list[dict], min_s: float, max_s: float, max_palavras: int = 10) -> list[dict]:
    """Trechos contíguos que começam e terminam em fronteira de oração (vírgula/ponto), dentro de uma frase."""
    fala = [(k, w) for k, w in enumerate(words) if not w.get("gancho")]
    inicios = [0] + [j + 1 for j, (_k, w) in enumerate(fala[:-1]) if _fim_de_oracao(w)
                     or fala[j + 1][1]["t0"] - w["t1"] > 0.35]
    out = []
    for s in inicios:
        for e in range(s, min(s + max_palavras, len(fala))):
            ws = [w for _k, w in fala[s:e + 1]]
            if any(_fim_de_frase(w) for w in ws[:-1]):
                break
            fim_ok = e == len(fala) - 1 or _fim_de_oracao(ws[-1]) or fala[e + 1][1]["t0"] - ws[-1]["t1"] > 0.35
            dur = ws[-1]["t1"] - ws[0]["t0"]
            if fim_ok and min_s <= dur <= max_s:
                out.append({"palavras": ws, "texto": " ".join(w["w"] for w in ws), "t0": ws[0]["t0"],
                            "t1": ws[-1]["t1"], "dur": round(dur, 2)})
    return out


def nota(c: dict) -> tuple[float, list[str]]:
    from plan import score_word
    ns = [norm(w["w"]) for w in c["palavras"]]
    pontos, motivos = 0.0, []
    if c["palavras"][-1]["w"].endswith("?"):
        pontos += 4
        motivos.append("pergunta")
    if any(n.isdigit() or n in NUM_PALAVRAS or "%" in n for n in ns):
        pontos += 3
        motivos.append("número")
    if any(n in VOCE for n in ns):
        pontos += 2
        motivos.append("fala com você")
    p = sum(n in PROMESSA for n in ns) + (ns[0] == "como")   # "como ..." no começo = promessa de método
    if p:
        pontos += min(p, 2) * 1.5
        motivos.append("promessa")
    d = sum(n in DOR for n in ns)
    if d:
        pontos += min(d, 2) * 1.5
        motivos.append("dor")
    fortes = sorted((score_word(w["w"]) for w in c["palavras"]), reverse=True)[:2]
    pontos += sum(fortes) / 4
    if _fim_de_frase(c["palavras"][-1]):
        pontos += 1
    if len(c["palavras"]) < 2:
        pontos -= 2
    return round(pontos, 2), motivos


def _sobrepoe(a: dict, b: dict | None) -> bool:
    return bool(b) and a["t0"] < b["t1"] and a["t1"] > b["t0"]


def melhor(cands: list[dict], extra=None, evitar=()) -> dict | None:
    pont = []
    for c in cands:
        n, mot = nota(c)
        n += extra(c, mot) if extra else 0.0
        if any(_sobrepoe(c, e) for e in evitar):
            n -= 5
        pont.append((n, -c["t0"], c, mot))
    if not pont:
        return None
    n, _t, c, mot = max(pont, key=lambda x: (x[0], x[1]))
    return {**c, "nota": round(n, 2), "motivos": mot}


def mais_fortes(c: dict, k: int) -> list[dict]:
    """As k palavras mais fortes do trecho, na ordem em que foram ditas."""
    from plan import score_word
    idx = sorted(range(len(c["palavras"])), key=lambda i: -score_word(c["palavras"][i]["w"]))[:k]
    return [c["palavras"][i] for i in sorted(idx)]


def _limpo(w: str) -> str:
    return w.strip(".,!?:;…\"“”")


# ---------------------------------------------------------------------------------------------------------------
# variações

def abertura(tl: dict) -> dict:
    """O que hoje ocupa o começo (até GANCHO_S) e sai para dar lugar ao gancho novo."""
    manuais = [m["id"] for m in tl.get("motion", []) if m["t0"] < GANCHO_S and not m.get("auto")]
    autos = [m["id"] for m in tl.get("motion", []) if m["t0"] < GANCHO_S and m.get("auto")]
    outros = [g["id"] for g in tl.get("graphics", []) if g["type"] in ("hook", "lower_third") and g["t0"] < GANCHO_S]
    outros += [b["id"] for b in tl.get("behind", []) if b["t0"] < GANCHO_S]
    return {"motion_remove": manuais, "patch_remove": autos + outros}


def _limpa_abertura(ov: dict, ab: dict) -> None:
    ov.setdefault("motion_remove", []).extend(ab["motion_remove"])
    ov["patches"] = revisao.juntar_patches(ov.get("patches", []), [
        {"id": i, "remover": True, "origem": "ganchos.py (abertura trocada)"} for i in ab["patch_remove"]])


def montar(tl: dict, proj: dict, n: int = 3) -> list[dict]:
    """Variações (A, B, C[, D]) com o pedido de cada uma (operações sobre overrides) e a explicação."""
    words = tl["words"]
    # o gancho termina numa troca de plano (1,5-3,2 s): um texto de zona topo faz a cena recuar no plano que ele
    # toca, então passar da troca obrigaria a refazer o plano seguinte (e o que depende dele)
    trocas = [s["t1"] for s in tl["shots"] if 1.5 <= s["t1"] <= GANCHO_S + 0.2]
    dur_g = round(max(trocas) if trocas else min(GANCHO_S, tl["duration"]), 2)
    ab = abertura(tl)
    sem_cortes = bool(proj.get("overrides", {}).get("sem_cortes") or proj.get("ja_editado"))
    cands = candidatas(words, 0.8, 4.5, 12)
    if not cands:
        raise EditorError("Transcrição curta demais para escolher frases de gancho.")
    accent = (tl.get("graphics_cfg") or {}).get("accent")
    out = []

    # A: pergunta/dor dita no vídeo, digitada num card no alto
    a = melhor(cands, lambda c, m: (3 if "pergunta" in m else 0) + (2 if "dor" in m else 0))
    falada_no_inicio = a["t0"] < dur_g
    out.append({"letra": "A", "nome": "pergunta na tela", "frase": a, "dur": dur_g,
                "motion": {"id": "gancho_a", "template": "pergunta", "at": 0, "dur": dur_g,
                           "params": {"text": a["texto"], "label": "PERGUNTA" if a["texto"].endswith("?") else "",
                                      **({"accent": accent} if accent else {}),
                                      # a legenda só some se o card mostra o que está sendo dito naquele instante
                                      "esconde_legenda": falada_no_inicio}},
                "explica": f"card de pergunta no alto digitando \"{a['texto']}\" (dito em {a['t0']:.1f}s; "
                           f"{', '.join(a['motivos']) or 'frase forte'})"})

    # B: manchete gigante com as palavras mais fortes + zoom de impacto no 1º plano + tremida
    curtas = candidatas(words, 0.4, 3.0, 4) or cands      # manchete: 2 a 4 palavras seguidas, ditas assim
    b = melhor(curtas, lambda c, m: (2 if "número" in m else 0) + (1 if "promessa" in m else 0), evitar=[a])
    ws = b["palavras"] if len(b["palavras"]) <= 4 else mais_fortes(b, 3)
    linhas = [" ".join(_limpo(w["w"]).upper() for w in ws[:2]), " ".join(_limpo(w["w"]).upper() for w in ws[2:4])]
    linhas = [x for x in linhas if x]
    destaque = _limpo(mais_fortes(b, 1)[0]["w"]).upper()
    s0 = tl["shots"][0]
    zb = max(s0["zoom0"], 1.0)
    out.append({"letra": "B", "nome": "manchete de impacto + zoom", "frase": b, "dur": dur_g,
                "motion": {"id": "gancho_b", "template": "manchete", "at": 0, "dur": dur_g,
                           "params": {"linhas": linhas, "destaque": [destaque]}},
                "patches": [{"id": s0["id"], "set": {"zoom0": round(zb + 0.3, 3), "zoom1": round(zb + 0.08, 3)},
                             "origem": "ganchos.py (zoom de impacto)"},
                            {"colecao": "fx", "adicionar": {"id": "gancho_fx_b", "type": "tremida", "t": 0.12},
                             "origem": "ganchos.py"}],
                "explica": f"manchete gigante \"{' / '.join(linhas)}\" (palavras ditas em {b['t0']:.1f}s; "
                           f"{', '.join(b['motivos']) or 'palavras fortes'}), começa em zoom {zb + 0.3:.2f} e abre, "
                           f"com tremida na entrada"})

    # C: corte de gancho (frase mais forte antes do começo) ou, sem cortes, profundidade 2.5D com a palavra forte
    if not sem_cortes:
        cc = [c for c in candidatas(words, 1.5, 3.0, 10) if c["t0"] >= dur_g
              and all(w2["i"] == w1["i"] + 1 for w1, w2 in zip(c["palavras"], c["palavras"][1:]))]
        c = melhor(cc, evitar=[a, b]) if cc else None
    else:
        c = None
    if c:
        out.append({"letra": "C", "nome": "corte de gancho", "frase": c, "dur": c["dur"],
                    "corte_gancho": {"i0": c["palavras"][0]["i"], "i1": c["palavras"][-1]["i"]},
                    "explica": f"abre com a frase mais forte \"{c['texto']}\" ({c['dur']:.1f}s, dita em "
                               f"{c['t0']:.1f}s; {', '.join(c['motivos']) or 'frase forte'}) e depois segue do começo"})
    else:
        c = melhor(cands, evitar=[a, b])
        palavra = _limpo(mais_fortes(c, 1)[0]["w"]).upper()
        out.append({"letra": "C", "nome": "profundidade 2.5D com palavra", "frase": c, "dur": dur_g,
                    "motion": {"id": "gancho_c", "template": "profundidade", "at": 0, "dur": dur_g,
                               "params": {"movimento": "dolly", "intensidade": 0.85, "texto": palavra,
                                          "texto_at": 0.3, **({"cor": accent} if accent else {})}},
                    "explica": f"câmera anda no cenário em 2.5D com \"{palavra}\" entre o fundo e a pessoa "
                               f"(dita em {c['t0']:.1f}s)" + (" — vídeo sem cortes/já editado: sem corte de gancho"
                                                              if sem_cortes else "")})

    if n >= 4:
        d = melhor(cands, evitar=[a, b, c])
        palavra = _limpo(mais_fortes(d, 1)[0]["w"]).upper()
        out.append({"letra": "D", "nome": "palavra gigante atrás + clarão", "frase": d, "dur": dur_g,
                    "motion": {"id": "gancho_d", "template": "palavra", "at": 0, "dur": dur_g,
                               "params": {"text": palavra}},
                    "patches": [{"colecao": "fx", "adicionar": {"id": "gancho_fx_d", "type": "clarao", "t": 0.05},
                                 "origem": "ganchos.py"}],
                    "explica": f"\"{palavra}\" gigante atrás da pessoa com clarão na entrada (dita em {d['t0']:.1f}s)"})
    for v in out:
        if "corte_gancho" not in v:
            v["abertura"] = ab
    return out[:max(1, min(n, 4))]


def aplicar(v: dict, proj: dict, transcript: dict) -> dict:
    """Pedido da variação aplicado numa CÓPIA do project.json (o original não é tocado)."""
    p = copy.deepcopy(proj)
    ov = p.setdefault("overrides", {})
    if v.get("abertura"):
        _limpa_abertura(ov, v["abertura"])
    if v.get("motion"):
        ov.setdefault("motion", []).append(copy.deepcopy(v["motion"]))
    if v.get("patches"):
        ov["patches"] = revisao.juntar_patches(ov.get("patches", []), copy.deepcopy(v["patches"]))
    if v.get("corte_gancho"):
        ws = transcript["words"][v["corte_gancho"]["i0"]:v["corte_gancho"]["i1"] + 1]
        ov["corte_gancho"] = {"texto": " ".join(w["w"] for w in ws)}
    return p


# ---------------------------------------------------------------------------------------------------------------
# comparação de trechos (sem render) e execução

def trechos(tl: dict, work: Path) -> dict:
    """Chave de cada trecho de 4 s (mesma regra do render; sem preset/fontes: só o conteúdo)."""
    import render
    cp = [revisao.chave_plano(sh, tl["w"], tl["h"], tl["fps"]) for sh in tl["shots"]]
    tm = render.precisa_mascara(tl)
    cm = {m.get("id"): revisao.chave_motion(m, tl, cp, tm, work) for m in tl.get("motion", [])}
    return {(round(a, 3), round(b, 3)): revisao.chave_trecho(tl, a, b, cp, cm, tm, "-", "-")
            for a, b, _n in revisao.janelas(tl["duration"], tl["fps"])}


def trechos_alterados(base: dict, var: dict, work: Path) -> list[tuple[float, float]]:
    kb, kv = trechos(base, work), trechos(var, work)
    return sorted(j for j in kv if kb.get(j) != kv[j])


def _rodar(script: str, project: Path, *extra: str, saida: Path | None = None) -> None:
    proc = subprocess.run([sys.executable, str(HERE / script), str(project), *extra], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if saida is not None:
        with saida.open("a", encoding="utf-8") as fh:
            fh.write(f"\n### {script}\n{proc.stdout}{proc.stderr}")
    if proc.returncode:
        raise EditorError(f"{script} falhou:\n{(proc.stdout + proc.stderr)[-1500:]}")


def _resumo(rev: dict) -> str:
    return " | ".join(f"{t} {x['HIT']} HIT/{x['MISS']} MISS" for t, x in (rev.get("resumo") or {}).items())


def gerar(project: Path, n: int = 3, draft: bool = False, so_plano: bool = False) -> list[dict]:
    project = Path(project).resolve()
    paths = project_paths(project)
    proj = load_json(paths["project"])
    tr = load_json(paths["transcript"])
    if not proj or not tr:
        raise EditorError("Projeto sem project.json/transcript.json (rode run.py all antes).")
    gerada = paths["work"] / "timeline_gerada.json"
    guardados = {p: p.read_bytes() for p in (paths["project"], paths["edl"], paths["timeline"], gerada,
                                             paths["qa"] / "takes.md") if p.exists()}
    ausentes = [p for p in (paths["edl"], paths["timeline"], gerada) if not p.exists()]
    gdir = paths["work"] / "ganchos"
    gdir.mkdir(parents=True, exist_ok=True)
    resultados = []
    versao = proj.get("version", 0)

    def restaura():
        for p, data in guardados.items():
            p.write_bytes(data)
        for p in ausentes:
            p.unlink(missing_ok=True)
        if not so_plano:   # o contador de versões continua subindo (renders das variações ficam em versions/)
            atual = json.loads(guardados[paths["project"]].decode("utf-8"))
            atual["version"] = max(versao, atual.get("version", 0))
            save_json(paths["project"], atual)

    try:
        log("Gancho testado: planejando o vídeo principal ...")
        _rodar("analyze.py", project)
        _rodar("plan.py", project)
        base = load_json(paths["timeline"])
        proj_base = load_json(paths["project"])     # já com edições manuais capturadas pelo plan.py
        base_prev = None
        if not so_plano:
            try:   # o que já estava fora do cache ANTES das variações (para não culpar o gancho)
                base_prev = {it["janela"][0] for it in revisao.prever(project, base, "ultrafast" if draft else "veryfast").itens
                             if it["tipo"] == "trecho" and it["status"] == "MISS"}
            except Exception:  # noqa: BLE001 — sem vídeo/rostos em cache: segue sem a prévia
                base_prev = None
        variacoes = montar(base, proj_base, n)
        for v in variacoes:
            letra = v["letra"]
            log(f"\n[{letra}] {v['nome']}: {v['explica']}")
            p = aplicar(v, proj_base, tr)
            p["version"] = versao
            save_json(paths["project"], p)
            log_v = gdir / f"log_{letra}.txt"
            log_v.write_text("", encoding="utf-8")
            _rodar("analyze.py", project, saida=log_v)
            _rodar("plan.py", project, saida=log_v)
            tl = load_json(paths["timeline"])
            save_json(gdir / f"timeline_{letra}.json", tl)
            mudou = trechos_alterados(base, tl, paths["work"])
            r = {"letra": letra, "nome": v["nome"], "explica": v["explica"], "frase": v["frase"]["texto"],
                 "frase_t0": round(v["frase"]["t0"], 2), "motivos": v["frase"].get("motivos", []),
                 "duracao": tl["duration"], "duracao_base": base["duration"],
                 "trechos_diferentes": [list(j) for j in mudou]}
            if not so_plano:
                _rodar("render.py", project, *(["--draft"] if draft else []), saida=log_v)
                vv = load_json(paths["project"])["version"]
                versao = vv
                src = next(paths["renders"].glob(f"v{vv}_*.mp4"))
                dst = paths["renders"] / f"gancho_{letra}.mp4"
                shutil.copy2(src, dst)
                src.unlink()      # a cópia com nome de gancho basta (economiza disco)
                rev = load_json(paths["versions"] / f"v{vv}" / "revisao.json") or {}
                miss = [it for it in rev.get("itens", []) if it["status"] == "MISS"]
                r.update(arquivo=str(dst), versao=vv, segundos=rev.get("segundos"), resumo=rev.get("resumo"),
                         miss=[{"tipo": it["tipo"], "id": it["id"], "janela": it.get("janela")} for it in miss],
                         trechos_miss_fora=[it["id"] for it in miss if it["tipo"] == "trecho"
                                            and it["janela"][0] >= 4.0 - 1e-6
                                            and not (base_prev and it["janela"][0] in base_prev)])
                log(f"   -> {dst} | {_resumo(rev)} | render {rev.get('segundos')}s")
            else:
                log(f"   trechos diferentes do vídeo principal: "
                    f"{', '.join(f'{a:.1f}-{b:.1f}s' for a, b in mudou) or 'nenhum'}")
            resultados.append(r)
            restaura()
    finally:
        restaura()
    relatorio(project, resultados, base, draft, so_plano)
    return resultados


def relatorio(project: Path, res: list[dict], base: dict, draft: bool, so_plano: bool) -> None:
    paths = project_paths(project)
    paths["qa"].mkdir(parents=True, exist_ok=True)
    save_json(paths["qa"] / "ganchos.json", res)
    L = ["# Gancho testado", "",
         f"Vídeo principal: {base['duration']:.1f}s, {len(base['shots'])} planos. Cada versão só troca os primeiros "
         f"~{GANCHO_S:.0f} s; o resto é o mesmo vídeo e vem do cache (trechos de 4 s).",
         "Textos na tela = palavras ditas no vídeo (nada inventado). O projeto principal voltou ao estado original.",
         ""]
    if draft:
        L += ["Prévia rápida (--draft): os trechos não reaproveitam o cache do render final (outro preset).", ""]
    for r in res:
        L += [f"## Gancho {r['letra']}: {r['nome']}", "", f"- O que muda: {r['explica']}",
              f"- Frase escolhida: \"{r['frase']}\" (dita em {r['frase_t0']:.1f}s"
              + (f"; {', '.join(r['motivos'])}" if r["motivos"] else "") + ")",
              f"- Duração: {r['duracao']:.2f}s (principal {r['duracao_base']:.2f}s)",
              f"- Trechos de 4 s diferentes do principal: "
              + (", ".join(f"{a:.1f}-{b:.1f}s" for a, b in r["trechos_diferentes"]) or "nenhum")]
        if not so_plano:
            res_ = " | ".join(f"{t} {x['HIT']} HIT/{x['MISS']} MISS" for t, x in (r.get("resumo") or {}).items())
            L += [f"- Arquivo: `{r['arquivo']}` (v{r['versao']}, render {r['segundos']}s)", f"- Custo: {res_}",
                  "- Refeito: " + (", ".join(f"{m['tipo']} {m['id']}" for m in r["miss"]) or "nada")]
            if r["trechos_miss_fora"]:
                L.append(f"- Atenção: trechos depois do gancho refeitos: {', '.join(r['trechos_miss_fora'])}"
                         + (" (o corte de gancho empurra o vídeo inteiro: os planos vêm do cache, a composição não)"
                            if r["duracao"] != r["duracao_base"] else
                            " (provável: o vídeo principal não usava a máscara da pessoa — sem rosto detectado — e "
                            "o gancho de zona topo/2.5D a ligou; a máscara entra na chave de todos os trechos)"))
        L.append("")
    (paths["qa"] / "ganchos.md").write_text("\n".join(L), encoding="utf-8")
    log(f"\nRelatório: {paths['qa'] / 'ganchos.md'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="N aberturas diferentes do mesmo vídeo (teste de gancho no anúncio).")
    ap.add_argument("project")
    ap.add_argument("--n", type=int, default=3, help="quantas variações (1 a 4)")
    ap.add_argument("--draft", action="store_true", help="prévia rápida")
    ap.add_argument("--so-plano", action="store_true", help="não renderiza: só planeja e compara os trechos")
    a = ap.parse_args()
    gerar(Path(a.project), a.n, a.draft, a.so_plano)


if __name__ == "__main__":
    main_guard(main)
