// Kit para MODELAR OBJETOS 3D no código (usado pelos arquivos de assets/motion/objetos/*.js e pelo template
// objeto_cinema). Cada objeto é um arquivo curto que monta peças com estes materiais e formas; o template cuida
// de tamanho, posição na tela, luz, brilho, entrada animada e saída.
//
// Contrato de um objeto (assets/motion/objetos/<nome>.js):
//   export const info = { nome: 'sofá', sinonimos: ['sofa', 'poltrona'], cor: '#C9773B', entrada: 'monta' };
//   export default function criar(T, k) {          // T = THREE, k = este kit
//     const g = new T.Group();
//     g.add(k.malha(k.caixa(1.6, 0.4, 0.8, 0.08), k.tecido('#C9773B'), [0, 0.2, 0]));   // cada filho = 1 peça
//     return g;                                     // qualquer tamanho: o template normaliza e centraliza
//   }
//   export function animar(g, k, s, t) { ... }      // opcional: animação própria (s = segundos desde a entrada)
// As peças (filhos diretos do grupo) são o que voa/monta/explode na entrada "monta" e em "explodir".
import * as THREE from 'three';
import { mergeVertices } from '/vendor/three/addons/utils/BufferGeometryUtils.js';

const k = {};

// ---------------------------------------------------------------------------------------------------- materiais
k.fosco = (cor, rug = 0.6, met = 0.05) => new THREE.MeshStandardMaterial({ color: cor, roughness: rug, metalness: met });
k.plastico = (cor) => new THREE.MeshPhysicalMaterial({ color: cor, roughness: 0.32, metalness: 0, clearcoat: 0.6,
                                                      clearcoatRoughness: 0.25 });
k.metal = (cor = '#c9ccd2', rug = 0.28) => new THREE.MeshStandardMaterial({ color: cor, roughness: rug, metalness: 1 });
k.ouro = () => k.metal('#f5c04a', 0.22);
k.prata = () => k.metal('#d9dde3', 0.2);
k.madeira = (cor = '#9b6a43') => {
  const c = document.createElement('canvas'); c.width = 256; c.height = 256;
  const g = c.getContext('2d'); g.fillStyle = cor; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 46; i++) {                      // veios
    g.strokeStyle = `rgba(40,20,5,${0.05 + 0.12 * k.rnd()})`; g.lineWidth = 1 + 3 * k.rnd();
    const y = k.rnd() * 256; g.beginPath(); g.moveTo(0, y);
    g.bezierCurveTo(85, y + 10 * (k.rnd() - 0.5), 170, y + 10 * (k.rnd() - 0.5), 256, y); g.stroke();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return new THREE.MeshStandardMaterial({ map: t, roughness: 0.55, metalness: 0 });
};
k.tecido = (cor) => new THREE.MeshPhysicalMaterial({ color: cor, roughness: 0.9, sheen: 1, sheenRoughness: 0.6,
                                                    sheenColor: new THREE.Color(cor).offsetHSL(0, -0.1, 0.25) });
k.vidro = (cor = '#ffffff', op = 0.5) => new THREE.MeshPhysicalMaterial({ color: cor, roughness: 0.04, metalness: 0,
  transmission: 1, thickness: 0.2, ior: 1.45, transparent: true, opacity: op, side: THREE.DoubleSide });
k.borracha = (cor = '#1d1f24') => k.fosco(cor, 0.85, 0);
k.emissivo = (cor, i = 2) => new THREE.MeshStandardMaterial({ color: '#000', emissive: cor, emissiveIntensity: i });
k.holograma = (cor = '#41E2FF', op = 0.55) => new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: op,
  wireframe: false, depthWrite: false, toneMapped: false });

// ---------------------------------------------------------------------------------------------------- formas
// caixa com cantos arredondados (o que tira a cara de "jogo" dos objetos)
k.caixa = (w, h, d, r = 0) => {
  if (r <= 0) return new THREE.BoxGeometry(w, h, d);
  r = Math.min(r, w / 2 - 1e-3, h / 2 - 1e-3, d / 2 - 1e-3);
  const s = new THREE.Shape(), x = -w / 2 + r, y = -h / 2 + r, ww = w - 2 * r, hh = h - 2 * r;
  s.absarc(x, y, r, Math.PI, 1.5 * Math.PI); s.absarc(x + ww, y, r, 1.5 * Math.PI, 2 * Math.PI);
  s.absarc(x + ww, y + hh, r, 0, 0.5 * Math.PI); s.absarc(x, y + hh, r, 0.5 * Math.PI, Math.PI);
  const g = new THREE.ExtrudeGeometry(s, { depth: d - 2 * r, bevelEnabled: true, bevelSize: r * 0.98,
                                           bevelThickness: r, bevelSegments: 5, curveSegments: 8 });
  g.translate(0, 0, -(d - 2 * r) / 2);
  g.computeVertexNormals();
  return g;
};
k.cilindro = (rTopo, rBase, h, seg = 48) => new THREE.CylinderGeometry(rTopo, rBase ?? rTopo, h, seg);
k.esfera = (r, ws = 48, hs = 32) => new THREE.SphereGeometry(r, ws, hs);
k.cone = (r, h, seg = 48) => new THREE.ConeGeometry(r, h, seg);
k.anel = (r, tubo, seg = 64, arco = Math.PI * 2) => new THREE.TorusGeometry(r, tubo, 16, seg, arco);
k.capsula = (r, h) => new THREE.CapsuleGeometry(r, h, 8, 24);
// torno: perfil [[raio, altura], ...] girado em volta do eixo Y (vasos, copos, garrafas, lâmpadas, troféus)
k.torno = (perfil, seg = 64) => new THREE.LatheGeometry(perfil.map(([r, y]) => new THREE.Vector2(Math.max(r, 1e-3), y)), seg);
// tubo por uma curva [[x,y,z], ...] (cabos, alças, fios, molas)
k.tubo = (pontos, raio, seg = 120, fechado = false) => new THREE.TubeGeometry(
  new THREE.CatmullRomCurve3(pontos.map((p) => new THREE.Vector3(...p)), fechado), seg, raio, 12, fechado);
// extrusão de um contorno 2D [[x,y], ...] com espessura e chanfro (silhuetas: chave, raio, coração, seta)
k.extrusao = (contorno, prof, chanfro = 0.02) => {
  const s = new THREE.Shape(contorno.map(([x, y]) => new THREE.Vector2(x, y)));
  const g = new THREE.ExtrudeGeometry(s, { depth: prof, bevelEnabled: chanfro > 0, bevelSize: chanfro,
                                           bevelThickness: chanfro, bevelSegments: 4, curveSegments: 24 });
  g.translate(0, 0, -prof / 2);
  return g;
};
k.suave = (geo) => { const g = mergeVertices(geo); g.computeVertexNormals(); return g; };

// malha posicionada: k.malha(geo, mat, [x,y,z], [rx,ry,rz], escala)
k.malha = (geo, mat, pos = [0, 0, 0], rot = [0, 0, 0], esc = 1) => {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(...pos); m.rotation.set(...rot);
  if (Array.isArray(esc)) m.scale.set(...esc); else m.scale.setScalar(esc);
  m.castShadow = m.receiveShadow = true;
  return m;
};
// agrupa várias malhas numa peça só (ela voa/monta junto)
k.peca = (...malhas) => { const g = new THREE.Group(); malhas.forEach((m) => g.add(m)); return g; };
// repete uma peça em círculo ou em linha
k.repetir = (n, fazer) => Array.from({ length: n }, (_, i) => fazer(i, n));

// ---------------------------------------------------------------------------------------------------- brilho
const _halo = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d'), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.2, 'rgba(255,255,255,.5)');
  gr.addColorStop(0.55, 'rgba(255,255,255,.12)'); gr.addColorStop(0.92, 'rgba(255,255,255,0)');
  gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
})();
k.texturaHalo = _halo;
k.halo = (cor, tam = 1) => {
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: _halo, color: cor, depthWrite: false, transparent: true,
                                                         opacity: 0, toneMapped: false }));
  sp.scale.setScalar(tam); sp.userData.halo = true; return sp;
};

// ---------------------------------------------------------------------------------------------------- utilidades
let _s = 7;
k.rnd = () => ((_s = (_s * 16807) % 2147483647) / 2147483647);   // aleatório fixo: o mesmo quadro sai igual
k.semente = (n) => { _s = n; };
k.lerp = (a, b, x) => a + (b - a) * x;
k.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
k.THREE = THREE;

export default k;
