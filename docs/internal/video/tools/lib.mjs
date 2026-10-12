// Recording helpers for Flock videos: launch Chromium, screencast a page into
// JPEG frames with timestamps, and drive the dashboard (see ../README.md).
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';

const require = createRequire(import.meta.url);
export const { chromium } = require('playwright');

/** docs/internal/video: frames/ and out/ live here (both gitignored). */
export const VIDEO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const FRAMES = path.join(VIDEO, 'frames');
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/**
 * Seconds since the epoch on a monotonic clock. The screencast's own frame
 * timestamps follow the wall clock, which can step back: on WSL by about 2 s
 * every 30 s (time sync), and the stage would play those frames out of order.
 */
const now = () => (performance.timeOrigin + performance.now()) / 1000;

/**
 * Chromium, one browser per device scale: the screencast sends frames at device
 * pixels only when the browser itself runs at the page's scale
 * (--force-device-scale-factor); with the page's deviceScaleFactor alone a 1.5x
 * page still comes as CSS pixels, 1280x720 instead of 1920x1080.
 */
export async function launch() {
  const browsers = new Map();
  return {
    at(scale) {
      if (!browsers.has(scale)) {
        browsers.set(scale, chromium.launch({
          // CHROME points at a Chromium build when Playwright's own is not installed
          executablePath: process.env.CHROME || undefined,
          args: ['--force-color-profile=srgb', `--force-device-scale-factor=${scale}`],
        }));
      }
      return browsers.get(scale);
    },
    async close() {
      for (const browser of browsers.values()) await (await browser).close();
    },
  };
}

export async function newPage(browser, width, height, scale = 1, colorScheme = 'dark') {
  const context = await (await browser.at(scale)).newContext({ viewport: { width, height }, deviceScaleFactor: scale, colorScheme });
  return context.newPage();
}

/**
 * Screencast `page` into FRAMES/<name>-raw: one JPEG per repaint and index.json
 * with each frame's time (seconds since the epoch, monotonic: when the frame
 * arrived). mark(name) notes a moment to cut on.
 * Pages repaint only when something changes, so a still page gives few frames;
 * the stage holds the last frame and dissolves jumps.
 */
export async function record(page, name, { quality = 92 } = {}) {
  const dir = path.join(FRAMES, `${name}-raw`);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const client = await page.context().newCDPSession(page);
  const frames = [];
  const marks = [];
  let n = 0;
  client.on('Page.screencastFrame', async ({ data, sessionId }) => {
    const t = now();
    const file = `f${String(n++).padStart(6, '0')}.jpg`;
    fs.writeFileSync(path.join(dir, file), Buffer.from(data, 'base64'));
    frames.push({ file, t });
    try { await client.send('Page.screencastFrameAck', { sessionId }); } catch {}
  });
  const vp = page.viewportSize();
  const scale = await page.evaluate(() => window.devicePixelRatio);
  await client.send('Page.startScreencast', {
    format: 'jpeg', quality, everyNthFrame: 1,
    maxWidth: Math.round(vp.width * scale), maxHeight: Math.round(vp.height * scale),
  });
  return {
    mark(markName) { marks.push({ name: markName, t: now() }); },
    async stop() {
      await page.evaluate(() => new Promise(requestAnimationFrame));
      await sleep(300);
      await client.send('Page.stopScreencast');
      fs.writeFileSync(path.join(dir, 'index.json'), JSON.stringify({ frames, marks }, null, 1));
      return frames.length;
    },
  };
}

// ---- The dashboard -----------------------------------------------------------

/** Open the dashboard on `port` and wait until it is live. */
export async function dashboard(browser, port, { width = 1280, height = 720, scale = 1.5, ready = 'text=Live' } = {}) {
  const page = await newPage(browser, width, height, scale);
  await page.goto(`http://127.0.0.1:${port}/`);
  if (ready) await page.locator(ready).first().waitFor({ timeout: 30000 });
  await sleep(2500);
  return page;
}

/** Run a command of the ⌘K palette ("fit", "last hour", "paper", ...). */
export async function palette(page, query) {
  await page.keyboard.press('Control+k');
  await page.locator('input[role=combobox]').fill(query);
  await page.locator('[role=option][aria-selected=true]').waitFor({ timeout: 5000 });
  await page.keyboard.press('Enter');
  await sleep(900);
}

export const lastHour = (page) => palette(page, 'last hour');
export const fit = (page) => page.locator('[aria-label="Fit to screen"]').click();
export const blackboard = async (page) => {
  await page.locator('nav[aria-label="Views"] button:has-text("Blackboard")').click();
  await sleep(2000);
};

/** The Blackboard's artifacts of the last hour, as the dashboard reads them. */
export async function snapshot(port) {
  const response = await fetch(`http://127.0.0.1:${port}/api/dashboard/graph`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ viewMode: 'blackboard', filters: { time_range: { preset: 'last1hour' } }, options: { include_statistics: false } }),
  });
  return (await response.json()).nodes;
}

export const decisionsOf = (nodes) => nodes.filter((n) => n.data?.decision).map((n) => ({ id: n.id, cid: n.data.correlationId, ...n.data.decision }));
