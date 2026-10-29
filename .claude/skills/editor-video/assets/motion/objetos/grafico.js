// Gráfico de barras 3D subindo uma a uma, com a seta de crescimento. valores: params.valores (0..1).
export const info = { nome: 'gráfico', sinonimos: ['grafico', 'crescimento', 'resultado', 'vendas subindo', 'chart'],
  cor: '#22C55E', angulo: [0.25, -0.45] };
export default function criar(T, k) {
  const vals = (k.params?.valores?.length ? k.params.valores : [0.25, 0.4, 0.55, 0.78, 1]).slice(0, 7);
  const g = new T.Group(), n = vals.length, larg = 1.2 / n;
  g.add(k.malha(k.caixa(1.35, 0.03, 0.4, 0.01), k.fosco('#20232b', 0.5, 0.3), [0, -0.5, 0]));
  const barras = vals.map((v, i) => { const ult = i === n - 1;
    const m = k.malha(k.caixa(larg * 0.7, 1, 0.26, 0.02), new T.MeshStandardMaterial({ color: ult ? k.cor : '#e9eef5',
      metalness: 0.3, roughness: 0.3, emissive: ult ? k.cor : '#000', emissiveIntensity: ult ? 0.35 : 0 }), [-0.6 + larg * (i + 0.5), 0, 0]);
    g.add(m); return { m, v, atraso: 0.12 * i }; });
  const seta = new T.Group(), mat = k.fosco(k.cor, 0.3, 0.3);
  const haste = k.malha(k.cilindro(0.02, 0.02, 1, 12), mat), ponta = k.malha(k.cone(0.07, 0.15, 20), mat);
  seta.add(haste, ponta); g.add(seta);
  const h = k.halo(k.cor, 1.2); g.add(h);
  const a = new T.Vector3(-0.55, -0.35, 0.25), b = new T.Vector3(0.62, 0.62, 0.25), dir = b.clone().sub(a).normalize();
  seta.position.copy(a); seta.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), dir);
  haste.scale.y = a.distanceTo(b); haste.position.y = a.distanceTo(b) / 2; ponta.position.y = a.distanceTo(b);
  g.userData.animar = (s) => {
    for (const c of barras) { const alt = Math.max(c.v * 0.95 * k.spring(s, c.atraso, { dur: 0.6, bounce: 0.25 }), 1e-3);
      c.m.scale.y = alt; c.m.position.y = -0.485 + alt / 2; }
    const qs = k.ease.outCubic(k.clamp((s - 0.15 * n) / 0.6)), len = Math.max(a.distanceTo(b) * qs, 1e-3);
    haste.scale.y = len; haste.position.y = len / 2; ponta.position.y = len; seta.visible = qs > 0;
    h.position.copy(a.clone().lerp(b, qs)); h.material.opacity = 0.6 * k.brilho * qs;
  };
  return g;
}
