// Cadeira de design: assento e encosto estofados, pés de madeira inclinados.
export const info = { nome: 'cadeira', sinonimos: ['poltrona', 'assento', 'chair'], cor: '#E5A54B', entrada: 'monta', angulo: [0.25, -0.7] };
export default function criar(T, k) {
  const g = new T.Group(), tec = k.tecido('#d98c3f'), mad = k.madeira('#7b5130');
  g.add(k.malha(k.caixa(0.6, 0.1, 0.56, 0.04), tec, [0, 0.47, 0]));
  g.add(k.malha(k.caixa(0.6, 0.42, 0.08, 0.04), tec, [0, 0.78, -0.27], [-0.12, 0, 0]));
  for (const [x, z] of [[-0.24, 0.22], [0.24, 0.22], [-0.24, -0.22], [0.24, -0.22]])
    g.add(k.malha(k.cilindro(0.025, 0.018, 0.46, 12), mad, [x * 1.05, 0.22, z * 1.05], [z > 0 ? 0.08 : -0.08, 0, x > 0 ? -0.08 : 0.08]));
  return g;
}
