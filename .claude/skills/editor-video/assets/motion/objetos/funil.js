// Funil de vidro: bolinhas (leads) caem girando por cima e sai uma moeda dourada embaixo.
export const info = { nome: 'funil', sinonimos: ['funil de vendas', 'leads', 'conversao', 'funnel'], cor: '#59D2FF',
  angulo: [0.35, 0] };
export default function criar(T, k) {
  const g = new T.Group(), perfil = [];
  for (let i = 0; i <= 24; i++) { const u = i / 24; perfil.push([u < 0.62 ? k.lerp(0.5, 0.09, k.ease.inOutQuad(u / 0.62)) : 0.09, 0.5 - u]); }
  const corpo = k.malha(k.torno(perfil), k.vidro('#dff6ff', 0.55)); g.add(corpo);
  const aro = k.malha(k.anel(0.5, 0.018, 80), k.metal(k.cor, 0.3), [0, 0.5, 0], [Math.PI / 2, 0, 0]); g.add(aro);
  const leads = k.repetir(16, (i) => { const m = k.malha(k.esfera(0.045, 20, 12), k.plastico(k.cor)); g.add(m);
    return { m, a: k.rnd() * Math.PI * 2, r: 0.15 + k.rnd() * 0.3, atraso: i * 0.09 }; });
  const moeda = k.malha(k.cilindro(0.11, 0.11, 0.025), k.ouro(), [0, -0.6, 0.05], [Math.PI / 2, 0, 0]); g.add(moeda);
  const h = k.halo('#ffd76a', 0.8); g.add(h);
  g.userData.animar = (s, t) => {
    const q = Math.max(k.spring(s, 0, { dur: 0.6, bounce: 0.3 }), 1e-3);
    corpo.scale.setScalar(q); aro.scale.setScalar(q);
    for (const l of leads) {
      const u = k.clamp((s - 0.4 - l.atraso) / 0.9), r = k.lerp(l.r, 0.02, u * u);
      l.m.position.set(Math.cos(l.a + u * 5) * r, k.lerp(0.95, -0.2, u * u), Math.sin(l.a + u * 5) * r);
      l.m.visible = u > 0 && u < 1;
    }
    const qm = k.spring(s, 1.5, { dur: 0.6, bounce: 0.35 });
    moeda.position.y = k.lerp(-0.2, -0.72, qm); moeda.scale.setScalar(Math.max(qm * 1.3, 1e-3)); moeda.rotation.z = t * 2.2;
    h.position.copy(moeda.position); h.material.opacity = 0.7 * k.brilho * qm;
  };
  return g;
}
