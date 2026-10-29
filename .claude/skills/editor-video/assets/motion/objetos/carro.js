// Carro hatch moderno: carroceria vermelha com perfil extrudado, vidros escuros, rodas com aro de liga e faróis.
export const info = { nome: 'carro', sinonimos: ['automovel', 'veiculo', 'consorcio', 'carro novo', 'car'], cor: '#FF4D4D',
  entrada: 'voa', angulo: [0.2, -0.65] };
export default function criar(T, k) {
  const g = new T.Group(), pint = new T.MeshPhysicalMaterial({ color: k.params?.cor_objeto || '#d62f2f', metalness: 0.4,
    roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.08 });
  // perfil lateral (x = comprimento, y = altura), extrudado na largura
  const lado = [[-2.0, 0.25], [-2.05, 0.55], [-1.85, 0.8], [-0.9, 0.9], [-0.45, 1.38], [0.85, 1.4], [1.45, 0.92],
                [2.0, 0.82], [2.08, 0.5], [2.0, 0.25]];
  g.add(k.malha(k.extrusao(lado, 1.6, 0.08), pint));
  const vid = k.vidro('#1b2433', 0.92);
  // vidros laterais um pouco para fora da lataria (a carroceria tem 1,6 + chanfro de 0,08 de cada lado)
  for (const [a, b] of [[-0.8, 0.22], [0.3, 1.28]])
    g.add(k.malha(k.extrusao([[a, 0.96], [Math.max(a, -0.4) + (a < 0 ? 0.04 : 0), 1.3], [b - (b > 1 ? 0.45 : 0), 1.31], [b, 0.96]], 1.8, 0.01), vid));
  g.add(k.malha(k.caixa(0.04, 0.36, 1.5, 0.02), vid, [1.17, 1.14, 0], [0, 0, 0.62]));       // para-brisa
  g.add(k.malha(k.caixa(0.04, 0.34, 1.5, 0.02), vid, [-0.66, 1.12, 0], [0, 0, -0.85]));     // vidro traseiro
  for (const z of [-0.82, 0.82]) {
    for (const x of [-1.25, 1.3]) {
      const roda = k.peca(k.malha(k.anel(0.3, 0.13, 48), k.borracha('#15171b'), [0, 0, 0]),
                          k.malha(k.cilindro(0.26, 0.26, 0.12, 32), k.metal('#c9ccd2', 0.25), [0, 0, 0], [Math.PI / 2, 0, 0]),
                          k.malha(k.cilindro(0.08, 0.08, 0.14, 16), k.metal('#6b6f77', 0.4), [0, 0, 0], [Math.PI / 2, 0, 0]));
      roda.position.set(x, 0.32, z); g.add(roda);
    }
  }
  for (const z of [-0.55, 0.55]) {
    g.add(k.malha(k.caixa(0.06, 0.12, 0.3, 0.03), k.emissivo('#fff3c4', 2.2), [2.06, 0.7, z]));
    g.add(k.malha(k.caixa(0.06, 0.1, 0.3, 0.03), k.emissivo('#ff2a2a', 1.6), [-2.04, 0.72, z]));
  }
  g.add(k.malha(k.caixa(0.08, 0.14, 1.2, 0.04), k.borracha('#20232a'), [2.08, 0.38, 0]));
  return g;
}
