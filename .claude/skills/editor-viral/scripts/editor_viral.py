#!/usr/bin/env python3
"""Editor Viral (versão leve): edita vídeo falado para Reels/TikTok/anúncio DENTRO do Claude ou do ChatGPT.

Tudo roda na caixinha de código do próprio assistente, sem servidor:
  - transcrição offline: Whisper (sherpa-onnx, int8) + detector de voz (Silero); ou faster-whisper se existir;
  - edição: ffmpeg (o do sistema ou o do pacote imageio-ffmpeg, que tem legenda libass);
  - voz limpa e trilha sem direitos em numpy puro (dsp.py / trilha.py).

Comandos (a IA roda nesta ordem):
  python editor_viral.py setup                         prepara tudo (só na 1ª vez; mostra o que achou)
  python editor_viral.py transcrever VIDEO             -> pasta VIDEO_ev/ com transcricao.txt e palavras.json
  python editor_viral.py auto VIDEO                    -> VIDEO_ev/plano.json com um plano pronto (a IA ajusta)
  python editor_viral.py editar VIDEO [--plano p.json] -> VIDEO_ev/VIDEO_editado.mp4 + .srt + folha.jpg (conferência)
  python editor_viral.py versoes VIDEO                 -> 3 aberturas diferentes para teste A/B
  python editor_viral.py folha arquivo.mp4             -> folha de quadros para conferir o resultado
  ... --fundo                                          roda em segundo plano (vídeo longo: evita limite de tempo)
  python editor_viral.py andamento VIDEO               PRONTO + resultado, ou AINDA PROCESSANDO

Procura arquivos de apoio (modelos, rodas Python, fontes, emojis) nesta pasta, em /mnt/data (ChatGPT),
/mnt/user-data/uploads (Claude) e na pasta atual. Sem internet, usa só o que achar ali.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import wave
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
CASA = Path(os.environ.get("EDITOR_VIRAL_CASA") or Path.home() / ".editor_viral")
BUSCA = [AQUI, AQUI.parent, Path("/mnt/data"), Path("/mnt/user-data/uploads"), Path("/mnt/user-data"),
         Path.cwd(), CASA]
MODELO_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
W, H, FPS = 1080, 1920, 30
# idioma da fala (transcrição e emojis): "pt" ou "es" — vem do idioma.txt da skill ou de EDITOR_VIRAL_IDIOMA
IDIOMA = (os.environ.get("EDITOR_VIRAL_IDIOMA") or next((p.read_text(encoding="utf-8").strip() for p in
          (AQUI / "idioma.txt", AQUI.parent / "idioma.txt") if p.exists()), "") or "pt").lower()[:2]
SR16 = 16000


def log(*a):
    print(*a, flush=True)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))


def achar(*padroes: str) -> Path | None:
    for base in BUSCA:
        for p in padroes:
            hits = sorted(glob.glob(str(base / "**" / p), recursive=True)) if base.exists() else []
            if hits:
                return Path(hits[0])
    return None


# ---------------------------------------------------------------------------------------------------------------
# preparação

def _pip(*args: str) -> bool:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *args],
                       capture_output=True, text=True)
    return r.returncode == 0


def _extrair_zips():
    """Pacotes de apoio enviados como .zip (ChatGPT/Claude): extrai uma vez em ~/.editor_viral."""
    CASA.mkdir(parents=True, exist_ok=True)
    for base in BUSCA[:-1]:
        if not base.exists():
            continue
        for z in base.glob("*.zip"):
            marca = CASA / f".{z.name}.ok"
            if marca.exists() or not zipfile.is_zipfile(z):
                continue
            nomes = zipfile.ZipFile(z).namelist()
            if any(n.endswith((".onnx", ".ttf", ".png", ".whl", "tokens.txt")) for n in nomes):
                zipfile.ZipFile(z).extractall(CASA)
                marca.write_text("ok")


def ffmpeg_bin() -> str:
    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        if " ass " in r.stdout:
            return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pass
    roda = achar("imageio_ffmpeg-*.whl")
    if (roda and _pip("--no-deps", str(roda))) or _pip("imageio-ffmpeg"):
        import importlib
        importlib.invalidate_caches()
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    if shutil.which("ffmpeg"):
        return "ffmpeg"      # sem libass: a legenda sai pelo filtro drawtext (mais simples)
    raise SystemExit("ffmpeg não encontrado e não deu para instalar (sem internet e sem o arquivo imageio_ffmpeg*.whl)")


FF = None


def ff(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    global FF
    FF = FF or ffmpeg_bin()
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg falhou: {r.stderr[-1500:]}")
    return r


def sondar(video: Path) -> dict:
    """Duração, tamanho e rotação via ffmpeg -i (ffprobe nem sempre existe)."""
    global FF
    FF = FF or ffmpeg_bin()
    r = subprocess.run([FF, "-hide_banner", "-i", str(video)], capture_output=True, text=True)
    txt = r.stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    v = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})", txt)
    w, h = (int(v.group(1)), int(v.group(2))) if v else (0, 0)
    rot = re.search(r"rotation of (-?[\d.]+)|rotate\s*:\s*(-?\d+)", txt)
    if rot and abs(float(rot.group(1) or rot.group(2))) in (90.0, 270.0):
        w, h = h, w
    return {"duracao": round(dur, 3), "w": w, "h": h, "audio": "Audio:" in txt,
            "mb": round(video.stat().st_size / 1e6, 1)}


def asr_modelo() -> dict | None:
    """Arquivos do Whisper (sherpa-onnx). Ordem: base > small > tiny, o que existir; senão baixa o base."""
    _extrair_zips()
    for nome in ("base", "small", "tiny"):
        enc = achar(f"{nome}-encoder.int8.onnx")
        dec = achar(f"{nome}-decoder.int8.onnx")
        tok = achar(f"{nome}-tokens.txt")
        if enc and dec and tok:
            return {"nome": nome, "encoder": enc, "decoder": dec, "tokens": tok}
    return None


def baixar_modelo(nome: str = "base") -> dict | None:
    import tarfile
    import urllib.request
    CASA.mkdir(parents=True, exist_ok=True)
    tgz = CASA / f"whisper-{nome}.tar.bz2"
    try:
        log(f"baixando o modelo de transcrição ({nome}) ...")
        urllib.request.urlretrieve(f"{MODELO_URL}sherpa-onnx-whisper-{nome}.tar.bz2", tgz)
        with tarfile.open(tgz) as t:
            for m in t.getmembers():
                if m.name.endswith((f"{nome}-encoder.int8.onnx", f"{nome}-decoder.int8.onnx", f"{nome}-tokens.txt")):
                    m.name = Path(m.name).name
                    t.extract(m, CASA, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        tgz.unlink(missing_ok=True)
        if not achar("silero_vad.onnx"):
            urllib.request.urlretrieve(f"{MODELO_URL}silero_vad.onnx", CASA / "silero_vad.onnx")
        return asr_modelo()
    except Exception as exc:  # noqa: BLE001
        log(f"não deu para baixar o modelo ({exc})")
        tgz.unlink(missing_ok=True)
        return None


def sherpa_ok() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        pass
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    core = achar("sherpa_onnx_core-*.whl")
    roda = achar(f"sherpa_onnx-*{tag}*.whl")
    if core and roda and _pip("--no-deps", str(core), str(roda)):
        pass
    elif not _pip("sherpa-onnx"):
        return False
    import importlib
    importlib.invalidate_caches()
    try:
        import sherpa_onnx  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def setup() -> dict:
    t0 = time.time()
    _extrair_zips()
    st = {"python": sys.version.split()[0]}
    try:
        import numpy  # noqa: F401
        st["numpy"] = "ok"
    except Exception:  # noqa: BLE001
        st["numpy"] = "instalando" if _pip("numpy") else "FALTA"
    try:
        st["ffmpeg"] = ffmpeg_bin()
    except SystemExit as exc:
        st["ffmpeg"] = f"FALTA: {exc}"
    st["transcricao"] = "sherpa-onnx" if sherpa_ok() else "FALTA (sem sherpa-onnx)"
    mod = asr_modelo() or (baixar_modelo("base") if st["transcricao"] == "sherpa-onnx" else None)
    st["modelo"] = mod["nome"] if mod else "FALTA"
    st["vad"] = "ok" if achar("silero_vad.onnx") else "sem (usa energia)"
    st["fontes"] = "ok" if achar("Anton-Regular.ttf") else "FALTA"
    st["emojis"] = len(list((achar("1f525.png") or Path("/x")).parent.glob("*.png"))) if achar("1f525.png") else 0
    st["segundos"] = round(time.time() - t0, 1)
    st["pronto"] = all(not str(v).startswith("FALTA") for v in st.values())
    CASA.mkdir(parents=True, exist_ok=True)
    (CASA / "setup.json").write_text(json.dumps(st, ensure_ascii=False))
    return st


# ---------------------------------------------------------------------------------------------------------------
# transcrição

def pasta_de(video: Path) -> Path:
    d = video.with_name(video.stem + "_ev")
    if not os.access(video.parent, os.W_OK):
        d = Path("/mnt/data" if Path("/mnt/data").exists() else Path.cwd()) / (video.stem + "_ev")
    d.mkdir(parents=True, exist_ok=True)
    return d


def audio16(video: Path, saida: Path):
    import numpy as np
    ff("-i", str(video), "-vn", "-ac", "1", "-ar", str(SR16), "-f", "s16le", str(saida))
    return np.fromfile(saida, dtype="<i2").astype("float32") / 32768.0


def trechos_de_fala(x, min_silencio: float = 0.22) -> list[tuple[float, float]]:
    """Silero VAD (quando existe) ou energia: trechos com voz, em segundos."""
    import numpy as np
    vad_arq = achar("silero_vad.onnx")
    if vad_arq:
        try:
            import sherpa_onnx as so
            cfg = so.VadModelConfig()
            cfg.silero_vad.model = str(vad_arq)
            cfg.silero_vad.min_silence_duration = min_silencio
            cfg.silero_vad.min_speech_duration = 0.12
            cfg.silero_vad.max_speech_duration = 30
            cfg.sample_rate = SR16
            vad = so.VoiceActivityDetector(cfg, buffer_size_in_seconds=max(60, int(len(x) / SR16) + 5))
            for i in range(0, len(x), 512):
                vad.accept_waveform(x[i:i + 512])
            vad.flush()
            out = []
            while not vad.empty():
                s = vad.front
                out.append((s.start / SR16, (s.start + len(s.samples)) / SR16))
                vad.pop()
            if out:
                return out
        except Exception as exc:  # noqa: BLE001
            log(f"VAD falhou ({exc}); usando energia")
    q = int(0.02 * SR16)
    e = np.sqrt(np.convolve(x ** 2, np.ones(q) / q, "same"))[::q]
    lim = max(np.percentile(e, 20) * 3, 0.008)
    fala, out, ini, sil = e > lim, [], None, 0
    for i, f in enumerate(fala):
        t = i * 0.02
        if f:
            ini = t if ini is None else ini
            sil = 0
        elif ini is not None:
            sil += 0.02
            if sil >= min_silencio:
                out.append((ini, t - sil + 0.02))
                ini, sil = None, 0
    if ini is not None:
        out.append((ini, len(x) / SR16))
    return [(a, b) for a, b in out if b - a > 0.12]


def _pedacos(x, a: float, b: float, alvo: float = 2.6) -> list[tuple[float, float]]:
    """Divide um trecho longo de fala em pedaços de ~2-3 s nos pontos de menor energia (entre palavras)."""
    import numpy as np
    out, ini = [], a
    q = int(0.01 * SR16)
    while b - ini > alvo + 1.0:
        j0, j1 = int((ini + alvo - 0.7) * SR16), int((ini + alvo + 0.7) * SR16)
        seg = x[j0:j1]
        if len(seg) < q * 3:
            break
        e = np.convolve(seg ** 2, np.ones(q * 4) / (q * 4), "same")
        corte = (j0 + int(np.argmin(e[q * 2:-q * 2])) + q * 2) / SR16
        out.append((ini, corte))
        ini = corte
    out.append((ini, b))
    return out


def _silabas(p: str) -> int:
    return max(1, len(re.findall(r"[aeiouáéíóúâêôãõàüy]+", p.lower())))


def _colocar(texto: str, a: float, b: float, x) -> list[dict]:
    """Palavras com tempo: distribui pelo número de sílabas dentro da parte com som do pedaço."""
    import numpy as np
    ps = texto.split()
    if not ps:
        return []
    seg = x[int(a * SR16):int(b * SR16)]
    q = int(0.01 * SR16)
    if len(seg) > q * 4:     # apara silêncio no começo/fim do pedaço
        e = np.sqrt(np.convolve(seg ** 2, np.ones(q) / q, "same"))
        lim = max(e.max() * 0.12, 1e-4)
        idx = np.where(e > lim)[0]
        if len(idx):
            a, b = a + idx[0] / SR16, a + idx[-1] / SR16
    pesos = [_silabas(p) + 0.6 for p in ps]
    tot = sum(pesos)
    out, t = [], a
    for p, w in zip(ps, pesos):
        d = (b - a) * w / tot
        out.append({"w": p, "t0": round(t, 3), "t1": round(t + d * 0.92, 3)})
        t += d
    return out


def transcrever(video: Path, idioma: str = IDIOMA) -> dict:
    video = Path(video).resolve()
    d = pasta_de(video)
    info = sondar(video)
    x = audio16(video, d / "audio16.raw")
    fala = trechos_de_fala(x)
    palavras = []
    t0 = time.time()
    motor = None
    if not sherpa_ok() or not (asr_modelo() or baixar_modelo("base")):
        try:   # plano B: faster-whisper (precisa baixar o modelo da internet)
            from faster_whisper import WhisperModel
            wm = WhisperModel(os.environ.get("EV_WHISPER", "small"), compute_type="int8")
            segs, _ = wm.transcribe(x, language=idioma, word_timestamps=True, vad_filter=True)
            for s in segs:
                for w in s.words or []:
                    palavras.append({"w": w.word.strip(), "t0": round(w.start, 3), "t1": round(w.end, 3)})
            motor = "faster-whisper"
        except Exception:  # noqa: BLE001
            palavras = []
        if not palavras:
            raise SystemExit("Sem transcrição: rode `python editor_viral.py setup` e veja o que falta.")
    if not palavras:
        import sherpa_onnx as so
        mod = asr_modelo() or baixar_modelo("base")
        if not mod:
            raise SystemExit("Modelo de transcrição não encontrado (arquivos *-encoder.int8.onnx) e sem internet.")
        rec = so.OfflineRecognizer.from_whisper(encoder=str(mod["encoder"]), decoder=str(mod["decoder"]),
                                                tokens=str(mod["tokens"]), language=idioma, task="transcribe",
                                                num_threads=max(os.cpu_count() or 2, 2))
        motor = f"whisper-{mod['nome']}"
        for a, b in fala:
            for pa, pb in _pedacos(x, a, b):
                s = rec.create_stream()
                s.accept_waveform(SR16, x[int(pa * SR16):int(pb * SR16)])
                rec.decode_stream(s)
                txt = s.result.text.strip()
                if txt and not re.fullmatch(r"[\W_]*", txt):
                    palavras += _colocar(txt, pa, pb, x)
    frases, cur = [], []
    for i, w in enumerate(palavras):
        w["i"] = i
        cur.append(w)
        if w["w"].endswith((".", "!", "?")) or (i + 1 < len(palavras) and palavras[i + 1]["t0"] - w["t1"] > 0.6):
            frases.append(cur)
            cur = []
    if cur:
        frases.append(cur)
    linhas = [f"Vídeo: {video.name} | {info['duracao']:.1f}s | {info['w']}x{info['h']} | transcrição: {motor}",
              "Formato: [início-fim] (índices das palavras) frase", ""]
    for f in frases:
        linhas.append(f"[{f[0]['t0']:6.2f}-{f[-1]['t1']:6.2f}] ({f[0]['i']}-{f[-1]['i']}) "
                      + " ".join(w["w"] for w in f))
    pausas = [(round(b0, 2), round(a1, 2)) for (_, b0), (a1, _) in zip(fala, fala[1:]) if a1 - b0 >= 0.35]
    linhas += ["", f"Pausas de 0,35 s ou mais: {len(pausas)}"]
    res = {"video": str(video), "info": info, "motor": motor, "palavras": palavras, "fala": fala,
           "segundos": round(time.time() - t0, 1)}
    (d / "palavras.json").write_text(json.dumps(res, ensure_ascii=False))
    (d / "transcricao.txt").write_text("\n".join(linhas), encoding="utf-8")
    (d / "audio16.raw").unlink(missing_ok=True)
    log("\n".join(linhas))
    log(f"\nTranscrição em {res['segundos']}s ({motor}) -> {d / 'transcricao.txt'}")
    return res


# ---------------------------------------------------------------------------------------------------------------
# emoção, emoji e cor (léxico pt-BR: só palavras ditas)

EMOCOES = {"dinheiro": "#22C55E", "urgencia": "#F43F5E", "alerta": "#F97316", "curiosidade": "#B794FF",
           "confianca": "#60A5FA", "desejo": "#F472B6", "alegria": "#FACC15"}
LEXICO = {
    "dinheiro": ("dinheiro", "💰"), "reais": ("dinheiro", "💸"), "real": ("dinheiro", "💸"), "lucro": ("dinheiro", "📈"),
    "vender": ("dinheiro", "🤑"), "venda*": ("dinheiro", "🤑"), "vendi*": ("dinheiro", "🤑"), "fatur*": ("dinheiro", "💰"),
    "promocao": ("dinheiro", "🏷️"), "desconto": ("dinheiro", "🏷️"), "barato": ("dinheiro", "🏷️"), "comprar": ("dinheiro", "🛒"),
    "gratis": ("alegria", "🎁"), "presente": ("alegria", "🎁"), "bonus": ("alegria", "🎁"),
    "rapido": ("urgencia", "⚡"), "agora": ("urgencia", "⏰"), "hoje": ("urgencia", "⏰"), "ultim*": ("urgencia", "⏳"),
    "corre": ("urgencia", "🏃"), "acaba*": ("urgencia", "⏳"), "urgente": ("urgencia", "🚨"),
    "cuidado": ("alerta", "⚠️"), "erro": ("alerta", "❌"), "errado": ("alerta", "❌"), "nunca": ("alerta", "🚫"),
    "pare": ("alerta", "✋"), "estrag*": ("alerta", "⚠️"), "jamais": ("alerta", "🚫"), "problema": ("alerta", "⚠️"),
    "perig*": ("alerta", "⚠️"), "golpe": ("alerta", "🚨"),
    "segredo": ("curiosidade", "🤫"), "descobri": ("curiosidade", "💡"), "ideia": ("curiosidade", "💡"),
    "olha": ("curiosidade", "👀"), "veja": ("curiosidade", "👀"), "imagina": ("curiosidade", "💭"),
    "sabia": ("curiosidade", "🤔"), "verdade": ("curiosidade", "🤯"),
    "metodo": ("confianca", "🧠"), "garantia": ("confianca", "🛡️"), "seguro": ("confianca", "🛡️"),
    "comprovado": ("confianca", "✅"), "resultado*": ("confianca", "📈"), "funciona": ("confianca", "✅"),
    "facil": ("confianca", "👌"), "simples": ("confianca", "👌"), "passo": ("confianca", "📌"),
    "gostoso": ("desejo", "😋"), "delicia": ("desejo", "😋"), "lindo": ("desejo", "😍"), "amo": ("desejo", "❤️"),
    "perfeito": ("desejo", "🤩"), "incrivel": ("alegria", "🤩"), "top": ("alegria", "🔥"), "fogo": ("alegria", "🔥"),
    "viral": ("alegria", "🚀"), "crescer": ("alegria", "🚀"), "sucesso": ("alegria", "🏆"), "ganhar": ("dinheiro", "💰"),
    "ganh*": ("dinheiro", "💰"), "cliente*": ("dinheiro", "🤝"), "audiencia": ("alegria", "📊"), "seguidor*": ("alegria", "🚀"),
}
CURTAS = {"que", "uma", "pra", "para", "com", "por", "isso", "esse", "essa", "aqui", "voce", "mais", "como", "mas",
          "quando", "porque", "entao", "tambem", "muito", "sobre", "tipo", "tudo", "nao", "sim", "ele", "ela", "eles"}

# léxico em espanhol (mesmas emoções e emojis)
LEXICO_ES = {
    "dinero": ("dinero", "💰"), "plata": ("dinero", "💸"), "pesos": ("dinero", "💸"), "dolares": ("dinero", "💸"),
    "ganancia*": ("dinero", "📈"), "vender": ("dinero", "🤑"), "venta*": ("dinero", "🤑"), "vendi*": ("dinero", "🤑"),
    "factur*": ("dinero", "💰"), "promocion": ("dinero", "🏷️"), "oferta": ("dinero", "🏷️"), "descuento": ("dinero", "🏷️"),
    "barato": ("dinero", "🏷️"), "comprar": ("dinero", "🛒"), "compra*": ("dinero", "🛒"),
    "gratis": ("alegria", "🎁"), "regalo": ("alegria", "🎁"), "bono": ("alegria", "🎁"), "bonus": ("alegria", "🎁"),
    "rapido": ("urgencia", "⚡"), "ahora": ("urgencia", "⏰"), "hoy": ("urgencia", "⏰"), "ultim*": ("urgencia", "⏳"),
    "corre": ("urgencia", "🏃"), "acaba*": ("urgencia", "⏳"), "urgente": ("urgencia", "🚨"),
    "cuidado": ("alerta", "⚠️"), "error*": ("alerta", "❌"), "equivoc*": ("alerta", "❌"), "nunca": ("alerta", "🚫"),
    "deja": ("alerta", "✋"), "jamas": ("alerta", "🚫"), "problema*": ("alerta", "⚠️"),
    "peligr*": ("alerta", "⚠️"), "estafa": ("alerta", "🚨"),
    "secreto": ("curiosidad", "🤫"), "descubri": ("curiosidad", "💡"), "idea": ("curiosidad", "💡"),
    "mira": ("curiosidad", "👀"), "miren": ("curiosidad", "👀"), "imagina": ("curiosidad", "💭"),
    "sabias": ("curiosidad", "🤔"), "verdad": ("curiosidad", "🤯"),
    "metodo": ("confianza", "🧠"), "garantia": ("confianza", "🛡️"), "seguro": ("confianza", "🛡️"),
    "comprobado": ("confianza", "✅"), "resultado*": ("confianza", "📈"), "funciona": ("confianza", "✅"),
    "facil": ("confianza", "👌"), "simple": ("confianza", "👌"), "paso": ("confianza", "📌"),
    "rico": ("deseo", "😋"), "delicioso": ("deseo", "😋"), "hermos*": ("deseo", "😍"), "lind*": ("deseo", "😍"),
    "amo": ("deseo", "❤️"), "perfecto": ("deseo", "🤩"), "increible": ("alegria", "🤩"), "fuego": ("alegria", "🔥"),
    "viral": ("alegria", "🚀"), "crecer": ("alegria", "🚀"), "exito": ("alegria", "🏆"), "ganar": ("dinero", "💰"),
    "gan*": ("dinero", "💰"), "cliente*": ("dinero", "🤝"), "audiencia": ("alegria", "📊"), "seguidor*": ("alegria", "🚀"),
}
CURTAS_ES = {"que", "una", "uno", "para", "con", "por", "eso", "esto", "esta", "este", "aqui", "tu", "mas", "como",
             "pero", "cuando", "porque", "entonces", "tambien", "muy", "sobre", "todo", "no", "si", "el", "ella",
             "ellos", "los", "las", "del", "les", "nos", "vos", "usted"}
# nomes das emoções em espanhol -> mesmas cores
EMOCOES.update({"dinero": EMOCOES["dinheiro"], "curiosidad": EMOCOES["curiosidade"],
                "confianza": EMOCOES["confianca"], "deseo": EMOCOES["desejo"]})
if IDIOMA == "es":
    LEXICO, CURTAS = LEXICO_ES, CURTAS_ES


def emocao(p: str) -> tuple[str, str | None]:
    n = norm(p)
    if n in LEXICO:
        return LEXICO[n]
    for k, v in LEXICO.items():
        if k.endswith("*") and n.startswith(k[:-1]):
            return v
    return "neutro", None


def emoji_png(e: str) -> Path | None:
    nome = "-".join(f"{ord(c):x}" for c in e if ord(c) != 0xFE0F) + ".png"
    return achar(nome)


# ---------------------------------------------------------------------------------------------------------------
# plano automático (a IA ajusta depois)

def plano_auto(tr: dict, objetivo: str = "anuncio") -> dict:
    ps = tr["palavras"]
    destaques, ult = [], -99.0
    for w in ps:
        emo, em = emocao(w["w"])
        dig = any(c.isdigit() for c in w["w"])
        if (em or dig) and w["t0"] - ult >= 3.0 and norm(w["w"]) not in CURTAS:
            destaques.append({"i": w["i"], "emoji": em or "", "cor": EMOCOES.get(emo, "#FFD400")})
            ult = w["t0"]
    zooms = [ps[d["i"]]["t0"] for d in destaques]
    return {"formato": "9:16", "corte": {"pausas": True, "max_pausa": 0.3, "remover": [], "gancho": None},
            "legenda": {"cor_destaque": "#FFD400", "tamanho": 118, "altura": 0.70, "palavras_por_tela": 3,
                        "maiusculas": True, "fonte": "Anton"},
            "destaques": destaques, "zoom": {"momentos": zooms, "forca": 1.12, "respira": True},
            "voz": "estudio", "trilha": {"clima": "energia" if objetivo != "aula" else "corporativo", "volume": 0.45},
            "titulo_gancho": None, "cta": None, "correcoes": {}}


# ---------------------------------------------------------------------------------------------------------------
# edição

def _manter(tr: dict, plano: dict) -> list[tuple[float, float]]:
    """Trechos do vídeo original que ficam (em ordem de exibição)."""
    c = plano.get("corte") or {}
    dur = tr["info"]["duracao"]
    if c.get("pausas", True) and tr.get("fala"):
        gap = float(c.get("max_pausa", 0.3))
        seg = []
        for a, b in tr["fala"]:
            a, b = max(a - 0.07, 0), min(b + 0.12, dur)
            if seg and a - seg[-1][1] <= gap:
                seg[-1][1] = b
            else:
                seg.append([a, b])
    else:
        seg = [[0.0, dur]]
    for ra, rb in c.get("remover") or []:
        novo = []
        for a, b in seg:
            if rb <= a or ra >= b:
                novo.append([a, b])
                continue
            if ra > a:
                novo.append([a, ra])
            if rb < b:
                novo.append([rb, b])
        seg = novo
    seg = [s for s in seg if s[1] - s[0] > 0.15]
    g = c.get("gancho")
    if g:
        ga, gb = g
        resto = []
        for a, b in seg:   # o trecho do gancho sai do meio e vai para o começo
            if gb <= a or ga >= b:
                resto.append([a, b])
            else:
                if ga > a:
                    resto.append([a, ga])
                if gb < b:
                    resto.append([gb, b])
        seg = [[ga, gb]] + [s for s in resto if s[1] - s[0] > 0.15]
    return [(round(a, 3), round(b, 3)) for a, b in seg]


def _mapa(tempos: list[tuple[float, float]]):
    """Tempo original -> tempo editado (None se o instante foi cortado)."""
    base = []
    acc = 0.0
    for a, b in tempos:
        base.append((a, b, acc))
        acc += b - a

    def f(t: float) -> float | None:
        for a, b, o in base:
            if a - 1e-3 <= t <= b + 1e-3:
                return o + (min(max(t, a), b) - a)
        return None
    return f, acc


def _ass_cor(hexa: str) -> str:
    h = hexa.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _ts(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def legenda_ass(palavras: list[dict], plano: dict, dur: float, destaques: dict) -> str:
    lg = plano.get("legenda") or {}
    tam = int(lg.get("tamanho", 118))
    y = int(H * float(lg.get("altura", 0.70)))
    fonte = lg.get("fonte", "Anton")
    cor = _ass_cor(lg.get("cor_destaque", "#FFD400"))
    n = int(lg.get("palavras_por_tela", 3))
    up = lg.get("maiusculas", True)
    L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
         "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
         "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
         "MarginR, MarginV, Encoding",
         f"Style: Leg,{fonte},{tam},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,7,3,5,60,60,0,1",
         f"Style: Big,{fonte},{int(tam * 1.75)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,10,4,5,40,40,0,1",
         f"Style: Topo,Poppins Black,{int(tam * 0.78)},&H00FFFFFF,&H00FFFFFF,&H00000000,&HC8000000,0,0,0,0,100,100,0,0,3,18,0,8,70,70,260,1",
         "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    txt = lambda s: (s.upper() if up else s).replace("{", "(").replace("}", ")")
    # páginas de n palavras (quebra em pontuação e em pausas)
    paginas, cur = [], []
    for w in palavras:
        if cur and (len(cur) >= n or w["t0"] - cur[-1]["t1"] > 0.5 or cur[-1]["w"].endswith((".", "?", "!", ","))):
            paginas.append(cur)
            cur = []
        cur.append(w)
    if cur:
        paginas.append(cur)
    por_i = {p["i"]: p for p in palavras}
    # quanto tempo cada palavra gigante fica na tela: a legenda comum espera ela sair (nunca as duas juntas)
    gigantes = [(por_i[i]["t0"] - 0.04, max(por_i[i]["t1"] + 0.55, por_i[i]["t0"] + 1.1)) for i in destaques if i in por_i]
    for k, pg in enumerate(paginas):
        fim_pg = min(paginas[k + 1][0]["t0"] if k + 1 < len(paginas) else pg[-1]["t1"] + 0.4, pg[-1]["t1"] + 0.6)
        if any(w["i"] in destaques for w in pg):
            continue   # a palavra gigante ocupa a vez da legenda
        for j, w in enumerate(pg):
            t0 = w["t0"] if j else pg[0]["t0"]
            t1 = pg[j + 1]["t0"] if j + 1 < len(pg) else fim_pg
            for a, b in gigantes:
                if a < t1 and t0 < b:
                    t0 = max(t0, b) if a <= t0 else t0
                    t1 = min(t1, a) if a > t0 else t1
            if t1 - t0 < 0.04:
                continue
            partes = []
            for m, o in enumerate(pg):
                s = txt(o["w"].strip(".,"))
                partes.append(r"{\c" + cor + r"\fscx112\fscy112}" + s + r"{\c&H00FFFFFF&\fscx100\fscy100}" if m == j else s)
            pop = r"{\fad(40,0)\t(0,90,\fscx106\fscy106)\t(90,160,\fscx100\fscy100)}" if j == 0 else ""
            L.append(f"Dialogue: 0,{_ts(t0)},{_ts(t1)},Leg,,0,0,0,,{{\\pos({W // 2},{y})}}{pop}" + " ".join(partes))
    for i, d in destaques.items():
        w = next((p for p in palavras if p["i"] == i), None)
        if not w:
            continue
        t1 = next(b for a, b in gigantes if abs(a - (w["t0"] - 0.04)) < 1e-6)
        c = _ass_cor(d.get("cor") or lg.get("cor_destaque", "#FFD400"))
        L.append(f"Dialogue: 1,{_ts(w['t0'] - 0.04)},{_ts(t1)},Big,,0,0,0,,{{\\pos({W // 2},{int(H * 0.72)})"
                 rf"\c{c}\fscx40\fscy40\t(0,140,\fscx118\fscy118)\t(140,240,\fscx100\fscy100)\fad(0,120)}}"
                 + txt(w["w"].strip(".,!?")))
    tg = plano.get("titulo_gancho")
    if tg and tg.get("texto"):
        L.append(f"Dialogue: 2,{_ts(0.05)},{_ts(float(tg.get('ate', 2.6)))},Topo,,0,0,0,,{{\\fad(120,150)}}{txt(tg['texto'])}")
    cta = plano.get("cta")
    if cta and cta.get("texto"):
        a = max(dur - float(cta.get("segundos", 3.0)), 0)
        L.append(f"Dialogue: 2,{_ts(a)},{_ts(dur)},Topo,,0,0,0,,{{\\fad(150,0)\\move({W // 2},{H - 300},{W // 2},{H - 420},0,250)"
                 rf"\an2}}{txt(cta['texto'])}")
    return "\n".join(L) + "\n"


def srt(palavras: list[dict]) -> str:
    out, k, cur = [], 1, []
    for w in palavras + [None]:
        if w is None or (cur and (len(cur) >= 6 or w["t0"] - cur[-1]["t1"] > 0.6)):
            if cur:
                ts = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}"
                out += [str(k), f"{ts(cur[0]['t0'])} --> {ts(cur[-1]['t1'])}", " ".join(p["w"] for p in cur), ""]
                k += 1
            cur = []
        if w is not None:
            cur.append(w)
    return "\n".join(out)


def _zoom_expr(momentos: list[float], forca: float, dur: float, respira: bool) -> str:
    """Fator de zoom por tempo: soco rápido (0,12 s) em cada momento, segura ~1,2 s e volta; respiração leve."""
    termos = []
    for t in momentos[:40]:
        termos.append(f"({forca - 1:.3f})*clip((t-{t - 0.05:.2f})/0.12,0,1)*clip(({t + 1.35:.2f}-t)/0.3,0,1)")
    base = f"1+0.03*t/{max(dur, 1):.2f}" if respira else "1"
    return base + ("+" + "+".join(termos) if termos else "")


def editar(video: Path, plano: dict | None = None, saida: Path | None = None, rapido: bool = False) -> dict:
    t_ini = time.time()
    video = Path(video).resolve()
    saida = Path(saida).resolve() if saida else None
    d = pasta_de(video)
    trf = d / "palavras.json"
    tr = json.loads(trf.read_text(encoding="utf-8")) if trf.exists() else transcrever(video)
    if plano is None:
        pf = d / "plano.json"
        plano = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else plano_auto(tr)
    corr = {norm(k): v for k, v in (plano.get("correcoes") or {}).items()}
    tempos = _manter(tr, plano)
    f, total = _mapa(tempos)
    # palavras no tempo editado (as cortadas somem)
    ps = []
    for w in tr["palavras"]:
        a, b = f(w["t0"]), f(w["t1"])
        if a is None or b is None or b <= a:
            continue
        txt = corr.get(norm(w["w"]), w["w"])
        ps.append({"w": txt, "t0": round(a, 3), "t1": round(b, 3), "i": w["i"]})
    gancho = (plano.get("corte") or {}).get("gancho")
    if gancho:  # o gancho repetido: palavras do gancho aparecem no começo
        ps.sort(key=lambda w: w["t0"])
    destaques = {int(x["i"]): x for x in plano.get("destaques") or [] if "i" in x}
    for x in plano.get("destaques") or []:   # destaque por palavra (texto): 1ª ocorrência
        if "i" not in x and x.get("palavra"):
            w = next((p for p in ps if norm(p["w"]) == norm(x["palavra"])), None)
            if w:
                destaques[w["i"]] = x
    ass = d / "legenda.ass"
    ass.write_text(legenda_ass(ps, plano, total, destaques), encoding="utf-8")
    (d / (video.stem + "_editado.srt")).write_text(srt(ps), encoding="utf-8")
    fontes = (achar("Anton-Regular.ttf") or AQUI).parent
    # áudio: voz limpa + trilha
    audio_voz = d / "voz.wav"
    partes_a = "".join(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{k}];" for k, (a, b) in enumerate(tempos))
    ff("-i", str(video), "-filter_complex",
       partes_a + "".join(f"[a{k}]" for k in range(len(tempos))) + f"concat=n={len(tempos)}:v=0:a=1[o]",
       "-map", "[o]", "-ac", "1", "-ar", "48000", str(audio_voz))
    if plano.get("voz", "estudio") == "estudio":
        try:
            limpar_voz(audio_voz, [(w["t0"], w["t1"]) for w in ps])
        except Exception as exc:  # noqa: BLE001
            log(f"voz limpa pulada ({exc})")
    trilha_wav = None
    tri = plano.get("trilha")
    if tri and tri.get("clima"):
        try:
            import trilha as tmod
            trilha_wav = d / "trilha.wav"
            fala = [[w["t0"], w["t1"]] for w in ps]
            tmod.gerar_arquivo(tri["clima"], trilha_wav, total, None, 1, tmod.regioes_fala(ps, total)[0], 6.0)
        except Exception as exc:  # noqa: BLE001
            log(f"trilha pulada ({exc})")
            trilha_wav = None
    # vídeo: cortes -> 9:16 -> zoom -> emojis -> legenda
    info = tr["info"]
    z = plano.get("zoom") or {}
    momentos = [m2 for m2 in (f(t) if not z.get("editado") else t for t in z.get("momentos", [])) if m2 is not None]
    if destaques and not z.get("momentos"):
        momentos = [w["t0"] for w in ps if w["i"] in destaques]
    zexp = _zoom_expr(momentos, float(z.get("forca", 1.12)), total, z.get("respira", True))
    fc = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{k}];" for k, (a, b) in enumerate(tempos))
    fc += "".join(f"[v{k}]" for k in range(len(tempos))) + f"concat=n={len(tempos)}:v=1:a=0[vc];"
    vertical = info["h"] >= info["w"]
    if vertical or plano.get("formato", "9:16") != "9:16":
        fc += f"[vc]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[vb];"
    else:   # vídeo deitado: fundo desfocado + vídeo no meio
        fc += (f"[vc]fps={FPS},split[x1][x2];[x1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
               f"boxblur=30:2[bg];[x2]scale={W}:-2[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1[vb];")
    fc += (f"[vb]scale=w='trunc({W}*({zexp})/2)*2':h='trunc({H}*({zexp})/2)*2':eval=frame,"
           f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.42[vz];")
    entradas = ["-i", str(video)]
    cur, n_in = "vz", 1
    for k, (i, dd) in enumerate(destaques.items()):
        w = next((p for p in ps if p["i"] == i), None)
        png = emoji_png(dd.get("emoji") or "") if dd.get("emoji") and w else None
        if not png:
            continue
        entradas += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(png)]
        a, b = w["t0"] - 0.04, max(w["t1"] + 0.55, w["t0"] + 1.1)
        fc += (f"[{n_in}:v]scale=200:200,format=rgba[e{k}];[{cur}][e{k}]overlay=x=(W-w)/2:y='{int(H * 0.72) + 95}"
               f"+40*clip(1-(t-{a:.2f})/0.15,0,1)':enable='between(t,{a:.2f},{b:.2f})'[ve{k}];")
        cur, n_in = f"ve{k}", n_in + 1
    fc += f"[{cur}]ass={ass.name}:fontsdir={fontes},format=yuv420p[vout]"
    aud = ["-i", str(audio_voz)]
    ia = n_in
    n_in += 1
    af = f"[{ia}:a]acompressor=threshold=-20dB:ratio=2.5:attack=5:release=90:makeup=1.5,loudnorm=I=-14:TP=-1.5:LRA=9[voz]"
    if trilha_wav:
        aud += ["-i", str(trilha_wav)]
        af += (f";[voz]asplit=2[vo1][vo2];[{n_in}:a]volume={float(tri.get('volume', 0.45)):.2f}[m];"
               "[m][vo2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md];"
               "[vo1][md]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[aout]")
    else:
        af += ";[voz]alimiter=limit=0.95[aout]"
    saida = saida or d / f"{video.stem}_editado.mp4"
    crf = "26" if rapido else "22"
    gf = d / "grafo.txt"
    gf.write_text(fc + ";" + af, encoding="utf-8")
    cwd = os.getcwd()
    os.chdir(d)   # legenda.ass com caminho relativo (evita problemas de escape no filtro)
    try:
        ff(*entradas, *aud, "-filter_complex_script", gf.name, "-map", "[vout]", "-map", "[aout]",
           "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast" if not rapido else "ultrafast",
           "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida))
    finally:
        os.chdir(cwd)
    mb = saida.stat().st_size / 1e6
    if mb > 48:   # anexos têm limite: reduz
        menor = saida.with_name(saida.stem + "_leve.mp4")
        ff("-i", str(saida), "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "copy", str(menor))
        menor.replace(saida)
        mb = saida.stat().st_size / 1e6
    folha(saida, d / "folha.jpg", total)
    res = {"arquivo": str(saida), "srt": str(d / (video.stem + "_editado.srt")), "folha": str(d / "folha.jpg"),
           "duracao_bruto": info["duracao"], "duracao_final": round(total, 2), "cortes": len(tempos) - 1,
           "destaques": len(destaques), "zooms": len(momentos), "mb": round(mb, 1),
           "segundos": round(time.time() - t_ini, 1)}
    (d / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    log(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def folha(video: Path, saida: Path, dur: float | None = None) -> Path:
    dur = dur or sondar(video)["duracao"]
    passo = max(dur / 9, 0.1)
    ff("-i", str(video), "-vf", f"fps=1/{passo:.3f},scale=270:-2,tile=3x3:padding=6:color=white", "-frames:v", "1",
       str(saida))
    return saida


def limpar_voz(wav: Path, fala: list[tuple[float, float]]) -> None:
    """Voz de estúdio (Wiener com o ruído medido nas pausas + gate suave + presença + de-esser + compressor)."""
    import numpy as np
    import dsp
    x = dsp.le_wav(wav).mean(axis=0)
    sr = dsp.SR
    n_fft, hop = 1024, 256
    jan = np.sqrt(np.hanning(n_fft + 1)[:-1])
    pad = np.concatenate([np.zeros(n_fft), x, np.zeros(n_fft)])
    nq = 1 + (len(pad) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(nq)[:, None]
    X = np.fft.rfft(pad[idx] * jan, axis=1)
    P = np.abs(X) ** 2
    tq = (np.arange(nq) * hop - n_fft / 2) / sr
    falando = np.zeros(nq, bool)
    for a, b in fala:
        falando |= (tq >= a - 0.12) & (tq <= b + 0.12)
    N = np.median(P[~falando], axis=0) * 1.4 if (~falando).sum() * hop / sr >= 0.3 else \
        P[P.sum(1) <= np.quantile(P.sum(1), 0.1)].mean(0)
    piso, ant, G = 10 ** (-15 / 20), np.zeros(P.shape[1]), np.empty_like(P)
    for i in range(nq):
        prio = 0.96 * ant / (N + 1e-12) + 0.04 * np.maximum(P[i] / (N + 1e-12) - 1, 0)
        G[i] = np.maximum(prio / (1 + prio), piso)
        ant = G[i] ** 2 * P[i]
    q = np.fft.irfft(X * G, n_fft, axis=1) * jan
    y = np.zeros(hop * (nq - 1) + n_fft)
    pw = np.zeros_like(y)
    for i in range(nq):
        y[i * hop:i * hop + n_fft] += q[i]
        pw[i * hop:i * hop + n_fft] += jan ** 2
    y = (y / np.maximum(pw, 1e-8))[n_fft:n_fft + len(x)]
    m = np.full(len(y), 10 ** (-10 / 20))
    for a, b in fala:
        m[max(int((a - 0.12) * sr), 0):int((b + 0.12) * sr)] = 1.0
    r = dsp.seg(0.08)
    m = np.maximum(np.convolve(np.pad(m, (r // 2, r - 1 - r // 2), mode="edge"), np.ones(r) / r, "valid"), m)
    y = dsp.filtro_fft(y * m, dsp.combina(dsp.r_passa_alta(75, 3), dsp.r_sino(250, -2.5, 1.2),
                                          dsp.r_sino(3200, 2.5, 1.0), dsp.r_prateleira(10000, 2.0, alta=True)))
    y = dsp.compressor(y[None, :], limiar_db=-24, razao=2.0, ataque=0.008, soltura=0.12)[0]
    dsp.grava_wav(wav, y * min(1.0, 0.89 / (np.max(np.abs(y)) or 1)))


def versoes(video: Path) -> list[dict]:
    """3 aberturas para teste A/B: A = frase mais forte no topo; B = gancho trazido do meio; C = sem título, soco forte."""
    d = pasta_de(video)
    tr = json.loads((d / "palavras.json").read_text(encoding="utf-8")) if (d / "palavras.json").exists() else transcrever(video)
    pf = d / "plano.json"
    base = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else plano_auto(tr)
    ps = tr["palavras"]
    frases, cur = [], []
    for w in ps:
        cur.append(w)
        if w["w"].endswith((".", "!", "?")):
            frases.append(cur)
            cur = []
    if cur:
        frases.append(cur)
    def forca(fr):
        txt = " ".join(w["w"] for w in fr)
        return ("?" in txt) * 3 + sum(1 for w in fr if emocao(w["w"])[1]) * 2 + sum(c.isdigit() for c in txt) \
            - abs(len(fr) - 9) * 0.2
    melhor = max(frases[1:] or frases, key=forca) if frases else None
    out = []
    for letra in "ABC":
        p = json.loads(json.dumps(base))
        if letra == "A" and frases:
            p["titulo_gancho"] = {"texto": " ".join(w["w"] for w in frases[0][:7]).strip(".,"), "ate": 2.6}
        if letra == "B" and melhor and melhor is not frases[0]:
            p.setdefault("corte", {})["gancho"] = [melhor[0]["t0"] - 0.05, melhor[-1]["t1"] + 0.1]
        if letra == "C":
            p["zoom"] = {**(p.get("zoom") or {}), "forca": 1.2}
            p["titulo_gancho"] = None
        r = editar(video, p, d / f"{video.stem}_gancho_{letra}.mp4", rapido=True)
        out.append({"versao": letra, **r})
    return out


def iniciar(argv: list[str], video: Path) -> None:
    """Roda um comando em segundo plano (o ChatGPT/Claude cortam comandos longos): volta na hora."""
    d = pasta_de(Path(video).resolve())
    (d / "pronto.json").unlink(missing_ok=True)
    logf = open(d / "andamento.log", "w", encoding="utf-8")
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *argv, "--marcar-fim"], stdout=logf,
                     stderr=subprocess.STDOUT, start_new_session=True, cwd=str(d))
    print(f"Começou em segundo plano. Consulte com: andamento {video}")


def andamento(video: Path) -> None:
    d = pasta_de(Path(video).resolve())
    fim = d / "pronto.json"
    lg = (d / "andamento.log").read_text(encoding="utf-8", errors="replace") if (d / "andamento.log").exists() else ""
    if fim.exists():
        print("PRONTO\n" + fim.read_text(encoding="utf-8"))
    else:
        print("AINDA PROCESSANDO (consulte de novo em ~20 s)\n" + "\n".join(lg.strip().splitlines()[-4:]))


def main() -> None:
    if "--fundo" in sys.argv:   # editar/versoes/transcrever em segundo plano
        argv = [a for a in sys.argv[1:] if a != "--fundo"]
        argv[1] = str(Path(argv[1]).resolve())
        if "--plano" in argv:
            k = argv.index("--plano") + 1
            argv[k] = str(Path(argv[k]).resolve())
        return iniciar(argv, Path(argv[1]))
    marcar = "--marcar-fim" in sys.argv
    if marcar:
        sys.argv.remove("--marcar-fim")
    try:
        _main()
    except BaseException as exc:
        if marcar and not isinstance(exc, KeyboardInterrupt):
            pasta_de(Path(sys.argv[2]).resolve()).joinpath("pronto.json").write_text(
                json.dumps({"erro": str(exc)}, ensure_ascii=False), encoding="utf-8")
        raise
    if marcar:
        d = pasta_de(Path(sys.argv[2]).resolve())
        res = d / "resultado.json"
        (d / "pronto.json").write_text(res.read_text(encoding="utf-8") if res.exists() and sys.argv[1] == "editar"
                                       else json.dumps({"ok": sys.argv[1]}), encoding="utf-8")


def _main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    an = sub.add_parser("andamento")
    an.add_argument("video")
    for nome in ("transcrever", "auto", "editar", "versoes"):
        s = sub.add_parser(nome)
        s.add_argument("video")
        if nome == "editar":
            s.add_argument("--plano")
            s.add_argument("--rapido", action="store_true")
        if nome == "auto":
            s.add_argument("--objetivo", default="anuncio")
    fo = sub.add_parser("folha")
    fo.add_argument("video")
    a = ap.parse_args()
    if a.cmd == "setup":
        print(json.dumps(setup(), ensure_ascii=False, indent=1))
    elif a.cmd == "andamento":
        andamento(Path(a.video))
    elif a.cmd == "transcrever":
        transcrever(Path(a.video))
    elif a.cmd == "auto":
        v = Path(a.video)
        d = pasta_de(v)
        tr = json.loads((d / "palavras.json").read_text(encoding="utf-8")) if (d / "palavras.json").exists() \
            else transcrever(v)
        p = plano_auto(tr, a.objetivo)
        (d / "plano.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(p, ensure_ascii=False, indent=1))
        log(f"Plano: {d / 'plano.json'}")
    elif a.cmd == "editar":
        plano = json.loads(Path(a.plano).read_text(encoding="utf-8")) if a.plano else None
        editar(Path(a.video), plano, rapido=a.rapido)
    elif a.cmd == "versoes":
        print(json.dumps(versoes(Path(a.video)), ensure_ascii=False, indent=1))
    else:
        print(folha(Path(a.video), Path(a.video).with_suffix(".folha.jpg")))


if __name__ == "__main__":
    main()
