// Cadeado de metal com corpo dourado (segurança, garantia, "trancado", exclusivo).
export const info = { nome: 'cadeado', sinonimos: ['seguranca', 'garantia', 'protecao', 'exclusivo', 'lock'], cor: '#FFC83D', entrada: 'cai' };
export default function criar(T, k) {
  const g = new T.Group();
  g.add(k.malha(k.caixa(0.7, 0.56, 0.24, 0.07), k.ouro(), [0, 0, 0]));
  g.add(k.malha(k.anel(0.22, 0.05, 64, Math.PI), k.prata(), [0, 0.28, 0]));
  for (const x of [-0.22, 0.22]) g.add(k.malha(k.cilindro(0.05, 0.05, 0.12, 24), k.prata(), [x, 0.28, 0]));
  g.add(k.malha(k.cilindro(0.06, 0.06, 0.03, 32), k.fosco('#2a2a2e', 0.4, 0.3), [0, 0.02, 0.12], [Math.PI / 2, 0, 0]));
  g.add(k.malha(k.caixa(0.035, 0.12, 0.03), k.fosco('#2a2a2e', 0.4, 0.3), [0, -0.06, 0.12]));
  return g;
}
