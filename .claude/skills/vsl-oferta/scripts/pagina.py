#!/usr/bin/env python3
"""Gera a página de vendas da VSL (pagina.html): um arquivo só, sem dependências, pronto para subir.

  python3 pagina.py metodo-sono-leve               página final (tira o marcador [HIPÓTESE] e avisa)
  python3 pagina.py metodo-sono-leve --rascunho    marca em amarelo o que ainda é hipótese
  python3 pagina.py metodo-sono-leve --sem-delay   oferta aparece direto (sem esperar o vídeo)

Estrutura: barra de aviso -> headline -> subheadline -> aviso de play -> player -> (oferta escondida até
vsl.delay_oferta_s segundos) -> o que leva, stack com valores, bônus, preço com ancoragem, botão, garantia, provas,
para quem é, autor, perguntas, chamada final, rodapé. Página fechada: todo botão vai para produto.checkout_url.
Para conferir a oferta sem esperar: abra pagina.html?ver=1
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from common import HIPOTESE, VslError, carregar, die, log, parcela, parcelado, reais


class Texto:
    """Escapa todo texto da ficha e trata o marcador [HIPÓTESE] (amarelo no rascunho; removido na final)."""

    def __init__(self, rascunho: bool):
        self.rascunho = rascunho
        self.achados: list[str] = []

    def __call__(self, s, destaque: bool = False) -> str:
        """destaque=True: *trecho* vira <em> (cor de destaque) — usado nos títulos."""
        s = "" if s is None else str(s)
        bruto = s.strip()
        hip = bruto.startswith(HIPOTESE)
        if hip:
            bruto = bruto[len(HIPOTESE):].strip()
            self.achados.append(bruto[:70])
        out = html.escape(bruto if hip else s)
        if destaque:
            out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
        return f'<mark class="hip">{out}</mark>' if hip and self.rascunho else out


# ---------------------------------------------------------------- player

def player(embed: str, formato: str) -> str:
    e = (embed or "").strip()
    vertical = formato == "9:16"
    cls = "player vertical" if vertical else "player"
    if not e:
        return (f'<div class="{cls} vazio"><div><b>Seu vídeo entra aqui</b><span>Cole o código do player (YouTube, '
                f'Vimeo, Panda, VTurb) ou o link do Google Drive em <code>vsl.embed</code> e gere de novo.</span>'
                f'</div></div>')
    if re.search(r"<(iframe|script|div|video|vturb|smartplayer)", e, re.I):
        return f'<div class="{cls} codigo">{e}</div>'
    src = None
    if m := re.search(r"(?:youtu\.be/|v=|/embed/|/shorts/|/live/)([\w-]{11})", e):
        src = f"https://www.youtube.com/embed/{m.group(1)}?rel=0&modestbranding=1&playsinline=1"
        if "/shorts/" in e and not formato:
            cls = "player vertical"
    elif m := re.search(r"vimeo\.com/(?:video/)?(\d+)", e):
        src = f"https://player.vimeo.com/video/{m.group(1)}"
    elif m := re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=\w+&)?id=)([\w-]{20,})", e):
        src = f"https://drive.google.com/file/d/{m.group(1)}/preview"
    elif re.search(r"\.(mp4|webm|m3u8)(\?|$)", e, re.I):
        return (f'<div class="{cls}"><video src="{html.escape(e)}" controls playsinline preload="metadata">'
                f'</video></div>')
    if not src:
        raise VslError(f"Não reconheci o vídeo em vsl.embed: '{e[:80]}'. Use o código de incorporação do player ou "
                       f"um link do YouTube, Vimeo ou Google Drive.")
    return (f'<div class="{cls}"><iframe src="{html.escape(src)}" title="Vídeo de apresentação" '
            f'allow="autoplay; fullscreen; picture-in-picture; encrypted-media" allowfullscreen loading="eager">'
            f'</iframe></div>')


# ---------------------------------------------------------------- cores

def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(h: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def texto_sobre(cor: str) -> str:
    """Preto ou branco, o que contrastar mais com a cor de fundo do botão."""
    l = _lum(cor)
    return "#0B0B0F" if (l + 0.05) / 0.05 > 1.05 / (l + 0.05) else "#FFFFFF"


def cor_valida(c: str, padrao: str) -> str:
    return c if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", c) else padrao


# ---------------------------------------------------------------- página

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{background:var(--fundo);color:var(--texto);font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  font-size:1.0625rem;line-height:1.6;-webkit-font-smoothing:antialiased}
img{max-width:100%;display:block}
.wrap{width:100%;max-width:760px;margin:0 auto;padding:0 20px}
.estreito{max-width:640px}
.rascunho{background:#FDE047;color:#111;text-align:center;font-weight:800;font-size:.85rem;padding:8px 12px;letter-spacing:.02em}
mark.hip{background:#FDE047;color:#111;border-radius:4px;padding:0 3px;box-decoration-break:clone;-webkit-box-decoration-break:clone}
.aviso{background:var(--cor);color:var(--cor-txt);text-align:center;font-weight:700;font-size:.875rem;padding:10px 16px;line-height:1.35}
header.topo{padding:36px 0 8px;text-align:center}
.selo-topo{display:inline-block;font-size:.75rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--cor-claro);
  border:1px solid color-mix(in srgb,var(--cor) 55%,transparent);background:color-mix(in srgb,var(--cor) 14%,transparent);
  padding:6px 14px;border-radius:999px;margin-bottom:18px}
h1{font-size:clamp(1.75rem,6.4vw,2.75rem);line-height:1.12;font-weight:850;letter-spacing:-.02em;text-wrap:balance}
h1 em,h2 em{font-style:normal;color:var(--cor-claro)}
.sub{margin:16px auto 0;max-width:600px;font-size:clamp(1.05rem,3.6vw,1.25rem);color:var(--suave);text-wrap:pretty}
.play{margin:22px auto 14px;display:flex;text-align:center;align-items:center;justify-content:center;gap:8px;font-weight:700;font-size:.95rem;color:var(--texto)}
.play .ponto{width:10px;height:10px;border-radius:50%;background:#EF4444;box-shadow:0 0 0 0 rgba(239,68,68,.7);animation:pulso 1.6s infinite}
@keyframes pulso{70%{box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}}
.player{position:relative;width:100%;aspect-ratio:16/9;border-radius:16px;overflow:hidden;background:#000;
  box-shadow:0 0 0 1px var(--linha2),0 30px 80px -20px color-mix(in srgb,var(--cor) 45%,transparent)}
.player.vertical{aspect-ratio:9/16;max-width:400px;margin:0 auto}
.player iframe,.player video{position:absolute;inset:0;width:100%;height:100%;border:0}
.player.codigo{aspect-ratio:auto;background:transparent;box-shadow:none}
.player.vazio{display:grid;place-items:center;text-align:center;padding:24px;background:repeating-linear-gradient(135deg,#15151d 0 14px,#191922 14px 28px);
  border:2px dashed color-mix(in srgb,var(--cor) 60%,transparent)}
.player.vazio b{display:block;font-size:1.25rem;margin-bottom:6px}
.player.vazio span{display:block;color:var(--suave);font-size:.9rem;max-width:420px}
.player.vazio code{background:var(--linha2);padding:1px 6px;border-radius:4px}
.espera{text-align:center;color:var(--suave);font-size:.85rem;margin:14px 0 40px}
#oferta[hidden]{display:none}
#oferta{animation:surge .7s ease both}
@keyframes surge{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
section{padding:44px 0}
section+section{border-top:1px solid var(--linha)}
h2{font-size:clamp(1.5rem,5.2vw,2.1rem);line-height:1.18;font-weight:800;letter-spacing:-.015em;text-align:center;margin-bottom:24px;text-wrap:balance}
.rotulo{display:block;text-align:center;font-size:.75rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:var(--cor-claro);margin-bottom:10px}
.lista{list-style:none;display:grid;gap:12px}
.lista li{display:flex;gap:12px;align-items:flex-start;background:var(--cartao);border:1px solid var(--linha);border-radius:14px;padding:14px 16px}
.ok{flex:none;width:24px;height:24px;border-radius:50%;background:var(--cor2);color:var(--cor2-txt);display:grid;place-items:center;font-size:.8rem;font-weight:900;margin-top:2px}
.nao{background:#3a1c22;color:#FCA5A5}
.stack{background:var(--cartao);border:1px solid var(--linha2);border-radius:20px;overflow:hidden}
.item{display:flex;justify-content:space-between;gap:16px;padding:18px 20px;border-bottom:1px solid var(--linha)}
.item b{display:block;font-size:1.02rem;line-height:1.35}
.item small{display:block;color:var(--suave);font-size:.9rem;margin-top:4px;line-height:1.45}
.item .val{flex:none;color:var(--suave);text-decoration:line-through;font-variant-numeric:tabular-nums;white-space:nowrap;font-size:.95rem}
.item.bonus{background:color-mix(in srgb,var(--cor) 9%,transparent)}
.tag{display:inline-block;font-size:.68rem;font-weight:900;letter-spacing:.12em;color:var(--cor-txt);background:var(--cor);padding:3px 8px;border-radius:6px;margin-bottom:6px}
.total{display:flex;justify-content:space-between;padding:16px 20px;font-weight:700;color:var(--suave)}
.total s{font-variant-numeric:tabular-nums}
.preco{margin:28px auto 0;max-width:520px;text-align:center;background:linear-gradient(180deg,color-mix(in srgb,var(--cor) 22%,var(--cartao)),var(--cartao));
  border:1px solid color-mix(in srgb,var(--cor) 50%,transparent);border-radius:24px;padding:28px 20px 24px}
.preco .de{color:var(--suave);font-size:1rem}
.preco .de s{color:var(--suave)}
.preco .por{font-size:.95rem;margin-top:6px;color:var(--texto)}
.preco .parc{font-size:clamp(2.4rem,11vw,3.4rem);font-weight:900;line-height:1.05;letter-spacing:-.03em;margin:6px 0 4px;font-variant-numeric:tabular-nums}
.preco .vista{color:var(--suave);font-size:1rem;margin-bottom:20px}
.cta{display:flex;align-items:center;justify-content:center;width:100%;min-height:60px;padding:16px 22px;border-radius:14px;border:0;
  background:var(--cor2);color:var(--cor2-txt);font-weight:900;font-size:1.08rem;letter-spacing:.02em;text-decoration:none;text-align:center;line-height:1.25;
  box-shadow:0 12px 30px -8px color-mix(in srgb,var(--cor2) 70%,transparent),inset 0 -3px 0 rgba(0,0,0,.18);transition:transform .15s}
.cta:hover{transform:translateY(-2px)}
.cta:focus-visible{outline:3px solid var(--texto);outline-offset:3px}
.seguro{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;margin-top:14px;color:var(--suave);font-size:.8rem}
.garantia{display:flex;gap:22px;align-items:center;background:var(--cartao);border:1px solid var(--linha2);border-radius:20px;padding:24px}
.selo{flex:none;width:112px;height:112px;border-radius:50%;display:grid;place-items:center;text-align:center;color:var(--cor-txt);
  background:radial-gradient(circle at 50% 35%,color-mix(in srgb,var(--cor) 70%,#fff),var(--cor));
  box-shadow:0 0 0 6px var(--fundo),0 0 0 8px var(--cor),0 14px 30px -10px var(--cor);position:relative}
.selo:before{content:"";position:absolute;inset:7px;border-radius:50%;border:2px dashed color-mix(in srgb,var(--cor-txt) 55%,transparent)}
.selo b{display:block;font-size:2.1rem;line-height:1;font-weight:900}
.selo span{display:block;font-size:.62rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.garantia h3{font-size:1.2rem;margin-bottom:6px}
.garantia p{color:var(--suave);font-size:.98rem}
.provas{display:grid;gap:14px}
.prova{background:var(--cartao);border:1px solid var(--linha);border-radius:16px;padding:20px}
.prova p{font-size:1rem}
.prova p:before{content:"“";font-family:Georgia,"Times New Roman","DejaVu Serif",serif;font-size:2.4rem;line-height:0;vertical-align:-.42em;margin-right:4px;color:var(--cor-claro);font-weight:700}
.prova.dado{text-align:center;border-color:color-mix(in srgb,var(--cor) 45%,transparent)}
.prova.dado p{font-size:1.1rem;font-weight:700}
.prova.dado p:before{content:none}
.prova.dado .quem{justify-content:center}
.prova .quem{margin-top:12px;display:flex;align-items:center;gap:10px;color:var(--suave);font-size:.88rem;font-weight:600}
.prova .quem i{width:34px;height:34px;border-radius:50%;background:var(--cor);color:var(--cor-txt);display:grid;place-items:center;font-style:normal;font-weight:800}
.prova img{border-radius:10px;margin-bottom:12px;width:100%}
.estrelas{color:#FBBF24;letter-spacing:2px;font-size:.9rem;margin-bottom:6px}
.duas{display:grid;gap:16px}
.caixa{background:var(--cartao);border:1px solid var(--linha);border-radius:18px;padding:20px}
.caixa h3{font-size:1.05rem;margin-bottom:12px}
.caixa ul{list-style:none;display:grid;gap:10px}
.caixa li{display:flex;gap:10px;align-items:flex-start;font-size:.98rem}
.autor{display:flex;gap:20px;align-items:center}
.autor img,.autor .avatar{flex:none;width:96px;height:96px;border-radius:50%;object-fit:cover;border:3px solid var(--cor)}
.autor .avatar{display:grid;place-items:center;background:var(--cartao);font-size:2rem;font-weight:900;color:var(--cor-claro)}
.autor h3{font-size:1.2rem}
.autor .cred{color:var(--cor-claro);font-size:.9rem;font-weight:700;margin-bottom:8px}
.autor p{color:var(--suave);font-size:.98rem}
details{background:var(--cartao);border:1px solid var(--linha);border-radius:14px;margin-bottom:10px}
summary{cursor:pointer;list-style:none;padding:16px 48px 16px 18px;font-weight:700;position:relative;min-height:44px}
summary::-webkit-details-marker{display:none}
summary:after{content:"+";position:absolute;right:18px;top:50%;transform:translateY(-50%);font-size:1.4rem;color:var(--cor-claro);font-weight:400}
details[open] summary:after{content:"–"}
details p{padding:0 18px 18px;color:var(--suave)}
.final{text-align:center}
.final p{color:var(--suave);max-width:520px;margin:0 auto 22px}
footer{padding:32px 0 120px;text-align:center;color:var(--suave);font-size:.78rem;line-height:1.6;border-top:1px solid var(--linha)}
.fixo{position:fixed;left:0;right:0;bottom:0;padding:10px 14px calc(10px + env(safe-area-inset-bottom));background:color-mix(in srgb,var(--fundo) 88%,transparent);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-top:1px solid var(--linha2);display:flex;gap:12px;align-items:center;
  transform:translateY(110%);visibility:hidden;transition:transform .35s ease,visibility .35s;z-index:20}
.fixo.on{transform:none;visibility:visible}
.fixo .mini{flex:none;font-size:.78rem;line-height:1.25;color:var(--suave)}
.fixo .mini b{display:block;color:var(--texto);font-size:.98rem}
.fixo .cta{min-height:52px;font-size:.95rem;padding:12px 16px}
@media (min-width:768px){
  header.topo{padding-top:56px}
  section{padding:64px 0}
  .duas{grid-template-columns:1fr 1fr}
  .provas{grid-template-columns:1fr 1fr}
  .fixo{display:none}
  footer{padding-bottom:40px}
}
@media (max-width:420px){.garantia,.autor{flex-direction:column;text-align:center}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

JS = """
(function(){
  var D=%DELAY%, chave='vsl-oferta-'+%SLUG%;
  var of=document.getElementById('oferta'), fixo=document.getElementById('fixo'), espera=document.getElementById('espera');
  function mostrar(){ if(!of.hidden) return; of.hidden=false; if(espera) espera.remove();
    try{localStorage.setItem(chave,'1')}catch(e){}
    if(fixo){ var alvo=document.getElementById('preco');
      window.addEventListener('scroll',function(){ var r=alvo.getBoundingClientRect();
        fixo.classList.toggle('on', r.bottom<0 || r.top>window.innerHeight*1.2); },{passive:true}); } }
  var ja=false; try{ja=localStorage.getItem(chave)==='1'}catch(e){}
  if(D<=0 || ja || /[?&]ver=1/.test(location.search)) mostrar(); else setTimeout(mostrar, D*1000);
})();
"""


def montar(ficha: dict, rascunho: bool, sem_delay: bool) -> tuple[str, list[str]]:
    t = Texto(rascunho)
    pr, of, pg, au, mk = ficha["produto"], ficha["oferta"], ficha["pagina"], ficha["autor"], ficha["marca"]
    url = pr.get("checkout_url") or "#"
    href = html.escape(url)
    botao = t(pg.get("chamada_botao") or "QUERO COMEÇAR AGORA")

    def cta(txt: str = "") -> str:
        return f'<a class="cta" href="{href}" rel="noopener">{txt or botao}</a>'

    def li(itens, nao=False) -> str:
        return "".join(f'<li><span class="ok{" nao" if nao else ""}" aria-hidden="true">{"✕" if nao else "✓"}</span>'
                       f'<span>{t(x)}</span></li>' for x in itens if x)

    cor = cor_valida(mk.get("cor"), "#7C5CFF")
    cor2 = cor_valida(mk.get("cor2"), "#22C55E")
    fundo = cor_valida(mk.get("fundo"), "#0B0B12")
    texto = cor_valida(mk.get("texto"), "#F5F5F7")
    claro = _lum(fundo) > 0.4
    # tom do accent legível sobre o fundo (texto colorido); em fundo escuro clareia, em claro escurece
    cor_claro = f"color-mix(in srgb,{cor} 62%,{'#000' if claro else '#fff'})"
    cartao = f"color-mix(in srgb,{fundo} {'94%,#000' if claro else '90%,#fff'})"
    suave = f"color-mix(in srgb,{texto} 72%,{fundo})"
    vars_css = (f":root{{--cor:{cor};--cor-txt:{texto_sobre(cor)};--cor2:{cor2};--cor2-txt:{texto_sobre(cor2)};"
                f"--fundo:{fundo};--texto:{texto};--cor-claro:{cor_claro};--cartao:{cartao};--suave:{suave};"
                f"--linha:{'rgba(0,0,0,.08)' if claro else 'rgba(255,255,255,.07)'};"
                f"--linha2:{'rgba(0,0,0,.12)' if claro else 'rgba(255,255,255,.09)'}}}")
    if mk.get("fonte") and mk["fonte"] != "system":
        vars_css += f'body{{font-family:"{html.escape(mk["fonte"])}",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}'

    n, vp = parcela(pr)
    preco = pr.get("preco") or 0
    ancora = pr.get("preco_ancora") or 0
    stack = [s for s in of.get("stack") or [] if s.get("item")]
    bonus = [b for b in of.get("bonus") or [] if b.get("nome")]
    total = sum(float(s.get("valor") or 0) for s in stack) + sum(float(b.get("valor") or 0) for b in bonus)
    dias = pr.get("garantia_dias") or 0
    delay = 0 if sem_delay else int(ficha["vsl"].get("delay_oferta_s") or 0)

    p: list[str] = []
    if rascunho:
        p.append('<div class="rascunho">RASCUNHO — revise os trechos amarelos antes de publicar</div>')
    if of.get("escassez"):
        p.append(f'<div class="aviso">{t(of["escassez"])}</div>')
    p.append('<header class="topo"><div class="wrap">')
    if pr.get("nome"):
        p.append(f'<div class="selo-topo">{t(pr["nome"])}</div>')
    p.append(f'<h1>{t(pg.get("headline") or of.get("promessa") or pr.get("nome"), True)}</h1>')
    if pg.get("subheadline"):
        p.append(f'<p class="sub">{t(pg["subheadline"])}</p>')
    if pg.get("aviso_play"):
        # o ponto vermelho piscando só entra se o aviso não começar com emoji próprio (ex.: ⚠️)
        ponto = '<span class="ponto" aria-hidden="true"></span>' if pg["aviso_play"].strip()[:1].isalnum() else ""
        p.append(f'<p class="play">{ponto}{t(pg["aviso_play"])}</p>')
    p.append(player(ficha["vsl"].get("embed", ""), ficha["vsl"].get("formato", "")))
    if delay > 0:
        p.append('<p class="espera" id="espera">A oferta aparece logo abaixo durante o vídeo. Assista com o som '
                 'ligado.</p>')
    p.append('</div></header>')

    p.append(f'<main id="oferta"{" hidden" if delay > 0 else ""}>')
    if pg.get("bullets"):
        tit = f"Dentro do {t(pr['nome'])} você vai ter" if pr.get("nome") else "O que você leva"
        p.append(f'<section><div class="wrap estreito"><span class="rotulo">O que você vai conseguir</span>'
                 f'<h2>{tit}</h2><ul class="lista">{li(pg["bullets"])}</ul></div></section>')

    p.append('<section><div class="wrap estreito"><span class="rotulo">Tudo o que você recebe</span>'
             '<h2>Veja tudo o que está incluído</h2>')
    if stack or bonus:
        p.append('<div class="stack">')
        for s in stack:
            val = f'<span class="val">{reais(s["valor"])}</span>' if s.get("valor") else ""
            desc = f'<small>{t(s["descricao"])}</small>' if s.get("descricao") else ""
            p.append(f'<div class="item"><div><b>{t(s["item"])}</b>{desc}</div>{val}</div>')
        for i, b in enumerate(bonus, 1):
            val = f'<span class="val">{reais(b["valor"])}</span>' if b.get("valor") else ""
            desc = f'<small>{t(b["descricao"])}</small>' if b.get("descricao") else ""
            p.append(f'<div class="item bonus"><div><span class="tag">BÔNUS {i}</span><b>{t(b["nome"])}</b>{desc}'
                     f'</div>{val}</div>')
        if total:
            p.append(f'<div class="total"><span>Valor total</span><s>{reais(total)}</s></div>')
        p.append('</div>')
    p.append('<div class="preco" id="preco">')
    if ancora and ancora > preco:
        p.append(f'<div class="de">De <s>{reais(ancora)}</s></div>')
    elif total and total > preco:
        p.append(f'<div class="de">Tudo isso vale <s>{reais(total)}</s></div>')
    p.append('<div class="por">Hoje, por apenas</div>')
    if n > 1 and vp:
        p.append(f'<div class="parc">{n}x {reais(vp, centavos=True)}</div>')
        p.append(f'<div class="vista">ou {reais(preco)} à vista</div>')
    else:
        p.append(f'<div class="parc">{reais(preco)}</div><div class="vista">pagamento único</div>')
    p.append(cta())
    p.append('<div class="seguro"><span>🔒 Compra 100% segura</span><span>⚡ Acesso imediato</span>'
             + (f'<span>✓ Garantia de {dias} dias</span>' if dias else "") + '</div></div></div></section>')

    if dias:
        gtxt = pr.get("garantia_texto") or (f"Se em {dias} dias você achar que não é para você, é só pedir o "
                                            f"reembolso. Devolvemos 100% do valor, sem perguntas.")
        p.append(f'<section><div class="wrap estreito"><div class="garantia"><div class="selo"><div><b>{dias}</b>'
                 f'<span>dias de<br>garantia</span></div></div><div><h3>Risco zero para você</h3><p>{t(gtxt)}</p>'
                 f'</div></div></div></section>')

    provas = [x for x in ficha.get("provas") or [] if x.get("texto") or x.get("imagem")]
    if provas:
        p.append('<section><div class="wrap"><span class="rotulo">Quem já fez</span>'
                 '<h2>O que dizem os alunos</h2><div class="provas">')
        for x in provas:
            nome = x.get("nome") or ""
            img = f'<img src="{html.escape(x["imagem"])}" alt="Depoimento de {html.escape(nome)}" loading="lazy">' \
                if x.get("imagem") else ""
            txt = f'<p>{t(x["texto"])}</p>' if x.get("texto") else ""
            ini = html.escape((nome.strip()[:1] or "★").upper())
            quem = f'<div class="quem"><i>{ini}</i>{t(nome)}</div>' if nome else ""
            if x.get("tipo") in ("número", "numero", "dado"):
                p.append(f'<div class="prova dado">{img}{txt}<div class="quem">{t(nome)}</div></div>')
            else:
                p.append(f'<div class="prova">{img}<div class="estrelas" aria-label="5 estrelas">★★★★★</div>{txt}'
                         f'{quem}</div>')
        p.append('</div></div></section>')

    if pg.get("para_quem") or pg.get("nao_para_quem"):
        p.append('<section><div class="wrap"><h2>Isso é para você?</h2><div class="duas">')
        if pg.get("para_quem"):
            p.append(f'<div class="caixa"><h3>É para você se…</h3><ul>{li(pg["para_quem"])}</ul></div>')
        if pg.get("nao_para_quem"):
            p.append(f'<div class="caixa"><h3>Não é para você se…</h3><ul>{li(pg["nao_para_quem"], True)}</ul></div>')
        p.append('</div></div></section>')

    if au.get("nome"):
        foto = (f'<img src="{html.escape(au["foto"])}" alt="{html.escape(au["nome"])}">' if au.get("foto")
                else f'<div class="avatar" aria-hidden="true">{html.escape(au["nome"].strip()[:1].upper())}</div>')
        cred = f'<div class="cred">{t(au["credencial"])}</div>' if au.get("credencial") else ""
        hist = f'<p>{t(au["historia"])}</p>' if au.get("historia") else ""
        p.append(f'<section><div class="wrap estreito"><span class="rotulo">Quem vai te guiar</span>'
                 f'<div class="autor">{foto}<div><h3>{t(au["nome"])}</h3>{cred}{hist}</div></div></div></section>')

    faq = [f for f in ficha.get("faq") or [] if f.get("p")]
    if faq:
        p.append('<section><div class="wrap estreito"><h2>Perguntas frequentes</h2>')
        p += [f'<details><summary>{t(f["p"])}</summary><p>{t(f.get("r"))}</p></details>' for f in faq]
        p.append('</div></section>')

    p.append(f'<section class="final"><div class="wrap estreito"><h2>{t(of.get("promessa") or pr.get("nome"), True)}</h2>'
             f'<p>Garanta agora por {html.escape(parcelado(pr))}'
             + (f' com {dias} dias de garantia' if dias else "") + f'.</p>{cta()}</div></section>')
    p.append('</main>')
    rod = t(pg.get("rodape")) if pg.get("rodape") else ""
    p.append(f'<footer><div class="wrap">{rod}{"<br>" if rod else ""}Este site não é afiliado ao Facebook, Google ou '
             f'TikTok. Resultados variam de pessoa para pessoa.</div></footer>')
    p.append(f'<div class="fixo" id="fixo"><div class="mini">Hoje por<b>{html.escape(parcelado(pr))}</b></div>'
             f'{cta()}</div>')

    titulo = html.escape(re.sub(r"\s+", " ", (pg.get("headline") or pr.get("nome") or "Oferta")
                                .replace(HIPOTESE, "").replace("*", "")).strip()[:90])
    desc = html.escape((pg.get("subheadline") or of.get("promessa") or "").replace(HIPOTESE, "").strip()[:160])
    js = JS.replace("%DELAY%", str(delay)).replace("%SLUG%", json.dumps(ficha.get("slug") or "vsl"))
    doc = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
           f'<title>{titulo}</title><meta name="description" content="{desc}"><meta name="robots" content="noindex">'
           f'<meta name="theme-color" content="{fundo}"><style>{vars_css}{CSS}</style></head><body>'
           + "\n".join(p) + f'<script>{js}</script></body></html>\n')
    return doc, t.achados


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera pagina.html da VSL a partir da ficha")
    ap.add_argument("slug")
    ap.add_argument("--dir", help="pasta dos projetos (padrão ./vsl)")
    ap.add_argument("--rascunho", action="store_true", help="marca em amarelo o que ainda é [HIPÓTESE]")
    ap.add_argument("--sem-delay", action="store_true", help="oferta visível desde o início")
    ap.add_argument("--saida", help="arquivo de saída (padrão <projeto>/pagina.html)")
    a = ap.parse_args()
    try:
        ficha, pasta_proj = carregar(a.slug, a.dir)
        doc, achados = montar(ficha, a.rascunho, a.sem_delay)
    except VslError as e:
        die(str(e))
    saida = pasta_proj / "pagina.html" if not a.saida else Path(a.saida)
    saida.write_text(doc, encoding="utf-8")
    if not ficha["produto"].get("checkout_url"):
        log("AVISO: produto.checkout_url vazio — os botões não levam a lugar nenhum.")
    if not ficha["vsl"].get("embed"):
        log("AVISO: vsl.embed vazio — a página mostra um espaço reservado no lugar do vídeo.")
    if achados and not a.rascunho:
        log(f"AVISO: {len(achados)} trecho(s) ainda eram [HIPÓTESE] e foram publicados sem o marcador:")
        for x in achados:
            log(f"  - {x}")
        log("  Confirme com o cliente (ou gere com --rascunho para vê-los marcados).")
    delay = 0 if a.sem_delay else int(ficha["vsl"].get("delay_oferta_s") or 0)
    log(f"OK: {saida} ({len(doc) / 1024:.0f} KB; oferta aparece "
        + (f"aos {delay // 60}:{delay % 60:02d}" if delay else "direto") + "; prévia sem esperar: pagina.html?ver=1)")


if __name__ == "__main__":
    sys.exit(main())
