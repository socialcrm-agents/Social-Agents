// Lápis amarelo sextavado com ponta de grafite, ponteira de metal e borracha rosa.
export const info = { nome: 'lápis', sinonimos: ['lapis', 'escrever', 'desenhar', 'caneta', 'pencil', 'projeto'], cor: '#FFC531',
  entrada: 'voa', angulo: [0.3, -0.4] };
export default function criar(T, k) {
  const g = new T.Group(), z = Math.PI / 2;
  g.add(k.malha(k.cilindro(0.08, 0.08, 1.4, 6), k.plastico('#FFC531'), [0, 0, 0], [0, 0, z]));
  g.add(k.malha(k.cone(0.08, 0.26, 6), k.madeira('#e8c497'), [-0.83, 0, 0], [0, 0, z]));
  g.add(k.malha(k.cone(0.026, 0.08, 16), k.fosco('#2a2a2e', 0.4, 0.3), [-0.93, 0, 0], [0, 0, z]));
  g.add(k.malha(k.cilindro(0.083, 0.083, 0.16, 32), k.metal('#c9ccd2', 0.25), [0.78, 0, 0], [0, 0, z]));
  for (const x of [0.73, 0.83]) g.add(k.malha(k.anel(0.084, 0.006, 32), k.metal('#aeb2b9', 0.3), [x, 0, 0], [0, z, 0]));
  g.add(k.malha(k.caixa(0.12, 0.155, 0.155, 0.05), k.borracha('#f08ea0'), [0.92, 0, 0]));
  return g;
}
