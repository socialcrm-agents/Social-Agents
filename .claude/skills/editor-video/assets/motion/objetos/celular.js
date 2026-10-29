// Smartphone moderno: corpo de alumínio, tela acesa com app colorido, câmeras atrás.
export const info = { nome: 'celular', sinonimos: ['smartphone', 'telefone', 'iphone', 'app', 'aplicativo', 'phone'], cor: '#7C5CFF',
  entrada: 'gira', angulo: [0.15, -0.35] };
export default function criar(T, k) {
  const g = new T.Group();
  g.add(k.malha(k.caixa(0.5, 1.0, 0.06, 0.06), k.metal('#3a3d45', 0.35)));
  const c = document.createElement('canvas'); c.width = 256; c.height = 512; const x = c.getContext('2d');
  const gr = x.createLinearGradient(0, 0, 256, 512); gr.addColorStop(0, '#7C5CFF'); gr.addColorStop(1, '#22d3ee');
  x.fillStyle = gr; x.fillRect(0, 0, 256, 512);
  for (let i = 0; i < 12; i++) { x.fillStyle = 'rgba(255,255,255,.85)'; x.beginPath(); x.roundRect(28 + (i % 4) * 54, 90 + Math.floor(i / 4) * 64, 40, 40, 10); x.fill(); }
  x.fillStyle = 'rgba(255,255,255,.9)'; x.beginPath(); x.roundRect(28, 330, 200, 120, 18); x.fill();
  const tex = new T.CanvasTexture(c); tex.colorSpace = T.SRGBColorSpace;
  g.add(k.malha(k.caixa(0.46, 0.96, 0.005, 0), new T.MeshBasicMaterial({ map: tex, toneMapped: false }), [0, 0, 0.032]));
  g.add(k.malha(k.caixa(0.12, 0.03, 0.004, 0.0015), k.borracha('#0b0b0d'), [0, 0.45, 0.036]));
  for (const [px, py] of [[-0.14, 0.38], [-0.14, 0.27]]) g.add(k.malha(k.cilindro(0.04, 0.04, 0.02, 32), k.vidro('#1c2230', 0.9), [px, py, -0.04], [Math.PI / 2, 0, 0]));
  return g;
}
