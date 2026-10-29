// Mesa de madeira com tampo grosso e quatro pernas (escritório, jantar, projeto de arquiteto).
export const info = { nome: 'mesa', sinonimos: ['escrivaninha', 'mesa de jantar', 'table', 'escritorio'], cor: '#E0A15B', entrada: 'monta' };
export default function criar(T, k) {
  const g = new T.Group(), mad = k.madeira('#a0703f');
  g.add(k.malha(k.caixa(1.6, 0.08, 0.9, 0.02), mad, [0, 0.76, 0]));
  for (const [x, z] of [[-0.72, 0.36], [0.72, 0.36], [-0.72, -0.36], [0.72, -0.36]]) g.add(k.malha(k.caixa(0.07, 0.72, 0.07, 0.01), mad, [x, 0.36, z]));
  return g;
}
