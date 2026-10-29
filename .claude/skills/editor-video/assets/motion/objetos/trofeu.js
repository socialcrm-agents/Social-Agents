// Troféu de ouro: taça no torno, alças em curva e base de mármore escuro com placa.
export const info = { nome: 'troféu', sinonimos: ['trofeu', 'premio', 'vitoria', 'conquista', 'campeao', 'trophy'], cor: '#FFC83D', entrada: 'monta' };
export default function criar(T, k) {
  const g = new T.Group(), ouro = k.ouro();
  g.add(k.malha(k.caixa(0.62, 0.22, 0.5, 0.03), k.fosco('#1d1f26', 0.3, 0.2), [0, 0.11, 0]));
  g.add(k.malha(k.caixa(0.36, 0.08, 0.02, 0.01), ouro, [0, 0.12, 0.255]));
  g.add(k.malha(k.torno([[0.16, 0], [0.12, 0.04], [0.05, 0.08], [0.04, 0.3], [0.08, 0.34], [0.03, 0.36]]), ouro, [0, 0.22, 0]));
  g.add(k.malha(k.torno([[0.02, 0], [0.12, 0.02], [0.22, 0.12], [0.27, 0.3], [0.28, 0.42], [0.27, 0.43]]), ouro, [0, 0.56, 0]));
  for (const s of [-1, 1]) g.add(k.malha(k.tubo([[0.25 * s, 0.94, 0], [0.42 * s, 0.92, 0], [0.42 * s, 0.72, 0], [0.2 * s, 0.66, 0]], 0.025), ouro));
  return g;
}
