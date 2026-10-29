#!/usr/bin/env python3
"""Biblioteca de OBJETOS 3D (assets/motion/objetos/*.js) usada pelo template objeto_cinema.

Qualquer objeto que a pessoa falar ou pedir vira 3D: se já existe na biblioteca, usa; se não existe, a IA modela
um arquivo novo com o kit (assets/motion/lib/objetos.js), confere a prévia e ele fica guardado para sempre.

  python3 objetos.py listar                       nomes e sinônimos de tudo que existe
  python3 objetos.py achar "texto falado"         quais objetos da biblioteca aparecem no texto (com a palavra)
  python3 objetos.py novo <nome> [sinonimos...]   cria o arquivo-modelo para a IA preencher
  python3 objetos.py previa <nome> [--saida x.png] renderiza 4 quadros (entrada → pronto) para conferir
  python3 objetos.py indice                       refaz objetos/indice.json (sinônimo -> arquivo)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

SK = Path(__file__).resolve().parents[1]
MOTION = SK / "assets" / "motion"
PASTA = MOTION / "objetos"


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def ler_info(arq: Path) -> dict:
    txt = arq.read_text(encoding="utf-8")
    nome = re.search(r"nome:\s*'([^']+)'", txt)
    sin = re.search(r"sinonimos:\s*\[([^\]]*)\]", txt)
    desc = next((ln.strip("/ ").strip() for ln in txt.splitlines() if ln.startswith("//")), "")
    return {"arquivo": arq.stem, "nome": nome.group(1) if nome else arq.stem,
            "sinonimos": re.findall(r"'([^']+)'", sin.group(1)) if sin else [], "descricao": desc}


def todos() -> list[dict]:
    return [ler_info(a) for a in sorted(PASTA.glob("*.js"))]


def indice() -> dict:
    ind = {}
    for o in todos():
        for termo in [o["arquivo"], o["nome"], *o["sinonimos"]]:
            ind.setdefault(slug(termo), o["arquivo"])
    (PASTA / "indice.json").write_text(json.dumps(ind, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return ind


def achar(texto: str) -> list[dict]:
    t = " " + slug(texto).replace("_", " ") + " "
    out = []
    for o in todos():
        for termo in sorted({o["nome"], *o["sinonimos"]}, key=len, reverse=True):
            s = slug(termo).replace("_", " ")
            if s and re.search(rf"\b{re.escape(s)}\w{{0,2}}\b", t):   # aceita plural/flexão curta
                out.append({**o, "palavra": termo})
                break
    return out


MODELO = """// {desc}
export const info = {{ nome: '{nome}', sinonimos: [{sin}], cor: '#FFC83D', entrada: 'monta' }};
export default function criar(T, k) {{
  const g = new T.Group();
  // Cada g.add(...) é UMA PEÇA (é o que voa e se encaixa na entrada "monta" e se separa no "explodir").
  // Formas: k.caixa(w,h,d,raio) k.cilindro(rt,rb,h) k.esfera(r) k.cone(r,h) k.anel(r,tubo) k.capsula(r,h)
  //         k.torno([[raio,altura],...]) k.tubo([[x,y,z],...], raio) k.extrusao([[x,y],...], espessura)
  // Materiais: k.fosco(cor) k.plastico(cor) k.metal(cor) k.ouro() k.prata() k.madeira(cor) k.tecido(cor)
  //            k.vidro(cor) k.borracha(cor) k.emissivo(cor, intensidade) k.holograma(cor)
  // Peça: k.malha(geo, mat, [x,y,z], [rx,ry,rz], escala) · várias malhas numa peça: k.peca(m1, m2, ...)
  // Escala livre (o template normaliza). Use proporções reais (em metros) e cantos arredondados.
  g.add(k.malha(k.caixa(1, 1, 1, 0.08), k.plastico('#e5443b')));
  return g;
}}
// opcional: animação contínua depois da entrada (ex.: ponteiro girando, chama tremendo)
// export function animar(g, k, s, t) {{ }}
"""


def novo(nome: str, sinonimos: list[str]) -> Path:
    arq = PASTA / f"{slug(nome)}.js"
    if arq.exists():
        sys.exit(f"Já existe: {arq}")
    sin = ", ".join(f"'{s}'" for s in [slug(nome).replace("_", " "), *sinonimos] if s != nome)
    arq.write_text(MODELO.format(nome=nome, sin=sin, desc=f"{nome} (descreva em 1 linha como ele é)"), encoding="utf-8")
    indice()
    return arq


def previa(nome: str, saida: Path | None = None, params: dict | None = None) -> Path:
    ind = indice()
    arquivo = ind.get(slug(nome), slug(nome))
    if not (PASTA / f"{arquivo}.js").exists():
        sys.exit(f"Não existe na biblioteca: {nome} (crie com: objetos.py novo {nome})")
    saida = saida or Path(tempfile.gettempdir()) / f"previa_{arquivo}.png"
    tmp = Path(tempfile.mkdtemp(prefix="obj_"))
    (tmp / "work").mkdir()
    job = {"page": "/templates/objeto_cinema.html", "out": str(tmp / "o.mov"), "w": 1080, "h": 1920, "fps": 30,
           "duration": 2.6, "params": {"objeto": arquivo, "at": 0.05, "y": 0.5, "size": 0.42, **(params or {})},
           "opaque": False, "webgl": True,
           "roots": {"/": str(MOTION), "/fonts/": str(SK / "assets" / "fonts"), "/work/": str(tmp / "work")}}
    (tmp / "job.json").write_text(json.dumps(job))
    r = subprocess.run(["node", str(SK / "scripts" / "motion_render.mjs"), str(tmp / "job.json")],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("Erro no render do objeto (confira o .js):\n" + r.stderr[-1500:])
    quadros = []
    for i, t in enumerate((0.25, 0.6, 1.2, 2.0)):
        f = tmp / f"q{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x2a2f3a:s=1080x1920",
                        "-ss", str(t), "-i", str(tmp / "o.mov"), "-filter_complex",
                        "[0][1]overlay,crop=1080:1080:0:420,scale=360:360", "-frames:v", "1", str(f)], check=True)
        quadros.append(f)
    args = sum([["-i", str(f)] for f in quadros], [])
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", "hstack=4", str(saida)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return saida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar")
    sub.add_parser("indice")
    a = sub.add_parser("achar"); a.add_argument("texto")
    n = sub.add_parser("novo"); n.add_argument("nome"); n.add_argument("sinonimos", nargs="*")
    pv = sub.add_parser("previa"); pv.add_argument("nome"); pv.add_argument("--saida")
    args = ap.parse_args()
    if args.cmd == "listar":
        for o in todos():
            print(f"{o['arquivo']:<12} {o['nome']:<12} {', '.join(o['sinonimos'])}")
    elif args.cmd == "indice":
        print(f"{len(indice())} termos")
    elif args.cmd == "achar":
        print(json.dumps(achar(args.texto), ensure_ascii=False, indent=1))
    elif args.cmd == "novo":
        print(novo(args.nome, args.sinonimos))
    elif args.cmd == "previa":
        print(previa(args.nome, Path(args.saida) if args.saida else None))


if __name__ == "__main__":
    main()
