#!/usr/bin/env python3
"""Pedidos de mídia para os conectores: lê a fala e diz o que buscar/gerar, em qual conector e onde encaixar.

Os conectores (Pinterest via Scrape Creators, Canva, Moda, Instagram, HeyGen, Descript...) são ferramentas do
Claude (MCP), não do Python: este script só PLANEJA. O Claude lê qa/pedidos-de-midia.md, faz as chamadas, salva os
arquivos em <projeto>/midia/ e encaixa com edit.py (--add-broll, --motion cenario/documentario/giro...).
Playbook completo: references/conectores.md

Uso: conectores.py <projeto>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from common import load_json, log, main_guard, norm, project_paths, save_json

PROFISSOES = {"nutricionista": "consultório de nutrição", "psicologa": "consultório de psicologia aconchegante",
              "psicologo": "consultório de psicologia aconchegante", "personal": "academia moderna",
              "advogado": "escritório de advocacia", "advogada": "escritório de advocacia",
              "cabeleireira": "salão de beleza", "marceneiro": "marcenaria com madeira e ferramentas",
              "esteticista": "clínica de estética clara", "professora": "sala de aula", "professor": "sala de aula",
              "medico": "consultório médico", "medica": "consultório médico", "dentista": "consultório odontológico",
              "corretor": "apartamento decorado com vista", "fotografo": "estúdio fotográfico", "confeiteira": "cozinha de confeitaria"}
CENARIOS = {"praia": "praia ao entardecer", "escritorio": "escritório moderno com luz natural", "carro": "interior de carro de dia",
            "cozinha": "cozinha clara", "palco": "palco com luzes", "podcast": "estúdio de podcast com microfones",
            "academia": "academia", "casa": "sala de estar aconchegante", "rua": "rua de cidade movimentada",
            "estudio": "estúdio minimalista bege com luz de janela", "fundo": None, "cenario": None}
FERRAMENTAS = {"chatgpt": "ChatGPT", "claude": "Claude", "canva": "Canva", "hotmart": "Hotmart", "hubla": "Hubla",
               "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "whatsapp": "WhatsApp",
               "lovable": "Lovable", "heygen": "HeyGen", "gerenciador": "Gerenciador de Anúncios"}
CITACAO = re.compile(r"^(segundo|como diz|como disse|ja dizia|o|a)$")


def frase(words, i, n=8) -> str:
    out = []
    for w in words[max(0, i - 2): i + n]:
        out.append(w["w"])
    return " ".join(out)


def pedidos(words: list[dict]) -> list[dict]:
    out, seen = [], set()

    def add(kind, i, **kw):
        key = (kind, kw.get("query") or kw.get("nome"))
        if key in seen:
            return
        seen.add(key)
        out.append({"tipo": kind, "t": round(words[i]["t0"], 2), "palavra": words[i]["w"].strip(".,!?"),
                    "trecho": frase(words, i), **kw})

    for i, w in enumerate(words):
        n = norm(w["w"])
        if n in PROFISSOES:
            add("cena_profissao", i, query=PROFISSOES[n],
                conectores=["Moda/Canva: gerar fundo 9:16 '" + PROFISSOES[n] + ", luz natural, sem pessoas'",
                            "Pinterest (Scrape Creators v1_pinterest_search): referência visual",
                            "HeyGen: avatar na cena (não há ferramenta de avatar conectada; gravar no app HeyGen e anexar)"],
                encaixe="--motion cenario (você recortado na frente) ou --add-broll + --broll-at")
        if n in CENARIOS:
            q = CENARIOS[n] or "cenário citado na fala"
            add("cenario", i, query=q, conectores=["Canva generate-image / Moda: fundo 9:16 sem pessoas", "Pinterest: referência"],
                encaixe="--motion cenario")
        if n in FERRAMENTAS:
            add("ferramenta", i, nome=FERRAMENTAS[n],
                conectores=["gravação de tela do usuário (melhor)", "print autorizado", "logo só com direito de uso"],
                encaixe="tela_ia / documentario / objeto3d (image)")
        # citação: "segundo Fulano", "como diz Fulano" ou nome próprio no meio da frase
        if i and w["w"][:1].isupper() and not words[i - 1]["w"].endswith((".", "!", "?")) and n not in FERRAMENTAS \
                and len(n) > 3 and not n.isdigit():
            prev = norm(words[i - 1]["w"])
            if CITACAO.match(prev) or (i + 1 < len(words) and words[i + 1]["w"][:1].isupper()):
                nome = " ".join(x["w"].strip(".,!?") for x in words[i:i + 2] if x["w"][:1].isupper())
                add("citacao", i, nome=nome, query=nome,
                    conectores=["Pinterest (v1_pinterest_search): foto/referência de " + nome,
                                "Instagram (v1_instagram_profile/v2_instagram_reels_search): perfil e post citado, com crédito"],
                    encaixe="--motion documentario (foto + marcação) ou giro; sempre com crédito @ na tela")
    return out


def main() -> None:
    project = Path(sys.argv[1])
    paths = project_paths(project)
    tl = load_json(paths["timeline"])
    words = tl["words"] if tl else load_json(paths["transcript"])["words"]
    reqs = pedidos(words)
    save_json(paths["qa"] / "pedidos-de-midia.json", reqs)
    lines = ["# Pedidos de mídia (conectores)", "",
             "O Claude atende cada pedido com o conector indicado, salva em `midia/` e encaixa com edit.py.",
             "Detalhes de cada conector, limites e o caminho que funciona: `references/conectores.md`.", ""]
    for r in reqs:
        lines.append(f"## {r['t']:.1f}s · {r['tipo']} · \"{r['palavra']}\"")
        lines.append(f"Trecho: _{r['trecho']}_  ")
        if r.get("query"):
            lines.append(f"Busca/prompt: `{r['query']}`  ")
        lines += [f"- {c}" for c in r["conectores"]]
        lines.append(f"- Encaixe: `{r['encaixe']}`")
        lines.append("")
    (paths["qa"] / "pedidos-de-midia.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"OK: {len(reqs)} pedidos de mídia -> qa/pedidos-de-midia.md")


if __name__ == "__main__":
    main_guard(main)
