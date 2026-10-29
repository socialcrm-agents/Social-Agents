// Chave dourada (da casa nova, do sucesso, "a chave é…").
export const info = { nome: 'chave', sinonimos: ['chaves', 'segredo', 'acesso', 'solucao', 'key'], cor: '#FFC83D', entrada: 'gira', angulo: [0.2, -0.3] };
export default function criar(T, k) {
  const g = new T.Group(), ouro = k.ouro();
  g.add(k.malha(k.anel(0.22, 0.06, 64), ouro, [-0.55, 0, 0]));
  g.add(k.malha(k.cilindro(0.045, 0.045, 0.9, 24), ouro, [0.1, 0, 0], [0, 0, Math.PI / 2]));
  for (const [x, h] of [[0.42, 0.18], [0.3, 0.12], [0.2, 0.16]]) g.add(k.malha(k.caixa(0.07, h, 0.06, 0.012), ouro, [x, -h / 2 - 0.02, 0]));
  return g;
}
