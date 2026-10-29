// Casa que se monta em peças (gramado, paredes, telhado, chaminé, porta) e acende as janelas.
export const info = { nome: 'casa', sinonimos: ['casinha', 'imovel', 'lar', 'residencia', 'sobrado', 'house'],
  cor: '#FFB547', entrada: 'monta' };
export default function criar(T, k) {
  const g = new T.Group(), parede = k.fosco('#f4efe6', 0.7);
  g.add(k.malha(k.caixa(1.2, 0.05, 0.9, 0.02), k.fosco('#8fb58a', 0.85), [0, -0.46, 0]));
  g.add(k.malha(k.caixa(0.9, 0.5, 0.65, 0.015), parede, [0, -0.19, 0]));
  const tel = k.malha(k.cilindro(0.01, 0.62, 0.38, 4), k.fosco('#c4492f', 0.5), [0, 0.25, 0], [0, Math.PI / 4, 0]);
  tel.scale.set(1, 1, 0.78); g.add(tel);
  g.add(k.malha(k.caixa(0.1, 0.22, 0.1, 0.01), k.fosco('#8a7f78'), [0.22, 0.3, -0.05]));
  g.add(k.malha(k.caixa(0.17, 0.3, 0.03, 0.01), k.madeira('#7b4b2a'), [0, -0.29, 0.33]));
  for (const x of [-0.28, 0.28]) {
    const j = k.malha(k.caixa(0.16, 0.14, 0.02), new T.MeshStandardMaterial({ color: '#3b4f6e', roughness: 0.2,
      metalness: 0.3, emissive: '#ffcf70', emissiveIntensity: 0 }), [x, -0.12, 0.33]);
    j.userData.janela = true; g.add(j);
  }
  return g;
}
export function animar(g, k, s) {     // a montagem vem do template ("monta"); aqui só acendem as janelas
  const luz = k.clamp((s - 0.9) / 0.4);
  g.children.forEach((c) => { if (c.userData.janela) c.material.emissiveIntensity = 2.4 * luz; });
}
