"""Processamento de áudio em numpy puro (sem scipy): filtros, reverb, chorus, limitador, loudness e WAV.

Base da trilha (trilha.py) e dos efeitos sonoros (sfx.py). Tudo determinístico: o mesmo pedido gera os
mesmos bytes. Filtros estáticos são feitos no domínio da frequência (FFT do sinal inteiro, fase zero) e os
que mudam no tempo (varredura de um whoosh) por STFT.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000


# ---------------------------------------------------------------------------------------------------------------
# utilidades

def seg(n_seg: float) -> int:
    return max(int(round(n_seg * SR)), 1)


def tempo(n: int) -> np.ndarray:
    return np.arange(n) / SR


def db(x: float) -> float:
    return float(20 * np.log10(max(x, 1e-12)))


def de_db(v: float) -> float:
    return float(10 ** (v / 20))


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def mono_para_estereo(x: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """Pan com lei de potência constante (-1 = esquerda, 1 = direita)."""
    ang = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(ang), x * np.sin(ang)]) * np.sqrt(2)


def soma_em(dest: np.ndarray, x: np.ndarray, i0: int) -> None:
    """Soma x em dest a partir da amostra i0 (corta o que passar do fim). dest e x: (2, n) ou (n,)."""
    if i0 >= dest.shape[-1]:
        return
    if i0 < 0:
        x = x[..., -i0:]
        i0 = 0
    n = min(x.shape[-1], dest.shape[-1] - i0)
    if n > 0:
        dest[..., i0:i0 + n] += x[..., :n]


def fades(x: np.ndarray, ent: float = 0.002, sai: float = 0.005) -> np.ndarray:
    """Fade de entrada/saída em cosseno (sem clique nas pontas)."""
    x = x.copy()
    n = x.shape[-1]
    for comp, lado in ((seg(ent), 0), (seg(sai), 1)):
        comp = min(comp, n // 2)
        if comp < 2:
            continue
        r = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, comp))
        if lado == 0:
            x[..., :comp] *= r
        else:
            x[..., -comp:] *= r[::-1]
    return x


# ---------------------------------------------------------------------------------------------------------------
# filtros (magnitude estilo Butterworth, aplicada por FFT — fase zero)

def _freqs(n: int) -> np.ndarray:
    return np.fft.rfftfreq(n, 1 / SR)


def filtro_fft(x: np.ndarray, resposta) -> np.ndarray:
    """Aplica a resposta de magnitude resposta(f) ao sinal (1 ou 2 canais) com FFT do sinal todo."""
    n = x.shape[-1]
    nfft = 1 << int(np.ceil(np.log2(max(n, 2))))
    X = np.fft.rfft(x, nfft, axis=-1)
    X *= resposta(_freqs(nfft))
    return np.fft.irfft(X, nfft, axis=-1)[..., :n]


def r_passa_baixa(fc: float, ordem: int = 2):
    return lambda f: 1 / np.sqrt(1 + (f / fc) ** (2 * ordem))


def r_passa_alta(fc: float, ordem: int = 2):
    return lambda f: 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * ordem))


def r_passa_banda(f0: float, q: float = 1.0):
    """Ressonante de 2ª ordem centrado em f0 (pico 1)."""
    def r(f):
        f = np.maximum(f, 1e-3)
        return 1 / np.sqrt(1 + q * q * (f / f0 - f0 / f) ** 2)
    return r


def r_prateleira(fc: float, ganho_db: float, alta: bool = True):
    g = de_db(ganho_db)

    def r(f):
        s = 1 / (1 + (fc / np.maximum(f, 1e-3)) ** 2) if alta else 1 / (1 + (f / fc) ** 2)
        return 1 + (g - 1) * s
    return r


def r_sino(f0: float, ganho_db: float, q: float = 1.0):
    g = de_db(ganho_db)
    banda = r_passa_banda(f0, q)
    return lambda f: 1 + (g - 1) * banda(f) ** 2


def combina(*resps):
    def r(f):
        out = np.ones_like(f)
        for rr in resps:
            out = out * rr(f)
        return out
    return r


def passa_baixa(x, fc, ordem=2):
    return filtro_fft(x, r_passa_baixa(fc, ordem))


def passa_alta(x, fc, ordem=2):
    return filtro_fft(x, r_passa_alta(fc, ordem))


def passa_banda(x, f0, q=1.0):
    return filtro_fft(x, r_passa_banda(f0, q))


def filtro_variavel(x: np.ndarray, resposta_t, n_quadro: int = 2048) -> np.ndarray:
    """Filtro que muda no tempo por STFT (janela de Hann, sobreposição 75%). resposta_t(f, t_seg) -> ganho."""
    mono = x.ndim == 1
    xs = x[None] if mono else x
    hop = n_quadro // 4
    n = xs.shape[-1]
    pad = n_quadro
    xp = np.pad(xs, ((0, 0), (pad, pad + n_quadro)))
    jan = np.hanning(n_quadro + 1)[:-1]
    f = _freqs(n_quadro)
    out = np.zeros_like(xp)
    norma = np.zeros(xp.shape[-1])
    for i0 in range(0, xp.shape[-1] - n_quadro, hop):
        t = (i0 + n_quadro / 2 - pad) / SR
        q = xp[:, i0:i0 + n_quadro] * jan
        Q = np.fft.rfft(q, axis=-1) * resposta_t(f, t)
        out[:, i0:i0 + n_quadro] += np.fft.irfft(Q, n_quadro, axis=-1) * jan
        norma[i0:i0 + n_quadro] += jan ** 2
    out = out / np.maximum(norma, 1e-6)
    out = out[:, pad:pad + n]
    return out[0] if mono else out


# ---------------------------------------------------------------------------------------------------------------
# osciladores

def tabela_onda(harmonicos: np.ndarray, n: int = 4096) -> np.ndarray:
    """Um ciclo de onda a partir das amplitudes dos harmônicos (1, 2, 3...)."""
    fase = np.arange(n) / n
    tab = np.zeros(n)
    for k, a in enumerate(harmonicos, start=1):
        if a:
            tab += a * np.sin(2 * np.pi * k * fase)
    return tab


def serra_limitada(freq: float, brilho: float = 1.0) -> np.ndarray:
    """Harmônicos de uma dente-de-serra sem aliasing até Nyquist, com queda suave (brilho 0..1)."""
    kmax = max(int((SR / 2 * 0.9) / max(freq, 1)), 1)
    kmax = min(kmax, 96)
    k = np.arange(1, kmax + 1)
    corte = 2 + 40 * brilho
    return (1 / k) / np.sqrt(1 + (k / corte) ** 4)


def osc_tabela(tab: np.ndarray, freq, n: int, fase0: float = 0.0) -> np.ndarray:
    """Lê a tabela com frequência fixa ou variável (array de n valores), interpolação linear."""
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    fase = fase0 + np.cumsum(f) / SR
    pos = (fase % 1.0) * len(tab)
    i = pos.astype(np.int64)
    fr = pos - i
    return tab[i % len(tab)] * (1 - fr) + tab[(i + 1) % len(tab)] * fr


def senoide(freq, n: int, fase0: float = 0.0) -> np.ndarray:
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    return np.sin(2 * np.pi * (fase0 + np.cumsum(f) / SR))


def ruido(rng: np.random.Generator, n: int, cor: str = "branco") -> np.ndarray:
    x = rng.standard_normal(n)
    if cor == "rosa":
        x = filtro_fft(x, lambda f: 1 / np.sqrt(np.maximum(f, 20) / 20))
    elif cor == "marrom":
        x = filtro_fft(x, lambda f: 20 / np.maximum(f, 20))
    return x / (np.std(x) + 1e-12)


def env_adsr(n: int, a: float, d: float, s: float, r: float, dur_nota: float | None = None) -> np.ndarray:
    """Envelope ADSR com curvas exponenciais (soa natural). dur_nota = quando começa o release."""
    t = tempo(n)
    dn = dur_nota if dur_nota is not None else n / SR - r
    ata = np.clip(t / max(a, 1e-4), 0, 1) ** 0.7
    dec = s + (1 - s) * np.exp(-np.maximum(t - a, 0) / max(d, 1e-4))
    env = np.where(t < a, ata, dec)
    nivel_rel = (s + (1 - s) * np.exp(-max(dn - a, 0) / max(d, 1e-4))) if dn > a else min(dn / max(a, 1e-4), 1)
    rel = nivel_rel * np.exp(-np.maximum(t - dn, 0) / max(r / 4.6, 1e-4))
    return np.where(t < dn, env, rel)


# ---------------------------------------------------------------------------------------------------------------
# efeitos

def satura(x: np.ndarray, drive: float = 1.5) -> np.ndarray:
    """Saturação suave (tanh) com compensação de nível."""
    return np.tanh(x * drive) / np.tanh(drive)


def atraso_modulado(x: np.ndarray, atraso_s: np.ndarray) -> np.ndarray:
    """y[n] = x[n - d(n)] com interpolação linear (chorus, flanger, wow/flutter, doppler)."""
    n = x.shape[-1]
    idx = np.arange(n) - atraso_s * SR
    return np.interp(idx, np.arange(n), x, left=0.0, right=0.0)


def chorus(x: np.ndarray, prof_ms: float = 3.0, base_ms: float = 14.0, taxa: float = 0.35, mix: float = 0.5) -> np.ndarray:
    """Chorus estéreo de 2 vozes por lado (LFOs defasados). Entrada mono (n,) ou estéreo (2, n) -> (2, n)."""
    st = mono_para_estereo(x) if x.ndim == 1 else x
    n = st.shape[-1]
    t = tempo(n)
    out = np.empty_like(st)
    for c in range(2):
        acc = np.zeros(n)
        for v, fase in enumerate((0.0, 0.5)):
            lfo = np.sin(2 * np.pi * (taxa * (1 + 0.13 * v) * t + fase + 0.25 * c))
            acc += atraso_modulado(st[c], (base_ms + prof_ms * lfo) / 1000)
        out[c] = (1 - mix) * st[c] + mix * acc / 2
    return out


def resposta_reverb(rng: np.random.Generator, rt60: float = 1.8, pre_ms: float = 18.0,
                    brilho: float = 0.6, largura: float = 1.0) -> np.ndarray:
    """Resposta ao impulso sintética estéreo: reflexões iniciais + cauda de ruído com agudos decaindo mais rápido."""
    n = seg(rt60 * 1.15 + pre_ms / 1000)
    t = tempo(n)
    ir = np.zeros((2, n))
    p0 = seg(pre_ms / 1000)
    # cauda: 3 bandas com decaimentos diferentes (graves duram mais, agudos somem antes = sala real)
    bandas = ((r_passa_baixa(500, 2), 1.15), (combina(r_passa_alta(500, 2), r_passa_baixa(4000, 2)), 1.0),
              (r_passa_alta(4000, 2), 0.55 * (0.5 + brilho)))
    for c in range(2):
        cauda = np.zeros(n)
        base = rng.standard_normal(n)
        for resp, k_rt in bandas:
            b = filtro_fft(base, resp)
            cauda += b * np.exp(-6.9 * t / (rt60 * k_rt))
        sobe = np.clip((t - pre_ms / 1000) / 0.03, 0, 1)
        ir[c] = cauda * sobe
        # reflexões iniciais esparsas
        for _ in range(9):
            i = p0 + int(rng.uniform(0.001, 0.045) * SR)
            if i < n:
                ir[c, i] += rng.uniform(-1, 1) * 2.5
    if largura < 1:
        m = ir.mean(axis=0)
        ir = m + (ir - m) * largura
    return ir / np.sqrt(np.sum(ir ** 2) / 2 + 1e-12)


def convolve_fft(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Convolução estéreo (2, n) * (2, m) -> (2, n) (a cauda que passa do fim é cortada)."""
    n = x.shape[-1]
    nfft = 1 << int(np.ceil(np.log2(n + ir.shape[-1])))
    Y = np.fft.rfft(x, nfft, axis=-1) * np.fft.rfft(ir, nfft, axis=-1)
    return np.fft.irfft(Y, nfft, axis=-1)[..., :n]


def compressor(x: np.ndarray, limiar_db: float = -18, razao: float = 2.5, ataque: float = 0.01,
               soltura: float = 0.15, ganho_db: float = 0.0) -> np.ndarray:
    """Compressor de barramento (detecção RMS ligada nos dois canais, suavização por média móvel)."""
    nivel = np.sqrt(_media_movel(np.mean(x ** 2, axis=0), seg(ataque * 2)) + 1e-12)
    nv_db = 20 * np.log10(nivel)
    red = np.maximum(nv_db - limiar_db, 0) * (1 - 1 / razao)
    g = 10 ** ((-_media_movel(red, seg(soltura)) + ganho_db) / 20)
    return x * g


def _media_movel(v: np.ndarray, janela: int) -> np.ndarray:
    janela = max(int(janela), 1)
    c = np.cumsum(np.concatenate([np.zeros(janela), v]))
    out = (c[janela:] - c[:-janela]) / janela
    # centraliza (sem atraso)
    sh = janela // 2
    return np.concatenate([out[sh:], np.full(sh, out[-1])])


def _min_movel(v: np.ndarray, janela: int) -> np.ndarray:
    """Mínimo numa janela centrada (blocos de log2 — O(n log janela), sem laço por amostra)."""
    out = v.copy()
    passo = 1
    while passo < janela:
        d = min(passo, janela - passo)
        a = np.concatenate([out[d:], np.full(d, out[-1])])
        out = np.minimum(out, a)
        passo += d
    sh = janela // 2
    return np.concatenate([np.full(sh, out[0]), out[:-sh]]) if sh else out


def limitador(x: np.ndarray, teto_db: float = -1.5, olhar_ms: float = 2.0) -> np.ndarray:
    """Limitador com antecipação: nenhum pico passa do teto, ganho sem degraus (sem distorção audível)."""
    teto = de_db(teto_db)
    pico = np.max(np.abs(x), axis=0)
    g = np.minimum(1.0, teto / np.maximum(pico, 1e-12))
    jan = seg(olhar_ms / 1000)
    g = _min_movel(g, 2 * jan + 1)
    g = _media_movel(g, jan)
    g = _min_movel(g, 3)  # garante o teto depois da suavização
    y = x * g
    return np.clip(y, -teto, teto)


# ---------------------------------------------------------------------------------------------------------------
# medição (ITU-R BS.1770 / EBU R128)

_K1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_K2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def _resp_biquad(b, a, f):
    z = np.exp(-1j * 2 * np.pi * f / SR)
    return np.abs((b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z))


_K_CACHE: dict = {}


def _resp_k(f: np.ndarray) -> np.ndarray:
    if len(f) not in _K_CACHE:
        _K_CACHE.clear()
        _K_CACHE[len(f)] = _resp_biquad(*_K1, f) * _resp_biquad(*_K2, f)
    return _K_CACHE[len(f)]


def loudness(x: np.ndarray) -> float:
    """Loudness integrada (LUFS) com ponderação K e as duas janelas de corte da norma."""
    st = x[None] if x.ndim == 1 else x
    kw = filtro_fft(st, _resp_k)
    bloco, passo = seg(0.4), seg(0.1)
    if kw.shape[-1] < bloco:
        return -70.0
    ms = np.stack([_media_movel_bloco(c ** 2, bloco, passo) for c in kw]).sum(axis=0)
    lk = -0.691 + 10 * np.log10(ms + 1e-15)
    ok = ms[lk > -70]
    if not len(ok):
        return -70.0
    rel = -0.691 + 10 * np.log10(ok.mean()) - 10
    ok2 = ms[(lk > -70) & (lk > rel)]
    return float(-0.691 + 10 * np.log10(ok2.mean() + 1e-15))


def _media_movel_bloco(v: np.ndarray, bloco: int, passo: int) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(v)])
    ini = np.arange(0, len(v) - bloco + 1, passo)
    return (c[ini + bloco] - c[ini]) / bloco


def pico_verdadeiro(x: np.ndarray, sobre: int = 4) -> float:
    """Pico verdadeiro (dBTP) por sobreamostragem 4x em blocos."""
    st = x[None] if x.ndim == 1 else x
    bloco, borda = 1 << 15, 64
    pico = float(np.max(np.abs(st))) if st.size else 0.0
    for i0 in range(0, st.shape[-1], bloco):
        a, b = max(i0 - borda, 0), min(i0 + bloco + borda, st.shape[-1])
        q = st[:, a:b]
        n = q.shape[-1]
        if n < 4:
            continue
        Q = np.fft.rfft(q, axis=-1)
        up = np.fft.irfft(Q, n * sobre, axis=-1) * sobre
        pico = max(pico, float(np.max(np.abs(up[:, borda * sobre:-borda * sobre or None]))))
    return db(pico)


def rms_db(x: np.ndarray) -> float:
    return db(float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0)


# ---------------------------------------------------------------------------------------------------------------
# WAV

def grava_wav(path: Path, x: np.ndarray, bits: int = 24) -> None:
    """Grava WAV PCM estéreo 48 kHz (24 bits por padrão). x: (2, n) ou (n,) em [-1, 1]."""
    st = np.stack([x, x]) if x.ndim == 1 else x
    st = np.clip(st, -1.0, 1.0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if bits == 24:
        q = np.round(st.T * 8388607).astype("<i4")
        dados = q.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    else:
        dados = np.round(st.T * 32767).astype("<i2").tobytes()
    tmp = path.with_name(path.name + ".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(bits // 8)
        w.setframerate(SR)
        w.writeframes(dados)
    tmp.replace(path)


def le_wav(path: Path) -> np.ndarray:
    """Lê WAV PCM 16/24/32 bits -> (canais, n) float."""
    with wave.open(str(path), "rb") as w:
        nc, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v >= 1 << 23, v - (1 << 24), v) / 8388608.0
    elif sw == 2:
        v = np.frombuffer(raw, "<i2") / 32768.0
    else:
        v = np.frombuffer(raw, "<i4") / 2147483648.0
    return v.reshape(-1, nc).T.astype(float)
