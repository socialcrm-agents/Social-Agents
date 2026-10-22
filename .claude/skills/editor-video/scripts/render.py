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

from assets import behind_ass, caption_y, captions_ass, graphic_png, make_sfx
from common import FONTS_DIR, EditorError, ffmpeg, load_json, log, main_guard, probe, project_paths, run, save_json

W, H, FPS = 1080, 1920, 30


def face_for_shots(tl: dict, work: Path) -> bool:
    """Centraliza o zoom de cada plano no rosto. Devolve True se achou rosto."""
    try:
        from vision import face_track
    except EditorError:
        return False
    found = False
    tracks: dict[str, list] = {}
    for sh in tl["shots"]:
        if sh["clip"] not in tracks:
            cache = work / f"face_{sh['clip']}.json"
            tracks[sh["clip"]] = load_json(cache) if cache.exists() else None
            if tracks[sh["clip"]] is None:
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
            sh["cx"] = round(min(max((fx * z - 0.5) / (z - 1), 0), 1), 3)
            sh["cy"] = round(min(max((fy * z - target_y) / (z - 1), 0), 1), 3)
            # queixo no quadro final (px): a legenda desse plano fica sempre abaixo dele
            fh = statistics.median(p["h"] for p in pts)
            zf = max(sh["zoom0"], sh["zoom1"])
            face_y = fy * zf * H - (zf * H - H) * sh["cy"]
            sh["chin"] = int(face_y + 0.62 * fh * zf * H)
    return found


def render_shots(tl: dict, work: Path, preset: str) -> Path:
    """Monta o A-roll contínuo (cortes + zoom). Reaproveita se os planos não mudaram desde o último render."""
    import hashlib
    key = hashlib.sha1(json.dumps([tl["shots"], W, H, FPS], sort_keys=True).encode()).hexdigest()[:12]
    aroll = work / "aroll.mkv"
    stamp = work / "aroll.key"
    if aroll.exists() and stamp.exists() and stamp.read_text() == key:
        log("   A-roll reaproveitado (planos iguais)")
        return aroll
    d = work / "shots"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)

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
        out = d / f"{n:03d}.mp4"
        ffmpeg(["-ss", f"{sh['in']:.3f}", "-i", sh["src"], "-t", f"{dur:.3f}", "-vf", vf,
                "-af", f"{atempo}aresample=48000,afade=t=in:d=0.012,afade=t=out:st={max(tl_dur - 0.02, 0):.3f}:d=0.02,"
                f"apad,atrim=0:{tl_dur:.4f}",  # áudio com a duração exata do plano: sem deriva entre som e imagem
                "-frames:v", str(round(tl_dur * FPS)),
                "-c:v", "libx264", "-preset", preset, "-crf", "13", "-threads", "2",
                "-c:a", "pcm_s16le", str(out.with_suffix(".mkv"))])
        return out.with_suffix(".mkv")

    # um processo ffmpeg por plano, vários ao mesmo tempo (cada um usa pouco a CPU sozinho)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
        files = list(pool.map(lambda a: one(*a), enumerate(tl["shots"])))
    lst = d / "list.txt"
    lst.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(aroll)])
    stamp.write_text(key)
    (work / "mask.mp4").unlink(missing_ok=True)
    (work / "mask_stats.json").unlink(missing_ok=True)
    return aroll


# quanto do alto do quadro (px, em 1920) cada elemento de topo precisa livre
LIBERA = {"pergunta": 560, "etiqueta": 540, "manchete": 640, "palavra": 560, "proibido": 560, "tomadas": 700}


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
        out.append({"t0": m["t0"], "t1": m["t1"], "s": round(s, 3)})
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
            dst.symlink_to(src.resolve())
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
    if win("whip"):
        chain.append(f"avgblur=sizeX=60:sizeY=1:enable='{win('whip')}'")
    f.append(f"[{cur}]{','.join(chain)},setsar=1[vfx]")
    return "vfx"


DUR_FX = {"tremida": 0.3, "clarao": 0.08, "glitch": 0.22, "whip": 0.1}


def compose(tl: dict, project: Path, aroll: Path, mask: Path | None, behind: list, front: list,
            out: Path, preset: str, motion_clips: list | None = None) -> None:
    motion_clips = motion_clips or []
    m_behind = [(m, p) for m, p in motion_clips if m.get("layer") == "behind" and mask]
    work = project / "work"
    gdir = work / "gfx"
    shutil.rmtree(gdir, ignore_errors=True)
    gdir.mkdir(parents=True)
    captions_ass(tl, work / "captions.ass", extra_front=front)
    if behind:
        behind_ass(tl, behind, work / "behind.ass")
    sfx_files = make_sfx(work / "sfx")
    total = tl["duration"]

    inputs: list[str] = ["-i", str(aroll)]
    n_in = 1
    mask_idx = None
    if (behind or m_behind) and mask:
        inputs += ["-i", str(mask)]
        mask_idx, n_in = n_in, n_in + 1
    motion_idx = []
    for m, p in motion_clips:
        inputs += ["-i", str(p)]
        motion_idx.append((n_in, m))
        n_in += 1
    broll_idx = []
    for b in tl["broll"]:
        dur = b["t1"] - b["t0"]
        if b["kind"] == "image":
            inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", b["src"]]
        else:
            inputs += ["-ss", f"{b['src_in']:.3f}", "-t", f"{dur:.3f}", "-i", b["src"]]
        broll_idx.append(n_in)
        n_in += 1
    gfx = []
    for k, g in enumerate(tl["graphics"]):
        if g["type"] == "progress":
            continue
        png = gdir / f"{k:02d}_{g['type']}.png"
        import assets
        top_busy = any(m.get("zona") in ("topo", "barra") and m["t0"] < g["t1"] and m["t1"] > g["t0"]
                       for m in tl.get("motion", []))
        cta_top = g["type"] == "cta" and not top_busy and \
            max(caption_y(tl, t) for t in (g["t0"], (g["t0"] + g["t1"]) / 2)) > assets.SAFE_BOTTOM - 220
        gcfg = {**tl["graphics_cfg"], "logo_position": g.get("position"), "logo_opacity": g.get("opacity", 0.85)}
        graphic_png(g["type"], g["text"], tl["style"], gcfg, png, top=cta_top)
        inputs += ["-loop", "1", "-t", f"{g['t1'] - g['t0']:.3f}", "-i", str(png)]
        gfx.append((n_in, g))
        n_in += 1
    sfx_idx = []
    for s in tl["sfx"]:
        inputs += ["-i", str(sfx_files[s["type"]])]
        sfx_idx.append((n_in, s))
        n_in += 1
    music_idx = None
    if tl.get("music"):
        inputs += ["-stream_loop", "-1", "-i", tl["music"]["path"]]
        music_idx, n_in = n_in, n_in + 1

    splits = [b for b in tl["broll"] if b["mode"] == "split"]
    f: list[str] = []
    n_copies = 1 + (1 if mask_idx is not None else 0) + len(splits)
    f.append(f"[0:v]{tl['grade']},format=yuv420p,split={n_copies}" + "".join(f"[a{i}]" for i in range(n_copies)))
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
        f.append(f"[{mask_idx}:v]format=gray,scale={W}:{H}[mk]")
        f.append(f"[a{copy}][mk]alphamerge[fg]")
        wins = [(b["t0"], b["t1"]) for b in behind] + [(m["t0"], m["t1"]) for m, _ in m_behind]
        en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in wins)
        f.append(f"[{bcur}][fg]overlay=0:0:enable='{en}'[vb]")
        cur, copy = "vb", copy + 1

    for k, (b, idx) in enumerate(zip(tl["broll"], broll_idx)):
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
        f.append(f"[{cur}][mf{k}]overlay=0:0:eof_action=pass:enable='between(t,{m['t0']:.3f},{m['t1']:.3f})'[vm{k}]")
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
    f.append(f"[{cur}]ass=captions.ass:fontsdir=fonts,format=yuv420p[vout]")

    lufs = tl["audio"]["lufs"]
    f.append(f"[0:a]highpass=f=80,afftdn=nf=-28,acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2,"
             f"loudnorm=I={lufs}:TP=-1.5:LRA=9,aresample=48000[voice]")
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
        f.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.95[aout]")
    else:
        f.append("[voice]alimiter=limit=0.95[aout]")

    graph = work / "graph.txt"
    graph.write_text(";\n".join(f), encoding="utf-8")
    args = [*inputs, "-filter_complex_script", "graph.txt", "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", preset, "-crf", "19" if preset == "medium" else "18",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(out.resolve())]
    # caminhos relativos (behind.ass, captions.ass, fonts) são resolvidos dentro de work/
    ffmpeg(args, cwd=work)


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
    prepare_fonts(tl, work)
    has_face = face_for_shots(tl, work)
    log(f"   rosto detectado: {'sim' if has_face else 'não'}")
    etapa("rosto")
    aroll = render_shots(tl, work, "ultrafast")  # intermediário: rápido e quase sem perda (crf 13)
    etapa("planos")
    mask, stats = None, None
    motions = tl.get("motion", [])
    needs_mask = any(m.get("needs_video") or m.get("layer") == "behind" or m.get("zona") == "topo" for m in motions)
    if (tl["behind"] and has_face) or needs_mask:
        from vision import person_mask
        mask = work / "mask.mp4"
        cache = work / "mask_stats.json"
        if mask.exists() and cache.exists():
            stats = load_json(cache)
            log("   máscara reaproveitada")
        else:
            stats = person_mask(aroll, mask, W, H, FPS)
            save_json(cache, stats)
    etapa("máscara")
    clips = []
    if motions:
        from motion import hand_track, render_clip
        hands = hand_track(aroll, FPS, W, H) if any(m.get("hand") for m in motions) else None
        # duas animações por vez: enquanto uma abre o Chromium ou extrai quadros, a outra usa a CPU
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            clips = list(zip(motions, pool.map(lambda m: render_clip(m, project, aroll, mask, tl, hands), motions)))
    etapa("motion")
    tl["recuo"] = recuo_windows(motions, stats)
    if tl["recuo"]:
        log(f"   recuo (pessoa desce para abrir o topo): {len(tl['recuo'])} trecho(s)")
    behind, front = place_behind(tl, stats)
    behind, moved = fit_behind(tl, behind)
    front += moved
    for b in behind:
        size = b["size"]
        y1 = b["head_top"] + int(size * 0.2)
        luma = background_luma(aroll, (b["t0"] + b["t1"]) / 2, max(y1 - size, 0), y1)
        b["color"] = pick_color(tl["behind_cfg"]["color"], tl["graphics_cfg"]["accent"], luma)
    if tl["behind"]:
        log(f"   palavras atrás da pessoa: {len(behind)} | na frente (sem pessoa/cabeça instável): {len(front)}")

    proj["version"] = proj.get("version", 0) + 1
    v = proj["version"]
    name = f"v{v}_{tl['style']}"
    out = paths["renders"] / f"{name}.mp4"
    paths["renders"].mkdir(parents=True, exist_ok=True)
    etapa("palavras atrás")
    compose(tl, project, aroll, mask, behind, front, out, preset, clips)
    etapa("composição final")
    vdir = paths["versions"] / f"v{v}"
    vdir.mkdir(parents=True, exist_ok=True)
    save_json(vdir / "timeline.json", tl)
    save_json(vdir / "project.json", proj)
    save_json(paths["project"], proj)
    report = qa(out, tl, paths["qa"], name)
    etapa("QA")
    report.update(version=v, file=str(out), seconds=round(time.time() - t_start, 1),
                  behind_used=[b["text"] for b in behind], behind_front=[b["text"] for b in front],
                  tempos={n: round(s, 1) for n, s in tempos})
    save_json(vdir / "qa.json", report)
    log(f"OK: {out} ({report['duration']}s, {report['lufs']} LUFS, render {report['seconds']}s)")
    log(f"   contato dos cortes: {report['sheet']}")
    log("   tempos: " + " | ".join(f"{n} {s:.1f}s" for n, s in tempos if s >= 0.05))


if __name__ == "__main__":
    main_guard(main)
