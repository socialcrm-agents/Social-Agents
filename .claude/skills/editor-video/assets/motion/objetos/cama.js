// Cama de casal com cabeceira estofada, colchão, edredom e dois travesseiros.
export const info = { nome: 'cama', sinonimos: ['quarto', 'suite', 'dormir', 'bed'], cor: '#8FB3FF', entrada: 'monta' };
export default function criar(T, k) {
  const g = new T.Group();
  g.add(k.malha(k.caixa(1.5, 0.25, 2.0, 0.04), k.madeira('#8a5a36'), [0, 0.15, 0]));
  g.add(k.malha(k.caixa(1.6, 0.9, 0.12, 0.05), k.tecido('#c9b8a3'), [0, 0.6, -1.0]));
  g.add(k.malha(k.caixa(1.42, 0.2, 1.9, 0.07), k.tecido('#f4f2ee'), [0, 0.37, 0]));
  g.add(k.malha(k.caixa(1.46, 0.08, 1.3, 0.04), k.tecido('#7f9cc9'), [0, 0.49, 0.33]));
  for (const x of [-0.36, 0.36]) g.add(k.malha(k.caixa(0.6, 0.14, 0.34, 0.07), k.tecido('#ffffff'), [x, 0.53, -0.75]));
  return g;
}
