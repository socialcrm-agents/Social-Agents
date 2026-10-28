// Runtime das composições de motion (HTML -> vídeo).
//
// Contrato com o renderizador (scripts/motion_render.mjs):
//   - antes da página carregar, ele define window.__MOTION__ = {w, h, fps, duration, params}
//   - para cada quadro ele chama await window.__motionSeek(t) e tira um screenshot (fundo transparente)
// A composição só precisa registrar motion.onFrame((t, p) => {...}) e desenhar o estado no tempo t.
// Tudo é função do tempo (nada de setTimeout / requestAnimationFrame próprios): o render é determinístico.

const cfg = window.__MOTION__ || { w: 1080, h: 1920, fps: 30, duration: 4, params: {} };

const clamp = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
const lerp = (a, b, k) => a + (b - a) * k;

const ease = {
  linear: (k) => k,
  inQuad: (k) => k * k,
  outQuad: (k) => k * (2 - k),
  inOutQuad: (k) => (k < 0.5 ? 2 * k * k : -1 + (4 - 2 * k) * k),
  outCubic: (k) => 1 - Math.pow(1 - k, 3),
  inOutCubic: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
  outBack: (k) => { const c = 1.70158; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); },
  outExpo: (k) => (k === 1 ? 1 : 1 - Math.pow(2, -10 * k)),
  outElastic: (k) => (k === 0 || k === 1 ? k : Math.pow(2, -10 * k) * Math.sin((k * 10 - 0.75) * (2 * Math.PI) / 3) + 1),
};

/**
 * Mola amortecida em função do tempo decorrido tau (s): 0 -> 1, com overshoot controlado.
 * dur = tempo até assentar (~), bounce 0 (sem passar do ponto) .. 0.6 (bem elástico).
 */
function springK(tau, dur = 0.6, bounce = 0.25) {
  if (tau <= 0) return 0;
  const zeta = Math.max(0.12, 1 - bounce), w = (2 * Math.PI) / Math.max(dur, 0.05) * 0.9;
  if (zeta >= 1) return 1 - Math.exp(-w * tau) * (1 + w * tau);
  const wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * tau) * (Math.cos(wd * tau) + (zeta * w / wd) * Math.sin(wd * tau));
}

const imgCache = new Map();
function loadImage(src) {
  if (imgCache.has(src)) return imgCache.get(src);
  const p = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('imagem não carregou: ' + src));
    img.src = src;
  });
  imgCache.set(src, p);
  if (imgCache.size > 400) imgCache.delete(imgCache.keys().next().value);
  return p;
}

const motion = {
  w: cfg.w, h: cfg.h, fps: cfg.fps, duration: cfg.duration, params: cfg.params || {},
  clamp, lerp, ease, springK,
  _frame: [], _ready: [],

  /** registra a função que desenha o quadro no tempo t (segundos desde o início do clipe) */
  onFrame(fn) { this._frame.push(fn); },

  /** espera um carregamento (fonte, imagem, modelo 3D) antes do primeiro quadro */
  waitFor(promise) { this._ready.push(promise); return promise; },

  /** progresso 0..1 de uma animação que começa em t0 e dura d segundos */
  prog(t, t0, d, e = 'outCubic') { return (typeof e === 'function' ? e : ease[e])(clamp((t - t0) / Math.max(d, 1e-6))); },

  /** entra em t0 e sai em t1: 0 -> 1 -> 0 (in/out em segundos) */
  inOut(t, t0, t1, din = 0.35, dout = 0.3, e = 'outCubic') {
    return Math.min(this.prog(t, t0, din, e), 1 - this.prog(t, t1 - dout, dout, 'inQuad'));
  },

  // ---------------------------------------------------------------------------------------------------------
  // Vocabulário premium (mola, cascata, desfoque de movimento, saída limpa, respiração, wipe, contagem).
  // Tudo determinístico em t. Use em vez de transições lineares: é o que dá cara de After Effects.
  // ---------------------------------------------------------------------------------------------------------

  /** mola: 0 -> 1 (com overshoot) a partir de t0. opts: {dur, bounce} */
  spring(t, t0, opts = {}) { return springK(t - t0, opts.dur ?? 0.6, opts.bounce ?? 0.25); },

  /** saída 0 -> 1 nos últimos `d` segundos antes de t1 (curva suave) */
  exitK(t, t1, d = 0.32) { return ease.inOutCubic(clamp((t - (t1 - d)) / d)); },

  /** respiração/flutuação depois de entrar (px); fase por índice para não sincronizar tudo */
  float(t, amp = 6, period = 3.2, phase = 0) { return Math.sin((t / period + phase) * 2 * Math.PI) * amp; },

  /**
   * Entrada + respiração + saída aplicadas a um elemento (transform/filter/opacity).
   * opts: from ('up'|'down'|'left'|'right'|'scale'|'none'), dist (px), scale0, rot0 (graus), dur, bounce,
   *       blur (máx. px do desfoque de movimento), out (s da saída; 0 = sem saída), t1 (fim), float (px), phase,
   *       origin (transform-origin), extra (string de transform somada no fim). Devolve {k, o, x}.
   */
  appear(el, t, t0, opts = {}) {
    const dur = opts.dur ?? 0.6, bounce = opts.bounce ?? 0.22, dist = opts.dist ?? 60, from = opts.from ?? 'up';
    const k = springK(t - t0, dur, bounce), kp = springK(t - t0 - 1 / this.fps, dur, bounce);
    const vel = Math.abs(k - kp) * this.fps;                       // velocidade da entrada (1/s)
    const t1 = opts.t1 ?? this.duration, out = opts.out ?? 0.32;
    const x = out > 0 ? this.exitK(t, t1, out) : 0;
    const vis = t >= t0 ? 1 : 0;
    let tx = 0, ty = 0;
    const r = 1 - k;
    if (from === 'up') ty = r * dist; else if (from === 'down') ty = -r * dist;
    else if (from === 'left') tx = -r * dist; else if (from === 'right') tx = r * dist;
    const s0 = opts.scale0 ?? (from === 'scale' ? 0.6 : 0.92);
    const sc = (s0 + (1 - s0) * k) * (1 - 0.06 * x);
    const rot = (opts.rot0 ?? 0) * r;
    const fl = opts.float ? this.float(t, opts.float, 3.4, opts.phase ?? 0) * clamp((t - t0 - dur) / 0.6) : 0;
    const blur = Math.min(opts.blur ?? 14, vel * (opts.blurK ?? 2.2)) + 12 * x;
    const o = vis * clamp(k * 2.2) * (1 - x);
    el.style.opacity = o;
    el.style.transform = `translate(${tx}px, ${ty + fl - 14 * x}px) rotate(${rot}deg) scale(${sc}) ${opts.extra || ''}`;
    el.style.filter = blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : (opts.keepFilter || 'none');
    if (opts.origin) el.style.transformOrigin = opts.origin;
    return { k, o, x };
  },

  /** quebra o texto de um elemento em <span> por letra ('chars') ou palavra ('words'); devolve os spans */
  split(el, mode = 'words', text = null) {
    const src = text ?? el.textContent;
    el.textContent = '';
    const out = [];
    const parts = mode === 'chars' ? [...src] : src.split(/(\s+)/);
    for (const part of parts) {
      if (/^\s+$/.test(part)) { el.appendChild(document.createTextNode(part)); continue; }
      if (mode === 'chars' && part === ' ') { el.appendChild(document.createTextNode(' ')); continue; }
      const sp = document.createElement('span');
      sp.textContent = part;
      sp.style.display = 'inline-block';
      sp.style.willChange = 'transform, filter, opacity';
      el.appendChild(sp);
      out.push(sp);
    }
    return out;
  },

  /** cascata: aplica appear() em cada elemento com atraso `step` (s) entre eles */
  stagger(els, t, t0, step = 0.045, opts = {}) {
    els.forEach((e, i) => this.appear(e, t, t0 + i * step, { phase: i * 0.13, ...opts }));
  },

  /** pop com overshoot (escala) — selos, ícones, checks */
  pop(t, t0, dur = 0.45, bounce = 0.45) { return springK(t - t0, dur, bounce); },

  /** revelação com máscara (clip-path) na direção dada: 'right' (da esquerda p/ direita), 'left', 'down', 'up' */
  wipe(el, t, t0, d = 0.5, dir = 'right') {
    const k = ease.outExpo(clamp((t - t0) / d)), r = (1 - k) * 100;
    const ins = { right: `0 ${r}% 0 0`, left: `0 0 0 ${r}%`, down: `0 0 ${r}% 0`, up: `${r}% 0 0 0` }[dir];
    el.style.clipPath = `inset(${ins})`;
    return k;
  },

  /** contagem com desaceleração até o valor (para números que "rolam") */
  countUp(t, t0, d, value, decimals = 0) {
    const k = ease.outExpo(clamp((t - t0) / d));
    return (value * k).toFixed(decimals);
  },

  /** brilho que atravessa o texto/card (posição 0..1 a cada `period` s); use com a classe .shine */
  shimmer(el, t, period = 2.6, t0 = 0) {
    const ph = ((t - t0) / period) % 1;
    el.style.backgroundPosition = `${(1.3 - ph * 1.6) * 100}% 0`;
  },

  /** tremida curta de impacto (px) entre at e at+d */
  shake(t, at, amp = 10, d = 0.25) {
    if (t < at || t > at + d) return 0;
    return Math.sin((t - at) * 95) * amp * (1 - (t - at) / d);
  },

  /** tempo (s, relativo ao clipe) em que uma palavra-gatilho é dita; params.cues vem do plano */
  cue(key, fallback = 0) {
    const c = this.params.cues || {};
    return key in c ? c[key] : fallback;
  },

  /** SVG de um ícone Lucide (nome em inglês, ex.: 'house', 'map-pin', 'chef-hat') */
  async icon(name) {
    const r = await fetch('/vendor/lucide/icons/' + name + '.svg');
    if (!r.ok) return this.icon('circle');
    return r.text();
  },

  loadImage,

  /**
   * Quadro do vídeo real na posição t: kind = 'plate' (imagem inteira já com cor) ou 'cut' (só a pessoa, PNG
   * com transparência). Disponível quando o plano pede needs_video.
   */
  frameSrc(kind, t) {
    const v = this.params.video;
    if (!v) return null;
    const i = clamp(Math.round(t * this.fps), 0, v.count - 1) + 1;
    return v[kind].replace('%05d', String(i).padStart(5, '0'));
  },
  async frame(kind, t) { const s = this.frameSrc(kind, t); return s ? loadImage(s) : null; },

  /** coloca o quadro real num <img> e espera decodificar */
  async setFrame(img, kind, t) {
    const s = this.frameSrc(kind, t);
    if (!s || img.dataset.src === s) return;
    img.dataset.src = s;
    img.src = s;
    await img.decode().catch(() => {});
  },

  // ---------------------------------------------------------------------------------------------------------
  // Bibliotecas de animação no relógio do render (determinístico: o quadro t sempre sai igual).
  // ---------------------------------------------------------------------------------------------------------

  /**
   * Anime.js v4 (MIT, /vendor/animejs/anime.esm.min.js): crie a animação ou timeline com {autoplay: false} e
   * registre aqui; a cada quadro ela vai para (t - t0). Ex.:
   *   import { createTimeline, stagger, splitText } from '/vendor/animejs/anime.esm.min.js';
   *   motion.anime(createTimeline({ autoplay: false }).add(chars, { y: [80, 0], delay: stagger(30) }), 0.2);
   */
  anime(inst, t0 = 0) {
    this._seekers.push((t) => inst.seek(Math.max(0, (t - t0) * 1000)));
    return inst;
  },

  /**
   * Lottie (MIT, /vendor/lottie/lottie.min.js): animação do After Effects / LottieFiles (JSON) no quadro certo.
   * src = caminho/URL do .json ou o objeto JSON. opts: {t0 (s), speed, loop (true), renderer ('svg')}.
   * Devolve a promessa do carregamento (o primeiro quadro espera).
   */
  lottie(container, src, opts = {}) {
    const carrega = (window.lottie ? Promise.resolve() : new Promise((ok, erro) => {
      const s = document.createElement('script');
      s.src = '/vendor/lottie/lottie.min.js';
      s.onload = ok;
      s.onerror = () => erro(new Error('lottie.min.js não carregou'));
      document.head.appendChild(s);
    })).then(() => new Promise((ok) => {
      const anim = window.lottie.loadAnimation({
        container, renderer: opts.renderer || 'svg', loop: false, autoplay: false,
        ...(typeof src === 'string' ? { path: src } : { animationData: src }),
      });
      anim.addEventListener('DOMLoaded', () => {
        const total = anim.getDuration(true), fr = anim.frameRate || 30;
        this._seekers.push((t) => {
          let f = Math.max(0, (t - (opts.t0 || 0)) * fr * (opts.speed || 1));
          f = opts.loop === false ? Math.min(f, total - 1) : f % total;
          anim.goToAndStop(f, true);
        });
        ok(anim);
      });
    }));
    return this.waitFor(carrega);
  },

  _seekers: [],

  async _seek(t) {
    await Promise.all(this._ready);
    for (const fn of this._seekers) fn(t);
    for (const fn of this._frame) await fn(t, this.params);
  },
};

window.motion = motion;
window.__motionSeek = (t) => motion._seek(t);
export default motion;
