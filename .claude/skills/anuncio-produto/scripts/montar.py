#!/usr/bin/env python3
"""Monta e renderiza o anúncio: roteiro + narração + fotos -> cenas (HTML no Chromium) -> MP4 com som.

Uso: montar.py <projeto> [--roteiro roteiro.json] [--rascunho]
Saída: renders/<roteiro>_vN.mp4 + qa/<roteiro>_vN_cenas.jpg (um quadro por cena)
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from audio import make_sfx, music_bed
from common import (END_CARD, LEAD, FONTS_DIR, FPS, H, SKILL_DIR, STYLES_DIR, W, WEB_DIR, AdError, ffmpeg, load_json, log,
                    main_guard, probe, project_paths, run, save_json)



# ---------- cores ----------

def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, v)) * 255) for v in c)


def _mix(a: str, b: str, k: float) -> str:
    x, y = _rgb(a), _rgb(b)
    return _hex([x[i] * (1 - k) + y[i] * k for i in range(3)])


def _lum(h: str) -> float:
    r, g, b = _rgb(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def accent_from(palette: list[str]) -> str:
    """Cor mais viva do produto (nem branca, nem preta); sem cor viva, um coral neutro."""
    best, score = None, 0.0
    for c in palette:
        h, l, s = colorsys.rgb_to_hls(*_rgb(c))
        sc = s * (1 - abs(l - 0.5) * 1.6)
        if sc > score and 0.15 < l < 0.85:
            best, score = c, sc
    if not best or score < 0.12:
        return "#ff5a36"
    h, l, s = colorsys.rgb_to_hls(*_rgb(best))
    return _hex(colorsys.hls_to_rgb(h, min(max(l, 0.42), 0.55), max(s, 0.62)))  # mais vivo para tela


def colors(accent: str, style: dict, override: dict | None = None) -> dict:
    light = style.get("fundo") == "claro"
    c = {
        "destaque": accent, "destaque2": "#FFD21F",
        "fundo1": _mix(accent, "#000000", 0.62), "fundo2": _mix(accent, "#ffffff", 0.08),
        "escuro": "#121212", "escuro2": _mix(accent, "#000000", 0.78),
        "claro": _mix(accent, "#ffffff", 0.9), "claro2": _mix(accent, "#ffffff", 0.74),
        "titulo": "#1a1a1a" if light else "#ffffff",
        "texto_suave": "#6b6b6b" if light else "rgba(255,255,255,.72)",
        "cartao": "#ffffff", "texto_cartao": "#161616",
        "sobre_destaque": "#111111" if _lum(accent) > 0.6 else "#ffffff",
        "preco": accent if light else "#FFD21F",
        "alerta": "#E8243C", "ok": "#16a34a", "carrinho": "#FF4F2B",
    }
    c.update(override or {})
    return c


# ---------- roteiro -> cenas ----------

def norm(w: str) -> str:
    w = unicodedata.normalize("NFKD", w.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(ch for ch in w if not unicodedata.combining(ch)))


def word_time(words: list[dict], fala: int, needle: str) -> float | None:
    """Instante absoluto em que a palavra/trecho `needle` é dito dentro da fala."""
    key = [norm(x) for x in needle.split() if norm(x)]
    ws = [w for w in words if w["fala"] == fala]
    for i in range(len(ws)):
        if [norm(w["w"]) for w in ws[i:i + len(key)]] == key:
            return ws[i]["t0"]
    for w in ws:  # trecho parcial: primeira palavra que contém
        if key and key[0] in norm(w["w"]):
            return w["t0"]
    return None


def photo_url(ref, fotos: dict[str, str]) -> str:
    if ref is None:
        return next(iter(fotos.values()), "")
    if isinstance(ref, int):
        return list(fotos.values())[ref]
    if ref in fotos:
        return fotos[ref]
    stem = Path(str(ref)).stem
    if stem in fotos:
        return fotos[stem]
    raise AdError(f"Foto '{ref}' não existe. Fotos do projeto: {', '.join(fotos)}")


def build(project: Path, rot: dict, voz: dict, work: Path) -> tuple[dict, list[dict], float]:
    paths = project_paths(project)
    proj = load_json(paths["project"])
    style_name = rot.get("estilo") or proj.get("estilo", "tiktok_shop")
    style = load_json(STYLES_DIR / f"{style_name}.json")
    if not style:
        raise AdError(f"Estilo '{style_name}' não existe. Opções: {', '.join(p.stem for p in STYLES_DIR.glob('*.json'))}")
    style.update(rot.get("estilo_ajustes", {}))
    cuts = load_json(work.parent / "recortes.json", {}) if (work.parent / "recortes.json").exists() else {}
    assets = work / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    def serve(path: Path) -> str:
        dst = assets / f"{hashlib.sha1(str(path).encode()).hexdigest()[:8]}_{path.name}"
        if not dst.exists():
            shutil.copy2(path, dst)
        return f"/work/{dst.relative_to(work).as_posix()}"

    fotos = {Path(f).stem: serve(Path(f)) for f in proj["fotos"]}
    # recorte principal: o pedido no roteiro, senão a primeira foto com recorte bom
    cut_info = {Path(v["foto"]).stem: v for v in cuts.values()}
    hero = rot.get("recorte") or proj.get("recorte")
    if hero is None:
        hero = next((k for k, v in cut_info.items() if v.get("usar_recorte")), None)
    hero_info = cut_info.get(Path(str(hero)).stem) if hero else None
    produto = {k: proj.get(k) for k in ("nome", "nome_curto", "preco", "preco_antigo", "desconto", "parcelas")}
    produto.update({k: v for k, v in (rot.get("produto") or {}).items()})
    produto["fotos"] = fotos
    produto["foto_principal"] = photo_url(proj.get("foto_principal"), fotos)
    if hero_info and hero_info.get("recorte") and Path(hero_info["recorte"]).exists():
        produto["recorte"] = serve(Path(hero_info["recorte"]))
        produto["proporcao"] = hero_info.get("proporcao", 0.6)
    palette = (hero_info or {}).get("cores") or next((v.get("cores") for v in cut_info.values() if v.get("cores")), [])
    accent = proj.get("cor") or rot.get("cor") or accent_from(palette)
    cores = colors(accent, style, proj.get("cores"))

    falas = voz["falas"]
    words = [{**w, "t0": w["t0"] + LEAD, "t1": w["t1"] + LEAD} for w in voz["palavras"]]
    total = round(voz["duracao"] + LEAD + END_CARD, 3)
    # cada fala abre uma cena (ou continua a anterior); a cena vai até a próxima começar
    scenes = []
    for i, f in enumerate(rot["falas"]):
        cena = f.get("cena")
        start = 0.0 if i == 0 else falas[i]["t0"] + LEAD - 0.05
        if not cena or cena == "continua" or cena.get("tipo") == "continua":
            if scenes:
                continue
            cena = {"tipo": "heroi"}
        s = json.loads(json.dumps(cena))
        s["t0"], s["fala"] = round(start, 3), i
        scenes.append(s)
    for k, s in enumerate(scenes):
        s["t1"] = scenes[k + 1]["t0"] if k + 1 < len(scenes) else total
        for key in ("foto",):
            if key in s:
                s[key] = photo_url(s[key], fotos)
        if s["tipo"] in ("foto", "detalhe") and "foto" not in s:
            s["foto"] = produto["foto_principal"]
        if s["tipo"] == "galeria" and s.get("fotos"):
            s["fotos"] = [photo_url(x, fotos) for x in s["fotos"]]
        # "em": palavra falada -> instante relativo à cena
        for it in s.get("itens", []) + s.get("linhas", []):
            if isinstance(it.get("em"), str):
                tw = next((word_time(words, f, it["em"]) for f in range(s["fala"], len(falas))
                           if word_time(words, f, it["em"]) is not None), None)
                if tw is not None:
                    it["at"] = round(max(tw - s["t0"] - 0.1, 0.05), 3)
        if s["tipo"] == "oferta" and "preco_at" not in s:
            num = re.sub(r"[^\d]", "", str(produto.get("preco") or ""))[:3]
            hit = next((w for w in words if w["fala"] >= s["fala"] and num and num in re.sub(r"[^\d]", "", w["w"])), None)
            if hit:
                s["preco_at"] = round(max(hit["t0"] - s["t0"] - 0.05, 0.3), 3)
        if s["tipo"] == "video":
            s.update(video_frames(Path(s.pop("video")).expanduser() if "video" in s else Path(proj["videos"][0]),
                                  s.get("inicio", 0.0), s["t1"] - s["t0"] + 0.4, work))
        if s["tipo"] == "cta":
            s.setdefault("legenda", False)  # o título do CTA já diz a frase; legenda em cima atrapalha
    params = {"cores": cores, "estilo": style, "produto": produto, "cenas": scenes, "palavras": words,
              "plataforma": proj.get("plataforma", "tiktok_shop"), "total": total}
    return params, sfx_events(scenes, style), total


def video_frames(src: Path, start: float, dur: float, work: Path) -> dict:
    if not src.exists():
        raise AdError(f"Vídeo do produto não encontrado: {src}")
    key = hashlib.sha1(f"{src}{src.stat().st_mtime_ns}{start}{dur}".encode()).hexdigest()[:10]
    d = work / f"vid_{key}"
    if not (d / "done").exists():
        d.mkdir(parents=True, exist_ok=True)
        ffmpeg(["-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}", "-vf",
                f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-q:v", "3",
                str(d / "%05d.jpg")])
        (d / "done").write_text("ok")
    return {"frames": f"/work/{d.relative_to(work).as_posix()}/%05d.jpg", "count": len(list(d.glob("*.jpg"))), "fps": FPS}


def sfx_events(scenes: list[dict], style: dict) -> list[dict]:
    if not (style.get("sfx") or style.get("sfx_leve")):
        return []
    light = not style.get("sfx")
    ev = []
    for k, s in enumerate(scenes):
        t0 = s["t0"]
        if k > 0:
            ev.append({"t": max(t0 - 0.1, 0), "som": "whoosh", "gain": 0.5 if light else 0.8})
        if light:
            if s["tipo"] in ("oferta",):
                ev.append({"t": t0 + s.get("preco_at", 0.55), "som": "brilho", "gain": 0.7})
            continue
        if s["tipo"] == "gancho":
            ev.append({"t": t0 + 0.2, "som": "boom", "gain": 0.9})
        for it in s.get("itens", []):
            if "at" in it:
                ev.append({"t": t0 + it["at"] + 0.1, "som": "pop", "gain": 0.7})
        if s["tipo"] == "oferta":
            ev.append({"t": t0 + s.get("preco_at", 0.55), "som": "venda", "gain": 0.9})
        if s["tipo"] == "cta":
            tap = t0 + 0.9
            while tap < s["t1"] - 0.2:
                ev.append({"t": tap, "som": "click", "gain": 0.8})
                tap += 1.2
        if s["tipo"] == "heroi":
            ev.append({"t": t0 + 0.45, "som": "brilho", "gain": 0.6})
    return ev


# ---------- render ----------

def render_scenes(params: dict, total: float, work: Path, draft: bool) -> Path:
    page = WEB_DIR / "anuncio.html"
    sig = hashlib.sha1(json.dumps([params, total, draft], sort_keys=True, ensure_ascii=False).encode()
                       + page.read_bytes()).hexdigest()[:12]
    out = work / f"cenas_{sig}.mov"
    if out.exists():
        log("   cenas reaproveitadas (nada mudou na imagem)")
        return out
    for old in work.glob("cenas_*.mov"):
        old.unlink()
    job = {"page": "/anuncio.html", "out": str(out), "w": W, "h": H, "fps": 15 if draft else FPS, "duration": total,
           "params": params, "opaque": True, "webgl": False,
           "roots": {"/": str(WEB_DIR), "/fonts/": str(FONTS_DIR), "/work/": str(work)}}
    jf = work / "job.json"
    jf.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["node", str(SKILL_DIR / "scripts" / "render_html.mjs"), str(jf)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AdError(f"Render das cenas falhou:\n{proc.stderr[-2000:]}")
    log("   cenas: " + proc.stdout.strip().split(" -> ")[0])
    return out


def mix(project: Path, rot: dict, style: dict, scenes_mov: Path, sfx: list[dict], total: float, work: Path,
        out: Path, draft: bool) -> None:
    inputs = ["-i", str(scenes_mov), "-i", str(work / "voz.wav")]
    f = [f"[1:a]adelay={int(LEAD * 1000)}:all=1,highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,"
         f"loudnorm=I={style.get('lufs', -14)}:TP=-1.5:LRA=7,aresample=48000,apad=whole_dur={total:.3f}[voice]"]
    mixes = ["[voice_m]"]
    music = rot.get("musica", style.get("musica", "nenhuma"))
    idx = 2
    if music and music != "nenhuma":
        if music in ("batida", "suave"):
            mpath = music_bed(music, total, work / f"trilha_{music}.wav")
        else:
            mpath = Path(music).expanduser()
            if not mpath.is_absolute():
                mpath = project / mpath
            if not mpath.exists():
                raise AdError(f"Música não encontrada: {mpath}")
        inputs += ["-stream_loop", "-1", "-i", str(mpath)]
        vol = rot.get("musica_volume", style.get("musica_volume", 0.15))
        f.append("[voice]asplit=2[voice_m][voice_sc]")
        f.append(f"[{idx}:a]atrim=0:{total:.3f},volume={vol},aresample=48000,afade=t=out:st={max(total - 1, 0):.3f}:d=1[mus]")
        f.append("[mus][voice_sc]sidechaincompress=threshold=0.04:ratio=6:attack=15:release=250[duck]")
        mixes.append("[duck]")
        idx += 1
    else:
        f.append("[voice]anull[voice_m]")
    files = make_sfx(work.parent / "sfx")
    for k, e in enumerate(sfx):
        inputs += ["-i", str(files[e["som"]])]
        ms = int(e["t"] * 1000)
        f.append(f"[{idx}:a]volume={e['gain'] * 0.45:.3f},adelay={ms}|{ms}[s{k}]")
        mixes.append(f"[s{k}]")
        idx += 1
    f.append(f"{''.join(mixes)}amix=inputs={len(mixes)}:normalize=0:duration=first,alimiter=limit=0.95[aout]")
    graph = work / "mix.txt"
    graph.write_text(";\n".join(f), encoding="utf-8")
    ffmpeg([*inputs, "-filter_complex_script", str(graph), "-map", "0:v", "-map", "[aout]", "-t", f"{total:.3f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast" if draft else "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(out)])


def qa_sheet(out: Path, scenes: list[dict], sheet: Path) -> str:
    times = [min(s["t0"] + max((s["t1"] - s["t0"]) * 0.8, 0.5), s["t1"] - 0.3) for s in scenes][:12]
    sel = "+".join(f"between(t,{t:.3f},{t + 0.034:.3f})" for t in times)
    cols = min(len(times), 6)
    rows = (len(times) + cols - 1) // cols
    ffmpeg(["-i", str(out), "-vf", f"select='{sel}',scale=270:480,tile={cols}x{rows}:padding=6:color=white",
            "-frames:v", "1", "-vsync", "vfr", str(sheet)])
    loud = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"])
    return next((l.split()[1] for l in loud.splitlines()[::-1] if l.strip().startswith("I:")), "?")


def render(project: Path, script: Path, draft: bool = False) -> Path:
    t_start = time.time()
    paths = project_paths(project)
    rot = load_json(script)
    work = paths["work"] / script.stem
    voz = load_json(work / "voz.json")
    if not voz:
        raise AdError("Narração não gerada. Rode: anuncio.py voz <projeto>")
    params, sfx, total = build(project, rot, voz, work)
    save_json(work / "cenas.json", {k: v for k, v in params.items() if k != "palavras"})
    mov = render_scenes(params, total, work, draft)
    t_scenes = time.time() - t_start
    proj = load_json(paths["project"])
    n = proj.setdefault("versoes", {}).get(script.stem, 0) + 1
    proj["versoes"][script.stem] = n
    save_json(paths["project"], proj)
    paths["renders"].mkdir(parents=True, exist_ok=True)
    paths["qa"].mkdir(parents=True, exist_ok=True)
    out = paths["renders"] / f"{script.stem}_v{n}.mp4"
    mix(project, rot, params["estilo"], mov, sfx, total, work, out, draft)
    lufs = qa_sheet(out, params["cenas"], paths["qa"] / f"{script.stem}_v{n}_cenas.jpg")
    info = probe(out)
    log(f"OK: {out} ({info['duration']:.1f}s, {lufs} LUFS, {len(params['cenas'])} cenas, "
        f"render {time.time() - t_start:.0f}s: cenas {t_scenes:.0f}s)")
    log(f"   quadros por cena: {paths['qa'] / f'{script.stem}_v{n}_cenas.jpg'}")
    return out


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    script = project / "roteiro.json"
    if "--roteiro" in sys.argv:
        script = Path(sys.argv[sys.argv.index("--roteiro") + 1])
        script = script if script.is_absolute() else project / script
    render(project, script, "--rascunho" in sys.argv)


if __name__ == "__main__":
    main_guard(main)
