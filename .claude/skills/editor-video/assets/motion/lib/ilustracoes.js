// Ilustrações animadas (SVG desenhado aqui, sem imagem de terceiros) para "mostrar o que a pessoa fala".
// Cada uma: ilustracao(nome, holder, {cor}) -> update(t, k) — t = segundos desde que entrou, k = 0..1 de entrada.
// Tudo é função do tempo (render determinístico). Nomes: menta, frutas, dente, casa, sorriso, brilho.
// Para ilustração realista, use uma imagem gerada (documentario / cenario) — estas são o padrão sem custo.

const NS = 'http://www.w3.org/2000/svg';
const clamp = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
const outBack = (k) => { const c = 1.70158; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); };
const ease = (k) => 1 - Math.pow(1 - clamp(k), 3);
const pop = (t, t0, d = 0.45) => outBack(clamp((t - t0) / d));

function svg(holder, vb = '50 50 500 500') {  // desenhos ocupam ~70..530: recorte justo, sem borda vazia
  holder.innerHTML = `<svg xmlns="${NS}" viewBox="${vb}" width="100%" height="100%" style="overflow:visible"></svg>`;
  return holder.firstChild;
}
function g(parent, html, attrs = {}) {
  const e = document.createElementNS(NS, 'g');
  e.innerHTML = html;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent.appendChild(e);
  return e;
}
const tf = (e, x, y, s = 1, r = 0) => e.setAttribute('transform', `translate(${x} ${y}) rotate(${r}) scale(${s})`);

// ---------- folha de menta + frescor ----------
const LEAF = `<path d="M0,-70 C40,-55 52,-5 0,70 C-52,-5 -40,-55 0,-70 Z" fill="#2fbf71" stroke="#10783f" stroke-width="6"/>
  <path d="M0,-60 L0,62" stroke="#10783f" stroke-width="5" stroke-linecap="round"/>
  <path d="M0,-20 L22,-38 M0,5 L-24,-14 M0,30 L20,12" stroke="#10783f" stroke-width="4" stroke-linecap="round"/>`;
function menta(holder) {
  const s = svg(holder);
  const bg = g(s, `<circle r="230" fill="#dff7ea"/><circle r="230" fill="none" stroke="#2fbf71" stroke-width="8" stroke-dasharray="18 16"/>`);
  tf(bg, 300, 300);
  const leaves = [[300, 250, 1.6, -15], [205, 330, 1.05, -55], [400, 335, 1.1, 40], [300, 395, 0.8, 175]].map(([x, y, sc, r]) => ({ e: g(s, LEAF), x, y, sc, r }));
  const winds = [0, 1, 2].map((i) => g(s, `<path d="M-90,0 C-40,-30 20,30 90,0" fill="none" stroke="#7fd8ff" stroke-width="10" stroke-linecap="round" stroke-dasharray="220" stroke-dashoffset="220"/>`));
  const flakes = Array.from({ length: 7 }, (_, i) => g(s, `<path d="M0,-14 L0,14 M-12,-7 L12,7 M-12,7 L12,-7" stroke="#7fd8ff" stroke-width="5" stroke-linecap="round"/>`));
  return (t, k) => {
    tf(bg, 300, 300, 0.6 + 0.4 * pop(t, 0, 0.5), t * 6);
    leaves.forEach((L, i) => tf(L.e, L.x, L.y + Math.sin(t * 2 + i) * 8, L.sc * pop(t, 0.12 + i * 0.1), L.r + Math.sin(t * 1.6 + i) * 6));
    winds.forEach((w, i) => {
      const ph = ((t * 0.9 + i / 3) % 1);
      tf(w, 300, 160 + i * 140, 1.3);
      w.firstChild.setAttribute('stroke-dashoffset', 220 - 440 * ph);
      w.style.opacity = t > 0.5 ? Math.sin(ph * Math.PI) : 0;
    });
    flakes.forEach((f, i) => {
      const a = i / 7 * Math.PI * 2 + t * 0.6;
      tf(f, 300 + Math.cos(a) * 250, 300 + Math.sin(a) * 250, pop(t, 0.6 + i * 0.05), t * 90);
    });
  };
}

// ---------- tutti-frutti: frutas pulando ----------
const FRUTAS = {
  morango: `<path d="M0,-50 C45,-50 55,10 0,60 C-55,10 -45,-50 0,-50 Z" fill="#ff3b5c" stroke="#a3112b" stroke-width="6"/>
    <path d="M-28,-52 L0,-36 L28,-52 L14,-62 L0,-50 L-14,-62 Z" fill="#2fbf71" stroke="#10783f" stroke-width="4"/>
    <g fill="#ffe08a"><circle cx="-15" cy="-10" r="4"/><circle cx="12" cy="-6" r="4"/><circle cx="-4" cy="14" r="4"/><circle cx="18" cy="20" r="4"/><circle cx="-20" cy="22" r="4"/></g>`,
  laranja: `<circle r="56" fill="#ff9a1f" stroke="#b85c00" stroke-width="6"/><circle r="44" fill="#ffd27a"/>
    <g stroke="#ff9a1f" stroke-width="5">${Array.from({ length: 8 }, (_, i) => `<line x1="0" y1="0" x2="${Math.cos(i * Math.PI / 4) * 44}" y2="${Math.sin(i * Math.PI / 4) * 44}"/>`).join('')}</g>`,
  uva: `<g fill="#8b5cf6" stroke="#4c1d95" stroke-width="5">${[[0, -30], [-24, -10], [24, -10], [-12, 14], [12, 14], [0, 38], [-34, 18], [34, 18]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="20"/>`).join('')}</g>
    <path d="M0,-50 L0,-72" stroke="#10783f" stroke-width="7" stroke-linecap="round"/>`,
  abacaxi: `<ellipse rx="44" ry="58" fill="#ffc83d" stroke="#b07a00" stroke-width="6"/>
    <path d="M-30,-30 L30,30 M-30,10 L10,50 M-10,-50 L40,0 M30,-30 L-30,30 M30,10 L-10,50 M10,-50 L-40,0" stroke="#b07a00" stroke-width="4"/>
    <path d="M0,-56 L-30,-100 L-8,-78 L0,-112 L8,-78 L30,-100 Z" fill="#2fbf71" stroke="#10783f" stroke-width="5"/>`,
  melancia: `<path d="M-60,0 A60,60 0 0,0 60,0 Z" fill="#ff4d6d" stroke="#2fbf71" stroke-width="12"/>
    <g fill="#222"><ellipse cx="-22" cy="16" rx="5" ry="8"/><ellipse cx="0" cy="28" rx="5" ry="8"/><ellipse cx="22" cy="16" rx="5" ry="8"/></g>`,
};
function frutas(holder) {
  const s = svg(holder);
  const bg = g(s, `<circle r="230" fill="#fff0f6"/><circle r="230" fill="none" stroke="#ff3b8d" stroke-width="8" stroke-dasharray="18 16"/>`);
  const names = Object.keys(FRUTAS);
  const f = names.map((n, i) => {
    const a = -Math.PI / 2 + i / names.length * Math.PI * 2;
    return { e: g(s, FRUTAS[n]), x: 300 + Math.cos(a) * 140, y: 310 + Math.sin(a) * 140, i };
  });
  const confete = Array.from({ length: 14 }, (_, i) => g(s, `<rect x="-6" y="-12" width="12" height="24" rx="3" fill="${['#ff3b8d', '#ffc83d', '#8b5cf6', '#2fbf71', '#ff9a1f'][i % 5]}"/>`));
  return (t) => {
    tf(bg, 300, 300, 0.6 + 0.4 * pop(t, 0, 0.5), -t * 6);
    for (const it of f) {
      const k = pop(t, 0.1 + it.i * 0.12);
      const bounce = Math.abs(Math.sin(t * 3.2 + it.i)) * 22;
      tf(it.e, it.x, it.y - bounce * (t > 0.8 ? 1 : 0), 1.15 * k, Math.sin(t * 2 + it.i) * 10);
    }
    confete.forEach((c, i) => {
      const fall = ((t * 0.35 + i / 14) % 1);
      tf(c, 60 + (i * 37) % 480, -40 + fall * 680, pop(t, 0.4), t * 140 + i * 40);
      c.style.opacity = t > 0.4 ? 1 : 0;
    });
  };
}

// ---------- dente + escova + brilho ----------
function dente(holder) {
  const s = svg(holder);
  const bg = g(s, `<circle r="230" fill="#e6f6ff"/>`);
  const tooth = g(s, `<path d="M-95,-110 C-60,-140 -20,-120 0,-108 C20,-120 60,-140 95,-110 C130,-80 120,-20 100,30
      C85,70 80,140 55,150 C30,160 22,90 0,80 C-22,90 -30,160 -55,150 C-80,140 -85,70 -100,30 C-120,-20 -130,-80 -95,-110 Z"
      fill="#ffffff" stroke="#1f6f99" stroke-width="10" stroke-linejoin="round"/>
    <path d="M-60,-85 C-45,-100 -25,-98 -15,-90" fill="none" stroke="#bfe6ff" stroke-width="12" stroke-linecap="round"/>
    <g class="face"><circle cx="-35" cy="-20" r="10" fill="#1f2937"/><circle cx="35" cy="-20" r="10" fill="#1f2937"/>
      <path d="M-30,20 Q0,48 30,20" fill="none" stroke="#1f2937" stroke-width="8" stroke-linecap="round"/></g>`);
  const brush = g(s, `<rect x="-20" y="-150" width="40" height="230" rx="18" fill="#3b82f6" stroke="#1e3a8a" stroke-width="6"/>
    <rect x="-34" y="-215" width="68" height="70" rx="10" fill="#ffffff" stroke="#1e3a8a" stroke-width="6"/>
    <g stroke="#7dd3fc" stroke-width="7" stroke-linecap="round">${[-22, -8, 6, 20].map((x) => `<line x1="${x}" y1="-210" x2="${x}" y2="-238"/>`).join('')}</g>`);
  const bubbles = Array.from({ length: 9 }, (_, i) => g(s, `<circle r="${10 + (i % 3) * 7}" fill="#ffffff" stroke="#7dd3fc" stroke-width="4"/>`));
  const stars = [[170, 140], [450, 170], [440, 430]].map(([x, y]) => ({ e: g(s, `<path d="M0,-30 L8,-8 L30,0 L8,8 L0,30 L-8,8 L-30,0 L-8,-8 Z" fill="#ffd21f"/>`), x, y }));
  return (t) => {
    tf(bg, 300, 300, 0.6 + 0.4 * pop(t, 0, 0.5));
    tf(tooth, 300, 300, pop(t, 0.1), Math.sin(t * 2) * 3);
    const scrub = Math.sin(t * 9) * 70;
    tf(brush, 300 + scrub, 470, pop(t, 0.35), 70);
    bubbles.forEach((b, i) => {
      const life = ((t * 0.7 + i / 9) % 1);
      tf(b, 230 + (i * 53) % 160 + Math.sin(t * 3 + i) * 10, 360 - life * 260, t > 0.6 ? 0.4 + life : 0);
      b.style.opacity = 1 - life;
    });
    stars.forEach((st, i) => tf(st.e, st.x, st.y, pop(t, 1.0 + i * 0.15) * (0.8 + 0.25 * Math.sin(t * 6 + i)), t * 60));
  };
}

// ---------- casa 3D isométrica montando ----------
function iso(x, y, z) { return [300 + (x - y) * 0.866, 360 + (x + y) * 0.5 - z]; }
function poly(pts) { return pts.map((p) => iso(...p).join(',')).join(' '); }
function casa(holder) {
  const s = svg(holder);
  const W0 = 150, D0 = 130, H0 = 120;
  const chao = g(s, `<polygon points="${poly([[-170, -150, 0], [170, -150, 0], [170, 150, 0], [-170, 150, 0]])}" fill="#bde5a8" stroke="#5b9a3f" stroke-width="5"/>`);
  const paredeE = g(s, `<polygon points="${poly([[-W0, D0, 0], [W0, D0, 0], [W0, D0, H0], [-W0, D0, H0]])}" fill="#fbe7c6" stroke="#8a5a2b" stroke-width="6"/>
    <polygon points="${poly([[-40, D0, 0], [10, D0, 0], [10, D0, 85], [-40, D0, 85]])}" fill="#8a5a2b"/>
    <polygon class="jan" points="${poly([[50, D0, 45], [110, D0, 45], [110, D0, 95], [50, D0, 95]])}" fill="#7dd3fc" stroke="#8a5a2b" stroke-width="5"/>`);
  const paredeD = g(s, `<polygon points="${poly([[W0, D0, 0], [W0, -D0, 0], [W0, -D0, H0], [W0, D0, H0]])}" fill="#f2cf98" stroke="#8a5a2b" stroke-width="6"/>
    <polygon class="jan" points="${poly([[W0, 70, 45], [W0, 10, 45], [W0, 10, 95], [W0, 70, 95]])}" fill="#7dd3fc" stroke="#8a5a2b" stroke-width="5"/>
    <polygon class="jan" points="${poly([[W0, -20, 45], [W0, -80, 45], [W0, -80, 95], [W0, -20, 95]])}" fill="#7dd3fc" stroke="#8a5a2b" stroke-width="5"/>`);
  const telhado = g(s, `<polygon points="${poly([[-W0 - 20, D0 + 20, H0], [W0 + 20, D0 + 20, H0], [W0 + 20, 0, H0 + 90], [-W0 - 20, 0, H0 + 90]])}" fill="#e2553b" stroke="#8f2a17" stroke-width="6"/>
    <polygon points="${poly([[W0 + 20, D0 + 20, H0], [W0 + 20, -D0 - 20, H0], [W0 + 20, 0, H0 + 90]])}" fill="#c4442d" stroke="#8f2a17" stroke-width="6"/>`);
  const arvore = g(s, `<rect x="-10" y="-10" width="20" height="60" fill="#8a5a2b"/><circle cy="-40" r="48" fill="#2fbf71" stroke="#10783f" stroke-width="6"/>`);
  const partes = [[chao, 0, 0], [paredeE, 0.25, 260], [paredeD, 0.4, 260], [telhado, 0.65, 360]];
  return (t) => {
    for (const [e, t0, drop] of partes) {
      const k = ease((t - t0) / 0.45);
      e.setAttribute('transform', `translate(0 ${(1 - k) * -drop})`);
      e.style.opacity = clamp((t - t0) / 0.15);
    }
    tf(arvore, 470, 470, pop(t, 1.0));
    const luz = t > 1.2 ? (Math.sin(t * 3) > -0.2 ? '#ffe17a' : '#7dd3fc') : '#7dd3fc';
    s.querySelectorAll('.jan').forEach((j) => j.setAttribute('fill', luz));
  };
}

// ---------- sorriso / brilho genéricos ----------
function brilho(holder, { cor = '#ffd21f' } = {}) {
  const s = svg(holder);
  const st = Array.from({ length: 6 }, (_, i) => ({ e: g(s, `<path d="M0,-40 L10,-10 L40,0 L10,10 L0,40 L-10,10 L-40,0 L-10,-10 Z" fill="${cor}"/>`), i }));
  return (t) => st.forEach(({ e, i }) => {
    const a = i / 6 * Math.PI * 2 + t * 0.8;
    tf(e, 300 + Math.cos(a) * 180, 300 + Math.sin(a) * 180, pop(t, i * 0.1) * (0.7 + 0.4 * Math.sin(t * 5 + i)), t * 90);
  });
}

const LIB = { menta, frutas, dente, casa, brilho };
export const nomes = Object.keys(LIB);
export function ilustracao(nome, holder, opts = {}) {
  return (LIB[nome] || brilho)(holder, opts);
}
