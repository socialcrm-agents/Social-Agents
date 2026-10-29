// Processador numa placa: linhas de energia correm pela placa e o núcleo acende.
export const info = { nome: 'chip', sinonimos: ['processador', 'cpu', 'tecnologia', 'computador', 'ia', 'inteligencia artificial'],
  cor: '#3DF5B0', angulo: [0.75, 0.6] };
export default function criar(T, k) {
  const g = new T.Group();
  g.add(k.malha(k.caixa(1.2, 0.04, 1.2, 0.015), k.fosco('#0f2a22', 0.6, 0.2), [0, -0.08, 0]));
  g.add(k.malha(k.caixa(0.56, 0.1, 0.56, 0.02), k.fosco('#1b1d22', 0.35, 0.4)));
  g.add(k.malha(k.caixa(0.4, 0.012, 0.4), k.metal('#8f949c', 0.45), [0, 0.056, 0]));
  const nucleo = k.malha(k.caixa(0.16, 0.014, 0.16), k.emissivo(k.cor, 0), [0, 0.064, 0]); g.add(nucleo);
  const pino = k.caixa(0.03, 0.02, 0.09), ouro = k.ouro();
  for (let i = 0; i < 8; i++) for (let s = 0; s < 4; s++) {
    const o = -0.21 + i * 0.06, rot = s * Math.PI / 2;
    g.add(k.malha(pino, ouro, [Math.cos(rot) * 0.32 + Math.sin(rot) * o, -0.03, Math.sin(rot) * 0.32 - Math.cos(rot) * o], [0, -rot, 0]));
  }
  const trilhas = k.repetir(12, (i) => {
    const lado = i % 4, o = -0.25 + (i >> 2) * 0.25, len = 0.12 + k.rnd() * 0.14, rot = lado * Math.PI / 2, d = 0.42 + len / 2;
    const m = k.malha(k.caixa(len, 0.006, 0.014), k.emissivo(k.cor, 0),
      [Math.cos(rot) * d - Math.sin(rot) * o, -0.055, Math.sin(rot) * d + Math.cos(rot) * o], [0, -rot, 0]);
    g.add(m); return { m, atraso: k.rnd() * 0.6 };
  });
  const h = k.halo(k.cor, 1.4); h.position.y = 0.1; g.add(h);
  g.userData.animar = (s, t) => {
    const q = Math.max(k.spring(s, 0, { dur: 0.7, bounce: 0.3 }), 1e-3);
    g.scale.setScalar(q); g.rotation.y = (1 - q) * 2.5;
    for (const tr of trilhas) tr.m.material.emissiveIntensity = k.clamp((s - 0.6 - tr.atraso) / 0.3) * (1.2 + 2 * (0.5 + 0.5 * Math.sin((t - tr.atraso) * 6)));
    const ac = k.clamp((s - 1.0) / 0.35);
    nucleo.material.emissiveIntensity = ac * (2.5 + Math.sin(t * 5)); h.material.opacity = 0.55 * k.brilho * ac;
  };
  return g;
}
