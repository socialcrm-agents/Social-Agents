// Cérebro holográfico: milhares de pontos ciano voam e formam os dois hemisférios com sulcos, cerebelo e tronco;
// um anel de varredura passa de baixo para cima.
export const info = { nome: 'cérebro', sinonimos: ['cerebro', 'mente', 'inteligencia', 'pensar', 'brain', 'neuro'],
  cor: '#41E2FF', angulo: [0.25, -0.9], sombra: false };
export default function criar(T, k) {
  const g = new T.Group(), N = 4200, pos = new Float32Array(N * 3), alvo = [];
  const ruido = (v) => Math.sin(v.x * 21 + Math.sin(v.z * 9) * 2) * Math.sin(v.z * 17 + v.y * 6) * Math.cos(v.y * 15);
  for (let i = 0; i < N; i++) {
    let v; do { v = new T.Vector3(k.rnd() * 2 - 1, k.rnd() * 2 - 1, k.rnd() * 2 - 1); } while (v.length() > 1 || v.length() < 0.2);
    v.normalize(); const parte = i % 10;
    if (parte < 8) { const lado = parte % 2 ? 1 : -1; v.multiplyScalar(1 + 0.07 * ruido(v));
      v.set(v.x * 0.24 + lado * 0.255, v.y * 0.33 + 0.04, v.z * 0.5); if (v.y < -0.12) v.y = -0.12 + (v.y + 0.12) * 0.35; }
    else if (parte === 8) v.set(v.x * 0.26, v.y * 0.11 - 0.2, v.z * 0.15 - 0.33);
    else v.set(v.x * 0.05, -0.2 - Math.abs(v.y) * 0.22, v.z * 0.05 - 0.2);
    alvo.push(v);
  }
  const ini = alvo.map(() => new T.Vector3((k.rnd() - 0.5) * 4, (k.rnd() - 0.5) * 4, (k.rnd() - 0.5) * 2));
  const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(pos, 3));
  // a caixa tem que existir antes da animação (o template mede o objeto para normalizar)
  alvo.forEach((v, i) => { pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z; });
  const pontos = new T.Points(geo, new T.PointsMaterial({ color: k.cor, size: 0.03, map: k.texturaHalo, transparent: true,
    depthWrite: false, toneMapped: false })); g.add(pontos);
  const anel = k.malha(k.anel(0.62, 0.006, 120), new T.MeshBasicMaterial({ color: k.cor, transparent: true, opacity: 0, toneMapped: false }),
    [0, 0, 0], [Math.PI / 2, 0, 0]); g.add(anel);
  const h = k.halo(k.cor, 1.9); g.add(h);
  g.userData.animar = (s, t) => {
    const q = k.ease.outCubic(k.clamp(s / 1.1));
    for (let i = 0; i < N; i++) { const a = ini[i], b = alvo[i], qi = k.clamp(q * 1.3 - (i % 13) * 0.02);
      pos[i * 3] = k.lerp(a.x, b.x, qi); pos[i * 3 + 1] = k.lerp(a.y, b.y, qi); pos[i * 3 + 2] = k.lerp(a.z, b.z, qi); }
    geo.attributes.position.needsUpdate = true;
    pontos.material.opacity = 0.45 + 0.55 * q;
    const v = (t * 0.7) % 1;
    anel.position.y = k.lerp(-0.32, 0.4, v); anel.material.opacity = 0.85 * k.clamp((s - 1.0) / 0.3) * Math.sin(v * Math.PI);
    anel.scale.setScalar(0.85 + 0.2 * Math.sin(v * Math.PI)); h.material.opacity = 0.3 * k.brilho * q;
  };
  return g;
}
