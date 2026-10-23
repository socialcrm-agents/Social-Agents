#!/usr/bin/env python3
"""Aplica correções do usuário (já traduzidas em operações) e renderiza a próxima versão.

O Claude lê a correção em linguagem natural ("tira o 'é isso' do começo, legenda maior")
e chama este script com as operações equivalentes. Cada operação é gravada em
project.json -> overrides, então persiste nas próximas versões e em troca de estilo.

  edit.py <projeto> [operações...] [--note "texto original do usuário"] [--no-render] [--draft | --max]

Operações:
  --cut "trecho falado"          remove o trecho (todas as palavras, na ordem)
  --restore "trecho falado"      devolve um trecho que o corte automático tirou
  --fix "errado=certo"           corrige palavra na legenda (ex.: "cloud=Claude")
  --style NOME                   editorial_premium | reels_viral | anuncio_conversao
  --hook "texto"                 faixa de gancho dos primeiros segundos
  --cta "texto"                  chamada final
  --title "texto"                lower third (Editorial)
  --emph "palavra"               força destaque da palavra na legenda
  --behind-add "TEXTO@palavra"   palavra grande atrás da pessoa quando "palavra" é dita
  --behind-remove "TEXTO"        remove uma palavra atrás da pessoa
  --behind on|off                liga/desliga palavras atrás da pessoa
  --broll-at "palavra[:dur[:modo[:id]]]"  insere B-roll (modo full|card|split, id b1, b2...)
  --broll-remove N               remove o N-ésimo B-roll automático (1 = primeiro)
  --add-broll ARQUIVO            adiciona arquivo (vídeo/imagem) ao banco de B-roll
  --caption-size N|+N%|-N%       tamanho da legenda
  --caption-y N                  posição vertical da base da legenda (px, máx 1470)
  --zoom off|on|suave|forte      intensidade dos zooms
  --music ARQUIVO[:volume]       trilha (com ducking automático sob a voz)
  --format 9:16|16:9|1:1|4:5     formato de saída (Reels/Shorts, YouTube/aula, feed)
  --brand SLUG|nenhuma           aplica o kit de marca (cores, fontes, logo, CTAs, correções de palavras)
  --motion JSON|@arquivo.json    animação: {"template": "moldura", "at": "trecho falado", "dur": 5, "params": {...}}
                                 (lista em references/motion.md; "at" dentro de params aceita palavra falada)
  --motion-remove N              remove a N-ésima animação pedida
  --icons on|off                 ícones automáticos nas palavras-chave
  --gatilhos on|off              mapa de gatilhos (frase/dinheiro/enumeração -> efeito + som)
  --velocidade 1.15              acelera a fala sem mudar o tom (1 = original)
  --sem-cortes on|off            vídeo já cortado: mantém tudo e o ritmo original (só embeleza)
  --fx tipo@palavra              tremida | clarao | glitch | whip no instante em que a palavra é dita
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

from common import EditorError, load_json, load_style, log, main_guard, perfil, probe, project_paths, save_json
from drive import LinkError, baixar, eh_link

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--cut", action="append", default=[])
    ap.add_argument("--restore", action="append", default=[])
    ap.add_argument("--fix", action="append", default=[])
    ap.add_argument("--style")
    ap.add_argument("--hook")
    ap.add_argument("--cta")
    ap.add_argument("--title")
    ap.add_argument("--emph", action="append", default=[])
    ap.add_argument("--behind-add", action="append", default=[])
    ap.add_argument("--behind-remove", action="append", default=[])
    ap.add_argument("--behind", choices=["on", "off"])
    ap.add_argument("--broll-at", action="append", default=[])
    ap.add_argument("--broll-remove", action="append", type=int, default=[])
    ap.add_argument("--add-broll", action="append", default=[])
    ap.add_argument("--caption-size")
    ap.add_argument("--caption-y", type=int)
    ap.add_argument("--zoom", choices=["off", "on", "suave", "forte"])
    ap.add_argument("--music")
    ap.add_argument("--format", choices=["9:16", "16:9", "1:1", "4:5"])
    ap.add_argument("--brand", help="aplica o kit de marca brands/<slug> (ou 'nenhuma')")
    ap.add_argument("--motion", action="append", default=[])
    ap.add_argument("--motion-remove", action="append", type=int, default=[])
    ap.add_argument("--icons", choices=["on", "off"])
    ap.add_argument("--gatilhos", choices=["on", "off"])
    ap.add_argument("--velocidade", type=float, help="fala mais rápida/lenta, ex.: 1.15 (1 = original)")
    ap.add_argument("--sem-cortes", choices=["on", "off"])
    ap.add_argument("--fx", action="append", default=[], help="efeito de impacto: tipo@palavra (tremida, clarao, glitch, whip)")
    ap.add_argument("--note", default="")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--max", action="store_true", help="compressão mais lenta, arquivo menor")
    a = ap.parse_args()

    project = Path(a.project).resolve()
    paths = project_paths(project)
    proj = load_json(paths["project"])
    if not proj:
        raise EditorError("project.json não encontrado.")
    ov = proj.setdefault("overrides", {})
    done: list[str] = []

    def add(key, values, label):
        if values:
            ov.setdefault(key, []).extend(values)
            done.append(f"{label}: {', '.join(map(str, values))}")

    add("cuts", a.cut, "cortar")
    add("restores", a.restore, "restaurar")
    for fx in a.fix:
        wrong, right = fx.split("=", 1)
        ov.setdefault("word_fixes", {})[wrong.strip()] = right.strip()
        done.append(f"corrigir '{wrong.strip()}' -> '{right.strip()}'")
    if a.style:
        load_style(a.style)
        proj["style"] = a.style
        done.append(f"estilo: {a.style}")
    for key in ("hook", "cta", "title"):
        val = getattr(a, key)
        if val is not None:
            ov[key] = val
            done.append(f"{key}: {val}")
    add("emphasis_add", a.emph, "destacar")
    for item in a.behind_add:
        text, _, at = item.partition("@")
        ov.setdefault("behind_add", []).append({"text": text.strip(), "at": (at or text).strip()})
        done.append(f"atrás da pessoa: {text.strip()}")
    add("behind_remove", a.behind_remove, "tirar de trás da pessoa")
    if a.behind:
        ov["behind_enabled"] = a.behind == "on"
        done.append(f"palavras atrás da pessoa: {a.behind}")
    for item in a.broll_at:
        parts = item.split(":")
        req = {"at": parts[0]}
        if len(parts) > 1 and parts[1]:
            req["dur"] = float(parts[1])
        if len(parts) > 2 and parts[2]:
            req["mode"] = parts[2]
        if len(parts) > 3 and parts[3]:
            req["src"] = parts[3]
        ov.setdefault("broll_at", []).append(req)
        done.append(f"B-roll em '{parts[0]}'")
    add("broll_remove", a.broll_remove, "remover B-roll nº")
    for f in a.add_broll:
        if eh_link(f):
            try:
                f = str(baixar(f, project / "fontes"))
            except LinkError as exc:
                raise EditorError(str(exc)) from exc
        p = Path(f).expanduser().resolve()
        if not p.exists():
            raise EditorError(f"B-roll não encontrado: {f}")
        kind = "image" if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else "video"
        item = {"id": f"b{len(proj['broll']) + 1}", "path": str(p), "kind": kind}
        if kind == "video":
            item["duration"] = probe(p)["duration"]
        proj["broll"].append(item)
        done.append(f"novo B-roll {item['id']}: {p.name}")
    if a.caption_size:
        base = ov.get("caption", {}).get("size") or load_style(proj["style"], proj.get("brand"))["captions"]["size"]
        s = a.caption_size
        size = int(base * (1 + float(s[:-1]) / 100)) if s.endswith("%") else int(s)
        ov.setdefault("caption", {})["size"] = size
        ov["caption"]["emph_size"] = int(size * 1.15)
        done.append(f"legenda tamanho {size}")
    if a.caption_y is not None:
        ov.setdefault("caption", {})["y"] = min(a.caption_y, 1470)
        done.append(f"legenda y={min(a.caption_y, 1470)}")
    if a.zoom:
        st = load_style(proj["style"], proj.get("brand"))["zoom"]
        ov["zoom"] = {"off": {"off": True}, "on": {}, "suave": {"punch": 1 + (st["punch"] - 1) * 0.5, "push": st["push"] * 0.5},
                      "forte": {"punch": 1 + (st["punch"] - 1) * 1.5, "push": st["push"] * 1.5 + 0.02}}[a.zoom]
        done.append(f"zoom {a.zoom}")
    if a.music:
        path, _, vol = a.music.partition(":")
        ov["music"] = {"path": str(Path(path).expanduser().resolve()), "volume": float(vol or 0.12)}
        done.append(f"trilha {Path(path).name}")

    if a.brand:
        from common import load_brand
        proj["brand"] = None if a.brand == "nenhuma" else (load_brand(a.brand) and a.brand)
        done.append(f"marca: {a.brand}")
    if a.format:
        proj["format"] = a.format
        done.append(f"formato {a.format}")
    if a.motion and not perfil()["motion"]:
        raise EditorError("Animações (--motion) fazem parte do Pacote Motion 3D, que não está instalado nesta skill.")
    for spec in a.motion:
        text = Path(spec[1:]).read_text(encoding="utf-8") if spec.startswith("@") else spec
        try:
            reqs = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EditorError(f"--motion não é JSON válido: {exc}") from exc
        for req in reqs if isinstance(reqs, list) else [reqs]:
            if "template" not in req and "page" not in req:
                raise EditorError("--motion precisa de 'template' (ou 'page' para composição própria)")
            ov.setdefault("motion", []).append(req)
            done.append(f"motion {req.get('template') or req.get('page')} em '{req.get('at')}'")
    add("motion_remove", a.motion_remove, "remover motion nº")
    if a.icons:
        ov["icons"] = a.icons == "on"
        done.append(f"ícones automáticos: {a.icons}")
    if a.gatilhos:
        ov["triggers"] = a.gatilhos == "on"
        done.append(f"gatilhos automáticos: {a.gatilhos}")
    if a.sem_cortes:
        ov["sem_cortes"] = a.sem_cortes == "on"
        done.append(f"sem cortes: {a.sem_cortes}")
    if a.velocidade:
        ov["speed"] = a.velocidade
        done.append(f"velocidade da fala ×{a.velocidade}")
    for spec in a.fx:
        kind, _, at = spec.partition("@")
        ov.setdefault("fx_requests", []).append({"type": kind, "at": at})
        done.append(f"efeito {kind} em '{at}'")
    if not done and not a.note:
        raise EditorError("Nenhuma operação informada. Veja edit.py --help.")
    ov.setdefault("notes", []).append({"when": datetime.datetime.now().isoformat(timespec="seconds"),
                                       "note": a.note, "ops": done, "for_version": proj.get("version", 0) + 1})
    save_json(paths["project"], proj)
    changelog = paths["versions"] / "changelog.md"
    paths["versions"].mkdir(parents=True, exist_ok=True)
    with changelog.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## v{proj.get('version', 0) + 1}\n")
        if a.note:
            fh.write(f"Pedido: \"{a.note}\"\n\n")
        fh.writelines(f"- {d}\n" for d in done)
    log("Alterações: " + ("; ".join(done) or "(só anotação)"))
    if a.no_render:
        return
    for script, extra in (("analyze.py", []), ("plan.py", []), ("render.py", ["--draft"] if a.draft else (["--max"] if a.max else []))):
        if subprocess.run([sys.executable, str(HERE / script), str(project), *extra]).returncode:
            raise EditorError(f"{script} falhou")


if __name__ == "__main__":
    main_guard(main)
