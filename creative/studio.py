#!/usr/bin/env python3
"""Creative Studio — o fluxo executável do diretor (Windows, Mac e Linux; só biblioteca padrão).

A skill /creative-studio decide; este script faz a parte que não pode depender de memória: monta o mapa de cenas,
escolhe a equipe mínima, confere propostas contra templates, ids, comandos e decisões, aplica com o edit.py,
guarda o histórico e escreve o relatório.

  python creative/studio.py iniciar   <proj> --pedido "..." [--objetivo venda --tipo anuncio --nivel maximo ...]
  python creative/studio.py catalogo  [--json]                      templates, operações do edit.py, fx, gaps
  python creative/studio.py cenas     <proj> [--de 12 --ate 16]     cenas (fala, tempo, elementos com id)
  python creative/studio.py equipe    <proj> --pedido "..."          equipe mínima (JSON para o decision-plan)
  python creative/studio.py rascunho  <proj> --pedido "..."          creative/decision-plan.json inicial (não aprovado)
  python creative/studio.py verificar <proj> <arquivo.json> <schema> schema + templates + ids + comandos + decisões
  python creative/studio.py aprovar   <proj> [shot-plan.json ...]    junta as propostas, recusa conflito aberto, aprova
  python creative/studio.py aplicar   <proj> [--so-previa] [--preset draft|final|max]   aplica o aprovado (dry-run antes)
  python creative/studio.py qa        <proj> <qa-report.json>        registra o QA; falha => correções para a volta
  python creative/studio.py relatorio <proj>                         creative/relatorio-vN.md da última versão
  python creative/studio.py historico <proj>                         linha do tempo das decisões do projeto
  python creative/studio.py travar|liberar <proj> <id> --motivo "..." trava/libera um elemento aprovado pelo usuário
  python creative/studio.py status    <proj>                         o que já existe e qual é o próximo passo

Tudo fica em <proj>/creative/. O histórico (historico.jsonl) só cresce: decisões anteriores não se perdem.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import validar  # noqa: E402

AGENTES = ["conversion-strategist", "art-director", "senior-editor", "motion-3d-artist", "sound-designer",
           "render-engineer", "quality-director"]
# agentes que propõem mudanças (precisam de shot-plan antes da aprovação)
PROPOEM = {"conversion-strategist", "art-director", "motion-3d-artist", "sound-designer"}
# ações que mexem num elemento existente (o alvo precisa existir na timeline)
MEXEM_EM_ID = {"--patch", "--patch-remove", "--patch-clear", "--motion-remove"}
CTA_TEMPLATES = {"botao_cta", "comentario", "final"}
GAPS = [
    {"acao": "SFX avulso num instante sem animação", "motivo": "o som vem das animações (D08)",
     "alternativa": "pôr um ícone/palavra com som no instante"},
    {"acao": "trocar o som de uma animação específica", "motivo": "som escolhido por tipo de animação",
     "alternativa": "trocar o template"},
    {"acao": "equalização por trecho ou biblioteca de trilhas", "motivo": "só --music com arquivo do usuário"},
    {"acao": "estilo de legenda diferente por cena", "motivo": "legenda é global (--caption-size/--caption-y)"},
    {"acao": "gerar imagem/vídeo de B-roll", "motivo": "o editor só insere arquivos",
     "alternativa": "gerar com skill de imagem/vídeo e usar --add-broll"},
    {"acao": "cortar/acelerar vídeo já editado", "motivo": "D02"},
]


# ---------------------------------------------------------------------------------------------- caminhos e E/S
def editor_video() -> Path:
    """Pasta da skill editor-video: variável, repositório, instalação ao lado desta skill ou ~/.claude."""
    candidatos = [Path(os.environ["EDITOR_VIDEO_SK"])] if os.environ.get("EDITOR_VIDEO_SK") else []
    candidatos += [AQUI.parent / ".claude" / "skills" / "editor-video",      # repositório
                   AQUI.parent.parent / "editor-video",                       # skills/creative-studio/creative
                   Path.home() / ".claude" / "skills" / "editor-video"]
    for c in candidatos:
        if (c / "scripts" / "edit.py").exists():
            return c
    sys.exit("Não achei a skill editor-video (defina EDITOR_VIDEO_SK com a pasta dela).")


def norm(palavra: str) -> str:
    """Mesma normalização do editor (common.norm): minúscula, sem acento, sem pontuação."""
    p = unicodedata.normalize("NFKD", palavra.lower())
    return re.sub(r"[^a-z0-9%$]", "", "".join(c for c in p if not unicodedata.combining(c)))


def ocorrencias(words: list[dict], trecho: str, depois: float = 0.0, ultima: bool = False) -> list[float]:
    """Instantes em que o trecho é falado (o editor ancora na PRIMEIRA ocorrência); ultima=True dá o fim da última
    palavra de cada ocorrência (é assim que o editor resolve o 'until')."""
    alvo = [n for n in (norm(x) for x in trecho.split()) if n]
    seq = [norm(w["w"]) for w in words]
    return [round(words[i + len(alvo) - 1]["t1"] if ultima else words[i]["t0"], 2)
            for i in range(len(seq) - len(alvo) + 1)
            if alvo and words[i]["t0"] >= depois - 0.05 and seq[i:i + len(alvo)] == alvo]


def ler(p: Path, padrao=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else padrao


def gravar(p: Path, dado) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def cdir(proj: Path) -> Path:
    return proj / "creative"


def agora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def historico(proj: Path) -> list[dict]:
    f = cdir(proj) / "historico.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def registrar(proj: Path, evento: str, **dados) -> dict:
    h = historico(proj)
    item = {"n": len(h) + 1, "data": agora(), "evento": evento, **dados}
    cdir(proj).mkdir(parents=True, exist_ok=True)
    with open(cdir(proj) / "historico.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def travas(proj: Path) -> dict[str, dict]:
    """ids travados pelo usuário (o último evento travar/liberar de cada id vale)."""
    out: dict[str, dict] = {}
    for e in historico(proj):
        if e["evento"] == "travar":
            out[e["id"]] = e
        elif e["evento"] == "liberar":
            out.pop(e["id"], None)
    return out


def rodar(sk: Path, script: str, proj: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(sk / "scripts" / script), str(proj), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


# ---------------------------------------------------------------------------------------------- catálogo
def catalogo(sk: Path | None = None) -> dict:
    """O que o editor sabe fazer de verdade: templates, flags do edit.py, fx e estilos."""
    sk = sk or editor_video()
    descr: dict[str, str] = {}
    md = sk / "references" / "motion.md"
    if md.exists():
        for m in re.finditer(r"^\|\s*`(\w+)`\s*\|[^|]*\|([^|]+)\|", md.read_text(encoding="utf-8"), re.M):
            descr.setdefault(m.group(1), m.group(2).strip())
    templates = sorted(p.stem for p in (sk / "assets" / "motion" / "templates").glob("*.html"))
    fonte = (sk / "scripts" / "edit.py").read_text(encoding="utf-8")
    flags = sorted(set(re.findall(r'add_argument\("(--[\w-]+)"', fonte)))
    fx = re.search(r"tipo@palavra \(([^)]+)\)", fonte)
    return {"templates": {t: descr.get(t, "") for t in templates},
            "operacoes": flags,
            "fx": [x.strip() for x in fx.group(1).split(",")] if fx else [],
            "estilos": ["pro_clean", "anuncio_conversao", "reels_viral", "editorial_premium"],
            "gaps": GAPS}


# ---------------------------------------------------------------------------------------------- timeline e cenas
def timeline(proj: Path) -> dict:
    tl = ler(proj / "timeline.json")
    if tl is None:
        sys.exit(f"{proj}: sem timeline.json — rode antes: run.py plan {proj}")
    return tl


def ids_da_timeline(tl: dict) -> set[str]:
    return {x["id"] for k, v in tl.items() if isinstance(v, list) for x in v if isinstance(x, dict) and "id" in x}


def cenas(tl: dict, de: float | None = None, ate: float | None = None) -> list[dict]:
    """Cenas = frases (pontuação final ou pausa > 0,6 s), no mínimo 1,5 s, com os elementos que caem nelas."""
    words = tl.get("words", [])
    grupos, atual = [], []
    for i, w in enumerate(words):
        atual.append(w)
        prox = words[i + 1] if i + 1 < len(words) else None
        fim = w["w"].rstrip()[-1:] in ".?!" or prox is None or prox["t0"] - w["t1"] > 0.6
        if fim and (atual[-1]["t1"] - atual[0]["t0"] >= 1.5 or prox is None):
            grupos.append(atual)
            atual = []
    out = []
    for n, g in enumerate(grupos, 1):
        t0, t1 = round(g[0]["t0"], 2), round(g[-1]["t1"], 2)
        if (de is not None and t1 < de) or (ate is not None and t0 > ate):
            continue
        el = []
        for k in ("motion", "graphics", "behind", "broll", "fx"):
            for x in tl.get(k, []):
                a, b = x.get("t0", x.get("t")), x.get("t1", x.get("t"))
                if a is not None and a < t1 and b >= t0:
                    el.append({"colecao": k, "id": x.get("id", ""), "template": x.get("template") or x.get("type"),
                               "t0": a, "t1": b})
        out.append({"cena": f"c{n}", "t0": t0, "t1": t1, "fala": " ".join(w["w"] for w in g), "elementos": el})
    return out


# ---------------------------------------------------------------------------------------------- equipe mínima
REGRAS = [  # (agente, padrão no pedido, motivo)
    ("conversion-strategist", r"anúnci|anunci|venda|vend|criativo|vsl|oferta|gancho|cta|convers|tráfego|trafego",
     "função comercial de cada frase, gancho e CTA"),
    ("art-director", r"visual|bonit|profission|qualidade|melhor|cena|anima|card|fundo|cor|polu|edita|criativo|nível|nivel",
     "linguagem visual das cenas"),
    ("motion-3d-artist", r"\b3d\b|efeito novo|animação nova|animacao nova|não existe|nao existe|template novo",
     "animação que os templates não fazem ou ajuste de qualidade de template"),
    ("sound-designer", r"som|trilha|música|musica|volume|áudio|audio|sfx|lufs|barulho", "trilha, efeitos e volume"),
    ("render-engineer", r"render|lent|erro|trav|sincron|cache|quadro|arquivo|pesad|demor", "custo, erro ou arquivo"),
    ("quality-director", r"confer|qa\b|revis[ae] a vers|checa|verifica|aprova", "conferir a versão renderizada"),
]
PONTUAL = r"^(troca|muda|tira|remove|apaga|corrige|coloca|põe|poe)\b"


def janela_do_pedido(pedido: str) -> tuple[float, float] | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*s?\s*(?:a|-|–|até|ate)\s*(\d+(?:[.,]\d+)?)\s*s", pedido)
    return (float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))) if m else None


def equipe(proj: Path, pedido: str) -> list[dict]:
    """Regra do diretor (SKILL.md, 'Quem convocar'), executável: o mínimo suficiente, nunca todos por padrão."""
    p = pedido.lower()
    tl = timeline(proj)
    brief = ler(cdir(proj) / "brief.json", {})
    jan = janela_do_pedido(p)
    cs = cenas(tl, *jan) if jan else cenas(tl)
    ids = [c["cena"] for c in cs]
    escolhidos: dict[str, str] = {}
    for ag, rx, motivo in REGRAS:
        if re.search(rx, p):
            escolhidos[ag] = motivo
    venda = brief.get("objetivo") in {"venda", "vsl", "lead", "clique"} or brief.get("tipo") in {"anuncio", "vs", "vsl", "produto"}
    completa = not jan and re.search(r"edita|completo|do zero|criativo|profission|nível|nivel|máxima|maxima", p)
    if completa and venda:
        escolhidos.setdefault("conversion-strategist", "edição completa de criativo de venda")
        escolhidos.setdefault("art-director", "edição completa: linguagem visual")
        escolhidos.setdefault("quality-director", "QA da versão final")
    if jan:  # revisão de algumas cenas: arte só nessas cenas, sem estrategista (a não ser que o pedido fale de venda)
        escolhidos.setdefault("art-director", f"revisão das cenas {jan[0]:g}-{jan[1]:g} s")
    if re.match(PONTUAL, p) and len(p.split()) <= 12 and not jan and not completa:
        escolhidos = {k: v for k, v in escolhidos.items() if k in {"render-engineer", "sound-designer"}}
    if escolhidos.keys() & PROPOEM:
        escolhidos["senior-editor"] = "aplicar o plano aprovado com edit.py e medir com dry-run"
    return [{"agente": a, "motivo": escolhidos[a], "cenas": ids if a in PROPOEM | {"quality-director"} else ["todas"]}
            for a in AGENTES if a in escolhidos]


# ---------------------------------------------------------------------------------------------- verificação
def _alvo(flag: str, valor: str) -> str | None:
    if flag in ("--patch", "--patch-remove"):
        return valor.split(".", 1)[0].split("=", 1)[0] or None
    if flag in ("--patch-clear", "--motion-remove"):
        return valor
    return None


def acoes_de(dado: dict, schema: str) -> list[tuple[str, dict]]:
    """(cena, ação) de um shot-plan; as do decision-plan vêm dos elementos do mapa."""
    if schema == "shot-plan":
        return [(c["cena"], a) for c in dado.get("cenas", []) for a in c.get("acoes", [])]
    if schema == "qa-report":
        return [("qa", {"comando": cmd, "tipo": "patch"}) for c in dado.get("checks", []) for cmd in
                ([c["correcao"]] if c.get("correcao") and isinstance(c["correcao"][0], str) and c["correcao"][0].startswith("--") else [])]
    return []


def verificar(proj: Path, dado: dict, schema: str, cat: dict | None = None) -> tuple[list[str], list[str]]:
    """(erros, avisos). Erro = não pode seguir; aviso = o diretor decide."""
    erros = validar.validar(dado, schema)
    if erros:
        return erros, []
    avisos: list[str] = []
    cat = cat or catalogo()
    tl = timeline(proj)
    ids = ids_da_timeline(tl)
    trav = travas(proj)
    brief = ler(cdir(proj) / "brief.json", {})
    dur = tl.get("duration", 1e9)
    templates = set(cat["templates"])

    def tpl(nome: str | None, onde: str) -> None:
        if nome and nome not in templates:
            erros.append(f"{onde}: template '{nome}' não existe (veja: studio.py catalogo)")

    if schema == "decision-plan":
        for i, m in enumerate(dado["mapa"]):
            if m["t0"] >= m["t1"] or m["t1"] > dur + 0.05:
                erros.append(f"mapa[{i}]: tempo {m['t0']}-{m['t1']} fora do vídeo ({dur:.2f} s)")
            if m["elemento"]["tipo"] == "motion":
                tpl(m["elemento"].get("template"), f"mapa[{i}]")
        conv = {c["agente"] for c in dado["convocados"]}
        if conv >= set(AGENTES):
            erros.append("convocados: a equipe inteira foi chamada; convoque só o mínimo (SKILL.md, 'Quem convocar')")
        aprovadas = {d["id"] for d in ler(AQUI / "approved-decisions.json")["decisoes"]}
        for d in dado.get("decisoes_respeitadas", []):
            if d not in aprovadas:
                erros.append(f"decisoes_respeitadas: '{d}' não existe em approved-decisions.json")
        ctas = sorted((m["t0"], m["t1"]) for m in dado["mapa"]
                      if m["elemento"].get("template") in CTA_TEMPLATES - {"final"})
        if any(b[0] < a[1] for a, b in zip(ctas, ctas[1:])):
            erros.append("D07: dois CTAs ao mesmo tempo no mapa")

    janela = {c["cena"]: (c["t0"], c["t1"]) for c in dado.get("cenas", [])} if schema == "shot-plan" else {}
    for cena, a in acoes_de(dado, schema):
        cmd = a.get("comando") or []
        if schema == "shot-plan" and a.get("suportado") is False:
            if cmd:
                avisos.append(f"{cena}: ação marcada como gap traz comando (será ignorado): {cmd}")
            continue
        if schema == "shot-plan" and a.get("tipo") != "nenhuma" and not cmd:
            erros.append(f"{cena}: ação '{a.get('tipo')}' sem comando e sem suportado=false (gap)")
        for j, tok in enumerate(cmd):
            if not tok.startswith("--"):
                continue
            flag = tok.split("=", 1)[0]
            if flag not in cat["operacoes"]:
                erros.append(f"{cena}: '{flag}' não é operação do edit.py (sem executor inventado)")
                continue
            val = cmd[j + 1] if j + 1 < len(cmd) else ""
            alvo = _alvo(flag, val)
            if flag in MEXEM_EM_ID and alvo not in ids and not (flag == "--motion-remove" and alvo.isdigit()):
                erros.append(f"{cena}: '{alvo}' não existe na timeline (ids: studio.py cenas {proj})")
            if alvo and alvo in trav:
                erros.append(f"{cena}: '{alvo}' está travado pelo usuário ({trav[alvo].get('motivo', '')}); "
                             f"só com 'studio.py liberar' após o usuário pedir")
            if flag == "--motion":
                try:
                    mo = ler(Path(val[1:]) if Path(val[1:]).is_absolute() else proj / val[1:], {}) \
                        if val.startswith("@") else json.loads(val)
                except (json.JSONDecodeError, OSError):
                    mo = {}
                for item in mo if isinstance(mo, list) else [mo]:
                    tpl(item.get("template"), cena)
                    at = item.get("at")
                    if isinstance(at, str) and cena in janela:
                        occ = ocorrencias(tl.get("words", []), at)
                        j0, j1 = janela[cena]
                        if not occ:
                            erros.append(f"{cena}: âncora '{at}' não foi falada (copie do transcript/studio.py cenas)")
                        elif not j0 - 0.5 <= occ[0] <= j1 + 0.5:
                            erros.append(f"{cena}: âncora ambígua '{at}' é falada em {occ} s e o editor usa a 1ª "
                                         f"({occ[0]} s), fora da cena {j0}-{j1} s — use um trecho que só exista nela")
                        else:
                            # mesma conta do plan.py: início 0,1 s antes da âncora; fim na última palavra do
                            # 'until' (+0,2 s) ou 'dur' (3 s); menos de 1 s o editor descarta
                            t0 = max(occ[0] - 0.1, 0)
                            fim = ocorrencias(tl.get("words", []), item["until"], t0, ultima=True) \
                                if isinstance(item.get("until"), str) else []
                            t1 = min(fim[0] + 0.2 if fim else t0 + float(item.get("dur", 3.0)), dur)
                            if isinstance(item.get("until"), str) and not fim:
                                erros.append(f"{cena}: 'until' '{item['until']}' não é falado depois de '{at}'")
                            elif t1 - t0 < 1.0:
                                erros.append(f"{cena}: a animação ficaria com {t1 - t0:.2f} s ({t0:.2f}-{t1:.2f}); "
                                             f"menos de 1 s o editor descarta — estenda o 'until' ou use 'dur'")
                    if item.get("id") in trav:
                        erros.append(f"{cena}: '{item['id']}' está travado pelo usuário")
            if flag == "--fx" and val.split("@", 1)[0] not in cat["fx"]:
                erros.append(f"{cena}: fx '{val.split('@', 1)[0]}' não existe ({', '.join(cat['fx'])})")
            if brief.get("ja_editado") and (flag in ("--cut", "--velocidade") or (flag == "--sem-cortes" and val == "off")):
                erros.append(f"{cena}: D02 — vídeo já editado não se corta nem acelera ({flag})")
        if schema == "shot-plan" and a.get("motion"):
            tpl(a["motion"].get("template"), cena)
    if schema == "shot-plan":
        for c in dado["cenas"]:
            if c["t0"] >= c["t1"] or c["t1"] > dur + 0.05:
                erros.append(f"{c['cena']}: tempo {c['t0']}-{c['t1']} fora do vídeo ({dur:.2f} s)")
    return erros, avisos


# ---------------------------------------------------------------------------------------------- aprovação
def conflitos(planos: list[dict]) -> list[str]:
    """Mesmo alvo com comandos diferentes vindos de especialistas diferentes = conflito aberto."""
    por_alvo: dict[str, set] = {}
    for p in planos:
        for _, a in acoes_de(p, "shot-plan"):
            if a.get("suportado") is False or not a.get("comando"):
                continue
            chave = a.get("alvo_id") or next((_alvo(t, a["comando"][i + 1]) for i, t in enumerate(a["comando"][:-1])
                                              if _alvo(t, a["comando"][i + 1])), None)
            if chave:
                por_alvo.setdefault(chave, set()).add((p["agente"], json.dumps(a["comando"], ensure_ascii=False)))
    out = []
    for alvo, props in sorted(por_alvo.items()):
        if len({ag for ag, _ in props}) > 1 and len({c for _, c in props}) > 1:
            out.append(f"{alvo}: " + " x ".join(f"{ag} {c}" for ag, c in sorted(props)))
    return out


def aprovar(proj: Path, arquivos: list[Path]) -> dict:
    cat = catalogo()
    dp_f = cdir(proj) / "decision-plan.json"
    dp = ler(dp_f)
    if dp is None:
        raise SystemExit(f"Falta {dp_f} (rode: studio.py rascunho {proj} --pedido ...)")
    erros, avisos = verificar(proj, dp, "decision-plan", cat)
    planos = []
    for f in arquivos:
        p = ler(f)
        e, a = verificar(proj, p, "shot-plan", cat)
        erros += [f"{f.name}: {x}" for x in e]
        avisos += [f"{f.name}: {x}" for x in a]
        planos.append(p)
    conv = {c["agente"]: set(c["cenas"]) for c in dp["convocados"]}
    for p in planos:
        if p["agente"] not in conv:
            erros.append(f"{p['agente']}: propôs sem ter sido convocado")
            continue
        fora = {c["cena"] for c in p["cenas"]} - conv[p["agente"]] - {"todas"}
        if fora and "todas" not in conv[p["agente"]]:
            erros.append(f"{p['agente']}: mexeu em cenas fora do escopo {sorted(fora)}")
    faltam = (set(conv) & PROPOEM) - {p["agente"] for p in planos}
    if faltam:
        erros.append(f"convocados sem proposta: {sorted(faltam)}")
    abertos = conflitos(planos)
    if abertos:
        erros += [f"conflito aberto (resolva no decision-plan.conflitos e tire a opção perdedora do shot-plan): {c}"
                  for c in abertos]
    if erros:
        return {"aprovado": False, "erros": erros, "avisos": avisos}
    ops, gaps = [], list(dp.get("gaps", []))
    for p in planos:
        for cena, a in acoes_de(p, "shot-plan"):
            if a.get("suportado") is False:
                gaps.append({"acao": f"{cena}: {a.get('tipo')}", "motivo": a.get("justificativa", ""),
                             **({"alternativa": a["risco"]} if a.get("risco") else {})})
            elif a.get("comando"):
                op = {"comando": a["comando"], "motivo": f"{p['agente']} {cena}: {a['justificativa']}"}
                if a.get("alvo_id"):
                    op["alvo_id"] = a["alvo_id"]
                if op["comando"] not in [o["comando"] for o in ops]:
                    ops.append(op)
    dp["aprovado"] = True
    dp["gaps"] = gaps
    gravar(dp_f, dp)
    janelas = sorted({(c["t0"], c["t1"]) for p in planos for c in p["cenas"]})
    gravar(cdir(proj) / "aprovado.json", {"versao_plano": dp["versao"], "operacoes": ops, "janelas": janelas,
                                          "shot_plans": [str(f) for f in arquivos]})
    registrar(proj, "aprovacao", versao_plano=dp["versao"], operacoes=len(ops), convocados=sorted(conv),
              conflitos=dp.get("conflitos", []), gaps=gaps, decisoes=dp.get("decisoes_respeitadas", []))
    return {"aprovado": True, "operacoes": ops, "gaps": gaps, "avisos": avisos}


# ---------------------------------------------------------------------------------------------- aplicação
def aplicar(proj: Path, so_previa: bool = False, pedido: str | None = None, preset: str = "draft") -> dict:
    sk = editor_video()
    ap = ler(cdir(proj) / "aprovado.json")
    dp = ler(cdir(proj) / "decision-plan.json", {})
    if not ap or not dp.get("aprovado"):
        raise SystemExit("Nada aprovado ainda (rode: studio.py aprovar).")
    if not ap["operacoes"]:
        raise SystemExit("O plano aprovado não tem operações (só gaps).")
    args = [t for o in ap["operacoes"] for t in o["comando"]]
    # o preset entra na chave dos trechos: a prévia de custo usa o mesmo preset do próximo render
    flag_preset = {"draft": ["--draft"], "max": ["--max"]}.get(preset, [])
    dry = rodar(sk, "edit.py", proj, *args, "--dry-run", *flag_preset)
    if dry.returncode != 0:
        raise SystemExit(f"dry-run falhou:\n{dry.stdout[-1500:]}\n{dry.stderr[-1500:]}")
    miss = re.findall(r"MISS\s+(\w+)\s+(\S+)\s+\[([\d.]+)-([\d.]+)s\]", dry.stdout)
    resumo = next((l for l in dry.stdout.splitlines() if l.startswith("Resumo:")), "")
    hit = sum(int(x) for x in re.findall(r"(\d+) HIT", resumo))
    # MISS de trecho/motion fora das janelas do plano (±4 s do trecho) = investigar antes de renderizar
    jan = ap.get("janelas", [])
    vers = sorted(int(p.name[1:]) for p in (proj / "versions").glob("v*") if p.name[1:].isdigit()) \
        if (proj / "versions").exists() else []
    # sem render anterior não há cache: tudo é MISS e isso não é efeito do plano
    fora = [f"{t}:{i}" for t, i, a, b in miss if t in ("motion", "trecho") and jan and vers and
            not any(float(a) < j1 + 4 and float(b) > j0 - 4 for j0, j1 in jan)]
    rev = {"pedido": pedido or dp.get("gancho", "") or "plano aprovado do Creative Studio",
           "operacoes": ap["operacoes"],
           "dry_run": {"resumo": resumo, "miss": [f"{t}:{i}" for t, i, _, _ in miss], "hit": hit},
           "preset": preset,
           "rollback_para": vers[-1] if vers else None,
           "conflita_com_aprovadas": []}
    if fora:
        rev["observacoes"] = "MISS fora das cenas do plano (investigar antes do render): " + ", ".join(fora)
    elif not vers:
        rev["observacoes"] = "primeiro render do projeto: sem cache, todos os componentes são MISS"
    if not so_previa:
        r = rodar(sk, "edit.py", proj, *args, "--no-render", "--note", f"creative-studio plano v{dp['versao']}")
        if r.returncode != 0:
            raise SystemExit(f"edit.py falhou (o editor já desfez):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    e = validar.validar(rev, "revision-plan")
    if e:
        raise SystemExit("revision-plan inválido: " + "; ".join(e))
    n = len(list(cdir(proj).glob("revision-plan-*.json"))) + 1
    gravar(cdir(proj) / f"revision-plan-{n}.json", rev)
    registrar(proj, "previa" if so_previa else "aplicacao", revision_plan=f"revision-plan-{n}.json",
              operacoes=len(ap["operacoes"]), miss=len(miss), hit=hit, fora_do_plano=fora)
    return {**rev, "arquivo": f"creative/revision-plan-{n}.json", "aplicado": not so_previa}


# ---------------------------------------------------------------------------------------------- QA e relatório
def qa(proj: Path, arquivo: Path) -> dict:
    rep = ler(arquivo)
    erros = validar.validar(rep, "qa-report")
    if erros:
        raise SystemExit("qa-report inválido: " + "; ".join(erros))
    falhas = [c for c in rep["checks"] if c["status"] == "falha"]
    voltas = sum(1 for e in historico(proj) if e["evento"] == "qa" and not e["aprovado"])
    gravar(cdir(proj) / f"qa-report-v{rep['versao']}.json", rep)
    registrar(proj, "qa", versao=rep["versao"], aprovado=rep["aprovado"] and not falhas,
              falhas=[f"{c['area']}: {c['item']}" for c in falhas])
    correcoes = [c["correcao"] for c in falhas if c.get("correcao")]
    proximo = ("render final" if rep["aprovado"] and not falhas else
               "relatar pendências (3 voltas de QA esgotadas)" if voltas + 1 >= 3 else
               "voltar ao passo 5 só com as correções (senior-editor)")
    return {"aprovado": rep["aprovado"] and not falhas, "falhas": len(falhas), "correcoes": correcoes,
            "volta": voltas + (0 if rep["aprovado"] and not falhas else 1), "proximo": proximo}


def relatorio(proj: Path) -> Path:
    vers = sorted((proj / "versions").glob("v*"), key=lambda p: int(p.name[1:]) if p.name[1:].isdigit() else -1)
    if not vers:
        raise SystemExit("Nenhuma versão renderizada ainda.")
    v = vers[-1]
    rv = ler(v / "revisao.json", {})
    dp = ler(cdir(proj) / "decision-plan.json", {})
    qa_f = sorted(cdir(proj).glob("qa-report-v*.json"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    rep = ler(qa_f[-1]) if qa_f else None
    renders = sorted((proj / "renders").glob("*.mp4"), key=lambda p: p.stat().st_mtime) if (proj / "renders").exists() else []
    L = [f"# Relatório Creative Studio — {v.name}", "",
         f"- Arquivo: `{renders[-1] if renders else '(sem mp4)'}`",
         f"- Tipo/estilo: {dp.get('tipo', '?')} / {dp.get('estilo', '?')} · gancho: {dp.get('gancho', '-')} · CTA: {dp.get('cta', '-')}",
         "", "## Mapa", "", "| Cena | Tempo | Fala | Função | Elemento |", "|---|---|---|---|---|"]
    for m in dp.get("mapa", []):
        el = m["elemento"]
        L.append(f"| {m['cena']} | {m['t0']:.1f}-{m['t1']:.1f} s | {m['fala']} | {m['funcao']} | "
                 f"{el['tipo']} {el.get('template', '')} {el.get('id', '')} |")
    L += ["", "## Equipe convocada", ""] + [f"- `{c['agente']}` — {c['motivo']} (cenas: {', '.join(c['cenas'])})"
                                            for c in dp.get("convocados", [])] or ["- nenhuma (ajuste pontual)"]
    L += ["", "## Conflitos resolvidos", ""] + ([f"- {c['descricao']} → **{c['decisao']}** ({c['motivo']})"
                                                 for c in dp.get("conflitos", [])] or ["- nenhum"])
    L += ["", "## Decisões respeitadas", "", ", ".join(dp.get("decisoes_respeitadas", [])) or "-"]
    if rep:
        L += ["", f"## QA (versão {rep['versao']}): {'APROVADO' if rep['aprovado'] else 'REPROVADO'}", ""]
        L += [f"- [{c['status']}] {c['area']}: {c['item']}" for c in rep["checks"] if c["status"] != "ok"] or ["- tudo ok"]
    L += ["", "## Custo da revisão (cache)", ""]
    L += [f"- {t}: {d['HIT']} HIT / {d['MISS']} MISS" for t, d in rv.get("resumo", {}).items()] or ["- sem revisao.json"]
    L += ["", "## Gaps (sem executor no editor)", ""] + ([f"- {g['acao']}: {g['motivo']}" +
                                                         (f" → {g['alternativa']}" if g.get("alternativa") else "")
                                                         for g in dp.get("gaps", [])] or ["- nenhum"])
    out = cdir(proj) / f"relatorio-{v.name}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    registrar(proj, "relatorio", versao=v.name, arquivo=out.name)
    return out


def status(proj: Path) -> dict:
    c = cdir(proj)
    tem = {n: (c / n).exists() for n in ("brief.json", "decision-plan.json", "aprovado.json")}
    dp = ler(c / "decision-plan.json", {})
    revs = sorted(c.glob("revision-plan-*.json"))
    qas = sorted(c.glob("qa-report-v*.json"))
    if not (proj / "timeline.json").exists():
        prox = "passo 1: planejar (run.py plan <proj>)"
    elif not tem["brief.json"]:
        prox = "passo 1: studio.py iniciar"
    elif not tem["decision-plan.json"]:
        prox = "passo 2: studio.py rascunho (já traz a equipe)"
    elif not dp.get("aprovado"):
        prox = "passos 3-4: especialistas devolvem shot-plans → studio.py aprovar"
    elif not revs:
        prox = "passo 5: senior-editor roda studio.py aplicar"
    elif not qas or len(qas) < len(list((proj / "versions").glob("v*"))):
        prox = "passo 6: run.py render --draft, quality-director → studio.py qa"
    else:
        prox = "passos 7-8: render final e studio.py relatorio"
    return {**tem, "aprovado": bool(dp.get("aprovado")), "revision_plans": len(revs), "qa_reports": len(qas),
            "travas": sorted(travas(proj)), "eventos": len(historico(proj)), "proximo": prox}


# ---------------------------------------------------------------------------------------------- CLI
def _brief(proj: Path, a) -> dict:
    pj = ler(proj / "project.json", {})
    p = a.pedido.lower()
    b = {"projeto": str(proj),
         "clipes": [c.get("path", "") for c in pj.get("clips", [])],
         "objetivo": a.objetivo or ("vsl" if "vsl" in p else "venda" if re.search(r"anúnci|anunci|vend|criativo", p) else "seguidor"),
         "plataforma": a.plataforma or ["reels", "tiktok"],
         "formato": pj.get("format") or (pj.get("overrides") or {}).get("format") or "9:16",
         "tipo": a.tipo or "outro",
         "ja_editado": a.ja_editado or bool((pj.get("overrides") or {}).get("sem_cortes") or pj.get("sem_cortes")),
         "nivel": a.nivel or ("maximo" if re.search(r"máxima|maxima|concorrente|nível|nivel", p) else "padrao"),
         "restricoes": [a.pedido]}
    for k in ("publico", "oferta", "cta"):
        if getattr(a, k):
            b[k] = getattr(a, k)
    return b


def _rascunho(proj: Path, pedido: str) -> dict:
    tl = timeline(proj)
    brief = ler(cdir(proj) / "brief.json", {})
    anterior = ler(cdir(proj) / "decision-plan.json")
    mapa = []
    for c in cenas(tl):
        mo = next((e for e in c["elementos"] if e["colecao"] == "motion"), None)
        mapa.append({"cena": c["cena"], "t0": c["t0"], "t1": c["t1"], "fala": c["fala"],
                     "funcao": "gancho" if c["cena"] == "c1" else "cta" if mo and mo["template"] in CTA_TEMPLATES else "respiro",
                     "elemento": ({"tipo": "motion", "template": mo["template"], "id": mo["id"]} if mo else {"tipo": "legenda"}),
                     "responsavel": "diretor"})
    return {"versao": (anterior or {}).get("versao", 0) + 1,
            "tipo": brief.get("tipo", "outro"),
            "estilo": tl.get("style") if tl.get("style") in catalogo()["estilos"] else "pro_clean",
            "mapa": mapa, "convocados": equipe(proj, pedido),
            "decisoes_respeitadas": [d["id"] for d in ler(AQUI / "approved-decisions.json")["decisoes"]],
            "gaps": [], "aprovado": False}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Creative Studio: fluxo executável do diretor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("iniciar"); s.add_argument("proj"); s.add_argument("--pedido", required=True)
    for k in ("objetivo", "tipo", "nivel", "publico", "oferta", "cta"):
        s.add_argument(f"--{k}")
    s.add_argument("--plataforma", nargs="+"); s.add_argument("--ja-editado", action="store_true")
    s = sub.add_parser("catalogo"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("cenas"); s.add_argument("proj"); s.add_argument("--de", type=float); s.add_argument("--ate", type=float)
    for n in ("equipe", "rascunho"):
        s = sub.add_parser(n); s.add_argument("proj"); s.add_argument("--pedido", required=True)
    s = sub.add_parser("verificar"); s.add_argument("proj"); s.add_argument("arquivo"); s.add_argument("schema", choices=validar_schemas())
    s = sub.add_parser("aprovar"); s.add_argument("proj"); s.add_argument("shot_plans", nargs="*")
    s = sub.add_parser("aplicar"); s.add_argument("proj"); s.add_argument("--so-previa", action="store_true"); s.add_argument("--pedido")
    s.add_argument("--preset", choices=["draft", "final", "max"], default="draft", help="preset do próximo render")
    s = sub.add_parser("qa"); s.add_argument("proj"); s.add_argument("arquivo")
    for n in ("relatorio", "historico", "status"):
        s = sub.add_parser(n); s.add_argument("proj")
    for n in ("travar", "liberar"):
        s = sub.add_parser(n); s.add_argument("proj"); s.add_argument("id"); s.add_argument("--motivo", required=True)
    a = ap.parse_args(argv)
    proj = Path(a.proj).resolve() if hasattr(a, "proj") else None

    def out(x) -> None:
        print(json.dumps(x, ensure_ascii=False, indent=1))

    if a.cmd == "iniciar":
        timeline(proj)
        b = _brief(proj, a)
        e = validar.validar(b, "brief")
        if e:
            print("\n".join(e)); return 1
        gravar(cdir(proj) / "brief.json", b)
        registrar(proj, "inicio", pedido=a.pedido, brief="brief.json")
        out(b)
    elif a.cmd == "catalogo":
        c = catalogo()
        if a.json:
            out(c)
        else:
            print("TEMPLATES (--motion '{\"template\": ...}')")
            for t, d in c["templates"].items():
                print(f"  {t:<14} {d[:100]}")
            print("\nOPERAÇÕES do edit.py: " + " ".join(c["operacoes"]))
            print("FX: " + ", ".join(c["fx"]) + "\nESTILOS: " + ", ".join(c["estilos"]))
            print("\nGAPS (não prometa):")
            for g in c["gaps"]:
                print(f"  - {g['acao']}: {g['motivo']}")
    elif a.cmd == "cenas":
        out(cenas(timeline(proj), a.de, a.ate))
    elif a.cmd == "equipe":
        out(equipe(proj, a.pedido))
    elif a.cmd == "rascunho":
        dp = _rascunho(proj, a.pedido)
        gravar(cdir(proj) / "decision-plan.json", dp)
        registrar(proj, "rascunho", versao_plano=dp["versao"], convocados=[c["agente"] for c in dp["convocados"]])
        out({"arquivo": "creative/decision-plan.json", "versao": dp["versao"], "convocados": dp["convocados"]})
    elif a.cmd == "verificar":
        erros, avisos = verificar(proj, ler(Path(a.arquivo)), a.schema)
        for x in avisos:
            print("AVISO", x)
        print("\n".join(f"ERRO {x}" for x in erros) or "OK")
        return 1 if erros else 0
    elif a.cmd == "aprovar":
        r = aprovar(proj, [Path(f) for f in a.shot_plans])
        out(r)
        return 0 if r["aprovado"] else 1
    elif a.cmd == "aplicar":
        out(aplicar(proj, a.so_previa, a.pedido, a.preset))
    elif a.cmd == "qa":
        out(qa(proj, Path(a.arquivo)))
    elif a.cmd == "relatorio":
        print(relatorio(proj))
    elif a.cmd == "historico":
        for e in historico(proj):
            extra = {k: v for k, v in e.items() if k not in ("n", "data", "evento")}
            print(f"{e['n']:>3} {e['data']} {e['evento']:<10} {json.dumps(extra, ensure_ascii=False)[:160]}")
    elif a.cmd in ("travar", "liberar"):
        if a.cmd == "travar" and a.id not in ids_da_timeline(timeline(proj)):
            print(f"'{a.id}' não existe na timeline"); return 1
        registrar(proj, a.cmd, id=a.id, motivo=a.motivo)
        out({"travas": sorted(travas(proj))})
    elif a.cmd == "status":
        out(status(proj))
    return 0


def validar_schemas() -> list[str]:
    return ["brief", "decision-plan", "shot-plan", "revision-plan", "qa-report"]


if __name__ == "__main__":
    sys.exit(main())
