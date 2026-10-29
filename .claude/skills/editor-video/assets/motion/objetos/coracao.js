// Coração 3D brilhante que pulsa (amor, curtida, cliente fiel, saúde).
export const info = { nome: 'coração', sinonimos: ['coracao', 'amor', 'curtida', 'like', 'saude', 'heart'], cor: '#FF3D6E', entrada: 'surge', angulo: [0.05, -0.3] };
export default function criar(T, k) {
  const g = new T.Group(), pts = [];
  for (let i = 0; i <= 64; i++) { const a = (i / 64) * Math.PI * 2; pts.push([16 * Math.sin(a) ** 3 / 32, (13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)) / 32]); }
  g.add(k.malha(k.extrusao(pts, 0.18, 0.09), k.plastico('#ff3d6e')));
  return g;
}
export function animar(g, k, s, t) { const b = 1 + 0.06 * Math.max(0, Math.sin(t * 7)) ** 4; g.scale.setScalar(b); }
