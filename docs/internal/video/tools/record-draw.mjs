// Scene SEE: Quick, Draw! on a vision model and its Flow, side by side.
// node record-draw.mjs APP_PORT FLOCK_PORT [drawings] [take]
// (examples/16-sinks/03_quick_draw.py with its APP_PORT / FLOCK_PORT set to these)
import { launch, newPage, record, sleep } from './lib.mjs';
import { DRAWINGS, draw } from './drawings.mjs';
const [app_port = 8793, flock_port = 8344, want = 4, take = 'draw'] = process.argv.slice(2);
const SKIP = ['tree', 'flower'];  // too easy to mistake for something else
const browser = await launch();
const app = await newPage(browser, 864, 560, 1.5);
const board = await newPage(browser, 1280, 860, 1.5);
await board.goto(`http://127.0.0.1:${flock_port}/`);
await app.goto(`http://127.0.0.1:${app_port}/`);
await sleep(5000);

// A prompt we can draw: ask for new ones until one comes
async function drawable(done = []) {
  for (let tries = 0; tries < 40; tries++) {
    const prompt = (await app.locator('#prompt b').textContent()).trim();
    if (DRAWINGS[prompt] && !done.includes(prompt) && !SKIP.includes(prompt)) return prompt;
    await app.locator('#new').click();
    await sleep(400);
  }
  throw new Error('no drawable prompt');
}

// Warm-up, not recorded: every agent and the guesser's thumbnails are on the
// board, then the Flow is fitted once and keeps still (no auto-arrange), so
// the card only grows during the take instead of jumping and zooming
{
  const prompt = await drawable();
  const box = await app.locator('#canvas').boundingBox();
  await draw(app, DRAWINGS[prompt](), { box, pace: 4, pause: 900 });
  await sleep(4000);
  await board.locator('[aria-label="Fit to screen"]').click();
  await sleep(1200);
  const arrange = board.locator('button[role=switch]:has-text("Auto-arrange")');
  if ((await arrange.getAttribute('aria-checked')) === 'true') await arrange.click();
  await app.locator('#new').click();
  await sleep(1500);
}

const recApp = await record(app, `${take}-app`);
const recBoard = await record(board, `${take}-board`);
const done = [];
while (done.length < Number(want)) {
  const prompt = await drawable(done);
  recApp.mark(`start:${prompt}`); recBoard.mark(`start:${prompt}`);
  const box = await app.locator('#canvas').boundingBox();
  for (const stroke of DRAWINGS[prompt]()) {
    await draw(app, [stroke], { box, pace: 7, pause: 1200 });  // a pause for each stroke's guess
  }
  for (let w = 0; w < 10 && !(await app.locator('#status .got').count()); w++) await sleep(500);
  console.log(prompt, '->', (await app.locator('#status').textContent()).trim());
  recApp.mark(`end:${prompt}`); recBoard.mark(`end:${prompt}`);
  done.push(prompt);
  await sleep(2500);
  if (done.length < Number(want)) { await app.locator('#new').click(); await sleep(600); }
}
console.log('app frames', await recApp.stop(), 'board frames', await recBoard.stop());
await browser.close();
