// Lâmpada de vidro desce, o filamento em espiral esquenta, pisca e ACENDE com halo (ideia!).
export const info = { nome: 'lâmpada', sinonimos: ['lampada', 'ideia', 'insight', 'luz', 'bulb'], cor: '#FFD66B', angulo: [0.1, 0] };
export default function criar(T, k) {
  const g = new T.Group(), perfil = [];
  for (let i = 0; i <= 30; i++) {
    const a = -Math.PI / 2 + (i / 30) * Math.PI * 1.25;
    perfil.push([i < 24 ? 0.32 * Math.cos(a) : k.lerp(0.32 * Math.cos(a), 0.14, (i - 24) / 6), 0.32 * Math.sin(a) + 0.12]);
  }
  perfil.reverse(); perfil.push([0.14, -0.16]);
  const bulbo = k.malha(k.torno(perfil), k.vidro('#ffffff', 0.5)); g.add(bulbo);
  const metal = k.metal('#b9bcc3', 0.3);
  g.add(k.malha(k.cilindro(0.14, 0.12, 0.2, 32), metal, [0, -0.26, 0]));
  for (let i = 0; i < 4; i++) g.add(k.malha(k.anel(0.135, 0.008, 32), metal, [0, -0.33 + i * 0.045, 0], [Math.PI / 2, 0, 0]));
  const esp = []; for (let i = 0; i <= 120; i++) { const u = i / 120, a = u * Math.PI * 14; esp.push([k.lerp(-0.09, 0.09, u), 0.1 + Math.sin(a) * 0.018, Math.cos(a) * 0.018]); }
  const fil = k.malha(k.tubo(esp, 0.005, 240), k.emissivo('#ffb347', 0)); g.add(fil);
  for (const x of [-0.09, 0.09]) g.add(k.malha(k.cilindro(0.004, 0.004, 0.27, 6), k.metal('#9aa0a8', 0.4), [x, -0.035, 0]));
  const luz = new T.PointLight('#ffd27a', 0, 6); luz.position.y = 0.1; g.add(luz);
  const h = k.halo(k.cor, 2.6); h.position.y = 0.1; g.add(h);
  g.userData.animar = (s, t) => {
    const q = k.spring(s, 0, { dur: 0.6, bounce: 0.35 });
    g.position.y = k.lerp(1.2, 0, q); g.rotation.z = (1 - q) * 0.4;
    const ac = k.clamp((s - 0.7) / 0.25), fl = ac < 1 ? (Math.sin(s * 60) > 0 ? 1 : 0.3) * ac : 1;
    fil.material.emissiveIntensity = 6 * fl; luz.intensity = 4 * fl;
    bulbo.material.emissive = new T.Color('#ffcf66'); bulbo.material.emissiveIntensity = 0.45 * fl;
    h.material.opacity = 0.9 * k.brilho * fl;
  };
  return g;
}
