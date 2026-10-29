// Relógio de mesa com ponteiros girando (tempo, prazo, "em 7 dias", urgência).
export const info = { nome: 'relógio', sinonimos: ['relogio', 'tempo', 'prazo', 'hora', 'urgencia', 'clock'], cor: '#FF5C5C', entrada: 'gira', angulo: [0.1, -0.3] };
export default function criar(T, k) {
  const g = new T.Group();
  g.add(k.malha(k.cilindro(0.5, 0.5, 0.14, 64), k.plastico('#e5443b'), [0, 0, 0], [Math.PI / 2, 0, 0]));
  g.add(k.malha(k.cilindro(0.44, 0.44, 0.02, 64), k.fosco('#fbfbfb', 0.5), [0, 0, 0.07], [Math.PI / 2, 0, 0]));
  for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; g.add(k.malha(k.caixa(0.025, i % 3 ? 0.04 : 0.08, 0.01), k.fosco('#222'), [Math.sin(a) * 0.37, Math.cos(a) * 0.37, 0.085], [0, 0, -a])); }
  const hora = k.malha(k.caixa(0.035, 0.22, 0.01), k.fosco('#222'), [0, 0.1, 0.09]), min = k.malha(k.caixa(0.025, 0.32, 0.01), k.fosco('#222'), [0, 0.15, 0.095]);
  const ph = k.peca(hora), pm = k.peca(min); ph.userData.ponteiro = 1; pm.userData.ponteiro = 12; g.add(ph, pm);
  for (const s of [-1, 1]) g.add(k.malha(k.esfera(0.13), k.metal('#c9ccd2'), [0.32 * s, 0.5, 0], [0, 0, 0], [1, 0.6, 1]));
  return g;
}
export function animar(g, k, s, t) { g.children.forEach((c) => { if (c.userData.ponteiro) c.rotation.z = -t * c.userData.ponteiro * 0.6; }); }
