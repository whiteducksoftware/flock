// Render the stage (../README.md): node render.mjs --w 1920 --h 1080 [--at 1,5.5,20] [--all] [--name flock-16x9]
//   --at   preview: PNGs of the frames at these seconds (out/preview-<name>/)
//   --all  every frame as JPEG (out/frames-<name>/), then an MP4 (out/<name>.mp4)
import http from 'http';
import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { launch, newPage, VIDEO as ROOT } from './lib.mjs';

// Geist comes from the dashboard's dependencies (npm install in src/flock/frontend)
const FONTS = path.resolve(ROOT, '../../../src/flock/frontend/node_modules/@fontsource-variable');
const FONT_FILES = {
  'geist-latin-wght-normal.woff2': path.join(FONTS, 'geist/files/geist-latin-wght-normal.woff2'),
  'geist-mono-latin-wght-normal.woff2': path.join(FONTS, 'geist-mono/files/geist-mono-latin-wght-normal.woff2'),
};
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i < 0 ? d : process.argv[i + 1]; };
const W = Number(arg('w', 1920)), H = Number(arg('h', 1080));
const name = arg('name', `flock-${W}x${H}`);
const at = arg('at', null);
const all = process.argv.includes('--all');

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const font = pathname.startsWith('/stage/fonts/') && FONT_FILES[path.basename(pathname)];
  const file = font || path.join(ROOT, pathname);
  if ((!font && !file.startsWith(ROOT)) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'cache-control': 'max-age=3600' });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const browser = await launch();
const page = await newPage(browser, W, H, 1);
page.on('pageerror', (e) => console.error('page error:', e.message));
await page.goto(`http://127.0.0.1:${port}/stage/index.html?w=${W}&h=${H}`);
const total = await page.evaluate(() => window.ready);
const fps = 30;
console.log(`${name}: ${W}x${H}, ${total} frames, ${(total / fps).toFixed(1)} s`);

if (at) {
  const out = path.join(ROOT, 'out', `preview-${name}`);
  fs.mkdirSync(out, { recursive: true });
  for (const s of at.split(',').map(Number)) {
    const n = Math.min(total - 1, Math.round(s * fps));
    await page.evaluate((n) => window.renderFrame(n), n);
    await page.screenshot({ path: path.join(out, `t${String(s).padStart(5, '0')}.png`) });
  }
  console.log('preview in', out);
}

if (all) {
  const out = path.join(ROOT, 'out', `frames-${name}`);
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  const started = Date.now();
  for (let n = 0; n < total; n++) {
    await page.evaluate((n) => window.renderFrame(n), n);
    await page.screenshot({ path: path.join(out, `${String(n).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 95 });
    if (n % 300 === 0) console.log(`frame ${n}/${total} after ${((Date.now() - started) / 1000).toFixed(0)} s`);
  }
  const mp4 = path.join(ROOT, 'out', `${name}.mp4`);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(fps), '-i', path.join(out, '%05d.jpg'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4]);
  console.log('video', mp4, `${(fs.statSync(mp4).size / 1e6).toFixed(1)} MB`);
}

await browser.close();
server.close();
