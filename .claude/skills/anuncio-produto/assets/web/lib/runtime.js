// Runtime das cenas do anúncio (HTML -> vídeo). Mesmo contrato do motor de motion do editor de vídeo.
//
// Contrato com o renderizador (scripts/render_html.mjs):
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
  clamp, lerp, ease,
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

  /** tempo (s, relativo ao clipe) em que uma palavra-gatilho é dita; params.cues vem do plano */
  cue(key, fallback = 0) {
    const c = this.params.cues || {};
    return key in c ? c[key] : fallback;
  },

  /** SVG de um ícone Lucide (nome em inglês, ex.: 'truck', 'shield-check'); lista em assets/web/icons */
  async icon(name) {
    const r = await fetch('/icons/' + name + '.svg');
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

  async _seek(t) {
    await Promise.all(this._ready);
    for (const fn of this._frame) await fn(t, this.params);
  },
};

window.motion = motion;
window.__motionSeek = (t) => motion._seek(t);
export default motion;
