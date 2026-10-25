#!/usr/bin/env python3
"""Renderiza timeline.json em MP4 (1080x1920, 1920x1080 ou 1080x1080; H.264 + AAC), criando uma nova versão.

Etapas: rastreio de rosto -> planos com zoom animado -> A-roll contínuo -> máscara da
pessoa (se houver palavras atrás) -> legendas/gráficos/SFX -> um único grafo ffmpeg
(cor, texto atrás da pessoa, B-roll, gráficos, legendas, mixagem e loudness) -> QA.

Uso: render.py <projeto> [--draft | --max]   (--draft: prévia rápida; --max: compressão mais lenta, arquivo menor)
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import revisao
from assets import behind_ass, caption_y, captions_ass, graphic_png, make_sfx
from common import FONTS_DIR, EditorError, ffmpeg, load_json, log, main_guard, probe, project_paths, run, save_json

W, H, FPS = 1080, 1920, 30


def face_for_shots(tl: dict, work: Path, so_cache: bool = False) -> bool:
    """Centraliza o zoom de cada plano no rosto. Devolve True se achou rosto.

    so_cache: só usa rastreios já feitos (dry-run). Plano com `enquadramento_fixo` (patch manual) mantém cx/cy."""
    try:
        from vision import face_track
    except EditorError:
        _preparar_imagem(tl, work, {}, {}, so_cache)
        return False
    found = False
    tracks: dict[str, list] = {}
    alvos_y: dict[str, float] = {}
    for sh in tl["shots"]:
        if sh["clip"] not in tracks:
            cache = work / f"face_{sh['clip']}.json"
            tracks[sh["clip"]] = load_json(cache) if cache.exists() else None
            if tracks[sh["clip"]] is None and so_cache:
                tracks[sh["clip"]] = []
            elif tracks[sh["clip"]] is None:
                try:
                    tracks[sh["clip"]] = face_track(sh["src"], aspect=W / H)
                except EditorError as exc:
                    log(f"   (sem rastreio de rosto: {exc})")
                    tracks[sh["clip"]] = []
                save_json(cache, tracks[sh["clip"]])
        pts = [p for p in tracks[sh["clip"]] if sh["in"] - 0.3 <= p["t"] <= sh["out"] + 0.3]
        if len(pts) >= 1:
            found = True
            fx = statistics.median(p["cx"] for p in pts)
            fy = statistics.median(p["cy"] for p in pts)
            z = max((sh["zoom0"] + sh["zoom1"]) / 2, 1.0001)
            # com palavra atrás no plano, o rosto desce no quadro para sobrar espaço acima da cabeça
            has_word = any(b["t0"] < sh["t1"] and b["t1"] > sh["t0"] for b in tl["behind"]) or any(
                m.get("layer") == "behind" and m["t0"] < sh["t1"] and m["t1"] > sh["t0"] for m in tl.get("motion", []))
            top_busy = any(m.get("zona") == "topo" and m["t0"] < sh["t1"] and m["t1"] > sh["t0"]
                           for m in tl.get("motion", []))
            # card/player no alto ou palavra atrás: o rosto desce no quadro para sobrar espaço em cima
            target_y = 0.56 if top_busy else 0.48 if has_word else 0.40
            alvos_y[sh.get("id", "")] = target_y
            if not sh.get("enquadramento_fixo"):
                sh["cx"] = round(min(max((fx * z - 0.5) / (z - 1), 0), 1), 3)
                sh["cy"] = round(min(max((fy * z - target_y) / (z - 1), 0), 1), 3)
            # queixo no quadro final (px): a legenda desse plano fica sempre abaixo dele
            fh = statistics.median(p["h"] for p in pts)
            zf = max(sh["zoom0"], sh["zoom1"])
            face_y = fy * zf * H - (zf * H - H) * sh["cy"]
            sh["chin"] = int(face_y + 0.62 * fh * zf * H)
    _preparar_imagem(tl, work, tracks, alvos_y, so_cache)
    return found


def _preparar_imagem(tl: dict, work: Path, tracks: dict, alvos_y: dict, so_cache: bool) -> None:
    """Correção de imagem / estabilização (opção "imagem" do projeto). Desligada: nada muda nos planos."""
    if tl.get("imagem"):
        import imagem
        imagem.preparar_planos(tl, work, tracks, alvos_y, W, H, so_cache=so_cache)


class Cache:
    """Arquivos por componente em work/cache/<tipo>/<chave><ext>. Guarda várias versões: desfazer é HIT."""

    def __init__(self, work: Path):
        self.root = work / "cache"

    def caminho(self, tipo: str, chave: str, ext: str) -> Path:
        d = self.root / tipo
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{chave}{ext}"

    def tem(self, tipo: str, chave: str, ext: str) -> bool:
        return (self.root / tipo / f"{chave}{ext}").exists()


def _concat(files: list[Path], out: Path, extra: list[str] | None = None, inputs: list[str] | None = None) -> None:
    """Concatena sem recodificar (lista com caminhos absolutos em barra normal: funciona no Windows)."""
    lst = out.with_name(f".{out.stem}.lista.txt")
    lst.write_text("".join("file '" + f.resolve().as_posix().replace("'", "'\\''") + "'\n" for f in files),
                   encoding="utf-8")
    tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), *(inputs or []), *(extra or ["-c", "copy"]), str(tmp)])
    os.replace(tmp, out)
    lst.unlink(missing_ok=True)


def render_shots(tl: dict, work: Path, preset: str, reg: "revisao.Registro | None" = None,
                 chaves: list[str] | None = None) -> Path:
    """Monta o A-roll contínuo (cortes + zoom). Cada plano tem cache próprio (work/cache/planos): um corte num
    trecho só re-codifica os planos que mudaram; o A-roll é a concatenação (sem recodificar)."""
    chaves = chaves or [revisao.chave_plano(sh, W, H, FPS) for sh in tl["shots"]]
    key = revisao.hk("aroll", chaves)
    aroll = work / "aroll.mkv"
    stamp = work / "aroll.key"
    cache = Cache(work)
    if aroll.exists() and stamp.exists() and stamp.read_text() == key and all(cache.tem("planos", k, ".mkv") for k in chaves):
        for sh, k in zip(tl["shots"], chaves):
            reg and reg.anota("plano", sh.get("id", "?"), True, k, janela=(sh["t0"], sh["t1"]))
        log("   A-roll reaproveitado (planos iguais)")
        return aroll

    def one(n: int, sh: dict) -> Path:
        speed = sh.get("speed", 1.0)
        tl_dur = sh["t1"] - sh["t0"]              # duração na timeline (já em quadros inteiros)
        dur = tl_dur * speed                      # trecho do bruto que vira esse plano
        z0, z1 = sh["zoom0"], sh["zoom1"]
        z = f"({z0}+{z1 - z0:.4f}*t/{dur:.3f})"
        tempo = f",setpts=(PTS-STARTPTS)/{speed:.4f}" if abs(speed - 1) > 1e-3 else ""
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
              f"scale=w='2*trunc({W}*{z}/2)':h='2*trunc({H}*{z}/2)':eval=frame:flags=bicubic,"
              f"crop={W}:{H}:x='(in_w-{W})*{sh['cx']}':y='(in_h-{H})*{sh['cy']}'{tempo},fps={FPS},setsar=1,format=yuv420p")
        atempo = f"atempo={speed:.4f}," if abs(speed - 1) > 1e-3 else ""
        k = chaves[n]
        final = cache.caminho("planos", k, ".mkv")
        if final.exists():
            reg and reg.anota("plano", sh.get("id", str(n)), True, k, janela=(sh["t0"], sh["t1"]))
            return final
        t_ini = time.time()
        out = final.with_name(f"{k}.tmp.mp4")
        filtro = ["-vf", vf]
        if sh.get("imagem"):
            # correção de imagem e/ou recorte dinâmico (estabilização): o grafo vai num arquivo (as expressões
            # por quadro passariam do limite de linha de comando do Windows)
            import imagem
            script = final.with_name(f"{k}.vf.txt")
            script.write_text(f"{imagem.cadeia(sh, work, W, H, z)}{tempo},fps={FPS},setsar=1,format=yuv420p",
                              encoding="utf-8")
            filtro = ["-filter_script:v", str(script)]
        ffmpeg(["-ss", f"{sh['in']:.3f}", "-i", sh["src"], "-t", f"{dur:.3f}", *filtro,
                "-af", f"{atempo}aresample=48000,afade=t=in:d=0.012,afade=t=out:st={max(tl_dur - 0.02, 0):.3f}:d=0.02,"
                f"apad,atrim=0:{tl_dur:.4f}",  # áudio com a duração exata do plano: sem deriva entre som e imagem
                "-frames:v", str(round(tl_dur * FPS)),
                "-c:v", "libx264", "-preset", preset, "-crf", "13", "-threads", "2",
                "-c:a", "pcm_s16le", str(out.with_suffix(".mkv"))])
        os.replace(out.with_suffix(".mkv"), final)
        reg and reg.anota("plano", sh.get("id", str(n)), False, k, "plano novo ou alterado",
                          round(time.time() - t_ini, 1), janela=(sh["t0"], sh["t1"]))
        return final

    # um processo ffmpeg por plano, vários ao mesmo tempo (cada um usa pouco a CPU sozinho)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
        files = list(pool.map(lambda a: one(*a), enumerate(tl["shots"])))
    _concat(files, aroll)
    stamp.write_text(key)
    return aroll


def precisa_mascara(tl: dict, has_face: bool = True) -> bool:
    motions = tl.get("motion", [])
    needs = any(m.get("needs_video") or m.get("layer") == "behind" or m.get("zona") == "topo" for m in motions)
    return bool((tl["behind"] and has_face) or needs)


def mascara_por_plano(tl: dict, work: Path, chaves: list[str], reg: "revisao.Registro | None" = None):
    """Máscara da pessoa com cache por plano (work/cache/mascaras): só os planos novos passam pelo MediaPipe."""
    from vision import person_mask
    cache = Cache(work)
    mask = work / "mask.mp4"
    key = revisao.hk("mascara", chaves)
    stamp = work / "mask.key"
    arquivos, stats = [], []
    for sh, k in zip(tl["shots"], chaves):
        # "p2": as estatísticas passaram a guardar olhos/boca (pontos do rosto); máscaras antigas são refeitas uma vez
        mp4, js = cache.caminho("mascaras", k, ".mp4"), cache.caminho("mascaras", k + "p2", ".json")
        if mp4.exists() and js.exists():
            reg and reg.anota("mascara", sh.get("id", "?"), True, k, janela=(sh["t0"], sh["t1"]))
        else:
            t_ini = time.time()
            tmp = mp4.with_name(f"{k}.tmp.mp4")
            st = person_mask(cache.caminho("planos", k, ".mkv"), tmp, W, H, FPS)
            save_json(js, st)
            os.replace(tmp, mp4)
            reg and reg.anota("mascara", sh.get("id", "?"), False, k, "plano novo ou alterado",
                              round(time.time() - t_ini, 1), janela=(sh["t0"], sh["t1"]))
        arquivos.append(mp4)
        stats += load_json(js)
    if not (mask.exists() and stamp.exists() and stamp.read_text() == key):
        _concat(arquivos, mask)
        stamp.write_text(key)
    save_json(work / "mask_stats.json", stats)
    return mask, stats


# quanto do alto do quadro (px, em 1920) cada elemento de topo precisa livre
LIBERA = {"pergunta": 560, "etiqueta": 540, "manchete": 640, "palavra": 560, "proibido": 560, "tomadas": 700,
          "infografico": 560, "carimbo": 600, "checklist": 700}


def recuo_windows(motions: list[dict], stats: list | None) -> list[dict]:
    """Trechos em que um card/manchete no topo bateria na cabeça: a cena encolhe (s < 1) e desce.

    s é o menor encolhimento que deixa o topo da cabeça abaixo do espaço que o elemento precisa (mín. 0,62)."""
    if not stats:
        return []
    out = []
    for m in motions:
        if m.get("zona") != "topo":
            continue
        a, b = int(m["t0"] * FPS), int(m["t1"] * FPS)
        tops = sorted(st["top"] for st in stats[a:b] if st.get("top") is not None)
        if not tops:
            continue
        top = tops[len(tops) // 10]  # a cabeça mais alta do trecho (percentil 10)
        need = m.get("libera") or (m["params"].get("y", 230) + m["params"].get("altura", 600) + 60
                                   if m.get("template") == "player" else LIBERA.get(m.get("template"), 560))
        need = need * H / 1920
        if top >= need:
            continue
        s = max(0.62, min(1.0, (H - need) / max(H - top, 1)))
        out.append({"t0": m["t0"], "t1": m["t1"] + 0.3, "s": round(s, 3)})  # volta só depois do card sair
    return out


def fit_behind(tl: dict, behind: list[dict]) -> tuple[list[dict], list[dict]]:
    """Garante que ~70% da palavra fique visível acima da cabeça, dentro da zona segura.

    Reduz a fonte quando falta espaço; se mesmo assim não couber (cabeça encostada no topo),
    a palavra vai para a frente.
    """
    import assets
    from assets import WIDTH_FACTOR
    SAFE_SIDE, SAFE_TOP = assets.SAFE_SIDE, assets.SAFE_TOP
    k = tl["behind_cfg"]
    ok, moved = [], []
    for b in behind:
        size = min(k["size"], int((W - 2 * SAFE_SIDE) / max(len(b["text"]) * WIDTH_FACTOR.get(k["font"], 0.6), 1)))
        room = b["head_top"] - SAFE_TOP
        if room < 0.62 * size:
            size = int(room / 0.62)
        if size < 150:
            moved.append(b)
        else:
            ok.append({**b, "size": size})
    return ok, moved


def background_luma(aroll: Path, t: float, y0: int, y1: int) -> float:
    """Brilho médio (0-255) da faixa onde a palavra vai ficar, no quadro do instante t."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(aroll), "-frames:v", "1",
                          "-vf", f"crop={W}:{max(y1 - y0, 2)}:0:{y0},scale=64:16,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True)
    data = out.stdout
    return sum(data) / len(data) if data else 0.0


def pick_color(style_color: str, accent: str, luma: float) -> str:
    """Mantém a cor do estilo se houver contraste; senão troca por escuro (fundo claro) ou destaque."""
    def lum(hex_rgb):
        h = hex_rgb.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.299 * r + 0.587 * g + 0.114 * b
    if abs(lum(style_color) - luma) >= 90:
        return style_color
    if abs(lum(accent) - luma) >= 90:
        return accent
    return "#111111" if luma > 128 else "#FFFFFF"


def place_behind(tl: dict, stats: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """Separa as palavras que dá para pôr atrás da pessoa das que vão na frente."""
    behind, front = [], []
    for b in tl["behind"]:
        if not stats or not any(s["face"] for s in stats):
            front.append(b)
            continue
        win = stats[int(b["t0"] * FPS): int(b["t1"] * FPS)]
        faces = [s for s in win if s["face"]]
        good = [s for s in win if s["cov"] > 0.05 and s["top"] is not None]
        if win and len(good) >= 0.8 * len(win) and len(faces) * 3 >= 0.5 * len(win):
            tops = [s["top"] for s in good]
            if max(tops) - min(tops) < 220:  # cabeça estável: legível
                behind.append({**b, "head_top": int(statistics.median(tops))})
                continue
        if faces:
            continue  # rosto no quadro mas sem como ir atrás: a palavra sai (na frente ela cobriria o rosto)
        front.append(b)
    return behind, front


def prepare_fonts(tl: dict, work: Path) -> Path:
    """work/fonts = fontes da skill + fontes da marca (libass e o servidor de motion leem daqui)."""
    from common import load_brand
    fdir = work / "fonts"
    if fdir.is_symlink():
        fdir.unlink()
    fdir.mkdir(exist_ok=True)
    brand = load_brand(tl.get("brand"))
    files = list(FONTS_DIR.glob("*.[ot]tf"))
    if brand:
        import assets
        assets.register_fonts(brand.get("fonts", []), Path(brand["_dir"]))
        files += [Path(brand["_dir"]) / f["file"] for f in brand.get("fonts", [])]
    for src in files:
        dst = fdir / src.name
        if not dst.exists():
            try:
                dst.symlink_to(src.resolve())
            except OSError:  # Windows sem modo desenvolvedor: copia (as fontes são pequenas)
                shutil.copy2(src, dst)
    return fdir


def fx_chain(f: list[str], cur: str, fx: list[dict]) -> str:
    """Efeitos de impacto no quadro final: tremida, clarão, glitch e chicote (whip) nos instantes pedidos."""
    if not fx:
        return cur
    win = lambda kind: "+".join(f"between(t,{e['t']:.3f},{e['t'] + e.get('dur', DUR_FX[kind]):.3f})"
                                for e in fx if e["type"] == kind)
    chain = []
    if win("tremida"):
        m = 28  # margem para a tremida não mostrar borda
        sx = "+".join(f"between(t,{e['t']:.3f},{e['t'] + e.get('dur', DUR_FX['tremida']):.3f})*{e.get('force', 1)}"
                      for e in fx if e["type"] == "tremida")
        chain.append(f"scale={W + 2 * m}:{H + 2 * m},crop={W}:{H}:x='{m}+({sx})*{m * 0.8}*sin(t*97)':"
                     f"y='{m}+({sx})*{m * 0.8}*cos(t*83)'")
    if win("clarao"):
        chain.append(f"eq=brightness=0.35:contrast=0.8:enable='{win('clarao')}'")
    if win("glitch"):
        chain.append(f"rgbashift=rh=-14:bh=14:gv=6:enable='{win('glitch')}',noise=alls=35:allf=t:enable='{win('glitch')}'")
    if win("zoom_impacto"):
        # soco de câmera: entra 14% mais perto num quadro e volta em curva (0,35 s), centrado no rosto/alto
        z = "+".join(f"0.14*pow(max(0,1-(t-{e['t']:.3f})/{e.get('dur', DUR_FX['zoom_impacto']):.3f}),2)"
                     f"*between(t,{e['t']:.3f},{e['t'] + e.get('dur', DUR_FX['zoom_impacto']):.3f})"
                     for e in fx if e["type"] == "zoom_impacto")
        chain.append(f"scale=w='2*trunc({W}*(1+{z})/2)':h='2*trunc({H}*(1+{z})/2)':eval=frame,"
                     f"crop={W}:{H}:x='(in_w-{W})/2':y='(in_h-{H})*0.38'")
    if win("whip"):
        # chicote: a imagem corre para o lado com rastro (scroll + borrão horizontal forte) no instante da troca
        chain.append(f"scroll=horizontal=0.045:enable='{win('whip')}',avgblur=sizeX=90:sizeY=1:enable='{win('whip')}'")
    f.append(f"[{cur}]{','.join(chain)},setsar=1[vfx]")
    return "vfx"


DUR_FX = {"tremida": 0.3, "clarao": 0.08, "glitch": 0.22, "whip": 0.12, "zoom_impacto": 0.35}


VOZ = "highpass=f=80,afftdn=nf=-28,acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2,loudnorm=I={lufs}:TP=-1.5:LRA=9,aresample=48000"
LIMITE = "alimiter=limit=0.95"
_LAT: dict = {}


def latencia(filtro: str) -> float:
    """Atraso (s) que um filtro de áudio introduz, medido no ffmpeg desta máquina (afftdn atrasa ~25 ms e o
    alimiter ~5 ms, sem compensar). Medido uma vez por versão do ffmpeg e guardado em ~/.cache/editor-video."""
    from common import MODELS_DIR
    if filtro in _LAT:
        return _LAT[filtro]
    versao = run(["ffmpeg", "-hide_banner", "-version"]).splitlines()[0] if shutil.which("ffmpeg") else "?"
    arq = MODELS_DIR.parent / "latencias.json"
    dados = load_json(arq) or {}
    chave = f"{versao}|{filtro}"
    if chave not in dados:
        def onset(af: str) -> float:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                                  "aevalsrc='0.5*sin(2*PI*1000*t)*between(t,0.5,0.6)':s=48000:d=1.5", "-af",
                                  f"{af},aresample=48000", "-ac", "1", "-f", "s16le", "-"], capture_output=True).stdout
            import array
            amostras = array.array("h", raw)
            pico = max((abs(x) for x in amostras), default=0) or 1
            return next((i for i, x in enumerate(amostras) if abs(x) > 0.3 * pico), 0) / 48000
        try:
            dados[chave] = round(max(onset(filtro) - onset("anull"), 0.0), 4)
            arq.parent.mkdir(parents=True, exist_ok=True)
            save_json(arq, dados)
        except Exception:  # sem medição: não compensa (comportamento antigo)
            dados[chave] = 0.0
    _LAT[filtro] = dados[chave]
    return _LAT[filtro]


def cadeia_voz(lufs) -> str:
    """Tratamento da voz + compensação do atraso dos filtros (som e boca no mesmo quadro)."""
    voz = VOZ.format(lufs=lufs)
    lat = latencia(VOZ.format(lufs=-14))
    return voz + (f",atrim=start={lat:.4f},asetpts=PTS-STARTPTS" if lat > 0.001 else "")


def cadeia_limite() -> str:
    lat = latencia(LIMITE)
    return LIMITE + (f",atrim=start={lat:.4f},asetpts=PTS-STARTPTS,apad" if lat > 0.001 else "")


def proteger_rosto(clips: list, stats: list | None, tl: dict, work: Path, prep: dict | None = None) -> dict:
    """Rosto nunca tampado: para cada animação na frente da pessoa, mede a cobertura de olhos/boca quadro a quadro e
    aplica a menor mudança que libera o rosto (m["guarda"], usado no overlay). Devolve o resumo para o QA."""
    import rosto_guarda
    out = {"medidas": [], "ajustadas": [], "tampado": []}
    if not stats:
        return out
    frente = [(m, p) for m, p in sorted(clips, key=lambda c: c[0]["t0"]) if m.get("layer") == "front"]
    fixos = rosto_guarda.fixos_da_timeline(tl, (prep or {}).get("gfx", []), W, H)
    for m, path in frente:
        if m.get("rosto") == "livre":  # pedido explícito para cobrir (ex.: máscara de efeito no rosto)
            continue
        outros = [(o, p) for o, p in frente if o is not m and o["t0"] < m["t1"] and o["t1"] > m["t0"]]
        # transições (mão que cruza a tela) passam por cima de tudo de propósito; o resto desvia de legenda/gráficos
        d = rosto_guarda.guarda(Path(path), m, stats, tl.get("recuo", []), W, H, FPS, work / "motion", outros,
                                fixos if m.get("template") not in ("passa_mao",) else None)
        item = {"id": m.get("id"), "template": m.get("template"), "antes": d["antes"], "depois": d["depois"]}
        out["medidas"].append(item)
        if d["s"] != 1.0 or d["x"] or d["y"]:
            m["guarda"] = {"s": d["s"], "x": d["x"], "y": d["y"], "ax": d["ax"], "dy": d["dy"]}
            out["ajustadas"].append({**item, **m["guarda"]})
            log(f"   rosto livre: {m.get('id')} ({m.get('template')}) {d['antes']}→{d['depois']} quadros cobrindo "
                f"(escala {d['s']}, x {d['x']}, y {d['y']})")
        else:
            m.pop("guarda", None)
        if d["depois"] > rosto_guarda.TOLERA_QUADROS:
            out["tampado"].append(item)
        if d["s"] < 0.7:  # rosto livre custou tamanho: conferir se o texto ainda lê no celular
            out.setdefault("legibilidade", []).append({**item, "escala": d["s"]})
    return out


def preparar_composicao(tl: dict, project: Path, behind: list, front: list) -> dict:
    """Arquivos usados por toda a composição (uma vez por render): legendas, palavras atrás, gráficos e sons."""
    work = project / "work"
    gdir = work / "gfx"
    shutil.rmtree(gdir, ignore_errors=True)
    gdir.mkdir(parents=True)
    captions_ass(tl, work / "captions.ass", extra_front=front)
    if behind:
        behind_ass(tl, behind, work / "behind.ass")
    gfx = []
    import assets
    for k, g in enumerate(tl["graphics"]):
        if g["type"] == "progress":
            continue
        png = gdir / f"{k:02d}_{g['type']}.png"
        top_busy = any(m.get("zona") in ("topo", "barra") and m["t0"] < g["t1"] and m["t1"] > g["t0"]
                       for m in tl.get("motion", []))
        cta_top = g["type"] == "cta" and not top_busy and \
            max(caption_y(tl, t) for t in (g["t0"], (g["t0"] + g["t1"]) / 2)) > assets.SAFE_BOTTOM - 220
        gcfg = {**tl["graphics_cfg"], "logo_position": g.get("position"), "logo_opacity": g.get("opacity", 0.85)}
        graphic_png(g["type"], g["text"], tl["style"], gcfg, png, top=cta_top)
        gfx.append((png, g))
    return {"gfx": gfx, "sfx_files": make_sfx(work / "sfx")}


def compose(tl: dict, project: Path, aroll: Path, mask: Path | None, behind: list, front: list,
            out: Path, preset: str, motion_clips: list | None = None, prep: dict | None = None,
            janela: tuple | None = None, audio: bool = True) -> None:
    """Grafo ffmpeg da composição. Sem `janela`: vídeo inteiro com áudio (modo clássico).
    Com `janela` = (a, b, quadros): só aquele trecho, sem áudio, com o tempo absoluto preservado dentro do grafo
    (legendas, efeitos e animações usam o mesmo relógio do vídeo inteiro) e saída começando em 0."""
    motion_clips = motion_clips or []
    prep = prep or preparar_composicao(tl, project, behind, front)
    j0, j1 = (janela[0], janela[1]) if janela else (0.0, 0.0)
    if janela:
        motion_clips = [(m, p) for m, p in motion_clips if m["t0"] < j1 and m["t1"] > j0]
    brolls = [r for r in tl["broll"] if not janela or (r["t0"] < j1 and r["t1"] > j0)]
    gfx_sel = [(png, g) for png, g in prep["gfx"] if not janela or (g["t0"] < j1 and g["t1"] > j0)]
    # trecho: lê o A-roll (e a máscara) a partir de meio segundo antes, mantendo os tempos originais (-copyts),
    # e corta no grafo com meia-imagem de tolerância (o MKV guarda tempos em ms: 12,000 s pode virar 11,999 s)
    shift = ""
    seek = ["-ss", f"{max(j0 - 0.5, 0):.6f}", "-t", f"{j1 - j0 + 0.75:.6f}"] if janela else []
    m_behind = [(m, p) for m, p in motion_clips if m.get("layer") == "behind" and mask]
    work = project / "work"
    sfx_files = prep["sfx_files"]
    total = tl["duration"]

    inputs: list[str] = [*seek, "-i", str(aroll)]
    n_in = 1
    mask_idx = None
    if (behind or m_behind) and mask:
        inputs += [*seek, "-i", str(mask)]
        mask_idx, n_in = n_in, n_in + 1
    motion_idx = []
    for m, p in motion_clips:
        inputs += ["-i", str(p)]
        motion_idx.append((n_in, m))
        n_in += 1
    broll_idx = []
    for b_ in brolls:
        dur = b_["t1"] - b_["t0"]
        if b_["kind"] == "image":
            inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", b_["src"]]
        else:
            inputs += ["-ss", f"{b_['src_in']:.3f}", "-t", f"{dur:.3f}", "-i", b_["src"]]
        broll_idx.append(n_in)
        n_in += 1
    gfx = []
    for png, g in gfx_sel:
        inputs += ["-loop", "1", "-t", f"{g['t1'] - g['t0']:.3f}", "-i", str(png)]
        gfx.append((n_in, g))
        n_in += 1
    sfx_idx = []
    for s in (tl["sfx"] if audio else []):
        inputs += ["-i", str(sfx_files[s["type"]])]
        sfx_idx.append((n_in, s))
        n_in += 1
    music_idx = None
    if tl.get("music") and audio:
        inputs += ["-stream_loop", "-1", "-i", tl["music"]["path"]]
        music_idx, n_in = n_in, n_in + 1

    splits = [b_ for b_ in brolls if b_["mode"] == "split"]
    f: list[str] = []
    n_copies = 1 + (1 if mask_idx is not None else 0) + len(splits)
    f.append(f"[0:v]{shift}{tl['grade']},format=yuv420p,split={n_copies}" + "".join(f"[a{i}]" for i in range(n_copies)))
    cur, copy = "a0", 1
    def motion_in(idx: int, m: dict, lbl: str) -> None:
        f.append(f"[{idx}:v]fps={FPS},format=rgba,setpts=PTS-STARTPTS+{m['t0']:.3f}/TB[{lbl}]")

    if mask_idx is not None:
        f.append(f"[{cur}]ass=behind.ass:fontsdir=fonts[bt0]" if behind else f"[{cur}]null[bt0]")
        bcur = "bt0"
        for k, (idx, m) in enumerate((i, m) for i, m in motion_idx if m.get("layer") == "behind"):
            motion_in(idx, m, f"mb{k}")
            f.append(f"[{bcur}][mb{k}]overlay=0:0:eof_action=pass:enable='between(t,{m['t0']:.3f},{m['t1']:.3f})'[bt{k + 1}]")
            bcur = f"bt{k + 1}"
        f.append(f"[{mask_idx}:v]{shift}format=gray,scale={W}:{H}[mk]")
        f.append(f"[a{copy}][mk]alphamerge[fg]")
        wins = [(b["t0"], b["t1"]) for b in behind] + [(m["t0"], m["t1"]) for m, _ in m_behind]
        en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in wins)
        f.append(f"[{bcur}][fg]overlay=0:0:enable='{en}'[vb]")
        cur, copy = "vb", copy + 1

    for k, (b, idx) in enumerate(zip(brolls, broll_idx)):
        t0, t1 = b["t0"], b["t1"]
        dur = t1 - t0
        lbl = f"br{k}"
        if b["mode"] == "full":
            f.append(f"[{idx}:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                     f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t0:.3f}/TB[{lbl}]")
            x = f"'if(lt(t-{t0:.3f},0.16),{W}*(1-(t-{t0:.3f})/0.16),0)'"
            f.append(f"[{cur}][{lbl}]overlay=x={x}:y=0:eof_action=pass:enable='between(t,{t0:.3f},{t1:.3f})'[v{lbl}]")
        elif b["mode"] == "card":
            cw, chh = (620, 880) if H > W else (int(W * 0.5) // 2 * 2, int(H * 0.62) // 2 * 2)
            f.append(f"[{idx}:v]fps={FPS},scale={cw}:{chh}:force_original_aspect_ratio=increase,crop={cw}:{chh},"
                     f"pad={cw + 20}:{chh + 20}:10:10:color=0xF4EFE6,format=rgba,"
                     f"fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(dur - 0.3, 0):.3f}:d=0.3:alpha=1,"
                     f"setpts=PTS-STARTPTS+{t0:.3f}/TB[{lbl}]")
            y = f"'{int(H * 0.13)}+40*max(0,1-(t-{t0:.3f})/0.35)'"
            f.append(f"[{cur}][{lbl}]overlay=x=(W-w)/2:y={y}:eof_action=pass:enable='between(t,{t0:.3f},{t1:.3f})'[v{lbl}]")
        elif H > W:  # split vertical: B-roll em cima, pessoa embaixo
            f.append(f"[{idx}:v]fps={FPS},scale={W}:{H // 2}:force_original_aspect_ratio=increase,crop={W}:{H // 2},"
                     f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t0:.3f}/TB[{lbl}t]")
            f.append(f"[a{copy}]crop={W}:{H // 2}:0:{int(H * 0.18)},pad={W}:{H}:0:{H // 2},"
                     f"drawbox=x=0:y={H // 2 - 4}:w={W}:h=8:color=0x22E06B:t=fill[{lbl}l]")
        else:  # split horizontal: B-roll à esquerda, pessoa à direita
            f.append(f"[{idx}:v]fps={FPS},scale={W // 2}:{H}:force_original_aspect_ratio=increase,crop={W // 2}:{H},"
                     f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t0:.3f}/TB[{lbl}t]")
            f.append(f"[a{copy}]crop={W // 2}:{H}:{W // 4}:0,pad={W}:{H}:{W // 2}:0,"
                     f"drawbox=x={W // 2 - 4}:y=0:w=8:h={H}:color=0x22E06B:t=fill[{lbl}l]")
            copy += 1
            f.append(f"[{lbl}l][{lbl}t]overlay=0:0:eof_action=pass[{lbl}]")
            f.append(f"[{cur}][{lbl}]overlay=0:0:enable='between(t,{t0:.3f},{t1:.3f})'[v{lbl}]")
        cur = f"v{lbl}"

    if tl.get("recuo"):
        # recuo: a cena encolhe e desce (ancorada embaixo) para abrir o alto do quadro para card/manchete,
        # com o próprio quadro ampliado, desfocado e escurecido preenchendo o fundo
        k_expr = "+".join(f"{1 - r['s']:.3f}*clip((t-{r['t0']:.3f})/0.35,0,1)*clip(({r['t1']:.3f}-t)/0.35,0,1)"
                          for r in tl["recuo"])
        sc = f"(1-({k_expr}))"
        f.append(f"[{cur}]split[rc1][rc2]")
        f.append(f"[rc2]scale={int(W * 1.25) // 2 * 2}:-2,crop={W}:{H},boxblur=28:2,eq=brightness=-0.22:saturation=0.8[rcb]")
        f.append(f"[rc1]scale=w='2*trunc({W}*{sc}/2)':h='2*trunc({H}*{sc}/2)':eval=frame[rcf]")
        f.append(f"[rcb][rcf]overlay=x='(W-w)/2':y='H-h':eval=frame,format=yuv420p[vrc]")
        cur = "vrc"

    for k, (idx, m) in enumerate((i, m) for i, m in motion_idx if m.get("layer") in ("front", "full")):
        motion_in(idx, m, f"mf{k}")
        g = m.get("guarda")
        xy = "0:0"
        if g:  # rosto livre: a animação desce/sobe/vai para o lado/diminui (rosto_guarda.py)
            f.append(f"[mf{k}]scale={round(W * g['s']) // 2 * 2}:{round(H * g['s']) // 2 * 2}[mf{k}g]")
            xy = f"{g['x']}:{g['y']}"
            motion_lbl = f"mf{k}g"
        else:
            motion_lbl = f"mf{k}"
        f.append(f"[{cur}][{motion_lbl}]overlay={xy}:eof_action=pass:enable='between(t,{m['t0']:.3f},{m['t1']:.3f})'[vm{k}]")
        cur = f"vm{k}"

    if any(g["type"] == "progress" for g in tl["graphics"]):
        color = tl["graphics_cfg"]["accent"].lstrip("#")
        f.append(f"[{cur}]drawbox=x=0:y=0:w={W}:h=14:color=black@0.35:t=fill,"
                 f"drawbox=x=0:y=0:w='{W}*t/{total:.3f}':h=14:color=0x{color}:t=fill[vp]")
        cur = "vp"
    for k, (idx, g) in enumerate(gfx):
        t0, t1 = g["t0"], g["t1"]
        dur = t1 - t0
        f.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d=0.22:alpha=1,"
                 f"fade=t=out:st={max(dur - 0.22, 0):.3f}:d=0.22:alpha=1,setpts=PTS-STARTPTS+{t0:.3f}/TB[g{k}]")
        y = f"'34*max(0,1-(t-{t0:.3f})/0.25)'"
        f.append(f"[{cur}][g{k}]overlay=x=0:y={y}:eof_action=pass:enable='between(t,{t0:.3f},{t1:.3f})'[vg{k}]")
        cur = f"vg{k}"
    cur = fx_chain(f, cur, tl.get("fx", []))
    fim = (f",trim=start={max(j0 - 0.5 / FPS, 0):.6f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1"
           if janela else "")
    f.append(f"[{cur}]ass=captions.ass:fontsdir=fonts,format=yuv420p{fim}[vout]")
    if not audio:
        tag = f"{j0:07.2f}".replace(".", "_")
        graph = work / f"graph_{tag}.txt"
        graph.write_text(";\n".join(f), encoding="utf-8")
        ffmpeg([*(["-copyts"] if janela else []), *inputs, "-filter_complex_script", graph.name, "-map", "[vout]", "-an",
                *(["-frames:v", str(janela[2])] if janela else ["-t", f"{total:.3f}"]), "-r", str(FPS),
                "-c:v", "libx264", "-preset", preset, "-crf", "19" if preset == "medium" else "18",
                "-profile:v", "high", "-pix_fmt", "yuv420p", str(out.resolve())], cwd=work)
        return

    lufs = tl["audio"]["lufs"]
    f.append(f"[0:a]{cadeia_voz(lufs)}[voice]")
    mix = ["[voice]"]
    if music_idx is not None:
        mv = tl["music"].get("volume", 0.12)
        f.append("[voice]asplit=2[voice_m][voice_sc]")
        f.append(f"[{music_idx}:a]atrim=0:{total:.3f},volume={mv},aresample=48000[mus]")
        f.append("[mus][voice_sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[duck]")
        mix = ["[voice_m]", "[duck]"]
    for k, (idx, s) in enumerate(sfx_idx):
        ms = int(s["t"] * 1000)
        f.append(f"[{idx}:a]volume={s['gain'] * 0.5:.3f},adelay={ms}|{ms}[s{k}]")
        mix.append(f"[s{k}]")
    if len(mix) > 1:
        f.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,{cadeia_limite()}[aout]")
    else:
        f.append(f"[voice]{cadeia_limite()}[aout]")

    graph = work / "graph.txt"
    graph.write_text(";\n".join(f), encoding="utf-8")
    args = [*inputs, "-filter_complex_script", "graph.txt", "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", preset, "-crf", "19" if preset == "medium" else "18",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(out.resolve())]
    # caminhos relativos (behind.ass, captions.ass, fonts) são resolvidos dentro de work/
    ffmpeg(args, cwd=work)


def mix_audio(tl: dict, aroll: Path, prep: dict, out: Path) -> None:
    """Áudio final sozinho (voz tratada + SFX + trilha + loudness), igual ao da composição clássica."""
    total = tl["duration"]
    inputs: list[str] = ["-i", str(aroll)]
    n_in = 1
    sfx_idx = []
    for s in tl["sfx"]:
        inputs += ["-i", str(prep["sfx_files"][s["type"]])]
        sfx_idx.append((n_in, s))
        n_in += 1
    music_idx = None
    if tl.get("music"):
        inputs += ["-stream_loop", "-1", "-i", tl["music"]["path"]]
        music_idx, n_in = n_in, n_in + 1
    f: list[str] = []
    lufs = tl["audio"]["lufs"]
    f.append(f"[0:a]{cadeia_voz(lufs)}[voice]")
    mix = ["[voice]"]
    if music_idx is not None:
        mv = tl["music"].get("volume", 0.12)
        f.append("[voice]asplit=2[voice_m][voice_sc]")
        f.append(f"[{music_idx}:a]atrim=0:{total:.3f},volume={mv},aresample=48000[mus]")
        f.append("[mus][voice_sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[duck]")
        mix = ["[voice_m]", "[duck]"]
    for k, (idx, s) in enumerate(sfx_idx):
        ms = int(s["t"] * 1000)
        f.append(f"[{idx}:a]volume={s['gain'] * 0.5:.3f},adelay={ms}|{ms}[s{k}]")
        mix.append(f"[s{k}]")
    if len(mix) > 1:
        f.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,{cadeia_limite()}[aout]")
    else:
        f.append(f"[voice]{cadeia_limite()}[aout]")
    graph = out.with_suffix(".graph.txt")
    graph.write_text(";\n".join(f), encoding="utf-8")
    tmp = out.with_name(out.stem + ".tmp.m4a")
    ffmpeg([*inputs, "-filter_complex_script", str(graph), "-map", "[aout]", "-t", f"{total:.3f}",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(tmp)])
    os.replace(tmp, out)


def qa(out: Path, tl: dict, qa_dir: Path, name: str) -> dict:
    info = probe(out)
    loud = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"])
    lufs = next((l.split()[1] for l in loud.splitlines()[::-1] if l.strip().startswith("I:")), "?")
    times = [min(sh["t0"] + 0.15, tl["duration"] - 0.1) for sh in tl["shots"]][:24]
    sheet = qa_dir / f"{name}_cortes.jpg"
    sel = "+".join(f"eq(n\\,{round(t * FPS)})" for t in times)  # um quadro exato por plano
    ffmpeg(["-i", str(out), "-vf", f"select='{sel}',scale=270:480,tile=6x4:padding=6:color=white",
            "-frames:v", "1", "-vsync", "vfr", str(sheet)])
    return {"duration": round(info["duration"], 2), "lufs": lufs, "sheet": str(sheet)}


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    # final: veryfast/crf 18 tem a mesma qualidade visível do medium/crf 19 e codifica ~40% mais rápido
    # (Instagram e TikTok recomprimem de qualquer jeito); --max usa medium para arquivo de arquivo/YouTube
    preset = "ultrafast" if "--draft" in sys.argv else ("medium" if "--max" in sys.argv else "veryfast")
    # prévia de um trecho (--de A --ate B): só as animações e os trechos de 4 s dessa janela; nada vira versão
    previa = None
    if "--de" in sys.argv and "--ate" in sys.argv:
        previa = (float(sys.argv[sys.argv.index("--de") + 1]), float(sys.argv[sys.argv.index("--ate") + 1]))
        preset = "ultrafast"
    paths = project_paths(project)
    proj = load_json(paths["project"])
    tl = load_json(paths["timeline"])
    if not tl:
        raise EditorError("timeline.json não encontrado. Rode plan.py.")
    global W, H, FPS
    W, H, FPS = tl.get("w", 1080), tl.get("h", 1920), tl.get("fps", 30)
    import assets
    assets.set_format(W, H)
    t_start = time.time()
    tempos: list[tuple[str, float]] = []

    def etapa(nome: str, _t=[t_start]) -> None:
        agora = time.time()
        tempos.append((nome, agora - _t[0]))
        _t[0] = agora

    work = paths["work"]
    reg = revisao.Registro()
    prepare_fonts(tl, work)
    has_face = face_for_shots(tl, work)
    log(f"   rosto detectado: {'sim' if has_face else 'não'}")
    etapa("rosto")
    chaves_planos = [revisao.chave_plano(sh, W, H, FPS) for sh in tl["shots"]]
    aroll = render_shots(tl, work, "ultrafast", reg, chaves_planos)  # intermediário: rápido e quase sem perda (crf 13)
    etapa("planos")
    mask, stats = None, None
    motions = tl.get("motion", [])
    if precisa_mascara(tl, has_face):
        mask, stats = mascara_por_plano(tl, work, chaves_planos, reg)
    etapa("máscara")
    chaves_motion = {m.get("id"): revisao.chave_motion(m, tl, chaves_planos, bool(mask), work) for m in motions}
    clips = []
    if motions:
        from concurrent.futures import ThreadPoolExecutor

        from motion import hand_track, render_clip
        if previa:  # prévia: só as animações que aparecem na janela
            motions = [m for m in motions if m["t0"] < previa[1] and m["t1"] > previa[0]]
        novos = [m for m in motions if not (work / "motion" / f"clip_{chaves_motion[m.get('id')]}.mov").exists()]
        hands = hand_track(aroll, FPS, W, H) if any(m.get("hand") for m in novos) else None

        def um(m: dict) -> Path:
            k = chaves_motion[m.get("id")]
            hit = (work / "motion" / f"clip_{k}.mov").exists()
            t_ini = time.time()
            path = render_clip(m, project, aroll, mask, tl, hands, chave=k, chaves_planos=chaves_planos)
            reg.anota("motion", f"{m.get('id')}:{m.get('template') or m.get('page')}", hit, k,
                      "" if hit else "animação nova ou alterada", None if hit else round(time.time() - t_ini, 1),
                      janela=(m["t0"], m["t1"]))
            return path
        # duas animações por vez: enquanto uma abre o Chromium ou extrai quadros, a outra usa a CPU
        with ThreadPoolExecutor(max_workers=2) as pool:
            clips = list(zip(motions, pool.map(um, motions)))
    etapa("motion")
    tl["recuo"] = recuo_windows(motions, stats)
    if tl["recuo"]:
        log(f"   recuo (pessoa desce para abrir o topo): {len(tl['recuo'])} trecho(s)")
    behind, front = place_behind(tl, stats)
    behind, moved = fit_behind(tl, behind)  # sem espaço acima da cabeça: a palavra sai (não vai para o rosto)
    if moved:
        log(f"   palavras atrás puladas (cabeça encostada no topo): {', '.join(b['text'] for b in moved)}")
    for b in behind:
        size = b["size"]
        y1 = b["head_top"] + int(size * 0.2)
        luma = background_luma(aroll, (b["t0"] + b["t1"]) / 2, max(y1 - size, 0), y1)
        b["color"] = pick_color(tl["behind_cfg"]["color"], tl["graphics_cfg"]["accent"], luma)
    if tl["behind"]:
        log(f"   palavras atrás da pessoa: {len(behind)} | na frente (sem pessoa/cabeça instável): {len(front)}")

    proj["version"] = proj.get("version", 0) + (0 if previa else 1)
    v = proj["version"]
    name = f"previa_{previa[0]:05.1f}-{previa[1]:05.1f}" if previa else f"v{v}_{tl['style']}"
    out = paths["renders"] / f"{name}.mp4"
    paths["renders"].mkdir(parents=True, exist_ok=True)
    etapa("palavras atrás")
    prep = preparar_composicao(tl, project, behind, front)
    rosto = proteger_rosto(clips, stats, tl, work, prep)
    etapa("rosto livre")
    if os.environ.get("EDITOR_COMPOSICAO", "trechos") == "inteira" and not previa:
        compose(tl, project, aroll, mask, behind, front, out, preset, clips, prep=prep)  # modo clássico (um grafo)
    else:
        from concurrent.futures import ThreadPoolExecutor
        cache = Cache(work)
        fsig = revisao.fontes_sig(work)

        def trecho(j: tuple) -> Path:
            a_, b_, _nq = j
            k = revisao.chave_trecho(tl, a_, b_, chaves_planos, chaves_motion, bool(mask), preset, fsig)
            dst = cache.caminho("trechos", k, ".mp4")
            ident = f"{a_:05.1f}-{b_:05.1f}"
            if dst.exists():
                reg.anota("trecho", ident, True, k, janela=(a_, b_))
                return dst
            t_ini = time.time()
            tmp = dst.with_name(f"{k}.tmp.mp4")
            compose(tl, project, aroll, mask, behind, front, tmp, preset, clips, prep=prep, janela=j, audio=False)
            os.replace(tmp, dst)
            reg.anota("trecho", ident, False, k, "algo mudou neste trecho", round(time.time() - t_ini, 1), janela=(a_, b_))
            return dst
        js = [j for j in revisao.janelas(tl["duration"], FPS) if not previa or (j[0] < previa[1] and j[1] > previa[0])]
        with ThreadPoolExecutor(max_workers=2) as pool:
            partes = list(pool.map(trecho, js))
        ka = revisao.chave_audio(tl, chaves_planos)
        am = cache.caminho("audio", ka, ".m4a")
        if am.exists():
            reg.anota("audio", "mix", True, ka)
        else:
            t_ini = time.time()
            mix_audio(tl, aroll, prep, am)
            reg.anota("audio", "mix", False, ka, "voz, sons ou trilha mudaram", round(time.time() - t_ini, 1))
        if previa:
            a_, b_ = max(previa[0], 0.0), min(previa[1], tl["duration"])
            bruto = work / "previa_video.mp4"
            _concat(partes, bruto)
            ffmpeg(["-ss", f"{a_ - js[0][0]:.3f}", "-t", f"{b_ - a_:.3f}", "-i", str(bruto), "-ss", f"{a_:.3f}",
                    "-t", f"{b_ - a_:.3f}", "-i", str(am), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                    "-preset", "ultrafast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", str(out)])
            etapa("composição final")
            log(f"OK prévia: {out} ({b_ - a_:.1f}s em {time.time() - t_start:.1f}s) | {reg.linha()}")
            log("   tempos: " + " | ".join(f"{n} {s:.1f}s" for n, s in tempos if s >= 0.05))
            return
        _concat(partes, out, inputs=["-i", str(am)],
                extra=["-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart"])
    etapa("composição final")
    vdir = paths["versions"] / f"v{v}"
    vdir.mkdir(parents=True, exist_ok=True)
    save_json(vdir / "timeline.json", tl)
    save_json(vdir / "project.json", proj)
    if (work / "timeline_gerada.json").exists():  # a timeline exatamente como o plan.py gerou (para o rollback)
        shutil.copy2(work / "timeline_gerada.json", vdir / "timeline_gerada.json")
    save_json(paths["project"], proj)
    report = qa(out, tl, paths["qa"], name)
    etapa("QA")
    report["rosto"] = rosto
    for x in rosto.get("legibilidade", []):
        report.setdefault("alertas", []).append(f"{x['id']} diminuído para {x['escala']:.0%} para liberar o rosto: "
                                                f"conferir leitura no celular")
    if rosto["tampado"]:
        report.setdefault("alertas", []).append(
            "rosto tampado: " + ", ".join(f"{x['id']} ({x['depois']} quadros)" for x in rosto["tampado"]))
        log("   ATENÇÃO rosto tampado (QA reprova): " + ", ".join(f"{x['id']} {x['depois']}q" for x in rosto["tampado"]))
    report.update(version=v, file=str(out), seconds=round(time.time() - t_start, 1),
                  behind_used=[b["text"] for b in behind], behind_front=[b["text"] for b in front],
                  tempos={n: round(s, 1) for n, s in tempos})
    save_json(vdir / "qa.json", report)
    save_json(vdir / "revisao.json", {"versao": v, "resumo": reg.resumo(), "itens": reg.itens,
                                      "segundos": report["seconds"], "tempos": report["tempos"]})
    log(f"OK: {out} ({report['duration']}s, {report['lufs']} LUFS, render {report['seconds']}s)")
    log(f"   revisão: {reg.linha()}")
    log(f"   contato dos cortes: {report['sheet']}")
    log("   tempos: " + " | ".join(f"{n} {s:.1f}s" for n, s in tempos if s >= 0.05))

if __name__ == "__main__":
    main_guard(main)
