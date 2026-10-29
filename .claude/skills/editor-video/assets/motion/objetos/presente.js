// Caixa de presente com laço (bônus, brinde, grátis).
export const info = { nome: 'presente', sinonimos: ['bonus', 'brinde', 'gratis', 'surpresa', 'gift'], cor: '#FF5C8A', entrada: 'monta' };
export default function criar(T, k) {
  const g = new T.Group(), caixa = k.plastico(k.params?.cor_objeto || '#e5445f'), fita = k.plastico('#ffd25e');
  g.add(k.malha(k.caixa(0.8, 0.6, 0.8, 0.03), caixa, [0, 0.3, 0]));
  g.add(k.malha(k.caixa(0.88, 0.14, 0.88, 0.03), caixa, [0, 0.66, 0]));
  g.add(k.malha(k.caixa(0.14, 0.76, 0.82), fita, [0, 0.36, 0]));
  g.add(k.malha(k.caixa(0.82, 0.76, 0.14), fita, [0, 0.36, 0]));
  for (const s of [-1, 1]) g.add(k.malha(k.anel(0.14, 0.04, 48), fita, [0.13 * s, 0.8, 0], [0, 0, 0.5 * s], [1, 0.75, 1]));
  return g;
}
