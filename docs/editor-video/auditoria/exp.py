"""Experimento de retrabalho: aplica revisões típicas em sequência e mede o que cada uma refaz."""
import json, subprocess, sys, time, hashlib
from pathlib import Path
SK = Path('/home/user/Social-Agents/.claude/skills/editor-video/scripts')
E = Path(sys.argv[1]); OUT = Path(sys.argv[2])

def snap():
    w = E / 'work'
    files = {}
    for p in list(w.glob('motion/clip_*.mov')) + list(w.glob('motion/frames_*')) + [w/'aroll.mkv', w/'mask.mp4', w/'aroll.key']:
        if p.exists(): files[str(p.relative_to(E))] = p.stat().st_mtime
    return files

def run(label, cmd):
    before = snap(); t = time.time()
    p = subprocess.run(cmd, cwd=SK, capture_output=True, text=True)
    dt = time.time() - t; after = snap()
    new = sorted(k for k in after if k not in before); touched = sorted(k for k in after if k in before and after[k] != before[k])
    log = p.stdout + p.stderr
    tempos = next((l.strip() for l in log.splitlines() if 'tempos:' in l), '')
    reuse = [l.strip() for l in log.splitlines() if 'reaproveitad' in l]
    motions = [l.strip() for l in log.splitlines() if l.strip().startswith('motion ') and 'quadros' in l]
    rec = {"rev": label, "segundos": round(dt, 1), "ok": p.returncode == 0, "tempos": tempos, "reaproveitado": reuse,
           "motions_renderizados": len(motions), "arquivos_novos": new, "arquivos_reescritos": touched}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    with OUT.open('a') as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if p.returncode: print(log[-3000:])

py = sys.executable; P = str(E)
run("R0 sem mudança (render de novo)", [py, 'run.py', 'render', P, '--draft'])
run("R1 só legenda maior", [py, 'edit.py', P, '--caption-size', '+10%', '--draft'])
run("R2 só CTA (texto)", [py, 'edit.py', P, '--cta', 'COMPRE AGORA', '--draft'])
run("R3 corta 1 frase no meio", [py, 'edit.py', P, '--cut', 'dá uma olhadinha, um', '--draft'])
run("R4 desfaz o corte (restore)", [py, 'edit.py', P, '--restore', 'dá uma olhadinha, um', '--draft'])
run("R5 velocidade 1.1", [py, 'edit.py', P, '--velocidade', '1.1', '--draft'])
