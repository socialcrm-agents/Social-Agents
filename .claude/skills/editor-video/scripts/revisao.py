#!/usr/bin/env python3
"""Smart Revision Engine: timeline persistente, patches manuais, cache por componente e grafo de dependências.

Ideias centrais
- Todo elemento da timeline tem `id` estável (plano, legenda, palavra atrás, B-roll, gráfico, motion, fx).
- Edição manual = patch {id, set:{caminho: valor}} | {id, remover:true} | {colecao, adicionar:{...}} guardado em
  project.json["overrides"]["patches"]. O plan.py reaplica os patches depois de replanejar: a edição sobrevive.
- Quem edita timeline.json à mão não perde nada: no próximo plan.py a diferença para a última timeline gerada
  (work/timeline_gerada.json) vira patch automaticamente ("captura").
- Render por componente, cada um com chave de conteúdo (sha1 das entradas):
      plano[i] ← clipe, in/out, zoom, enquadramento, velocidade, formato
      máscara[i] ← plano[i]
      motion[id] ← página+lib, params, duração, (quadros dos planos sob a janela, se usa o vídeo)
      trecho[k] (4 s) ← planos, máscaras, motions, legendas, gráficos, palavras atrás, B-roll, fx e recuo da janela
      áudio ← áudio dos planos, SFX, trilha, loudness
      final ← trechos + áudio (concatenação sem recodificar)
  Mudou uma animação entre 12 s e 16 s? Só o clipe dela e os trechos 12-16 são refeitos (MISS); o resto é HIT.

Uso direto:
  revisao.py <projeto>                 relatório HIT/MISS do que o próximo render faria (dry-run, não grava nada)
"""

from __future__ import annotations

import copy
import hashlib
import threading
import json
import sys
from pathlib import Path

from common import FONTS_DIR, load_json, log

TRECHO_S = 4.0                      # tamanho do trecho de composição (segundos; múltiplo de 1/fps)
COLECOES = ("shots", "motion", "behind", "broll", "graphics", "fx")
SCRIPTS = Path(__file__).resolve().parent
MOTION_DIR = SCRIPTS.parent / "assets" / "motion"
# templates que só desenham texto/ícones: não dependem dos quadros da pessoa (o resto depende do vídeo da janela)
MOTION_PUROS = {"pergunta", "manchete", "etiqueta", "checklist", "infografico", "carimbo", "botao_cta", "comentario",
                "final", "empilha", "tabela", "proibido", "notificacao", "cronometro", "giro", "anotacao", "icone",
                "luz", "mapa", "documentario", "tela_ia", "vendas", "card_fogo"}
# templates cujos dados extras vêm da timeline inteira (palavras, cortes): dependem também da transcrição/EDL
MOTION_GLOBAIS = {"transcricao", "tomadas", "onda_audio", "editor_ia"}


# ---------------------------------------------------------------------------------------------------------------
# hashing

def hk(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


def bytes_hash(paths) -> str:
    sha = hashlib.sha1()
    for p in paths:
        p = Path(p)
        if p.exists():
            sha.update(p.name.encode())
            sha.update(p.read_bytes())
    return sha.hexdigest()[:16]


def versao_render() -> str:
    """Mudou o código que compõe o quadro? Os trechos são refeitos (os planos e motions não)."""
    return bytes_hash([SCRIPTS / "render.py", SCRIPTS / "assets.py"])


def arquivo_sig(path: str) -> list:
    p = Path(path)
    try:
        st = p.stat()
        return [str(p), st.st_size, int(st.st_mtime)]
    except OSError:
        return [str(p), None, None]


# ---------------------------------------------------------------------------------------------------------------
# caminhos com ponto: "params.text", "itens.0.texto"

def _pega(obj, path: str):
    for k in path.split("."):
        obj = obj[int(k)] if isinstance(obj, list) else obj[k]
    return obj


def _poe(obj, path: str, value) -> None:
    keys = path.split(".")
    for k in keys[:-1]:
        nxt = obj[int(k)] if isinstance(obj, list) else obj.setdefault(k, {})
        obj = nxt
    last = keys[-1]
    if isinstance(obj, list):
        obj[int(last)] = value
    else:
        obj[last] = value


def valor(texto: str):
    """Valor de linha de comando: JSON quando dá (números, true, listas), senão texto."""
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return texto


# ---------------------------------------------------------------------------------------------------------------
# patches

def aplicar_patches(colecao: str, itens: list[dict], patches: list[dict], usados: set | None = None) -> list[dict]:
    """Aplica os patches desta coleção (por id). Devolve a lista nova; marca em `usados` os patches aplicados."""
    usados = usados if usados is not None else set()
    por_id = {it.get("id"): it for it in itens if it.get("id")}
    for n, p in enumerate(patches):
        if p.get("adicionar") is not None and p.get("colecao") == colecao:
            novo = copy.deepcopy(p["adicionar"])
            novo.setdefault("id", f"manual{n}")
            novo["_patch"] = "adicionado"
            if novo["id"] not in por_id:
                itens.append(novo)
                por_id[novo["id"]] = novo
            usados.add(n)
            continue
        alvo = por_id.get(p.get("id"))
        if alvo is None:
            continue
        if p.get("remover"):
            alvo["_remover"] = True
        for path, val in (p.get("set") or {}).items():
            try:
                _poe(alvo, path, copy.deepcopy(val))
            except (KeyError, IndexError, ValueError, TypeError):
                log(f"   aviso: patch {p.get('id')}.{path} não se aplica à estrutura atual; ignorado")
                continue
            if colecao == "shots" and path in ("cx", "cy"):
                alvo["enquadramento_fixo"] = True   # render.py não recalcula pelo rosto
        alvo["_patch"] = "editado"
        usados.add(n)
    out = [it for it in itens if not it.get("_remover")]
    if colecao in ("shots",):
        return out
    return sorted(out, key=lambda x: x.get("t0", 0))


def avisar_orfaos(patches: list[dict], usados: set) -> None:
    for n, p in enumerate(patches):
        if n not in usados:
            log(f"   aviso: patch para '{p.get('id') or p.get('colecao')}' sem elemento correspondente nesta versão "
                f"(continua guardado; volta a valer se o elemento voltar)")


def _diff(a, b, base: str, out: dict) -> None:
    """Diferenças folha a folha de a (gerado) para b (editado)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in b:
            if k in ("_patch",):
                continue
            if k not in a:
                out[f"{base}{k}"] = b[k]
            else:
                _diff(a[k], b[k], f"{base}{k}.", out)
        return
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{base}{i}.", out)
        return
    if a != b:
        out[base.rstrip(".")] = b


def capturar_edicoes(gerada: dict | None, atual: dict | None) -> list[dict]:
    """Transforma edições feitas à mão em timeline.json (comparadas com a última timeline gerada) em patches."""
    if not gerada or not atual or gerada == atual:
        return []
    patches = []
    for col in COLECOES:
        g = {it["id"]: it for it in gerada.get(col, []) if isinstance(it, dict) and it.get("id")}
        a_itens = [it for it in atual.get(col, []) if isinstance(it, dict)]
        a = {it["id"]: it for it in a_itens if it.get("id")}
        for i, it in a.items():
            if i in g:
                d: dict = {}
                _diff(g[i], it, "", d)
                d = {k: v for k, v in d.items() if not k.startswith("_")}
                if d:
                    patches.append({"id": i, "set": d, "origem": "timeline.json editada à mão"})
            else:
                patches.append({"colecao": col, "adicionar": it, "origem": "timeline.json editada à mão"})
        for i in g:
            if i not in a:
                patches.append({"id": i, "remover": True, "origem": "timeline.json editada à mão"})
        for it in a_itens:
            if not it.get("id"):
                patches.append({"colecao": col, "adicionar": it, "origem": "timeline.json editada à mão"})
    return patches


def juntar_patches(existentes: list[dict], novos: list[dict]) -> list[dict]:
    """Patch novo para o mesmo id+campo substitui o antigo; o resto acumula (ordem preservada)."""
    out = [copy.deepcopy(p) for p in existentes]
    for p in novos:
        alvo = next((q for q in out if p.get("id") and q.get("id") == p.get("id") and "set" in q and "set" in p), None)
        if alvo:
            alvo["set"].update(p["set"])
        elif p not in out:
            out.append(p)
    return out


# ---------------------------------------------------------------------------------------------------------------
# chaves de cache por componente

def chave_plano(sh: dict, w: int, h: int, fps: int) -> str:
    return hk("plano", arquivo_sig(sh["src"]), sh["in"], sh["out"], round(sh["t1"] - sh["t0"], 4), sh["zoom0"], sh["zoom1"],
             sh.get("cx"), sh.get("cy"), sh.get("speed", 1.0), w, h, fps)


def planos_na_janela(tl: dict, chaves: list[str], a: float, b: float) -> list:
    """Planos que aparecem em [a, b): chave + deslocamento relativo (para quadros e máscara da janela)."""
    return [[k, round(sh["t0"] - a, 3)] for sh, k in zip(tl["shots"], chaves) if sh["t0"] < b and sh["t1"] > a]


def usa_video(item: dict) -> bool:
    return bool(item.get("needs_video") or item.get("hand") or item.get("layer") == "behind"
                or item.get("page") or item.get("template") not in MOTION_PUROS)


def chave_motion(item: dict, tl: dict, chaves_planos: list[str], tem_mascara: bool, work: Path) -> str:
    page = item.get("page") or f"/templates/{item.get('template')}.html"
    path = work / page[len("/work/"):] if page.startswith("/work/") else MOTION_DIR / page.lstrip("/")
    pagina = bytes_hash([path, *sorted((MOTION_DIR / "lib").glob("*.*"))])
    base = {k: v for k, v in item.items() if k not in ("t0", "t1", "id", "_patch", "auto", "trigger")}
    janela = planos_na_janela(tl, chaves_planos, item["t0"], item["t1"]) if usa_video(item) else None
    glob = hk([w["w"] for w in tl.get("words", [])], tl.get("duration")) if item.get("template") in MOTION_GLOBAIS else None
    return hk("motion", pagina, base, round(item["t1"] - item["t0"], 3), tl["w"], tl["h"], tl["fps"],
             janela, tem_mascara and usa_video(item), glob)


def janelas(total: float, fps: int) -> list[tuple[float, float, int]]:
    """Trechos de TRECHO_S segundos com número inteiro de quadros: (início, fim, quadros)."""
    nq = round(total * fps)
    passo = round(TRECHO_S * fps)
    out = []
    for q0 in range(0, nq, passo):
        q1 = min(q0 + passo, nq)
        out.append((q0 / fps, q1 / fps, q1 - q0))
    return out


def _sobre(x: dict, a: float, b: float, folga: float = 0.0) -> bool:
    return x.get("t0", 0) < b + folga and x.get("t1", 0) > a - folga


def chave_trecho(tl: dict, a: float, b: float, chaves_planos: list[str], chaves_motion: dict, tem_mascara: bool,
                 preset: str, fontes_sig: str) -> str:
    mot = [m for m in tl.get("motion", []) if _sobre(m, a, b)]
    # o recuo e a posição da legenda olham a janela das animações que tocam o trecho: inclui os planos sob elas
    lo = min([a] + [m["t0"] for m in mot])
    hi = max([b] + [m["t1"] for m in mot])
    ent = {
        "janela": [round(a, 3), round(b, 3)],
        "planos": planos_na_janela(tl, chaves_planos, lo, hi),
        "mascara": tem_mascara,
        "motion": [[chaves_motion.get(m.get("id")), m.get("layer"), m.get("zona"), m.get("libera"), m["t0"], m["t1"],
                    m.get("guarda")]
                   for m in mot],
        "legendas": [[pg["t0"], pg["t1"], [tl["words"][i] for i in pg["words"]]]
                     for pg in tl["captions"]["pages"] if _sobre(pg, a, b, 0.5)],
        "atras": [b_ for b_ in tl.get("behind", []) if _sobre(b_, a, b)],
        "broll": [[r, arquivo_sig(r["src"])] for r in tl.get("broll", []) if _sobre(r, a, b)],
        "graficos": [g for g in tl.get("graphics", []) if _sobre(g, a, b) or g["type"] == "progress"],
        "fx": [f for f in tl.get("fx", []) if a - 0.5 <= f["t"] < b + 0.1],
        "cfg": [tl["captions"]["cfg"], tl["behind_cfg"], tl["graphics_cfg"], tl["grade"], tl["style"], tl.get("brand")],
        "total": tl["duration"] if any(g["type"] == "progress" for g in tl.get("graphics", [])) else None,
    }
    return hk("trecho", versao_render(), ent, tl["w"], tl["h"], tl["fps"], preset, fontes_sig)


def sig_musica(musica: dict | None):
    """Trilha automática (trilha.py): a chave é o pedido resolvido (clima, BPM, duração, semente e versão do
    gerador), não o caminho — o mesmo pedido em outra pasta (dry-run) dá a mesma chave. Arquivo do usuário:
    caminho + tamanho + data."""
    if not musica:
        return None
    if musica.get("auto"):
        return [{k: v for k, v in musica.items() if k != "path"}]
    return [musica, arquivo_sig(musica["path"])]


def chave_audio(tl: dict, chaves_planos: list[str]) -> str:
    # os sons (sfx.py/dsp.py) entram na chave do áudio: mudou um efeito, o mix é refeito (os trechos de vídeo não)
    return hk("audio", versao_render(), bytes_hash([SCRIPTS / "sfx.py", SCRIPTS / "dsp.py"]), chaves_planos,
              tl["sfx"], tl["audio"], tl["duration"], sig_musica(tl.get("music")))


def fontes_sig(work: Path) -> str:
    d = work / "fonts"
    files = sorted(d.glob("*.[ot]tf")) if d.is_dir() else sorted(FONTS_DIR.glob("*.[ot]tf"))
    return hk([[f.name, f.stat().st_size] for f in files])


# ---------------------------------------------------------------------------------------------------------------
# registro HIT/MISS

class Registro:
    """Anota HIT/MISS de cada componente (com motivo) e grava o relatório da versão."""

    def __init__(self, dry: bool = False):
        self.itens: list[dict] = []
        self.dry = dry
        self._lock = threading.Lock()  # planos, motions e trechos são feitos em paralelo

    def anota(self, tipo: str, ident: str, hit: bool, chave: str, motivo: str = "", segundos: float | None = None,
              janela=None) -> None:
        with self._lock:
            self.itens.append({"tipo": tipo, "id": ident, "status": "HIT" if hit else "MISS", "chave": chave,
                               "motivo": motivo, "segundos": segundos, "janela": janela})
            if not self.dry:
                extra = f" [{janela[0]:.1f}-{janela[1]:.1f}s]" if janela else ""
                log(f"   {'HIT ' if hit else 'MISS'} {tipo:<8} {ident}{extra}" + (f" — {motivo}" if motivo and not hit else ""))

    def resumo(self) -> dict:
        out: dict = {}
        for it in self.itens:
            d = out.setdefault(it["tipo"], {"HIT": 0, "MISS": 0})
            d[it["status"]] += 1
        return out

    def linha(self) -> str:
        return " | ".join(f"{t} {d['HIT']} HIT/{d['MISS']} MISS" for t, d in self.resumo().items())


def manifesto_anterior(paths: dict) -> dict:
    """Chaves do último render (para explicar o motivo de cada MISS)."""
    vdir = paths["versions"]
    if not vdir.is_dir():
        return {}
    versoes = sorted((int(p.name[1:]) for p in vdir.glob("v*") if p.name[1:].isdigit()), reverse=True)
    for v in versoes:
        m = load_json(vdir / f"v{v}" / "revisao.json")
        if m:
            return m
    return {}


# ---------------------------------------------------------------------------------------------------------------
# dry-run

def prever(project: Path, tl: dict | None = None, preset: str = "veryfast") -> Registro:
    """O que o próximo render refaria, sem renderizar nem gravar nada (usa os caches existentes em work/)."""
    import render
    from common import project_paths
    paths = project_paths(project)
    tl = copy.deepcopy(tl or load_json(paths["timeline"]))
    reg = Registro(dry=True)
    W, H, FPS = tl["w"], tl["h"], tl["fps"]
    work = paths["work"]
    render.W, render.H, render.FPS = W, H, FPS
    render.face_for_shots(tl, work, so_cache=True)
    cache = render.Cache(work)
    chaves_planos = [chave_plano(sh, W, H, FPS) for sh in tl["shots"]]
    for sh, k in zip(tl["shots"], chaves_planos):
        reg.anota("plano", sh.get("id", "?"), cache.tem("planos", k, ".mkv"), k, janela=(sh["t0"], sh["t1"]))
    tem_mascara = render.precisa_mascara(tl)
    if tem_mascara:
        for sh, k in zip(tl["shots"], chaves_planos):
            reg.anota("mascara", sh.get("id", "?"), cache.tem("mascaras", k, ".mp4"), k, janela=(sh["t0"], sh["t1"]))
    chaves_motion = {}
    for m in tl.get("motion", []):
        k = chave_motion(m, tl, chaves_planos, tem_mascara, work)
        chaves_motion[m.get("id")] = k
        lado = work / "motion" / f"clip_{k}.item.json"
        if lado.exists():  # mesma decisão que o render aplica (camada/zona definidas no render do clipe)
            m.update(json.loads(lado.read_text(encoding="utf-8")))
        reg.anota("motion", f"{m.get('id')}:{m.get('template') or m.get('page')}",
                  (work / "motion" / f"clip_{k}.mov").exists(), k, janela=(m["t0"], m["t1"]))
    fsig = fontes_sig(work)
    for a, b, _n in janelas(tl["duration"], FPS):
        k = chave_trecho(tl, a, b, chaves_planos, chaves_motion, tem_mascara, preset, fsig)
        reg.anota("trecho", f"{a:05.1f}-{b:05.1f}", cache.tem("trechos", k, ".mp4"), k, janela=(a, b))
    k = chave_audio(tl, chaves_planos)
    reg.anota("audio", "mix", cache.tem("audio", k, ".m4a"), k)
    return reg


def imprimir(reg: Registro, titulo: str = "Prévia da revisão (dry-run: nada foi renderizado nem gravado)") -> None:
    log(titulo)
    for it in reg.itens:
        jan = f" [{it['janela'][0]:.1f}-{it['janela'][1]:.1f}s]" if it.get("janela") else ""
        log(f"   {it['status']:<4} {it['tipo']:<8} {it['id']}{jan}")
    miss = [it for it in reg.itens if it["status"] == "MISS"]
    log(f"Resumo: {reg.linha()}")
    log("Nada a refazer: o render só remonta o arquivo final." if not miss else
        f"Seriam refeitos {len(miss)} componente(s); o resto vem do cache.")


if __name__ == "__main__":
    from common import main_guard

    def _main():
        imprimir(prever(Path(sys.argv[1]).resolve()))
    main_guard(_main)
