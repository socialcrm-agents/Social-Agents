#!/usr/bin/env python3
"""Escolhe as melhores tomadas e remove pausas, gaguejos, muletas e frases quebradas.

Regras (determinísticas, revisáveis pelo Claude em qa/takes.md):
1. Frases = palavras separadas por pausa > 0.45s ou pontuação final.
2. Regravação: se uma frase seguinte (até 4 à frente, inclusive em outro clipe)
   começa igual / é muito parecida, a anterior é descartada (vale a ÚLTIMA tomada).
3. Gaguejo: "o sistema o sistema" -> remove a primeira repetição (n-gramas 1..4).
4. Muletas sem conteúdo (ãh, ahn, hum, hmm) são removidas.
5. Frase final cortada (termina em artigo/preposição) é removida.
6. Pausas internas acima de cuts.max_gap viram corte seco.
Overrides do usuário: cuts (trechos a remover) e restores (trechos a manter).

Uso: analyze.py <projeto>
"""

from __future__ import annotations

import sys
from difflib import SequenceMatcher
from pathlib import Path

from common import EditorError, load_json, load_style, log, main_guard, norm, project_paths, save_json

HARD_FILLERS = {"ah", "ahn", "eh", "hum", "hm", "hmm", "uh", "ã", "ãh", "éé", "ééé"}
DANGLING = {"o", "a", "os", "as", "de", "do", "da", "para", "pra", "que", "e", "um", "uma", "no", "na", "com", "em", "se", "mas"}


def split_phrases(words: list[dict]) -> list[list[int]]:
    phrases, cur = [], []
    for i, w in enumerate(words):
        if cur:
            prev = words[cur[-1]]
            new_clip = prev["clip"] != w["clip"]
            if new_clip or w["t0"] - prev["t1"] > 0.45 or prev["w"].endswith((".", "!", "?")):
                phrases.append(cur)
                cur = []
        cur.append(i)
    if cur:
        phrases.append(cur)
    return phrases


def ntext(words, idx) -> list[str]:
    return [n for n in (norm(words[i]["w"]) for i in idx) if n]


def is_retake(a: list[str], b: list[str]) -> bool:
    """True se a frase `a` foi regravada como `b` (b começa como a ou é parecida)."""
    if len(a) < 2 or not b:
        return False
    head = b[: max(len(a), 2)]
    if SequenceMatcher(None, a, head).ratio() >= 0.72:
        return True
    k = min(3, len(a))
    return len(a) <= len(b) and a[:k] == b[:k] and SequenceMatcher(None, a, b[: len(a)]).ratio() >= 0.6


def matches(words, phrase_text: str) -> list[int]:
    """Índices das palavras que formam o trecho `phrase_text` (busca por texto normalizado)."""
    target = [n for n in (norm(t) for t in phrase_text.split()) if n]
    seq = [norm(w["w"]) for w in words]
    for s in range(len(seq) - len(target) + 1):
        if seq[s:s + len(target)] == target:
            return list(range(s, s + len(target)))
    return []


def analyze(words: list[dict], style: dict, overrides: dict) -> tuple[set[int], list[tuple[str, str]]]:
    drop: set[int] = set()
    report: list[tuple[str, str]] = []
    phrases = split_phrases(words)
    texts = [ntext(words, p) for p in phrases]

    for i, p in enumerate(phrases):
        for j in range(i + 1, min(i + 5, len(phrases))):
            if is_retake(texts[i], texts[j]):
                drop.update(p)
                report.append(("Tomada repetida (ficou a última)", " ".join(words[k]["w"] for k in p)))
                break

    seq = [(i, norm(w["w"])) for i, w in enumerate(words) if i not in drop]
    for n in (4, 3, 2, 1):
        k = 0
        while k + 2 * n <= len(seq):
            a = [t for _, t in seq[k:k + n]]
            b = [t for _, t in seq[k + n:k + 2 * n]]
            if a == b and all(a) and words[seq[k + n][0]]["clip"] == words[seq[k][0]]["clip"]:
                idx = [i for i, _ in seq[k:k + n]]
                if n > 1 or a[0] not in {"muito", "bem", "ja", "nao"}:
                    drop.update(idx)
                    report.append(("Gaguejo / repetição", " ".join(words[i]["w"] for i in idx)))
                    seq = seq[:k] + seq[k + n:]
                    continue
            k += 1

    for i, w in enumerate(words):
        n = norm(w["w"])
        if n in HARD_FILLERS or (w["w"].strip(".,") in HARD_FILLERS):
            drop.add(i)
            report.append(("Muleta", w["w"]))

    kept_phr = [p for p in phrases if not set(p) <= drop]
    if kept_phr:
        last = [i for i in kept_phr[-1] if i not in drop]
        if last and norm(words[last[-1]]["w"]) in DANGLING and not words[last[-1]]["w"].endswith((".", "!", "?")):
            # frase final interrompida: corta até a última pontuação dentro dela
            cut_from = last[0]
            for i in last:
                if words[i]["w"].endswith((".", "!", "?", ",")):
                    cut_from = i + 1
            gone = [i for i in last if i >= cut_from]
            drop.update(gone)
            report.append(("Frase final interrompida", " ".join(words[i]["w"] for i in gone)))

    for phrase in overrides.get("cuts", []):
        idx = matches(words, phrase)
        drop.update(idx)
        report.append(("Removido a pedido", phrase if idx else f"{phrase} (NÃO ENCONTRADO)"))
    for phrase in overrides.get("restores", []):
        idx = matches(words, phrase)
        drop.difference_update(idx)
        report.append(("Restaurado a pedido", phrase if idx else f"{phrase} (NÃO ENCONTRADO)"))
    return drop, report


def split_on_silences(segs: list[dict], words, silences: dict, c: dict) -> list[dict]:
    """Corta as pausas medidas no áudio que caem dentro de um segmento (respiros longos)."""
    out = []
    for seg in segs:
        pieces = [seg]
        for s, e in silences.get(seg["clip"], []):
            if e - s <= c["max_gap"] + c["pad_in"] + c["pad_out"]:
                continue
            last = pieces[-1]
            if last["in"] + 0.15 < s and e < last["out"] - 0.15:
                left = [i for i in last["words"] if words[i]["t0"] < s]
                right = [i for i in last["words"] if words[i]["t0"] >= s]
                if not left or not right:
                    continue
                pieces[-1:] = [
                    {**last, "out": round(s + c["pad_out"], 3), "words": left},
                    {**last, "in": round(e - c["pad_in"], 3), "words": right},
                ]
        for p in pieces:
            p["text"] = " ".join(words[i]["w"] for i in p["words"])
        out += pieces
    return out


def build_segments(words, keep: list[int], style: dict, silences: dict | None = None) -> list[dict]:
    c = style["cuts"]
    segs: list[dict] = []
    for i in keep:
        w = words[i]
        # mesma tomada contínua: mesmo clipe, nenhuma palavra removida no meio, pausa curta
        if segs and segs[-1]["clip"] == w["clip"] and i == segs[-1]["last"] + 1 \
                and w["t0"] - words[segs[-1]["last"]]["t1"] <= c["max_gap"]:
            segs[-1]["last"] = i
            segs[-1]["words"].append(i)
        else:
            segs.append({"clip": w["clip"], "first": i, "last": i, "words": [i]})
    out = []
    for s in segs:
        a, b = words[s["first"]], words[s["last"]]
        out.append({"clip": s["clip"], "in": round(max(0.0, a["t0"] - c["pad_in"]), 3),
                    "out": round(b["t1"] + c["pad_out"], 3), "words": s["words"],
                    "text": " ".join(words[i]["w"] for i in s["words"])})
    out = split_on_silences(out, words, silences or {}, c)
    # evita sobreposição entre segmentos vizinhos do mesmo clipe
    for x, y in zip(out, out[1:]):
        if x["clip"] == y["clip"] and x["out"] > y["in"]:
            mid = round((words[x["words"][-1]]["t1"] + words[y["words"][0]]["t0"]) / 2, 3)
            x["out"], y["in"] = mid, mid
    return out


def main() -> None:
    project = Path(sys.argv[1])
    paths = project_paths(project)
    proj = load_json(paths["project"])
    tr = load_json(paths["transcript"])
    if not tr:
        raise EditorError("transcript.json não encontrado. Rode transcribe.py.")
    style = load_style(proj["style"])
    words = tr["words"]
    drop, report = analyze(words, style, proj.get("overrides", {}))
    keep = [i for i in range(len(words)) if i not in drop]
    segs = build_segments(words, keep, style, tr.get("silences"))
    raw = sum(c["duration"] for c in proj["clips"])
    final = sum(s["out"] - s["in"] for s in segs)
    save_json(paths["edl"], {"style": proj["style"], "segments": segs, "dropped": sorted(drop),
                             "raw_duration": round(raw, 2), "edit_duration": round(final, 2)})
    lines = ["# Tomadas e cortes", "", f"Bruto: {raw:.1f}s -> editado: {final:.1f}s ({len(segs)} cortes)", "",
             "## Removido", ""]
    lines += [f"- **{why}**: {txt}" for why, txt in report] or ["- nada"]
    lines += ["", "## Mantido (segmentos)", ""]
    lines += [f"{n + 1}. [{s['clip']} {s['in']:.2f}-{s['out']:.2f}] {s['text']}" for n, s in enumerate(segs)]
    paths["qa"].mkdir(parents=True, exist_ok=True)
    (paths["qa"] / "takes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"OK: {raw:.1f}s -> {final:.1f}s, {len(segs)} segmentos, {len(drop)} palavras removidas (qa/takes.md)")


if __name__ == "__main__":
    main_guard(main)
