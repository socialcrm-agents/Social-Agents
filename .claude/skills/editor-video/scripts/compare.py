#!/usr/bin/env python3
"""Gera o vídeo ANTES | DEPOIS lado a lado (1080x960 por lado, 2160x1920 total -> 1080x960 em 50%).

  compare.py <bruto.mp4> <editado.mp4> <saida.mp4> [--seconds N]

O lado ANTES toca o bruto do início; o DEPOIS toca a edição. Os dois param juntos
(N segundos, padrão: duração da edição) para comparar ritmo, cor, legendas e cortes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common import FONTS_DIR, ffmpeg, main_guard, probe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("edit")
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float)
    a = ap.parse_args()
    dur = a.seconds or probe(Path(a.edit))["duration"]
    font = (FONTS_DIR / "Anton-Regular.ttf").as_posix().replace(":", "\\:")
    label = (f"drawtext=fontfile='{font}':text='{{t}}':fontsize=64:fontcolor=white:box=1:boxcolor=black@0.6:"
             f"boxborderw=18:x=(w-tw)/2:y=40")
    f = (f"[0:v]fps=30,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
         f"setsar=1,{label.format(t='ANTES')}[l];"
         f"[1:v]fps=30,scale=1080:1920,setsar=1,{label.format(t='DEPOIS')}[r];"
         f"[l][r]hstack=2,scale=1080:960[v];"
         f"[1:a]anull[a]")
    ffmpeg(["-t", f"{dur:.2f}", "-i", a.raw, "-t", f"{dur:.2f}", "-i", a.edit, "-filter_complex", f,
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", a.out])
    print(f"OK: {a.out}")


if __name__ == "__main__":
    main_guard(main)
