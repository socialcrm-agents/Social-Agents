"""Gera os elementos do render: legendas ASS animadas, palavras atrás da pessoa,
gráficos PNG (gancho, CTA, lower third, capítulo) e efeitos sonoros sintetizados.

Tudo é criado do zero no projeto: nenhum sample ou template de terceiros, então não
há licença de efeito sonoro ou de arte a controlar.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import FONTS_DIR, SAFE_BOTTOM, SAFE_SIDE, SAFE_TOP, H, W, ffmpeg, safe_zone

FONT_FILES = {
    ("Anton", False): "Anton-Regular.ttf",
    ("Poppins", False): "Poppins-ExtraBold.ttf",
    ("Poppins Black", False): "Poppins-Black.ttf",
    ("DM Serif Display", False): "DMSerifDisplay-Regular.ttf",
    ("DM Serif Display", True): "DMSerifDisplay-Italic.ttf",
}
WIDTH_FACTOR = {"Anton": 0.47, "Poppins": 0.66, "DM Serif Display": 0.52}


def set_format(w: int, h: int) -> None:
    """Ajusta tamanho do quadro e zona segura (o render chama antes de gerar legendas e gráficos)."""
    global W, H, SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE
    W, H = w, h
    SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE = safe_zone(w, h)


def ass_color(hex_rgb: str, alpha: str = "00") -> str:
    h = hex_rgb.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def _header(styles: list[str]) -> str:
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding", *styles, "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", ""])


def _case(text: str, case: str) -> str:
    return text.upper() if case == "upper" else text


def caption_y(tl: dict, t: float) -> int:
    """Base da legenda no instante t: posição do estilo, mas sempre abaixo do queixo do plano atual."""
    c = tl["captions"]["cfg"]
    base = min(c["y"], SAFE_BOTTOM)
    if any(m["t0"] <= t < m["t1"] for m in tl.get("motion", []) if m.get("layer") == "full"):
        return base  # animação de tela cheia: não há rosto para desviar
    if any(m.get("zona") == "topo" and m["t0"] <= t < m["t1"] for m in tl.get("motion", [])) and \
            any(g["type"] == "cta" and g["t0"] <= t < g["t1"] for g in tl.get("graphics", [])):
        return SAFE_BOTTOM - 190  # CTA desceu (o alto está ocupado): a legenda fica logo acima do botão
    shot = next((s for s in tl["shots"] if s["t0"] <= t < s["t1"]), None)
    chin = shot.get("chin") if shot else None
    if not chin:
        return base
    return int(min(max(base, chin + int(c["size"] * 2.2)), SAFE_BOTTOM))


def captions_ass(tl: dict, out: Path, extra_front: list[dict] | None = None) -> None:
    c = tl["captions"]["cfg"]
    words = tl["words"]
    box = c.get("box")
    back = ass_color(c.get("box_color", "#000000"), c.get("box_alpha", "40")) if box else ass_color("#000000", "80")
    style = (f"Style: Cap,{c['font']},{c['size']},{ass_color(c['color'])},{ass_color(c['color'])},"
             f"{ass_color(c['outline_color']) if not box else back},{back},{-1 if c['bold'] else 0},0,0,0,100,100,0,0,"
             f"{3 if box else 1},{18 if box else c['outline']},{c['shadow']},2,{SAFE_SIDE},{SAFE_SIDE},0,1")
    kin = tl.get("behind_cfg", {})
    styles = [style]
    if extra_front:
        styles.append(f"Style: Kin,{kin['font']},{int(kin['size'] * 0.55)},{ass_color(kin['color'])},"
                      f"{ass_color(kin['color'])},{ass_color('#000000')},{ass_color('#000000', '90')},0,"
                      f"{-1 if kin.get('italic') else 0},0,0,100,100,0,0,1,4,0,8,{SAFE_SIDE},{SAFE_SIDE},0,1")
    lines = [_header(styles)]
    y = min(c["y"], SAFE_BOTTOM)
    hl = c.get("highlight", "none")
    italic = "\\i1" if c.get("emph_italic") else ""
    emph_open = f"{{\\fn{c['emph_font']}\\fs{c['emph_size']}\\c{ass_color(c['emph_color'])}{italic}}}"
    base_close = f"{{\\fn{c['font']}\\fs{c['size']}\\c{ass_color(c['color'])}\\i0}}"
    max_line = c["max_chars"] if c["font"] == "Anton" or W > H else 18

    def page_text(idx: list[int], active: int | None) -> str:
        tokens = []
        for i in idx:
            word = esc(_case(words[i]["w"], c["case"]))
            tokens.append(word.rstrip(".,;:") if c["case"] == "upper" else word)
        # quebra em 2 linhas equilibradas quando a página passa do limite (sem palavra órfã)
        brk = None
        if sum(len(t) + 1 for t in tokens) - 1 > max_line and len(tokens) > 1:
            brk = min(range(1, len(tokens)), key=lambda k: max(len(" ".join(tokens[:k])), len(" ".join(tokens[k:]))))
        parts = []
        for k, (i, word) in enumerate(zip(idx, tokens)):
            if k == brk:
                parts.append("\\N")
            if i == active and hl != "none":
                pop = "\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)" if c["animation"] == "pop" else ""
                parts.append(f"{{\\c{ass_color(hl)}{pop}}}{word}{{\\c{ass_color(c['color'])}\\fscx100\\fscy100}}")
            elif words[i]["emph"]:
                parts.append(f"{emph_open}{word}{base_close}")
            else:
                parts.append(word)
        return " ".join(parts).replace(" \\N ", "\\N")

    def y_at(t: float) -> int:
        return caption_y(tl, t)

    base_y = y
    for page in tl["captions"]["pages"]:
        idx = page["words"]
        y = y_at(page["t0"])
        pos = "" if c["animation"] == "slide" else f"\\pos({W // 2},{y})"
        intro = {"pop": "\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)", "fade": "\\fad(160,0)",
                 "slide": f"\\move({W // 2},{y + 26},{W // 2},{y},0,140)"}.get(c["animation"], "")
        if c["animation"] == "acumula":
            # a frase se monta: cada palavra aparece (fade curto) quando é dita, as anteriores ficam
            for k, i in enumerate(idx):
                t0 = page["t0"] if k == 0 else words[i]["t0"]
                t1 = words[idx[k + 1]]["t0"] if k + 1 < len(idx) else page["t1"]
                if t1 <= t0:
                    continue
                txt = page_text(idx[:k + 1], i)
                head, sep, last = txt.rpartition(" ")
                last = "{\\alpha&HFF&\\t(0,110,\\alpha&H00&)}" + last
                lines.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Cap,,0,0,0,,{{\\an2\\pos({W // 2},{y})\\blur0.6}}"
                             + (head + sep if sep else "") + last)
            continue
        if hl == "none":
            lines.append(f"Dialogue: 0,{ts(page['t0'])},{ts(page['t1'])},Cap,,0,0,0,,"
                         f"{{\\an2{pos}{intro}}}{page_text(idx, None)}")
            continue
        for k, i in enumerate(idx):
            t0 = page["t0"] if k == 0 else words[i]["t0"]
            t1 = words[idx[k + 1]]["t0"] if k + 1 < len(idx) else page["t1"]
            if t1 <= t0:
                continue
            p = pos if k else (pos + intro if c["animation"] != "slide" else intro)
            if k and c["animation"] == "slide":
                p = f"\\pos({W // 2},{y})"
            lines.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Cap,,0,0,0,,{{\\an2{p}}}{page_text(idx, i)}")

    y = base_y
    for b in extra_front or []:
        lines.append(f"Dialogue: 1,{ts(b['t0'])},{ts(b['t1'])},Kin,,0,0,0,,"
                     f"{{\\an8\\pos({W // 2},{SAFE_TOP + 140})\\fad(120,200)\\fscx85\\fscy85\\t(0,160,\\fscx100\\fscy100)}}"
                     f"{esc(b['text'])}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def behind_ass(tl: dict, items: list[dict], out: Path) -> None:
    """Palavras gigantes posicionadas para a cabeça cobrir só a parte de baixo das letras."""
    k = tl["behind_cfg"]
    styles = [f"Style: Bh,{k['font']},{k['size']},{ass_color(k['color'], k.get('alpha', '00'))},"
              f"{ass_color(k['color'])},{ass_color('#000000')},{ass_color('#000000', 'A0')},"
              f"{-1 if k['font'] != 'Anton' else 0},{-1 if k.get('italic') else 0},0,0,100,100,0,0,1,0,5,8,0,0,0,1"]
    lines = [_header(styles)]
    for b in items:
        text = esc(b["text"])
        size = b.get("size") or int(min(k["size"], (W - 2 * SAFE_SIDE) / max(len(text) * WIDTH_FACTOR.get(k["font"], 0.6), 1)))
        top = b.get("head_top") or 520
        y = int(max(SAFE_TOP, top - size * 0.84))  # a cabeça cobre só a base das letras
        color = f"\\c{ass_color(b['color'])}" if b.get("color") else ""
        lines.append(f"Dialogue: 0,{ts(b['t0'])},{ts(b['t1'])},Bh,,0,0,0,,"
                     f"{{\\an8\\pos({W // 2},{y})\\fs{size}{color}\\fad(140,220)\\fscx90\\fscy90\\t(0,220,\\fscx100\\fscy100)}}{text}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- gráficos PNG ----------

def register_fonts(fonts: list[dict], base: Path) -> None:
    """Fontes da marca (brand.json -> fonts: [{family, file, italic}]) passam a valer nos gráficos."""
    for f in fonts or []:
        FONT_FILES[(f["family"], bool(f.get("italic")))] = str((base / f["file"]).resolve())
        WIDTH_FACTOR.setdefault(f["family"], f.get("width_factor", 0.6))


def _font(name: str, size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    file = FONT_FILES.get((name, italic)) or FONT_FILES.get((name, False)) or FONT_FILES[("Poppins", False)]
    return ImageFont.truetype(str(FONTS_DIR / file), size)  # caminho absoluto (marca) ignora FONTS_DIR


def _wrap(draw, text, font, max_w) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _shadow(canvas: Image.Image, box, radius, blur=18, alpha=110):
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(box, radius=radius, fill=(0, 0, 0, alpha))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


def _rgb(hex_rgb: str, a: int = 255):
    h = hex_rgb.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def graphic_png(kind: str, text: str, style: str, g: dict, out: Path, top: bool = False) -> None:
    """top=True põe o CTA no alto do quadro (quando a legenda está ocupando a faixa de baixo)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    accent, fg = g["accent"], g["text"]
    if kind == "hook":
        upper = text.upper()
        font = _font("Anton" if style == "reels_viral" else "Poppins", 74 if style == "reels_viral" else 58)
        lines = _wrap(d, upper, font, W - 2 * SAFE_SIDE - 120)[:3]
        lh = int(font.size * 1.12)
        bw = max(d.textlength(l, font=font) for l in lines) + 80
        bh = lh * len(lines) + 50
        x0, y0 = (W - bw) / 2, SAFE_TOP + 30
        _shadow(img, (x0, y0 + 8, x0 + bw, y0 + bh + 8), 28)
        fill = _rgb(accent) if style == "reels_viral" else _rgb("#FFFFFF")
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=28, fill=fill)
        if style != "reels_viral":
            d.rounded_rectangle((x0, y0 + bh - 12, x0 + bw, y0 + bh), radius=6, fill=_rgb(accent))
        for n, l in enumerate(lines):
            tw = d.textlength(l, font=font)
            d.text(((W - tw) / 2, y0 + 22 + n * lh), l, font=font, fill=(0, 0, 0, 255))
    elif kind == "cta":
        if style == "editorial_premium":
            font = _font("DM Serif Display", 78, italic=True)
            tw = d.textlength(text, font=font)
            y = SAFE_TOP + 60 if top else int(H * 0.52)
            d.text(((W - tw) / 2, y), text, font=font, fill=_rgb(fg))
            d.line(((W - 160) / 2, y + 112, (W + 160) / 2, y + 112), fill=_rgb(accent), width=4)
        else:
            font = _font("Poppins", 62)
            label = text.upper()
            tw = d.textlength(label, font=font)
            bw, bh = tw + 170, 130
            x0, y0 = (W - bw) / 2, (int(H * 0.6) if W > H else SAFE_TOP + 60 if top else SAFE_BOTTOM - 150)
            _shadow(img, (x0, y0 + 10, x0 + bw, y0 + bh + 10), bh // 2)
            d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=bh // 2, fill=_rgb(accent))
            ink = (0, 0, 0, 255) if style == "reels_viral" else (255, 255, 255, 255)
            d.text((x0 + 60, y0 + (bh - 78) / 2), label, font=font, fill=ink)
            ax, ay = x0 + bw - 80, y0 + bh / 2
            d.polygon([(ax - 18, ay - 22), (ax + 16, ay), (ax - 18, ay + 22)], fill=ink)
    elif kind == "lower_third":
        font = _font("DM Serif Display", 60, italic=True)
        lines = _wrap(d, text, font, 760)[:2]
        y0 = int(H * (0.51 if H > W else 0.66))
        x0 = SAFE_SIDE + 20
        h = 78 * len(lines) + 40
        d.rectangle((x0, y0, x0 + 8, y0 + h), fill=_rgb(accent))
        for n, l in enumerate(lines):
            d.text((x0 + 36, y0 + 14 + n * 78), l, font=font, fill=_rgb(fg))
    elif kind == "logo":
        # marca d'água: logo pequena num canto da zona segura (text = caminho do arquivo da logo)
        mark = Image.open(text).convert("RGBA")
        lw = int(W * 0.16)
        mark = mark.resize((lw, int(mark.height * lw / mark.width)), Image.LANCZOS)
        alpha = mark.getchannel("A").point(lambda v: int(v * g.get("logo_opacity", 0.85)))
        mark.putalpha(alpha)
        pos = g.get("logo_position") or "top-right"
        x = W - SAFE_SIDE - lw - 20 if "right" in pos else SAFE_SIDE + 20
        y = SAFE_TOP + 10 if "top" in pos else SAFE_BOTTOM - mark.height - 10
        img.alpha_composite(mark, (int(x), int(y)))
    elif kind == "chapter":
        font = _font("DM Serif Display", 150, italic=True)
        d.text((SAFE_SIDE + 20, SAFE_TOP + 10), text, font=font, fill=_rgb(accent, 235))
    img.save(out)


# ---------- efeitos sonoros sintetizados ----------

SFX_RECIPES = {
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.45:c=pink:a=0.9:r=48000",
               "-af", "highpass=f=400,lowpass=f=5000,afade=t=in:d=0.28:curve=exp,afade=t=out:st=0.28:d=0.17,volume=0.8"],
    "pop": ["-f", "lavfi", "-i",
            "aevalsrc='0.9*sin(2*PI*(380+1600*exp(-38*t))*t)*exp(-22*t)':d=0.16:s=48000"],
    "boom": ["-f", "lavfi", "-i",
             "aevalsrc='0.95*sin(2*PI*(46+70*exp(-9*t))*t)*exp(-4.5*t)+0.25*(random(0)-0.5)*exp(-18*t)':d=0.9:s=48000",
             "-af", "lowpass=f=900"],
    "ding": ["-f", "lavfi", "-i",
             "aevalsrc='0.5*sin(2*PI*1320*t)*exp(-5*t)+0.25*sin(2*PI*2640*t)*exp(-7*t)':d=0.8:s=48000"],
    "tick": ["-f", "lavfi", "-i", "aevalsrc='0.8*sin(2*PI*2200*t)*exp(-260*t)':d=0.05:s=48000"],
    "click": ["-f", "lavfi", "-i", "aevalsrc='(random(0)-0.5)*1.6*exp(-420*t)':d=0.04:s=48000",
              "-af", "highpass=f=1800"],
    "glitch": ["-f", "lavfi", "-i",
               "aevalsrc='0.5*sgn(sin(2*PI*(220+880*floor(mod(t*28,4)))*t))*lt(mod(t,0.07),0.045)':d=0.35:s=48000",
               "-af", "lowpass=f=5000,volume=0.6"],
    "venda": ["-f", "lavfi", "-i",
              "aevalsrc='0.45*sin(2*PI*1568*t)*exp(-6*t)*lt(t,0.6)+0.45*sin(2*PI*2093*(t-0.09))*exp(-5*(t-0.09))*gte(t,0.09)"
              "+0.15*sin(2*PI*4186*(t-0.09))*exp(-9*(t-0.09))*gte(t,0.09)':d=0.9:s=48000"],
    "riser": ["-f", "lavfi", "-i",
              "aevalsrc='0.35*sin(2*PI*(180*t+260*t*t))*min(t/1.1,1)':d=1.25:s=48000",
              "-af", "afade=t=out:st=1.1:d=0.15"],
}


def make_sfx(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, args in SFX_RECIPES.items():
        p = folder / f"{name}.wav"
        if not p.exists():
            ffmpeg([*args, "-ac", "2", str(p)])
        out[name] = p
    return out
