#!/usr/bin/env python3
"""Biblioteca de efeitos sonoros sem direitos autorais, sintetizada aqui (numpy) — nada baixado.

Cada som é desenhado em camadas (transiente + corpo + cauda), com fades sem clique, normalizado por
loudness de curta duração (cada tipo tem seu nível, pensado para ficar abaixo da voz no mix) e com pico
verdadeiro ≤ -1 dBTP. WAV estéreo 48 kHz 24 bits. Determinístico (mesma versão do código = mesmos bytes).

Nomes usados pelo planejador (não mudam): whoosh, pop, boom, ding, tick, click, glitch, venda, riser.
Novos: hit (impacto cinematográfico), swoosh (transição curta), swipe (mão passando), camera_shutter,
notification, cash ("cha-ching"), plim, pop_bolha.

  sfx.py <pasta>     gera todos os sons na pasta (e imprime nível e pico de cada um)
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

import dsp
from dsp import SR, seg

HERE = Path(__file__).resolve().parent


def _rng(nome: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(nome.encode()).hexdigest()[:8], 16))


def _ir(rt60: float, nome: str, brilho: float = 0.6) -> np.ndarray:
    return dsp.resposta_reverb(_rng("ir" + nome), rt60, 8, brilho)


def _com_reverb(x: np.ndarray, rt60: float, mix: float, nome: str) -> np.ndarray:
    """Acrescenta a cauda de reverb (estica o som para a cauda caber)."""
    st = dsp.mono_para_estereo(x) if x.ndim == 1 else x
    st = np.pad(st, ((0, 0), (0, seg(rt60 * 0.8))))
    return st + mix * dsp.convolve_fft(st, _ir(rt60, nome))


def _passagem(n: int, pico: float, sobe: float = 2.2, desce: float = 4.0) -> np.ndarray:
    """Envelope de algo passando: cresce devagar até `pico` (0..1) e cai mais rápido."""
    t = np.linspace(0, 1, n)
    a = np.clip(t / pico, 0, 1) ** sobe
    b = np.clip((1 - t) / (1 - pico), 0, 1) ** desce
    return np.where(t < pico, a, b)


# ---------------------------------------------------------------------------------------------------------------
# sons

def whoosh(dur: float = 0.62, brilho: float = 1.0, nome: str = "whoosh") -> np.ndarray:
    """Passagem com doppler: ar (ruído com banda varrendo), corpo grave descendo de tom e pan esquerda->direita."""
    rng = _rng(nome)
    n = seg(dur)
    t = dsp.tempo(n)
    pico = 0.58
    tc = pico * dur
    # doppler: aproximando = mais agudo; depois que passa, mais grave (v = 60 m/s, c = 343)
    v, c, dist = 60.0, 343.0, 1.2
    x_pos = v * (t - tc)
    v_rad = -v * x_pos / np.sqrt(x_pos ** 2 + dist ** 2)
    doppler = c / (c + v_rad)
    env = _passagem(n, pico)
    ar = dsp.ruido(rng, n, "rosa")
    fc_base = 900 * brilho

    def banda(f, tt):
        k = float(np.interp(tt, t, doppler))
        e = float(np.interp(tt, t, env))
        fc = fc_base * k ** 6 * (0.6 + 1.8 * e)
        return dsp.r_passa_banda(fc, 0.9)(f)
    ar = dsp.filtro_variavel(ar, banda, 1024)
    brisa = dsp.passa_alta(dsp.ruido(rng, n), 5000 * brilho, 2) * _passagem(n, pico, 4, 8) * 0.25
    corpo = dsp.senoide(110 * doppler, n) * _passagem(n, pico, 3, 3) * 0.35
    corpo += dsp.passa_baixa(dsp.ruido(rng, n, "marrom"), 220, 2) * _passagem(n, pico, 3, 3) * 0.3
    mono = ar / (np.std(ar) + 1e-9) * env * 0.5 + brisa + corpo
    pan = np.clip((t - tc) / (dur * 0.35), -1, 1) * 0.8
    ang = (pan + 1) * np.pi / 4
    st = np.stack([mono * np.cos(ang), mono * np.sin(ang)]) * np.sqrt(2)
    return dsp.fades(st, 0.01, 0.04)


def swoosh() -> np.ndarray:
    return whoosh(0.3, 1.6, "swoosh")


def swipe() -> np.ndarray:
    """Mão passando (fricção): grãos de ruído médio-agudo com envelope curto e leve movimento."""
    rng = _rng("swipe")
    n = seg(0.22)
    t = dsp.tempo(n)
    graos = dsp.passa_baixa(np.abs(rng.standard_normal(n)), 120, 1)
    graos = graos / graos.max()
    x = dsp.filtro_fft(dsp.ruido(rng, n), dsp.combina(dsp.r_passa_banda(3200, 0.7), dsp.r_passa_alta(1200, 2)))
    x = x / (np.std(x) + 1e-9) * (0.5 + 0.5 * graos) * _passagem(n, 0.45, 1.6, 2.5)
    pan = (t / t[-1] - 0.5) * 0.9
    ang = (pan + 1) * np.pi / 4
    return dsp.fades(np.stack([x * np.cos(ang), x * np.sin(ang)]) * np.sqrt(2), 0.004, 0.03)


def pop() -> np.ndarray:
    """Pop de interface: corpo com queda de tom rápida + clique fino."""
    rng = _rng("pop")
    n = seg(0.15)
    t = dsp.tempo(n)
    f = 330 + 1300 * np.exp(-t / 0.012)
    corpo = dsp.senoide(f, n) * np.exp(-t / 0.035) * np.clip(t / 0.0015, 0, 1)
    clique = dsp.passa_alta(rng.standard_normal(n), 3000, 2) * np.exp(-t / 0.002) * 0.15
    return dsp.fades(dsp.satura(corpo + clique, 1.2), 0.0005, 0.02)


def pop_bolha() -> np.ndarray:
    """Bolha: o tom SOBE enquanto a bolha fecha (física real), duas bolhas encadeadas."""
    n = seg(0.2)
    t = dsp.tempo(n)
    x = np.zeros(n)
    for t0, f0, a in ((0.0, 520, 1.0), (0.055, 760, 0.6)):
        tt = np.maximum(t - t0, 0)
        f = f0 * (1 + 1.6 * (1 - np.exp(-tt / 0.03)))
        x += a * dsp.senoide(f, n) * np.exp(-tt / 0.03) * (t >= t0) * np.clip(tt / 0.001, 0, 1)
    return dsp.fades(x, 0.0005, 0.02)


def _sino(freqs_amps_decai, dur: float, f0: float) -> np.ndarray:
    n = seg(dur)
    t = dsp.tempo(n)
    x = np.zeros(n)
    for razao, amp, tau in freqs_amps_decai:
        f = f0 * razao
        if f < SR * 0.45:
            x += amp * np.exp(-t / tau) * 0.5 * (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.0015 * t + 1.1))
    return x * np.clip(t / 0.0015, 0, 1)


_SINO = [(1.0, 1.0, 0.55), (2.0, 0.45, 0.35), (2.76, 0.35, 0.22), (5.4, 0.18, 0.09), (8.93, 0.08, 0.05)]


def ding() -> np.ndarray:
    x = _sino(_SINO, 0.9, 1318.5)
    return dsp.fades(_com_reverb(dsp.fades(x, 0.0005, 0.08), 1.0, 0.18, "ding"), 0.0005, 0.08)


def plim() -> np.ndarray:
    x = _sino(_SINO, 0.8, 2093.0) + 0.4 * _sino(_SINO, 0.8, 3136.0)
    return dsp.fades(_com_reverb(dsp.fades(x, 0.0005, 0.08), 0.9, 0.2, "plim"), 0.0005, 0.08)


def venda() -> np.ndarray:
    """Duas notas de sino (sol -> dó), o "som de venda" das notificações."""
    n = seg(0.95)
    x = np.zeros(n)
    dsp.soma_em(x, _sino(_SINO, 0.6, 1568.0) * 0.8, 0)
    dsp.soma_em(x, _sino(_SINO, 0.85, 2093.0), seg(0.09))
    return dsp.fades(_com_reverb(dsp.fades(x, 0.0005, 0.08), 0.8, 0.15, "venda"), 0.0005, 0.08)


def notification() -> np.ndarray:
    """Notificação suave: duas notas de marimba (madeira: parcial 4x some rápido)."""
    n = seg(0.7)
    x = np.zeros(n)
    for t0, f in ((0.0, 1318.5), (0.11, 1760.0)):
        m = seg(0.55)
        tt = dsp.tempo(m)
        nota = (np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.16) + 0.3 * np.sin(2 * np.pi * 4 * f * tt) * np.exp(-tt / 0.02)
                ) * np.clip(tt / 0.001, 0, 1)
        dsp.soma_em(x, nota, seg(t0))
    return dsp.fades(_com_reverb(dsp.fades(x, 0.0005, 0.05), 0.7, 0.15, "notification"), 0.0005, 0.06)


def cash() -> np.ndarray:
    """"Cha-ching": gaveta (transiente metálico), moedas (pings agudos aleatórios) e o sino da caixa."""
    rng = _rng("cash")
    n = seg(1.1)
    t = dsp.tempo(n)
    x = np.zeros(n)
    gaveta = dsp.filtro_fft(rng.standard_normal(n), dsp.combina(dsp.r_passa_banda(2500, 1.5), dsp.r_passa_alta(800, 2)))
    x += gaveta / (np.std(gaveta) + 1e-9) * np.exp(-t / 0.03) * 0.35
    for _ in range(14):
        t0 = rng.uniform(0.0, 0.18)
        f = rng.uniform(4200, 9000)
        m = seg(0.25)
        tt = dsp.tempo(m)
        dsp.soma_em(x, np.sin(2 * np.pi * f * tt) * np.exp(-tt / rng.uniform(0.02, 0.07)) * rng.uniform(0.08, 0.2), seg(t0))
    dsp.soma_em(x, _sino(_SINO, 0.85, 2637.0) * 0.8 + _sino(_SINO, 0.85, 3951.0) * 0.35, seg(0.16))
    return dsp.fades(_com_reverb(dsp.fades(x, 0.0005, 0.08), 0.8, 0.15, "cash"), 0.0005, 0.08)


def tick() -> np.ndarray:
    rng = _rng("tick")
    n = seg(0.05)
    t = dsp.tempo(n)
    x = np.sin(2 * np.pi * 2300 * t) * np.exp(-t / 0.004) + 0.4 * np.sin(2 * np.pi * 5100 * t) * np.exp(-t / 0.002)
    x += dsp.passa_banda(rng.standard_normal(n), 4000, 1.2) * np.exp(-t / 0.0015) * 0.2
    return dsp.fades(x, 0.0003, 0.01)


def click() -> np.ndarray:
    """Clique de botão: aperta e solta (dois transientes) com ressonância curta de plástico."""
    rng = _rng("click")
    n = seg(0.07)
    t = dsp.tempo(n)
    x = np.zeros(n)
    for t0, a in ((0.0, 1.0), (0.028, 0.45)):
        tt = np.maximum(t - t0, 0)
        on = t >= t0
        x += a * on * (dsp.passa_alta(rng.standard_normal(n), 2000, 2) * np.exp(-tt / 0.0012)
                       + 0.5 * np.sin(2 * np.pi * 3400 * tt) * np.exp(-tt / 0.004))
    return dsp.fades(x, 0.0002, 0.01)


def camera_shutter() -> np.ndarray:
    """Obturador: espelho sobe (clique + corpo), cortina corre (ruído curto), espelho desce (clique)."""
    rng = _rng("camera")
    n = seg(0.24)
    t = dsp.tempo(n)
    x = np.zeros(n)
    for t0, a, fr in ((0.0, 1.0, 1900), (0.085, 0.8, 2400)):
        tt = np.maximum(t - t0, 0)
        on = t >= t0
        x += a * on * (dsp.passa_alta(rng.standard_normal(n), 1500, 2) * np.exp(-tt / 0.002)
                       + 0.6 * np.sin(2 * np.pi * fr * tt) * np.exp(-tt / 0.01)
                       + 0.4 * np.sin(2 * np.pi * 380 * tt) * np.exp(-tt / 0.015))
    cortina = dsp.passa_banda(rng.standard_normal(n), 5000, 1.0)
    x += cortina / (np.std(cortina) + 1e-9) * np.exp(-((t - 0.045) / 0.015) ** 2) * 0.2
    return dsp.fades(_com_reverb(x, 0.3, 0.1, "camera"), 0.0002, 0.03)


def hit() -> np.ndarray:
    """Impacto cinematográfico: transiente (estalo) + corpo médio + sub descendo, com cauda de sala grande."""
    rng = _rng("hit")
    n = seg(1.8)
    t = dsp.tempo(n)
    sub = dsp.satura(dsp.senoide(42 + 48 * np.exp(-t / 0.07), n) * np.exp(-t / 0.42), 1.4) * 0.9
    corpo = dsp.passa_baixa(rng.standard_normal(n), 700, 2)
    corpo = corpo / (np.std(corpo) + 1e-9) * np.exp(-t / 0.12) * 0.45
    estalo = dsp.passa_alta(rng.standard_normal(n), 1500, 2) * np.exp(-t / 0.008) * 0.6
    sala = _com_reverb(dsp.fades(dsp.satura(corpo + estalo, 1.4), 0.0003, 0.2), 2.2, 0.3, "hit")  # o sub fica seco
    dsp.soma_em(sala, dsp.mono_para_estereo(dsp.fades(sub, 0.0003, 0.2)), 0)
    return dsp.fades(sala, 0.0003, 0.3)


def boom() -> np.ndarray:
    """Impacto mais curto que o hit (palavra gigante, carimbo): sub + transiente, cauda curta."""
    rng = _rng("boom")
    n = seg(0.9)
    t = dsp.tempo(n)
    sub = dsp.senoide(44 + 70 * np.exp(-t / 0.05), n) * np.exp(-t / 0.25)
    corpo = dsp.passa_baixa(rng.standard_normal(n), 900, 2)
    corpo = corpo / (np.std(corpo) + 1e-9) * np.exp(-t / 0.06) * 0.35
    estalo = dsp.passa_alta(rng.standard_normal(n), 2000, 2) * np.exp(-t / 0.004) * 0.35
    return dsp.fades(_com_reverb(dsp.satura(sub + corpo + estalo, 1.5), 0.9, 0.12, "boom"), 0.0003, 0.15)


def glitch() -> np.ndarray:
    """Falha digital: fatias de tons e ruído com sample-and-hold, redução de bits e saltos no estéreo."""
    rng = _rng("glitch")
    n = seg(0.36)
    t = dsp.tempo(n)
    st = np.zeros((2, n))
    pos = 0
    while pos < n:
        m = int(rng.integers(seg(0.012), seg(0.05)))
        tt = dsp.tempo(m)
        if rng.uniform() < 0.55:
            f = rng.choice([220, 330, 440, 880, 1760, 3520]) * rng.uniform(0.98, 1.02)
            q = np.sign(np.sin(2 * np.pi * f * tt)) * 0.5
        else:
            q = rng.standard_normal(m) * 0.35
        passo = int(rng.choice([1, 4, 8, 16]))  # sample-and-hold (reduz a taxa)
        q = np.repeat(q[::passo], passo)[:m]
        q = np.round(q * 8) / 8  # 4 bits
        q *= 1.0 if rng.uniform() < 0.8 else 0.0
        pan = rng.uniform(-0.8, 0.8)
        dsp.soma_em(st, dsp.fades(dsp.mono_para_estereo(q, pan), 0.001, 0.002), pos)
        pos += m
    st = dsp.filtro_fft(st, dsp.r_passa_baixa(9000, 2))
    return dsp.fades(st * np.clip(1.2 - t / t[-1], 0, 1), 0.001, 0.02)


def riser() -> np.ndarray:
    """Subida com tom de Shepard (parece subir sem fim) + ruído abrindo, crescendo até o ponto de impacto."""
    rng = _rng("riser")
    dur = 1.25
    n = seg(dur)
    t = dsp.tempo(n)
    x = np.zeros(n)
    base, oitavas = 55.0, 7
    subida = 1.6 * t / dur  # oitavas subidas no tempo do riser
    for k in range(oitavas):
        pos = (k + subida) % oitavas  # posição em oitavas
        f = base * 2 ** pos
        amp = np.exp(-0.5 * ((pos - oitavas / 2) / 1.2) ** 2)  # janela em sino: entra fraco embaixo, sai fraco em cima
        x += amp * dsp.senoide(f, n, k * 0.13)
    x /= oitavas / 2.5
    ar = dsp.ruido(rng, n, "rosa")
    ar = dsp.filtro_variavel(ar, lambda f, tt: dsp.r_passa_banda(400 * (8000 / 400) ** min(max(tt / dur, 0), 1), 1.2)(f), 1024)
    ar = ar / (np.std(ar) + 1e-9) * 0.35
    env = (t / dur) ** 1.8
    mono = (x * 0.6 + ar) * env
    st = dsp.chorus(mono, 2.0, 9.0, 0.6, 0.35)
    return dsp.fades(st, 0.02, 0.05)


# nome -> (função, loudness alvo: máximo de 400 ms em LUFS). Níveis dos 9 antigos próximos dos de antes
# (o planejador já tem os ganhos afinados para eles).
SONS = {
    "whoosh": (whoosh, -24.0), "pop": (pop, -16.0), "boom": (boom, -13.0), "ding": (ding, -14.0),
    "tick": (tick, -24.0), "click": (click, -25.0), "glitch": (glitch, -14.0), "venda": (venda, -12.5),
    "riser": (riser, -14.5),
    "hit": (hit, -12.0), "swoosh": (swoosh, -21.0), "swipe": (swipe, -23.0), "camera_shutter": (camera_shutter, -17.0),
    "notification": (notification, -15.0), "cash": (cash, -13.0), "plim": (plim, -14.0), "pop_bolha": (pop_bolha, -17.0),
}


def loud_max(x: np.ndarray) -> float:
    """Loudness máxima em janelas de 400 ms (o "momentary" da EBU R128)."""
    st = dsp.mono_para_estereo(x) if x.ndim == 1 else x
    n = seg(0.4)
    st = np.pad(st, ((0, 0), (0, max(n - st.shape[1], 0))))
    return max(dsp.loudness(st[:, i:i + n]) for i in range(0, st.shape[1] - n + 1, seg(0.05)))


def gerar(nome: str) -> np.ndarray:
    fn, alvo = SONS[nome]
    x = fn()
    st = dsp.mono_para_estereo(x) if x.ndim == 1 else x
    st = st * dsp.de_db(alvo - loud_max(st))
    if dsp.pico_verdadeiro(st) > -1.2:  # transientes muito curtos: limita o pico e, se preciso, baixa o ganho
        st = dsp.limitador(st, -2.0, 1.0)
        st = st * min(1.0, dsp.de_db(-1.2 - dsp.pico_verdadeiro(st)))
    return dsp.fades(st, 0.0003, 0.005)


def versao() -> str:
    h = hashlib.sha256()
    for f in (HERE / "sfx.py", HERE / "dsp.py"):
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def biblioteca(pasta: Path) -> dict[str, Path]:
    """Gera (uma vez por versão do código) todos os sons na pasta e devolve nome -> arquivo."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    marca = pasta / ".versao"
    v = versao()
    refazer = not marca.exists() or marca.read_text(encoding="utf-8").strip() != v
    out = {}
    for nome in SONS:
        p = pasta / f"{nome}.wav"
        if refazer or not p.exists():
            dsp.grava_wav(p, gerar(nome))
        out[nome] = p
    if refazer:
        marca.write_text(v, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    for nome, p in biblioteca(Path(sys.argv[1])).items():
        x = dsp.le_wav(p)
        print(f"{nome:15s} {x.shape[1] / SR:5.2f} s  {loud_max(x):6.1f} LUFS(máx 400 ms)  pico {dsp.pico_verdadeiro(x):5.1f} dBTP")
