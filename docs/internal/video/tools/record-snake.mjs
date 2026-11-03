// Scene PLAY: the Snake demo and its Flow, recorded side by side.
// node record-snake.mjs GAME_PORT FLOCK_PORT [seconds] [take]
// (examples/16-sinks/02_snake.py --port GAME_PORT --flock-port FLOCK_PORT, a fresh process)
import { launch, newPage, record, sleep } from './lib.mjs';
const [game_port = 8792, flock_port = 8344, seconds = 32, take = 'snake'] = process.argv.slice(2);
const browser = await launch();
const game = await newPage(browser, 480, 800, 1.5);
const board = await newPage(browser, 1280, 860, 1.5);

// Warm-up, not recorded: one step published here (in a run of its own) brings
// every agent onto the Flow, which is fitted once and keeps still (no
// auto-arrange) while the take plays
await board.goto(`http://127.0.0.1:${flock_port}/`);
await game.goto(`http://127.0.0.1:${game_port}/`);
// Recording only: the board above its bars, no address box
await game.addStyleTag({ content: `
  body { flex-direction: column; align-items: center; padding: 24px; gap: 22px; }
  .side { width: 420px; }
  label, .hint { display: none !important; }
` });
await fetch(`http://127.0.0.1:${flock_port}/api/v1/artifacts`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    type: 'SnakeState',
    correlation_id: crypto.randomUUID(),
    payload: { game: 'warm-up', step: 0, eaten: 0, heading: 'up', moves: { up: 'empty, food 3 away', down: 'own body', left: 'empty, food 5 away', right: 'empty, food 4 away' } },
  }),
});
await sleep(6000);
await board.locator('[aria-label="Fit to screen"]').click();
await sleep(1200);
const arrange = board.locator('button[role=switch]:has-text("Auto-arrange")');
if ((await arrange.getAttribute('aria-checked')) === 'true') await arrange.click();
await sleep(1500);

const recGame = await record(game, `${take}-game`);
const recBoard = await record(board, `${take}-board`);
await sleep(1500);
recGame.mark('start'); recBoard.mark('start');
await game.locator('#toggle').click();  // Start
await sleep(Number(seconds) * 1000);
console.log('game frames', await recGame.stop(), 'board frames', await recBoard.stop());
await browser.close();
