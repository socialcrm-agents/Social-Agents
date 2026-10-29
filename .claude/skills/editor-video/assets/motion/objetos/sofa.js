// Sofá de três lugares em tecido, com almofadas, braços arredondados e pés de madeira.
export const info = { nome: 'sofá', sinonimos: ['sofa', 'estofado', 'sala de estar', 'couch'], cor: '#E08A4B', entrada: 'monta' };
export default function criar(T, k) {
  const g = new T.Group(), cor = k.params?.cor_objeto || '#5d7a8c', tec = k.tecido(cor), tec2 = k.tecido(new T.Color(cor).offsetHSL(0, 0, 0.06));
  g.add(k.malha(k.caixa(2.0, 0.28, 0.9, 0.08), tec, [0, 0.32, 0]));                 // base
  g.add(k.malha(k.caixa(2.0, 0.62, 0.24, 0.1), tec, [0, 0.72, -0.36]));             // encosto
  for (const x of [-1.04, 1.04]) g.add(k.malha(k.caixa(0.24, 0.52, 0.92, 0.11), tec, [x, 0.48, 0]));   // braços
  for (const x of [-0.6, 0, 0.6]) {
    g.add(k.malha(k.caixa(0.6, 0.16, 0.66, 0.07), tec2, [x, 0.53, 0.08]));           // assentos
    g.add(k.malha(k.caixa(0.56, 0.44, 0.16, 0.08), tec2, [x, 0.82, -0.2], [-0.12, 0, 0]));   // almofadas
  }
  const pe = k.madeira('#6b4428');
  for (const [x, z] of [[-0.95, 0.34], [0.95, 0.34], [-0.95, -0.34], [0.95, -0.34]]) g.add(k.malha(k.cilindro(0.035, 0.025, 0.2, 16), pe, [x, 0.1, z]));
  return g;
}
