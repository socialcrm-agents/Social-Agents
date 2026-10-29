// Megafone (anúncio, novidade, "atenção", divulgar).
export const info = { nome: 'megafone', sinonimos: ['anuncio', 'atencao', 'novidade', 'divulgar', 'megaphone'], cor: '#FF9F1C', entrada: 'voa', angulo: [0.2, -0.6] };
export default function criar(T, k) {
  const g = new T.Group(), z = -Math.PI / 2;
  g.add(k.malha(k.torno([[0.09, 0], [0.12, 0.2], [0.22, 0.5], [0.34, 0.7], [0.36, 0.72], [0.3, 0.72]]), k.plastico('#ff9f1c'), [0, 0, 0], [0, 0, z]));
  g.add(k.malha(k.cilindro(0.1, 0.1, 0.18, 32), k.plastico('#2a2d34'), [-0.08, 0, 0], [0, 0, Math.PI / 2]));
  g.add(k.malha(k.caixa(0.08, 0.3, 0.1, 0.03), k.borracha('#2a2d34'), [0.12, -0.2, 0]));
  return g;
}
