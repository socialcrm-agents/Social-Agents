"""Smart Revision Engine — testes com render de verdade (sincronismo, revisão parcial, rollback, equivalência).

Precisam de ffmpeg, Node + Playwright/Chromium e MediaPipe (o mesmo que o editor). Levam alguns minutos, por isso
só rodam com a variável ligada:

  EDITOR_TESTES_RENDER=1 python -m unittest tests/editor_video/test_render_revisao.py -v      (Linux/Mac)
  set EDITOR_TESTES_RENDER=1 && python -m unittest tests\\editor_video\\test_render_revisao.py -v   (Windows)

O vídeo de teste é sintético (gerado pelo ffmpeg): padrão em movimento com FLASH branco e BIPE de 1 kHz nos mesmos
instantes, inclusive exatamente em cima da emenda de dois trechos (8,0 s e 12,0 s). Se imagem e som saírem do lugar
em qualquer ponto, o teste pega.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from array import array
from pathlib import Path

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
import util  # noqa: E402

FPS = 30
EVENTOS = [2.0, 7.0, 8.0, 12.0, 13.5]   # instantes de flash + bipe (8,0 e 12,0 = emendas de trechos)
DUR = 16.5
LIGADO = os.environ.get("EDITOR_TESTES_RENDER") == "1" and shutil.which("ffmpeg") and shutil.which("node")


def ff(*args: str) -> str:
    return subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *args], capture_output=True, text=True,
                          check=True).stdout


def video_sintetico(path: Path) -> None:
    en = "+".join(f"between(t,{t:.3f},{t + 1 / FPS - 0.001:.3f})" for t in EVENTOS)
    beep = "+".join(f"between(t,{t:.3f},{t + 0.08:.3f})" for t in EVENTOS)
    ff("-f", "lavfi", "-i", f"testsrc2=s=540x960:r={FPS}:d={DUR}",
       "-f", "lavfi", "-i", f"aevalsrc='0.6*sin(2*PI*1000*t)*({beep})':s=48000:d={DUR}",
       "-vf", f"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{en}'",
       "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
       str(path))


def luma_por_quadro(video: Path) -> list[float]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-vf", "scale=16:16,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return [sum(raw[i:i + 256]) / 256 for i in range(0, len(raw), 256)]


def bipes(video: Path) -> list[float]:
    """Inícios de bipe (s): energia na banda de 1 kHz em janelas de 5 ms."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-vn", "-af",
                          "bandpass=f=1000:width_type=q:w=8,aresample=8000", "-ac", "1", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    s = array("h", raw)
    win = 40
    rms = [sum(abs(x) for x in s[i:i + win]) / win for i in range(0, len(s) - win, win)]
    pico = max(rms) or 1
    out, ativo = [], False
    for k, v in enumerate(rms):
        if v > 0.35 * pico and not ativo:
            out.append(k * win / 8000)
            ativo = True
        elif v < 0.1 * pico:
            ativo = False
    return out


def md5_quadros(video: Path) -> list[str]:
    txt = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-an", "-vf", "scale=270:480",
                          "-f", "framemd5", "-"], capture_output=True, text=True, check=True).stdout
    return [l.split(",")[-1].strip() for l in txt.splitlines() if l and not l.startswith("#")]


@unittest.skipUnless(LIGADO, "defina EDITOR_TESTES_RENDER=1 (precisa de ffmpeg, Node/Playwright e MediaPipe)")
class RenderRevisao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="ev_render_"))
        clip = cls.dir / "sintetico.mp4"
        video_sintetico(clip)
        cls.proj = cls.dir / "proj"
        r = subprocess.run([util.sys.executable, str(util.SCRIPTS / "run.py"), "new", str(cls.proj), "--clips", str(clip),
                            "--style", "pro_clean", "--sem-cortes", "--cta", "TESTE"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        # transcrição de mentira (o teste não depende do ASR): uma palavra a cada 0,5 s
        words = [{"w": f"palavra{i}" + ("." if i % 6 == 5 else ""), "t0": round(0.2 + i * 0.5, 3),
                  "t1": round(0.55 + i * 0.5, 3), "clip": "c1"} for i in range(int((DUR - 0.8) / 0.5))]
        (cls.proj / "transcript.json").write_text(json.dumps({"backend": "teste", "words": words, "silences": {}}),
                                                  encoding="utf-8")
        p = json.loads((cls.proj / "project.json").read_text(encoding="utf-8"))
        p["overrides"]["motion"] = [
            {"template": "etiqueta", "at": 1.0, "dur": 2.0, "params": {"text": "INICIO"}},
            {"template": "palavra", "at": 5.0, "dur": 1.6, "params": {"text": "SIM."}},
            {"template": "carimbo", "at": 13.0, "dur": 1.6, "params": {"text": "PROMO"}},
        ]
        p["overrides"]["triggers"] = False
        (cls.proj / "project.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        cls.render()

    @classmethod
    def tearDownClass(cls):
        if not os.environ.get("EDITOR_TESTES_MANTER"):
            shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def render(cls, *extra: str, env: dict | None = None) -> dict:
        r = subprocess.run([util.sys.executable, str(util.SCRIPTS / "run.py"), "render", str(cls.proj), *extra],
                           capture_output=True, text=True, env={**os.environ, **(env or {})})
        assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
        v = json.loads((cls.proj / "project.json").read_text(encoding="utf-8"))["version"]
        rev = json.loads((cls.proj / "versions" / f"v{v}" / "revisao.json").read_text(encoding="utf-8")) \
            if (cls.proj / "versions" / f"v{v}" / "revisao.json").exists() else {}
        return {"v": v, "rev": rev, "out": next((cls.proj / "renders").glob(f"v{v}_*.mp4"))}

    def video(self, v: int) -> Path:
        return next((self.proj / "renders").glob(f"v{v}_*.mp4"))

    def test_1_quadros_e_duracao_exatos(self):
        out = self.video(1)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                                          "stream=codec_type,nb_read_frames,duration", "-of", "json", str(out)],
                                         capture_output=True, text=True).stdout)["streams"]
        nv = int(next(s for s in info if s["codec_type"] == "video")["nb_read_frames"])
        da = float(next(s for s in info if s["codec_type"] == "audio")["duration"])
        self.assertEqual(nv, round(DUR * FPS))
        self.assertLess(abs(da - nv / FPS), 1.5 / FPS, "áudio e vídeo com durações diferentes")

    def test_1b_render_de_novo_sem_mudanca_nao_refaz_nada(self):
        antes = md5_quadros(self.video(1))
        res = self.render()
        miss = [f"{i['tipo']}:{i['id']}" for i in res["rev"]["itens"] if i["status"] == "MISS"]
        self.assertEqual(miss, [], "render sem mudança deveria ser 100% cache")
        self.assertEqual(md5_quadros(res["out"]), antes)

    def test_2_sincronismo_imagem_e_som_em_todos_os_eventos(self):
        out = self.video(1)
        luma = luma_por_quadro(out)
        sons = bipes(out)
        for t in EVENTOS:
            q = round(t * FPS)
            janela = range(max(q - 6, 0), min(q + 7, len(luma)))
            flash = max(janela, key=lambda i: luma[i])
            self.assertLessEqual(abs(flash - q), 1, f"flash de {t}s saiu no quadro {flash} (esperado {q})")
            bip = min(sons, key=lambda s: abs(s - t))
            # meio quadro + resolução da medição (5 ms): antes do motor o atraso era de 30-40 ms (filtros sem
            # compensação); agora a cadeia de áudio é calibrada e compensada
            self.assertLess(abs(bip - flash / FPS), 0.5 / FPS + 0.006, f"som e imagem desalinhados em {t}s")

    def test_3_mudar_animacao_entre_12_e_16_so_refaz_o_necessario(self):
        antes = md5_quadros(self.video(1))
        r = subprocess.run([util.sys.executable, str(util.SCRIPTS / "edit.py"), str(self.proj),
                            "--patch", "m3.params.text=NOVO", "--no-render"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = self.render()
        miss = {(i["tipo"], i["id"]) for i in res["rev"]["itens"] if i["status"] == "MISS"}
        self.assertEqual(miss, {("motion", "m3:carimbo"), ("trecho", "012.0-016.0")})
        depois = md5_quadros(res["out"])
        self.assertEqual(len(antes), len(depois))
        fora = [i for i in range(len(antes)) if not 360 <= i < 480 and antes[i] != depois[i]]
        self.assertEqual(fora, [], "quadros fora de 12-16 s mudaram")
        self.assertTrue(any(antes[i] != depois[i] for i in range(360, 480)), "a mudança não apareceu no vídeo")

    def test_4_rollback_volta_igual_e_sem_refazer(self):
        r = subprocess.run([util.sys.executable, str(util.SCRIPTS / "run.py"), "rollback", str(self.proj), "--para", "1"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = self.render()
        miss = [i for i in res["rev"]["itens"] if i["status"] == "MISS"]
        self.assertEqual(miss, [], f"rollback deveria ser 100% cache: {miss}")
        self.assertEqual(md5_quadros(res["out"]), md5_quadros(self.video(1)))

    def test_5_composicao_por_trechos_equivale_a_classica(self):
        res = self.render(env={"EDITOR_COMPOSICAO": "inteira"})
        a, b = self.video(1), res["out"]
        log = Path(tempfile.mkdtemp()) / "psnr.log"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(a), "-i", str(b), "-lavfi",
                        f"[0:v][1:v]psnr=stats_file='{log.as_posix()}'", "-f", "null", "-"], check=True)
        vals = []
        for line in log.read_text().splitlines():
            x = line.split("psnr_avg:")[1].split()[0]
            vals.append(99.0 if x == "inf" else float(x))
        self.assertGreater(min(vals), 35.0, f"trechos diferem da composição clássica (PSNR mínimo {min(vals):.1f})")


if __name__ == "__main__":
    unittest.main()
