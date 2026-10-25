// Renderiza uma composição HTML em vídeo, quadro a quadro, no Chromium headless (Playwright).
//
//   node motion_render.mjs <job.json>
//
// job.json: {page: "/templates/x.html" ou "/work/...", out: "clip.mov", w, h, fps, duration, params,
//            roots: {"/": assets/motion, "/fonts/": assets/fonts, "/work/": pasta work do projeto}}
// Saída: .mov (PNG com alfa; MJPEG quando opaque). Sem WebGL a página roda com --disable-gpu (raster por CPU
// em cada aba, ~3x mais rápido); composições Three.js pedem webgl: true (SwiftShader).

import { createServer } from 'node:http';
import { mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import { execSync, spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
function loadPlaywright() {
  let globalRoot = '';
  try { globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim(); } catch {}
  const candidates = ['playwright', 'playwright-core', '/opt/node-tools/node_modules/playwright',
    path.join(globalRoot, 'playwright'), path.join(globalRoot, 'playwright-core')];
  for (const p of candidates) {
    try { return require(p); } catch {}
  }
  throw new Error('Playwright não encontrado. Rode: npm install -g playwright && npx playwright install chromium');
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.css': 'text/css' };

function serve(roots) {
  const entries = Object.entries(roots).sort((a, b) => b[0].length - a[0].length);
  const server = createServer(async (req, res) => {
    const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    for (const [prefix, dir] of entries) {
      if (!url.startsWith(prefix)) continue;
      const file = path.resolve(dir, '.' + url.slice(prefix.length - 1));
      if (!file.startsWith(path.resolve(dir))) break;
      try {
        await stat(file);
        res.writeHead(200, { 'content-type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
        res.end(await readFile(file));
        return;
      } catch { break; }
    }
    res.writeHead(404); res.end('not found');
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

const job = JSON.parse(await readFile(process.argv[2], 'utf8'));
const { w, h, fps, duration } = job;
const frames = Math.max(1, Math.round(duration * fps));
const server = await serve(job.roots);
const port = server.address().port;
const { chromium } = loadPlaywright();
const browser = await chromium.launch({
  executablePath: process.env.EDITOR_VIDEO_CHROMIUM || undefined,
  args: [...(job.webgl ? [] : ['--disable-gpu']), '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox', '--force-color-profile=srgb',
         '--hide-scrollbars', '--mute-audio'],
});
// Vários quadros em paralelo: cada worker é uma aba (processo de render próprio) cuidando de um trecho do clipe.
const opaque = !!job.opaque;
const ext = opaque ? 'jpg' : 'png';
const tmp = await mkdtemp(path.join(os.tmpdir(), 'motion-'));
const logs = [];
const workers = Math.max(1, Math.min(job.workers || os.cpus().length, 6, frames));

async function openPage() {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  page.on('console', (m) => logs.push(m.text()));
  page.on('pageerror', (e) => logs.push('ERRO JS: ' + e.message));
  await page.addInitScript((cfg) => { window.__MOTION__ = cfg; }, { w, h, fps, duration, params: job.params || {} });
  await page.goto(`http://127.0.0.1:${port}${job.page}`, { waitUntil: 'load' });
  try {
    await page.waitForFunction(() => typeof window.__motionSeek === 'function', null, { timeout: 20000, polling: 100 });
  } catch {
    console.error(logs.join('\n'));
    throw new Error('A composição não registrou window.__motionSeek (importe /lib/runtime.js).');
  }
  await page.evaluate(() => document.fonts && document.fonts.ready);
  return page;
}

const t0 = Date.now();
const per = Math.ceil(frames / workers);
await Promise.all(Array.from({ length: workers }, async (_, k) => {
  const page = await openPage();
  for (let i = k * per; i < Math.min(frames, (k + 1) * per); i++) {
    await page.evaluate((tt) => window.__motionSeek(tt), i / fps);
    const shot = await page.screenshot(opaque ? { type: 'jpeg', quality: 92, animations: 'disabled' }
      : { type: 'png', omitBackground: true, animations: 'disabled' });
    await writeFile(path.join(tmp, `${String(i + 1).padStart(5, '0')}.${ext}`), shot);
  }
  await page.close();
}));
await browser.close();
server.close();
await new Promise((resolve, reject) => {
  const ff = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(fps),
    '-i', path.join(tmp, `%05d.${ext}`), ...(opaque ? ['-c:v', 'mjpeg', '-q:v', '2', '-pix_fmt', 'yuvj420p']
    : ['-c:v', 'png', '-pix_fmt', 'rgba']), job.out], { stdio: ['ignore', 'inherit', 'inherit'] });
  ff.on('close', (c) => (c === 0 ? resolve() : reject(new Error('ffmpeg falhou ao montar o clipe'))));
});
await rm(tmp, { recursive: true, force: true });
const errs = logs.filter((l) => l.startsWith('ERRO'));
if (errs.length) { console.error(errs.join('\n')); process.exit(2); }
console.log(`OK ${frames} quadros em ${((Date.now() - t0) / 1000).toFixed(1)}s (${workers} abas) -> ${job.out}`);
