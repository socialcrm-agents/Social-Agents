"""Mesmo experimento da auditoria, agora com o Smart Revision Engine (+ revisões novas: animação 12-16 s e rollback)."""
import json, subprocess, sys, time
from pathlib import Path
SK = Path('/home/user/Social-Agents/.claude/skills/editor-video/scripts')
E = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.unlink(missing_ok=True)
py = sys.executable; P = str(E)

def run(label, cmd):
    t = time.time(); p = subprocess.run(cmd, cwd=SK, capture_output=True, text=True); dt = time.time() - t
    v = json.loads((E / 'project.json').read_text())['version']
    rev = json.loads((E / 'versions' / f'v{v}' / 'revisao.json').read_text()) if (E / 'versions' / f'v{v}' / 'revisao.json').exists() else {}
    miss = [f"{i['tipo']}:{i['id']}" for i in rev.get('itens', []) if i['status'] == 'MISS']
    tempos = next((l.strip() for l in (p.stdout).splitlines() if 'tempos:' in l), '')
    rec = {"rev": label, "segundos": round(dt, 1), "ok": p.returncode == 0, "versao": v, "resumo": rev.get('resumo'),
           "refeito": miss, "tempos": tempos}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    OUT.open('a').write(json.dumps(rec, ensure_ascii=False) + "\n")
    if p.returncode: print(p.stdout[-2000:], p.stderr[-2000:])
    return v

v0 = run("R0 primeiro render (cache vazio)", [py, 'run.py', 'render', P, '--draft'])
run("R0b render de novo sem mudança", [py, 'run.py', 'render', P, '--draft'])
run("R1 só legenda maior", [py, 'edit.py', P, '--caption-size', '+10%', '--draft'])
run("R2 só CTA (texto)", [py, 'edit.py', P, '--cta', 'COMPRE AGORA', '--draft'])
run("R3 corta 1 frase no meio", [py, 'edit.py', P, '--cut', 'dá uma olhadinha, um', '--draft'])
run("R4 desfaz o corte (restore)", [py, 'edit.py', P, '--restore', 'dá uma olhadinha, um', '--draft'])
tl = json.loads((E / 'timeline.json').read_text())
alvo = max((m for m in tl['motion'] if m['id'].startswith('m')), key=lambda m: m['t0'])
run(f"R6 muda 1 animação ({alvo['id']} {alvo['t0']:.1f}-{alvo['t1']:.1f}s)", [py, 'edit.py', P, '--patch', f"{alvo['id']}.params.EXTRA=1", '--draft'])
run(f"R7 rollback para v{v0}", [py, 'run.py', 'rollback', P, '--para', str(v0), '--render', '--draft'])
run("R5 velocidade 1.1", [py, 'edit.py', P, '--velocidade', '1.1', '--draft'])
