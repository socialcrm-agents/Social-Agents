#!/usr/bin/env python3
"""Conta o tempo do roteiro e gera o teleprompter (teleprompter.html) para gravar a VSL bloco a bloco.

  python3 teleprompter.py metodo-sono-leve             tempo por bloco + teleprompter.html
  python3 teleprompter.py metodo-sono-leve --wpm 150   ritmo de fala (palavras por minuto; padrão 140)

Formato do roteiro.md:
  ## Nome do bloco        começa um bloco (grave um bloco por vez)
  frase falada            uma frase por linha
  > nota de direção       para quem grava (não é falada): "olhe para a câmera", "mostre o produto"
  [PAUSA]                 respiro de ~1 s

No teleprompter: espaço = rolar/pausar, + e - = velocidade, M = espelhar (vidro de teleprompter), A/a = tamanho
da letra, ← → = bloco anterior/próximo, R = voltar ao início do bloco. No celular, botões na tela.
Para abrir direto num bloco: teleprompter.html#bloco=3
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from common import VslError, carregar, die, log

PAUSA_S = 1.0


def ler_roteiro(texto: str) -> list[dict]:
    blocos: list[dict] = []
    atual = None
    for linha in texto.splitlines():
        s = linha.strip()
        if s.startswith("# ") and not blocos and atual is None:
            continue                                    # título do documento
        if s.startswith("## "):
            atual = {"nome": s[3:].strip(), "linhas": []}
            blocos.append(atual)
            continue
        if not s or s.startswith("<!--"):
            continue
        if atual is None:
            atual = {"nome": "Abertura", "linhas": []}
            blocos.append(atual)
        if s.startswith(">"):
            atual["linhas"].append({"tipo": "nota", "texto": s.lstrip("> ").strip()})
        elif s.upper() in ("[PAUSA]", "(PAUSA)"):
            atual["linhas"].append({"tipo": "pausa", "texto": ""})
        else:
            s = re.sub(r"^[-*]\s+", "", s)
            s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
            atual["linhas"].append({"tipo": "fala", "texto": s})
    return [b for b in blocos if any(l["tipo"] == "fala" for l in b["linhas"])]


def palavras(b: dict) -> int:
    return sum(len(re.findall(r"\w+", l["texto"])) for l in b["linhas"] if l["tipo"] == "fala")


def duracao(b: dict, wpm: int) -> float:
    return palavras(b) / wpm * 60 + PAUSA_S * sum(l["tipo"] == "pausa" for l in b["linhas"])


def mmss(s: float) -> str:
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


PAGINA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<title>Teleprompter — %TITULO%</title><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#000;color:#fff;height:100%;overflow:hidden;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-user-select:none;user-select:none}
#palco{position:fixed;inset:0;overflow:hidden}
#texto{position:absolute;left:0;right:0;top:0;padding:45vh 7vw 80vh;will-change:transform}
body.espelho #texto{transform-origin:center}
.bloco{margin-bottom:2.2em}
.bloco h2{font-size:.42em;letter-spacing:.14em;text-transform:uppercase;color:#A78BFA;font-weight:800;margin-bottom:.6em;padding-top:.4em;border-top:2px solid #2a2440}
.bloco h2 small{color:#777;font-weight:600;letter-spacing:.06em;margin-left:.6em}
.fala{line-height:1.38;font-weight:650;margin-bottom:.55em}
.nota{font-size:.42em;color:#FBBF24;font-weight:700;margin:.2em 0 1em;letter-spacing:.02em}
.nota:before{content:"▸ "}
.pausa{height:.9em;position:relative}
.pausa:after{content:"· pausa ·";position:absolute;left:0;font-size:.32em;color:#555;letter-spacing:.2em}
#guia{position:fixed;left:0;right:0;top:42vh;height:16vh;pointer-events:none;border-top:2px solid rgba(167,139,250,.55);border-bottom:2px solid rgba(167,139,250,.25);
  background:linear-gradient(180deg,rgba(167,139,250,.08),rgba(167,139,250,0))}
#guia:before{content:"";position:absolute;left:8px;top:-9px;border:8px solid transparent;border-left:12px solid #A78BFA}
#sombra{position:fixed;inset:0;pointer-events:none;background:linear-gradient(180deg,#000 0,rgba(0,0,0,.55) 22vh,rgba(0,0,0,0) 40vh,rgba(0,0,0,0) 62vh,rgba(0,0,0,.7) 85vh,#000)}
#barra{position:fixed;left:0;top:0;height:4px;background:#A78BFA;width:0;z-index:5}
#painel{position:fixed;left:0;right:0;bottom:0;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;align-items:center;padding:10px 10px calc(10px + env(safe-area-inset-bottom));
  background:rgba(12,12,16,.92);border-top:1px solid #222;z-index:6;transition:opacity .3s}
body.rodando #painel{opacity:.12}
body.rodando #painel:hover{opacity:1}
button,select{font:inherit;font-size:15px;font-weight:700;color:#fff;background:#1d1d26;border:1px solid #34343f;border-radius:10px;min-height:44px;min-width:44px;padding:0 14px;cursor:pointer}
button.principal{background:#7C3AED;border-color:#7C3AED;min-width:110px}
button:focus-visible,select:focus-visible{outline:2px solid #A78BFA;outline-offset:2px}
select{max-width:46vw}
#info{font-size:13px;color:#aaa;min-width:120px;text-align:center;font-variant-numeric:tabular-nums}
#ajuda{position:fixed;top:12px;right:12px;font-size:12px;color:#666;z-index:6;text-align:right;line-height:1.5}
@media (max-width:640px){#ajuda{display:none}button,select{font-size:14px;padding:0 10px}}
</style></head><body>
<div id="barra"></div>
<div id="palco"><div id="texto">%BLOCOS%</div></div>
<div id="sombra"></div><div id="guia"></div>
<div id="ajuda">espaço rolar · +/− velocidade · M espelhar · A/a letra · ←/→ bloco · R reinicia bloco</div>
<div id="painel">
  <button id="tocar" class="principal" aria-label="Rolar ou pausar">▶ Rolar</button>
  <button id="menos" aria-label="Mais devagar">−</button><span id="info"></span><button id="mais" aria-label="Mais rápido">+</button>
  <button id="aMenos" aria-label="Letra menor">A−</button><button id="aMais" aria-label="Letra maior">A+</button>
  <button id="espelho" aria-label="Espelhar">⇋</button>
  <select id="blocos" aria-label="Ir para o bloco">%OPCOES%</select>
  <button id="reinicia" aria-label="Reiniciar bloco">↺</button>
</div>
<script>
(function(){
  var WPM=%WPM%, texto=document.getElementById('texto'), body=document.body;
  var blocos=[].slice.call(document.querySelectorAll('.bloco')), sel=document.getElementById('blocos');
  var cfg={vel:1, tam:Math.max(30,Math.min(72,Math.round(window.innerWidth/14))), espelho:false};
  try{var s=JSON.parse(localStorage.getItem('teleprompter-cfg')||'{}'); for(var k in s) cfg[k]=s[k];}catch(e){}
  var y=0, rodando=false, ult=0;
  function salvar(){try{localStorage.setItem('teleprompter-cfg',JSON.stringify(cfg))}catch(e){}}
  function aplicar(){ texto.style.fontSize=cfg.tam+'px'; body.classList.toggle('espelho',cfg.espelho);
    document.getElementById('info').textContent=Math.round(WPM*cfg.vel)+' pal/min · '+cfg.tam+'px'; desenhar(); salvar(); }
  function maxY(){ return Math.max(0, texto.scrollHeight - window.innerHeight*1.25); }
  function desenhar(){ y=Math.max(0,Math.min(y,maxY()));
    texto.style.transform='translateY('+(-y)+'px)'+(cfg.espelho?' scaleX(-1)':'');
    document.getElementById('barra').style.width=(maxY()?100*y/maxY():0)+'%';
    var guia=window.innerHeight*0.42, atual=0;
    blocos.forEach(function(b,i){ if(b.offsetTop - y <= guia+5) atual=i; });
    if(sel.selectedIndex!==atual) sel.selectedIndex=atual; }
  function pxPorSeg(){ var linhaPx=cfg.tam*1.38, palPorLinha=Math.max(3,(texto.clientWidth*0.86)/(cfg.tam*2.9));
    return (WPM*cfg.vel/60)/palPorLinha*linhaPx; }
  function passo(ts){ if(!rodando) return; if(ult) y+=pxPorSeg()*(ts-ult)/1000; ult=ts; desenhar();
    if(y>=maxY()) parar(); else requestAnimationFrame(passo); }
  function tocar(){ rodando=true; ult=0; body.classList.add('rodando'); document.getElementById('tocar').textContent='❚❚ Pausar'; requestAnimationFrame(passo); }
  function parar(){ rodando=false; body.classList.remove('rodando'); document.getElementById('tocar').textContent='▶ Rolar'; }
  function alternar(){ rodando?parar():tocar(); }
  function irBloco(i){ i=Math.max(0,Math.min(blocos.length-1,i)); y=blocos[i].offsetTop - window.innerHeight*0.42; desenhar();
    try{history.replaceState(null,'','#bloco='+(i+1))}catch(e){} }
  function vel(d){ cfg.vel=Math.max(0.3,Math.min(2.5,Math.round((cfg.vel+d)*20)/20)); aplicar(); }
  function tam(d){ var bloco=sel.selectedIndex; cfg.tam=Math.max(20,Math.min(120,cfg.tam+d)); aplicar(); irBloco(bloco); }
  document.getElementById('tocar').onclick=alternar;
  document.getElementById('mais').onclick=function(){vel(0.05)};
  document.getElementById('menos').onclick=function(){vel(-0.05)};
  document.getElementById('aMais').onclick=function(){tam(4)};
  document.getElementById('aMenos').onclick=function(){tam(-4)};
  document.getElementById('espelho').onclick=function(){cfg.espelho=!cfg.espelho; aplicar()};
  document.getElementById('reinicia').onclick=function(){parar(); irBloco(sel.selectedIndex)};
  sel.onchange=function(){parar(); irBloco(sel.selectedIndex)};
  window.addEventListener('keydown',function(e){
    if(e.target.tagName==='SELECT') return;
    var k=e.key;
    if(k===' '){e.preventDefault(); alternar();}
    else if(k==='+'||k==='='||k==='ArrowUp'){e.preventDefault(); vel(0.05);}
    else if(k==='-'||k==='_'||k==='ArrowDown'){e.preventDefault(); vel(-0.05);}
    else if(k==='m'||k==='M'){cfg.espelho=!cfg.espelho; aplicar();}
    else if(k==='A'){tam(4);} else if(k==='a'){tam(-4);}
    else if(k==='ArrowRight'){parar(); irBloco(sel.selectedIndex+1);}
    else if(k==='ArrowLeft'){parar(); irBloco(sel.selectedIndex-1);}
    else if(k==='r'||k==='R'){parar(); irBloco(sel.selectedIndex);}
  });
  var toque=null;
  document.getElementById('palco').addEventListener('touchstart',function(e){toque=e.touches[0].clientY},{passive:true});
  document.getElementById('palco').addEventListener('touchmove',function(e){ if(toque===null) return; var d=toque-e.touches[0].clientY;
    toque=e.touches[0].clientY; y+=d; desenhar(); },{passive:true});
  document.getElementById('palco').addEventListener('touchend',function(){ toque=null; });
  document.getElementById('palco').addEventListener('wheel',function(e){ y+=e.deltaY; desenhar(); },{passive:true});
  window.addEventListener('resize',desenhar);
  aplicar();
  var m=/bloco=(\\d+)/.exec(location.hash); if(m) irBloco(parseInt(m[1],10)-1);
})();
</script></body></html>
"""


def gerar_html(titulo: str, blocos: list[dict], wpm: int) -> str:
    partes, opcoes = [], []
    for i, b in enumerate(blocos, 1):
        dur = mmss(duracao(b, wpm))
        linhas = []
        for l in b["linhas"]:
            if l["tipo"] == "fala":
                linhas.append(f'<p class="fala">{html.escape(l["texto"])}</p>')
            elif l["tipo"] == "nota":
                linhas.append(f'<p class="nota">{html.escape(l["texto"])}</p>')
            else:
                linhas.append('<div class="pausa"></div>')
        partes.append(f'<div class="bloco" id="b{i}"><h2>{i}. {html.escape(b["nome"])}<small>~{dur}</small></h2>'
                      + "".join(linhas) + '</div>')
        opcoes.append(f'<option value="{i}">{i}. {html.escape(b["nome"][:40])} ({dur})</option>')
    return (PAGINA.replace("%TITULO%", html.escape(titulo)).replace("%BLOCOS%", "\n".join(partes))
            .replace("%OPCOES%", "".join(opcoes)).replace("%WPM%", str(int(wpm))))


def main() -> None:
    ap = argparse.ArgumentParser(description="Tempo do roteiro e teleprompter da VSL")
    ap.add_argument("slug")
    ap.add_argument("--dir", help="pasta dos projetos (padrão ./vsl)")
    ap.add_argument("--wpm", type=int, default=140, help="palavras por minuto (padrão 140)")
    ap.add_argument("--roteiro", help="arquivo do roteiro (padrão <projeto>/roteiro.md)")
    a = ap.parse_args()
    try:
        ficha, pasta = carregar(a.slug, a.dir)
    except VslError as e:
        die(str(e))
    arq = Path(a.roteiro) if a.roteiro else pasta / "roteiro.md"
    if not arq.exists():
        die(f"Roteiro não encontrado: {arq}. Escreva o roteiro (## Bloco + uma frase por linha) e rode de novo.")
    blocos = ler_roteiro(arq.read_text(encoding="utf-8"))
    if not blocos:
        die("O roteiro não tem falas. Use '## Nome do bloco' e, embaixo, uma frase por linha.")
    total = 0.0
    log(f"Roteiro: {arq}  (ritmo {a.wpm} palavras/min)\n")
    acum = 0.0
    for i, b in enumerate(blocos, 1):
        d = duracao(b, a.wpm)
        log(f"  {i:2}. {b['nome'][:44]:44} {palavras(b):5} pal  {mmss(d):>6}   (começa em {mmss(acum)})")
        acum += d
        total += d
    soma = sum(palavras(b) for b in blocos)
    log(f"\n  Total: {soma} palavras ≈ {mmss(total)}")
    alvo = float(ficha["vsl"].get("duracao_min") or 0)
    if alvo:
        dif = total / 60 - alvo
        if abs(dif) > max(1.0, alvo * 0.15):
            log(f"  AVISO: a meta é {alvo:g} min; o roteiro está {'longo' if dif > 0 else 'curto'} em "
                f"{abs(dif):.1f} min.")
    # a oferta aparece na página quando o bloco de oferta começa a ser falado
    acum, inicio_oferta = 0.0, None
    for b in blocos:
        if inicio_oferta is None and re.search(r"\b(oferta|stack|o que voc[eê] recebe)\b", b["nome"], re.I):
            inicio_oferta = acum
        acum += duracao(b, a.wpm)
    if inicio_oferta is not None:
        atual = int(ficha["vsl"].get("delay_oferta_s") or 0)
        log(f"  Bloco da oferta começa em {mmss(inicio_oferta)} -> vsl.delay_oferta_s sugerido: {int(inicio_oferta)}"
            + (f" (na ficha: {atual})" if atual else "")
            + "\n  Depois de editar o vídeo, use o segundo real em que a oferta começa.")
    titulo = ficha["produto"].get("nome") or a.slug
    (pasta / "teleprompter.html").write_text(gerar_html(titulo, blocos, a.wpm), encoding="utf-8")
    (pasta / "roteiro_tempos.json").write_text(json.dumps(
        [{"bloco": b["nome"], "palavras": palavras(b), "segundos": round(duracao(b, a.wpm), 1)} for b in blocos],
        ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\nOK: {pasta / 'teleprompter.html'} (abra no navegador; #bloco=N começa num bloco)")


if __name__ == "__main__":
    sys.exit(main())
