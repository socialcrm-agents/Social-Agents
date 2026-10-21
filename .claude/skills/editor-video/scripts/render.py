#!/usr/bin/env python3
"""Renderiza timeline.json em MP4 1080x1920 (H.264 + AAC), criando uma nova versão.

Etapas: rastreio de rosto -> planos com zoom animado -> A-roll contínuo -> máscara da
pessoa (se houver palavras atrás) -> legendas/gráficos/SFX -> um único grafo ffmpeg
(cor, texto atrás da pessoa, B-roll, gráficos, legendas, mixagem e loudness) -> QA.

Uso: render.py <projeto> [--draft]   (--draft: preset rápido para revisar)
"""

from __future__ import annotations

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
                    tracks[sh["clip"]] = face_track(sh["src"])
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
            has_word = any(b["t0"] < sh["t1"] and b["t1"] > sh["t0"] for b in tl["behind"])
            target_y = 0.48 if has_word else 0.40
            sh["cx"] = round(min(max((fx * z - 0.5) / (z - 1), 0), 1), 3)
            sh["cy"] = round(min(max((fy * z - target_y) / (z - 1), 0), 1), 3)
            # queixo no quadro final (px): a legenda desse plano fica sempre abaixo dele
            fh = statistics.median(p["h"] for p in pts)
            zf = max(sh["zoom0"], sh["zoom1"])
            face_y = fy * zf * H - (zf * H - H) * sh["cy"]
            sh["chin"] = int(face_y + 0.62 * fh * zf * H)
    return found


def render_shots(tl: dict, work: Path, preset: str) -> Path:
    d = work / "shots"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    files = []
    for n, sh in enumerate(tl["shots"]):
        dur = sh["out"] - sh["in"]
        z0, z1 = sh["zoom0"], sh["zoom1"]
        z = f"({z0}+{z1 - z0:.4f}*t/{dur:.3f})"
        vf = (f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
              f"scale=w='2*trunc({W}*{z}/2)':h='2*trunc({H}*{z}/2)':eval=frame:flags=bicubic,"
              f"crop={W}:{H}:x='(in_w-{W})*{sh['cx']}':y='(in_h-{H})*{sh['cy']}',setsar=1,format=yuv420p")
        out = d / f"{n:03d}.mp4"
        ffmpeg(["-ss", f"{sh['in']:.3f}", "-i", sh["src"], "-t", f"{dur:.3f}", "-vf", vf,
                "-af", f"aresample=48000,afade=t=in:d=0.012,afade=t=out:st={max(dur - 0.02, 0):.3f}:d=0.02",
                "-c:v", "libx264", "-preset", preset, "-crf", "15", "-c:a", "pcm_s16le", str(out.with_suffix(".mkv"))])
        files.append(out.with_suffix(".mkv"))
    lst = d / "list.txt"
    lst.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    aroll = work / "aroll.mkv"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(aroll)])
    return aroll


def fit_behind(tl: dict, behind: list[dict]) -> tuple[list[dict], list[dict]]:
    """Garante que ~70% da palavra fique visível acima da cabeça, dentro da zona segura.

    Reduz a fonte quando falta espaço; se mesmo assim não couber (cabeça encostada no topo),
    a palavra vai para a frente.
    """
    from assets import WIDTH_FACTOR
    from common import SAFE_SIDE, SAFE_TOP
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
        if not stats:
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


def compose(tl: dict, project: Path, aroll: Path, mask: Path | None, behind: list, front: list,
            out: Path, preset: str) -> None:
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
    if behind and mask:
        inputs += ["-i", str(mask)]
        mask_idx, n_in = n_in, n_in + 1
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
        cta_top = g["type"] == "cta" and max(caption_y(tl, t) for t in (g["t0"], (g["t0"] + g["t1"]) / 2)) > 1250
        graphic_png(g["type"], g["text"], tl["style"], tl["graphics_cfg"], png, top=cta_top)
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
    if mask_idx is not None:
        f.append(f"[{cur}]ass=behind.ass:fontsdir=fonts[bt]")
        f.append(f"[{mask_idx}:v]format=gray,scale={W}:{H}[mk]")
        f.append(f"[a{copy}][mk]alphamerge[fg]")
        en = "+".join(f"between(t,{b['t0']:.3f},{b['t1']:.3f})" for b in behind)
        f.append(f"[bt][fg]overlay=0:0:enable='{en}'[vb]")
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
            f.append(f"[{idx}:v]fps={FPS},scale=620:880:force_original_aspect_ratio=increase,crop=620:880,"
                     f"pad=640:900:10:10:color=0xF4EFE6,format=rgba,"
                     f"fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(dur - 0.3, 0):.3f}:d=0.3:alpha=1,"
                     f"setpts=PTS-STARTPTS+{t0:.3f}/TB[{lbl}]")
            y = f"'250+40*max(0,1-(t-{t0:.3f})/0.35)'"
            f.append(f"[{cur}][{lbl}]overlay=x=(W-w)/2:y={y}:eof_action=pass:enable='between(t,{t0:.3f},{t1:.3f})'[v{lbl}]")
        else:  # split: B-roll em cima, pessoa embaixo
            f.append(f"[{idx}:v]fps={FPS},scale={W}:{H // 2}:force_original_aspect_ratio=increase,crop={W}:{H // 2},"
                     f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t0:.3f}/TB[{lbl}t]")
            f.append(f"[a{copy}]crop={W}:{H // 2}:0:{int(H * 0.18)},pad={W}:{H}:0:{H // 2},"
                     f"drawbox=x=0:y={H // 2 - 4}:w={W}:h=8:color=0x22E06B:t=fill[{lbl}l]")
            copy += 1
            f.append(f"[{lbl}l][{lbl}t]overlay=0:0:eof_action=pass[{lbl}]")
            f.append(f"[{cur}][{lbl}]overlay=0:0:enable='between(t,{t0:.3f},{t1:.3f})'[v{lbl}]")
        cur = f"v{lbl}"

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
    fonts_link = work / "fonts"
    if not fonts_link.exists():
        fonts_link.symlink_to(FONTS_DIR, target_is_directory=True)
    args = [*inputs, "-filter_complex_script", "graph.txt", "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", preset, "-crf", "19",
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
    sel = "+".join(f"between(t,{t:.3f},{t + 0.034:.3f})" for t in times)
    ffmpeg(["-i", str(out), "-vf", f"select='{sel}',scale=270:480,tile=6x4:padding=6:color=white",
            "-frames:v", "1", "-vsync", "vfr", str(sheet)])
    return {"duration": round(info["duration"], 2), "lufs": lufs, "sheet": str(sheet)}


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    preset = "ultrafast" if "--draft" in sys.argv else "medium"
    paths = project_paths(project)
    proj = load_json(paths["project"])
    tl = load_json(paths["timeline"])
    if not tl:
        raise EditorError("timeline.json não encontrado. Rode plan.py.")
    t_start = time.time()
    work = paths["work"]
    has_face = face_for_shots(tl, work)
    log(f"   rosto detectado: {'sim' if has_face else 'não'}")
    aroll = render_shots(tl, work, "veryfast")
    mask, stats = None, None
    if tl["behind"] and has_face:
        from vision import person_mask
        mask = work / "mask.mp4"
        stats = person_mask(aroll, mask)
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
    compose(tl, project, aroll, mask, behind, front, out, preset)
    vdir = paths["versions"] / f"v{v}"
    vdir.mkdir(parents=True, exist_ok=True)
    save_json(vdir / "timeline.json", tl)
    save_json(vdir / "project.json", proj)
    save_json(paths["project"], proj)
    report = qa(out, tl, paths["qa"], name)
    report.update(version=v, file=str(out), seconds=round(time.time() - t_start, 1),
                  behind_used=[b["text"] for b in behind], behind_front=[b["text"] for b in front])
    save_json(vdir / "qa.json", report)
    log(f"OK: {out} ({report['duration']}s, {report['lufs']} LUFS, render {report['seconds']}s)")
    log(f"   contato dos cortes: {report['sheet']}")


if __name__ == "__main__":
    main_guard(main)
