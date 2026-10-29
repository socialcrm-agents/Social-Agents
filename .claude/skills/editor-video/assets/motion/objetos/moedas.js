// Moedas de ouro caem girando e empilham; uma moeda grande gira na frente com faíscas.
export const info = { nome: 'moedas', sinonimos: ['moeda', 'dinheiro', 'grana', 'lucro', 'faturamento', 'coins'],
  cor: '#FFC83D', angulo: [0.15, 0] };
export default function criar(T, k) {
  const g = new T.Group(), ouro = k.ouro(), pilha = [];
  const geo = k.cilindro(0.34, 0.34, 0.07, 64), borda = k.anel(0.34, 0.012);
  for (let i = 0; i < 7; i++) {
    const m = k.peca(k.malha(geo, ouro), k.malha(borda, ouro, [0, 0, 0], [Math.PI / 2, 0, 0]));
    const fim = new T.Vector3((k.rnd() - 0.5) * 0.06, -0.42 + i * 0.075, (k.rnd() - 0.5) * 0.06);
    m.position.copy(fim); pilha.push({ m, fim, atraso: i * 0.11, giro: 2 + k.rnd() * 3 }); g.add(m);
  }
  const frente = k.peca(k.malha(k.cilindro(0.3, 0.3, 0.06, 64), ouro, [0, 0, 0], [Math.PI / 2, 0, 0]),
                        k.malha(k.anel(0.19, 0.02), ouro, [0, 0, 0.035]));
  frente.position.set(0.42, 0.05, 0.25); g.add(frente);
  const h = k.halo(k.cor, 2.2); g.add(h);
  const fag = k.repetir(14, () => { const s = k.halo('#fff2b0', 0.09); g.add(s);
    return { s, a: k.rnd() * Math.PI * 2, v: 0.6 + k.rnd() * 0.8, d: k.rnd() * 0.5 }; });
  g.userData.animar = (s, t) => {
    for (const c of pilha) {
      const q = k.spring(s, c.atraso, { dur: 0.55, bounce: 0.3 });
      c.m.position.set(c.fim.x, k.lerp(1.6, c.fim.y, q), c.fim.z); c.m.rotation.x = (1 - q) * c.giro;
      c.m.visible = s > c.atraso;
    }
    const qf = k.spring(s, 0.75, { dur: 0.7, bounce: 0.35 });
    frente.scale.setScalar(Math.max(qf, 1e-3)); frente.rotation.y = (1 - qf) * 6 + Math.sin(t * 1.4) * 0.35;
    h.material.opacity = 0.5 * k.brilho * qf;
    for (const f of fag) {
      const u = k.clamp((s - 0.8 - f.d) / 0.7);
      f.s.position.set(Math.cos(f.a) * u * f.v, -0.1 + Math.sin(f.a) * u * f.v * 0.8 + u * 0.3, 0.3);
      f.s.material.opacity = u > 0 && u < 1 ? (1 - u) * k.brilho : 0;
    }
  };
  return g;
}
