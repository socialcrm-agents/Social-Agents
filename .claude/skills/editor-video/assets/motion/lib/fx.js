// Peças reutilizáveis das telas animadas: cursor que anda e clica, seta/círculo desenhados à mão,
// carimbo, digitação. Tudo em função do tempo t (determinístico).
import motion from '/lib/runtime.js';

const NS = 'http://www.w3.org/2000/svg';

export function cursor(parent) {
  const el = document.createElement('div');
  el.className = 'cursor';
  el.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.5 15 L11.5 22 L14.5 20.7 L11.5 14 L18 14 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const ring = document.createElement('div');
  ring.className = 'ripple';
  parent.append(ring, el);
  // path: [{at, x, y, click}] — o cursor viaja até cada ponto nos 0,55 s antes de `at` e clica em `at`
  return (t, path) => {
    let x = path.length ? path[0].x : -100, y = path.length ? path[0].y : -100, rip = 0, rx = 0, ry = 0;
    for (let i = 0; i < path.length; i++) {
      const p = path[i], prev = path[i - 1] || p;
      const k = motion.prog(t, p.at - 0.55, 0.55, 'inOutCubic');
      if (t >= p.at - 0.55) { x = motion.lerp(prev.x, p.x, k); y = motion.lerp(prev.y, p.y, k); }
      if (p.click && t >= p.at && t < p.at + 0.45) { rip = motion.prog(t, p.at, 0.45, 'outCubic'); rx = p.x; ry = p.y; }
    }
    const press = rip > 0 && rip < 0.3 ? 0.88 : 1;
    el.style.transform = `translate(${x - 8}px, ${y - 4}px) scale(${press})`;
    el.style.opacity = path.length && t >= path[0].at - 0.9 ? 1 : 0;
    const r = 30 + 60 * rip;
    ring.style.cssText = `left:${rx - r}px;top:${ry - r}px;width:${2 * r}px;height:${2 * r}px;opacity:${rip ? 1 - rip : 0}`;
  };
}

/** seta/círculo/rabisco desenhado à mão num <svg> que cobre a tela; draw(t) anima o traço. */
export function handMark(svg, kind, from, to, color = '#E63B2E', width = 9) {
  const path = document.createElementNS(NS, 'path');
  const [x1, y1] = from, [x2, y2] = to;
  let d;
  if (kind === 'circle') {
    const rx = Math.abs(x2 - x1) / 2 + 30, ry = Math.abs(y2 - y1) / 2 + 26, cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    d = `M ${cx + rx} ${cy} C ${cx + rx} ${cy - ry * 1.1}, ${cx - rx * 1.05} ${cy - ry}, ${cx - rx} ${cy + 4}
         C ${cx - rx} ${cy + ry * 1.05}, ${cx + rx * 1.1} ${cy + ry}, ${cx + rx * 0.92} ${cy - ry * 0.35}`;
  } else if (kind === 'underline') {
    d = `M ${x1} ${y1} C ${x1 + (x2 - x1) * 0.3} ${y1 + 10}, ${x1 + (x2 - x1) * 0.7} ${y1 - 8}, ${x2} ${y1 + 4}`;
  } else {  // arrow
    const mx = (x1 + x2) / 2 + (y2 - y1) * 0.25, my = (y1 + y2) / 2 - (x2 - x1) * 0.25;
    const ang = Math.atan2(y2 - my, x2 - mx), h = 38;
    d = `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2} M ${x2} ${y2} L ${x2 - h * Math.cos(ang - 0.5)} ${y2 - h * Math.sin(ang - 0.5)}
         M ${x2} ${y2} L ${x2 - h * Math.cos(ang + 0.5)} ${y2 - h * Math.sin(ang + 0.5)}`;
  }
  path.setAttribute('d', d);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', color);
  path.setAttribute('stroke-width', width);
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  svg.appendChild(path);
  const len = path.getTotalLength();
  path.setAttribute('stroke-dasharray', `${len} ${len}`);
  const draw = (k) => path.setAttribute('stroke-dashoffset', String(len * (1 - k)));
  draw.el = path;
  return draw;
}

/** carimbo que "bate" na tela (escala grande -> 1 com tremidinha) */
export function stamp(parent, text, color = '#E63B2E') {
  const el = document.createElement('div');
  el.className = 'stamp';
  el.textContent = text;
  el.style.color = color;
  parent.appendChild(el);
  return (t, at, x, y, size = 92, rot = -8) => {
    const k = motion.prog(t, at, 0.28, 'outQuad');
    const shake = t > at + 0.28 && t < at + 0.5 ? Math.sin((t - at) * 90) * 6 * (1 - motion.prog(t, at + 0.28, 0.22)) : 0;
    el.style.fontSize = size + 'px';
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.opacity = t >= at ? Math.min(1, k * 1.6) : 0;
    el.style.transform = `translate(-50%, -50%) translate(${shake}px, 0) rotate(${rot}deg) scale(${motion.lerp(2.6, 1, k)})`;
  };
}

/** texto digitando: devolve a parte já digitada no tempo t */
export function typed(text, t, at, cps = 22) {
  if (t < at) return '';
  return text.slice(0, Math.min(text.length, Math.floor((t - at) * cps)));
}
