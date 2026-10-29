// Notebook aberto, alumínio, tela com painel de gráficos e teclado.
export const info = { nome: 'notebook', sinonimos: ['laptop', 'computador', 'macbook', 'trabalho online'], cor: '#4FA3FF', entrada: 'monta', angulo: [0.3, -0.45] };
export default function criar(T, k) {
  const g = new T.Group(), alu = k.metal('#c7cbd2', 0.35);
  g.add(k.malha(k.caixa(1.3, 0.04, 0.9, 0.02), alu, [0, 0, 0]));
  g.add(k.malha(k.caixa(1.1, 0.006, 0.45, 0.002), k.borracha('#2a2c31'), [0, 0.022, -0.12]));
  g.add(k.malha(k.caixa(0.42, 0.004, 0.24, 0.01), k.metal('#b7bbc2', 0.4), [0, 0.022, 0.27]));
  const c = document.createElement('canvas'); c.width = 512; c.height = 320; const x = c.getContext('2d');
  x.fillStyle = '#0f1420'; x.fillRect(0, 0, 512, 320);
  for (let i = 0; i < 7; i++) { x.fillStyle = i === 6 ? '#4FA3FF' : '#2c3a55'; const h = 40 + i * 28; x.fillRect(40 + i * 64, 290 - h, 40, h); }
  x.strokeStyle = '#3DF5B0'; x.lineWidth = 6; x.beginPath(); x.moveTo(40, 230); x.lineTo(470, 50); x.stroke();
  const tex = new T.CanvasTexture(c); tex.colorSpace = T.SRGBColorSpace;
  const tampa = k.peca(k.malha(k.caixa(1.3, 0.82, 0.03, 0.02), alu),
                       k.malha(k.caixa(1.2, 0.72, 0.002, 0), new T.MeshBasicMaterial({ map: tex, toneMapped: false }), [0, 0, 0.017]));
  tampa.position.set(0, 0.42, -0.47); tampa.rotation.x = -0.25; g.add(tampa);
  return g;
}
