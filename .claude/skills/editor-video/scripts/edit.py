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
  --music auto[:clima[:volume]]  trilha sem direitos gerada na hora (energia, inspirador, suspense, lofi,
                                 corporativo), na duração do vídeo e no ritmo da fala; "--music off" tira
  --trilha CLIMA                 o mesmo que --music auto:CLIMA  (--trilha-bpm N, --trilha-semente N)
  --format 9:16|16:9|1:1|4:5     formato de saída (Reels/Shorts, YouTube/aula, feed)
  --brand SLUG|nenhuma           aplica o kit de marca (cores, fontes, logo, CTAs, correções de palavras)
  --motion JSON|@arquivo.json    animação: {"template": "moldura", "at": "trecho falado", "dur": 5, "params": {...}}
                                 (lista em references/motion.md; "at" dentro de params aceita palavra falada)
  --motion-remove N|ID           remove a animação pelo número (1 = primeira pedida) ou pelo id (m3, a_carimbo_12)
  --patch "ID.campo=valor"       muda um elemento da timeline pelo id e o ajuste SOBREVIVE a replanejamentos
                                 (ex.: m5.params.text=VICIANTE, m5.t1=15.2, sc1_8920.zoom0=1.2, g_cta.text="COMPRE")
  --patch-remove ID              tira um elemento da timeline (vale também para os automáticos)
  --patch-clear ID               desfaz os patches de um elemento
  --icons on|off                 ícones automáticos nas palavras-chave
  --gatilhos on|off              mapa de gatilhos (frase/dinheiro/enumeração -> efeito + som)
  --direcao premium|off          seletor por intenção: palavra-chave com emoji/cor, 2.5D no gancho, transições
                                 no ritmo da fala, com controle de densidade (seletor.py)
  --produto foto.png             foto do produto (recortada) para o produto 3D nas cenas que mostram o produto
  --composicao NOME@trecho       composição de referência no trecho falado: revelacao (2.5D + palavra entre o
                                 cenário e a pessoa), produto_heroi (produto 3D pousa na mão), impacto (soco de
                                 câmera + palavra gigante com emoji + clarão); repetível
  --composicao-remove NOME@trecho  tira uma composição pedida
  --velocidade 1.15              acelera a fala sem mudar o tom (1 = original)
  --sem-cortes on|off            vídeo já cortado: mantém tudo e o ritmo original (só embeleza)
  --fx tipo@palavra              tremida | clarao | glitch | whip no instante em que a palavra é dita
  --cor-destaque #RRGGBB         cor da palavra em destaque na legenda (e do realce, se o estilo usa)
  --corte-gancho "trecho"|off    abre o vídeo com esse trecho falado (1,5-3 s) e depois segue do começo
                                 (corte de gancho; não vale para vídeo sem cortes/já editado)
  --correcao auto|off            luz/cor/ruído/nitidez automáticos por clipe (vídeo de celular escuro, cor puxada)
  --estabilizar auto|on|off      tira a tremida da câmera na mão e mantém o rosto centralizado (zoom mín. 1,06)
  --pele 0..1                    suavização só nos tons de pele (padrão 0.35 com --correcao auto; 0 desliga)
  --dry-run                      mostra o que seria refeito (HIT/MISS por componente) sem gravar nem renderizar

Pedidos de --motion com "id" substituem o pedido anterior com o mesmo id; um pedido idêntico a outro já existente é
ignorado (reaplicar o mesmo motion.json não duplica animações). Se o render falhar, o project.json volta ao estado
anterior (rollback automático).
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
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
    ap.add_argument("--trilha", help="trilha sintetizada: energia | inspirador | suspense | lofi | corporativo")
    ap.add_argument("--trilha-bpm", type=float)
    ap.add_argument("--trilha-semente", type=int)
    ap.add_argument("--format", choices=["9:16", "16:9", "1:1", "4:5"])
    ap.add_argument("--brand", help="aplica o kit de marca brands/<slug> (ou 'nenhuma')")
    ap.add_argument("--motion", action="append", default=[])
    ap.add_argument("--motion-remove", action="append", default=[])
    ap.add_argument("--patch", action="append", default=[])
    ap.add_argument("--patch-remove", action="append", default=[])
    ap.add_argument("--patch-clear", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--icons", choices=["on", "off"])
    ap.add_argument("--gatilhos", choices=["on", "off"])
    ap.add_argument("--direcao", choices=["premium", "off"])
    ap.add_argument("--produto", help="foto do produto (PNG recortado) para o produto 3D da direção premium")
    ap.add_argument("--composicao", action="append", default=[])
    ap.add_argument("--composicao-remove", action="append", default=[])
    ap.add_argument("--velocidade", type=float, help="fala mais rápida/lenta, ex.: 1.15 (1 = original)")
    ap.add_argument("--sem-cortes", choices=["on", "off"])
    ap.add_argument("--fx", action="append", default=[], help="efeito de impacto: tipo@palavra (tremida, clarao, glitch, whip)")
    ap.add_argument("--cor-destaque", help="cor de destaque da legenda, ex.: #FFE600")
    ap.add_argument("--corte-gancho", help="trecho falado que abre o vídeo (ou 'off')")
    ap.add_argument("--correcao", choices=["auto", "off"], help="luz, cor, ruído e nitidez automáticos")
    ap.add_argument("--estabilizar", choices=["auto", "on", "off"], help="tira a tremida e mantém o rosto centralizado")
    ap.add_argument("--pele", type=float, help="suavização de pele 0..1 (0 = desliga; padrão com --correcao auto: 0.35)")
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
    original = copy.deepcopy(proj)
    ov = proj.setdefault("overrides", {})
    done: list[str] = []
    ignorados: list[str] = []

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
    if a.trilha:
        a.music = f"auto:{a.trilha}"
    if a.music and a.music.strip().lower() in ("off", "nenhuma", "sem"):
        ov.pop("music", None)
        done.append("sem trilha")
    elif a.music and a.music.split(":")[0].strip().lower() == "auto":
        import trilha
        _, clima, vol = (a.music.split(":") + ["", ""])[:3]
        pedido = {"auto": True}
        if clima.strip():
            try:
                pedido["clima"] = trilha.nome_clima(clima)
            except ValueError as exc:
                raise EditorError(str(exc)) from exc
        if vol.strip():
            pedido["volume"] = float(vol)
        ov["music"] = pedido
        done.append(f"trilha automática {pedido.get('clima') or '(clima do estilo)'}")
    elif a.music:
        # "C:\\musica.mp3:0.2" no Windows: o volume é só o que vem depois do ÚLTIMO ':' e se for número
        path, sep, vol = a.music.rpartition(":")
        try:
            volume = float(vol) if sep else 0.12
        except ValueError:
            path, volume = a.music, 0.12
        if not sep:
            path = a.music
        ov["music"] = {"path": str(Path(path).expanduser().resolve()), "volume": volume}
        done.append(f"trilha {Path(path).name}")
    if (a.trilha_bpm or a.trilha_semente is not None):
        if not (ov.get("music") or {}).get("auto"):
            raise EditorError("--trilha-bpm/--trilha-semente valem para a trilha automática (--music auto ou --trilha).")
        if a.trilha_bpm:
            ov["music"]["bpm"] = a.trilha_bpm
            done.append(f"trilha {a.trilha_bpm:.0f} BPM")
        if a.trilha_semente is not None:
            ov["music"]["semente"] = a.trilha_semente
            done.append(f"trilha variação {a.trilha_semente}")

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
            lista = ov.setdefault("motion", [])
            # id explícito ou implícito (m<n> = n-ésimo pedido, o mesmo id que aparece na timeline)
            pos = next((k for k, r in enumerate(lista) if str(r.get("id") or f"m{k + 1}") == str(req.get("id"))), None)
            if req.get("id") and pos is not None:
                lista[pos] = req
                done.append(f"motion {req['id']} substituído")
                continue
            if req in lista:
                ignorados.append(f"{req.get('template')} em '{req.get('at')}'")
                continue
            lista.append(req)
            done.append(f"motion {req.get('template') or req.get('page')} em '{req.get('at')}' (id m{len(lista)})")
    add("motion_remove", [int(x) if str(x).isdigit() else x for x in a.motion_remove], "remover motion")
    import revisao
    # desfazer vem antes: "--patch-clear X --patch-remove X" = limpa o que havia e remove
    for ident in a.patch_clear:
        antes = len(ov.get("patches", []))
        ov["patches"] = [p for p in ov.get("patches", []) if p.get("id") != ident.strip()]
        done.append(f"desfeitos {antes - len(ov['patches'])} patch(es) de {ident}")
    novos = []
    for spec in a.patch:
        alvo, _, val = spec.partition("=")
        ident, _, campo = alvo.partition(".")
        if not campo or not _:
            raise EditorError(f"--patch precisa de ID.campo=valor (recebi '{spec}')")
        novos.append({"id": ident.strip(), "set": {campo.strip(): revisao.valor(val.strip())},
                      "origem": "edit.py --patch"})
        done.append(f"patch {ident}.{campo} = {val}")
    for ident in a.patch_remove:
        novos.append({"id": ident.strip(), "remover": True, "origem": "edit.py --patch-remove"})
        done.append(f"remover elemento {ident}")
    if novos:
        ov["patches"] = revisao.juntar_patches(ov.get("patches", []), novos)

    if a.icons:
        ov["icons"] = a.icons == "on"
        done.append(f"ícones automáticos: {a.icons}")
    if a.gatilhos:
        ov["triggers"] = a.gatilhos == "on"
        done.append(f"gatilhos automáticos: {a.gatilhos}")
    if a.direcao:
        if a.direcao == "premium":
            ov["direcao"] = "premium"
        else:
            ov.pop("direcao", None)
        done.append(f"direção: {a.direcao}")
    for c in a.composicao:
        nome, _, at = c.partition("@")
        lista = ov.setdefault("composicoes", [])
        pedido = {"nome": nome.strip(), "at": at.strip()}
        if pedido not in [{"nome": x["nome"], "at": x["at"]} for x in lista]:
            lista.append(pedido)
        done.append(f"composição {nome} em '{at}'")
    for c in a.composicao_remove:
        nome, _, at = c.partition("@")
        ov["composicoes"] = [x for x in ov.get("composicoes", []) if not (x["nome"] == nome.strip() and x["at"] == at.strip())]
        done.append(f"composição removida: {nome}@{at}")
    if a.produto:
        ov.setdefault("direcao_cfg", {})["produto"] = str(Path(a.produto).expanduser().resolve())
        done.append(f"produto 3D: {Path(a.produto).name}")
    if a.sem_cortes:
        ov["sem_cortes"] = a.sem_cortes == "on"
        done.append(f"sem cortes: {a.sem_cortes}")
    if a.velocidade:
        ov["speed"] = a.velocidade
        done.append(f"velocidade da fala ×{a.velocidade}")
    for chave in ("correcao", "estabilizar", "pele"):
        val = getattr(a, chave)
        if val is not None:
            if chave == "pele":
                val = round(min(max(val, 0.0), 1.0), 2)
            ov.setdefault("imagem", {})[chave] = val
            done.append(f"imagem {chave}: {val}")
    for spec in a.fx:
        kind, _, at = spec.partition("@")
        ov.setdefault("fx_requests", []).append({"type": kind, "at": at})
        done.append(f"efeito {kind} em '{at}'")
    if a.cor_destaque:
        cor = a.cor_destaque.strip()
        if not (len(cor) == 7 and cor.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in cor[1:])):
            raise EditorError(f"--cor-destaque precisa ser #RRGGBB (recebi '{cor}')")
        cap = ov.setdefault("caption", {})
        cap["emph_color"] = cor.upper()
        if load_style(proj["style"], proj.get("brand"))["captions"].get("highlight", "none") != "none":
            cap["highlight"] = cor.upper()
        done.append(f"cor de destaque {cor.upper()}")
    if a.corte_gancho:
        if a.corte_gancho.strip().lower() == "off":
            ov.pop("corte_gancho", None)
            done.append("corte de gancho: off")
        else:
            if ov.get("sem_cortes") or proj.get("ja_editado"):
                raise EditorError("Corte de gancho muda a ordem da fala: não vale para vídeo sem cortes/já editado.")
            ov["corte_gancho"] = {"texto": a.corte_gancho.strip()}
            done.append(f"corte de gancho: '{a.corte_gancho.strip()}'")
    if ignorados:
        log(f"   pedido(s) de motion idêntico(s) a um já existente ignorado(s): {'; '.join(ignorados)}")
    if not done and not a.note:
        if ignorados:
            log("Nada mudou: o projeto já tinha esse(s) pedido(s).")
            return
        raise EditorError("Nenhuma operação informada. Veja edit.py --help.")
    if a.dry_run:
        prever_edicao(project, proj, done, "ultrafast" if a.draft else ("medium" if a.max else "veryfast"))
        return
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
    tl_antes = paths["timeline"].read_bytes() if paths["timeline"].exists() else None
    for script, extra in (("analyze.py", []), ("plan.py", []), ("render.py", ["--draft"] if a.draft else (["--max"] if a.max else []))):
        if subprocess.run([sys.executable, str(HERE / script), str(project), *extra]).returncode:
            # rollback automático: o pedido não fica aplicado pela metade
            atual = load_json(paths["project"]) or {}
            original["version"] = max(original.get("version", 0), atual.get("version", 0))
            save_json(paths["project"], original)
            if tl_antes is not None:
                paths["timeline"].write_bytes(tl_antes)
            subprocess.run([sys.executable, str(HERE / "analyze.py"), str(project)], capture_output=True)
            raise EditorError(f"{script} falhou; o projeto voltou ao estado anterior (rollback). Nada foi perdido.")


def prever_edicao(project: Path, proj: dict, done: list[str], preset: str = "veryfast") -> None:
    """Dry-run: aplica o pedido numa cópia temporária (só os .json), replaneja lá e compara com os caches reais."""
    import revisao
    paths = project_paths(project)
    tmp = Path(tempfile.mkdtemp(prefix="editor_dry_"))
    try:
        for name in ("transcript.json", "timeline.json"):
            if (project / name).exists():
                shutil.copy2(project / name, tmp / name)
        (tmp / "work").mkdir()
        if (paths["work"] / "timeline_gerada.json").exists():
            shutil.copy2(paths["work"] / "timeline_gerada.json", tmp / "work" / "timeline_gerada.json")
        save_json(tmp / "project.json", proj)
        for script in ("analyze.py", "plan.py"):
            r = subprocess.run([sys.executable, str(HERE / script), str(tmp)], capture_output=True, text=True)
            if r.returncode:
                raise EditorError(f"dry-run: {script} falhou:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        tl = load_json(tmp / "timeline.json")
        log("Pedido: " + "; ".join(done))
        revisao.imprimir(revisao.prever(project, tl, preset))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_guard(main)
