// Foguete branco com janela, aletas vermelhas e chama saindo (decolar, escalar, crescer rápido).
export const info = { nome: 'foguete', sinonimos: ['decolar', 'escalar', 'lancamento', 'crescer', 'rocket', 'viral'], cor: '#FF6B3D',
  entrada: 'voa', angulo: [0.2, -0.5] };
export default function criar(T, k) {
  const g = new T.Group(), branco = k.plastico('#f3f4f7'), verm = k.plastico('#e5443b');
  g.add(k.malha(k.torno([[0.0, 0], [0.16, 0.02], [0.2, 0.2], [0.2, 0.6], [0.16, 0.82], [0.08, 0.95], [0.001, 1.0]]), branco));
  g.add(k.malha(k.cone(0.1, 0.18), verm, [0, 1.0, 0]));
  g.add(k.malha(k.cilindro(0.075, 0.075, 0.03, 32), k.metal('#b9bcc3'), [0, 0.6, 0.18], [Math.PI / 2, 0, 0]));
  g.add(k.malha(k.cilindro(0.055, 0.055, 0.035, 32), k.vidro('#7fd3ff', 0.85), [0, 0.6, 0.19], [Math.PI / 2, 0, 0]));
  for (let i = 0; i < 3; i++) { const a = i * Math.PI * 2 / 3;
    g.add(k.malha(k.extrusao([[0, 0], [0.18, -0.06], [0.18, -0.2], [0, -0.06]], 0.025, 0.006), verm, [Math.sin(a) * 0.18, 0.2, Math.cos(a) * 0.18], [0, a - Math.PI / 2, 0])); }
  const fogo = k.peca(k.malha(k.cone(0.12, 0.34), k.emissivo('#ff8a2a', 3), [0, -0.17, 0], [Math.PI, 0, 0]),
                      k.malha(k.cone(0.07, 0.22), k.emissivo('#ffe27a', 4), [0, -0.1, 0], [Math.PI, 0, 0]));
  fogo.userData.fogo = true; g.add(fogo);
  return g;
}
export function animar(g, k, s, t) {
  const f = g.children.find((c) => c.userData.fogo);
  if (f) f.scale.set(1, 0.85 + 0.25 * Math.abs(Math.sin(t * 23)), 1);
}
