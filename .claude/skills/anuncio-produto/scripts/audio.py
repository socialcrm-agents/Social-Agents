"""Som do anúncio: efeitos sintetizados, trilha gerada (sem licença de terceiros) e mixagem final.

A trilha é sintetizada aqui mesmo (bateria, baixo e acordes em lá menor), então pode ser usada
comercialmente sem risco de direitos autorais nem de bloqueio por Content ID. Música do cliente entra por
caminho de arquivo no roteiro ("musica": "trilha.mp3"), e é responsabilidade dele ter a licença.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from common import ffmpeg

SR = 48000

SFX_RECIPES = {
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.45:c=pink:a=0.9:r=48000",
               "-af", "highpass=f=400,lowpass=f=5000,afade=t=in:d=0.28:curve=exp,afade=t=out:st=0.28:d=0.17,volume=0.8"],
    "pop": ["-f", "lavfi", "-i", "aevalsrc='0.9*sin(2*PI*(380+1600*exp(-38*t))*t)*exp(-22*t)':d=0.16:s=48000"],
    "boom": ["-f", "lavfi", "-i",
             "aevalsrc='0.95*sin(2*PI*(46+70*exp(-9*t))*t)*exp(-4.5*t)+0.25*(random(0)-0.5)*exp(-18*t)':d=0.9:s=48000",
             "-af", "lowpass=f=900"],
    "click": ["-f", "lavfi", "-i", "aevalsrc='(random(0)-0.5)*1.6*exp(-420*t)':d=0.04:s=48000", "-af", "highpass=f=1800"],
    "venda": ["-f", "lavfi", "-i",
              "aevalsrc='0.45*sin(2*PI*1568*t)*exp(-6*t)*lt(t,0.6)+0.45*sin(2*PI*2093*(t-0.09))*exp(-5*(t-0.09))*gte(t,0.09)"
              "+0.15*sin(2*PI*4186*(t-0.09))*exp(-9*(t-0.09))*gte(t,0.09)':d=0.9:s=48000"],
    "brilho": ["-f", "lavfi", "-i",
               "aevalsrc='0.22*(sin(2*PI*2637*t)+sin(2*PI*3136*t)+sin(2*PI*3951*t))*exp(-4*t)*(0.6+0.4*sin(2*PI*14*t))':d=0.7:s=48000"],
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


# ---------- trilha sintetizada ----------

def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    f = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    f *= 1 / np.sqrt(1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(f, len(x))


def _highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    return x - _lowpass(x, cutoff)


def _note(freq: float, dur: float, kind: str = "saw", decay: float = 6.0, attack: float = 0.005) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    if kind == "sine":
        w = np.sin(2 * np.pi * freq * t)
    elif kind == "tri":
        w = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * freq * t))
    else:  # serra levemente desafinada (mais "cheia")
        w = sum(2 * ((freq * d * t) % 1) - 1 for d in (0.996, 1.0, 1.004)) / 3
    env = np.minimum(t / attack, 1) * np.exp(-decay * t)
    return w * env


def _put(buf: np.ndarray, x: np.ndarray, t: float, gain: float = 1.0) -> None:
    i = int(t * SR)
    if i >= len(buf):
        return
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += x[:n] * gain


CHORDS = [(220.0, [440.0, 523.25, 659.25]),   # Am
          (174.61, [349.23, 440.0, 523.25]),  # F
          (261.63, [392.0, 523.25, 659.25]),  # C
          (196.0, [392.0, 493.88, 587.33])]   # G


def music_bed(kind: str, seconds: float, out: Path) -> Path:
    rng = np.random.default_rng(7)
    bpm = 118 if kind == "batida" else 86
    beat = 60 / bpm
    bar = 4 * beat
    n = int((seconds + 1) * SR)
    drums, bass, keys = np.zeros(n), np.zeros(n), np.zeros(n)
    kick_times = []
    nbars = int(seconds / bar) + 2
    for b in range(nbars):
        root, triad = CHORDS[b % 4]
        t0 = b * bar
        if kind == "batida":
            for k in (0, 2):
                kt = t0 + k * beat
                kick_times.append(kt)
                tt = np.arange(int(0.38 * SR)) / SR
                _put(drums, np.sin(2 * np.pi * (45 * tt + 75 / 14 * (1 - np.exp(-14 * tt)))) * np.exp(-8 * tt), kt, 0.9)
            for k in (1, 3):
                st = t0 + k * beat
                noise = _highpass(rng.standard_normal(int(0.22 * SR)), 1200) * np.exp(-np.arange(int(0.22 * SR)) / SR * 16)
                _put(drums, noise, st, 0.32)
                _put(drums, _note(185, 0.12, "sine", 30), st, 0.25)
            for e in range(8):
                ht = t0 + e * beat / 2
                hat = _highpass(rng.standard_normal(int(0.06 * SR)), 7000) * np.exp(-np.arange(int(0.06 * SR)) / SR * 70)
                _put(drums, hat, ht, 0.10 if e % 2 else 0.06)
                _put(bass, _lowpass(_note(root / 2, beat / 2 * 0.95, "saw", 7), 380), ht, 0.45)
            for e in (1, 3, 5, 7):  # acordes no contratempo
                for f in triad:
                    _put(keys, _lowpass(_note(f, 0.32, "saw", 9), 2400), t0 + e * beat / 2, 0.07)
        else:  # suave: pad + arpejo
            for f in triad:
                _put(keys, _lowpass(_note(f / 2, bar * 1.05, "tri", 0.4, attack=0.6), 1500), t0, 0.08)
            for e in range(8):
                f = triad[e % 3] * (2 if e >= 4 else 1)
                _put(keys, _note(f, 0.5, "sine", 5), t0 + e * beat / 2, 0.05)
            _put(bass, _note(root / 2, bar, "sine", 0.6, attack=0.05), t0, 0.25)
    # "pumping": o resto abaixa um pouco a cada bumbo
    duck = np.ones(n)
    for kt in kick_times:
        i = int(kt * SR)
        m = min(int(0.25 * SR), n - i)
        if m > 0:
            duck[i:i + m] = np.minimum(duck[i:i + m], 0.55 + 0.45 * np.linspace(0, 1, m) ** 0.6)
    mix = drums + (bass + keys) * duck
    mix = mix[: int(seconds * SR)]
    fade = int(min(1.2, seconds / 4) * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(np.abs(mix).max(), 1e-6) / 0.8
    stereo = np.stack([mix, mix], 1)
    with wave.open(str(out), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((stereo * 32767).astype(np.int16).tobytes())
    return out
