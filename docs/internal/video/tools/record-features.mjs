// The feature clips: one short dashboard clip per feature, 1280x720 CSS at 1.5x
// (1920x1080 frames, the UI 1.5x larger than at 1080p).
// node record-features.mjs [clip ...]   (no names: all clips)
// Ports: PORTS='{"escalate": 8461, ...}' overrides the table below.
//   Decision examples: python fake_models.py examples/15-decisions/NN_x.py --port P
//   Dashboard clips:  examples/04-misc/10_dashboard_triage_demo.py --port P
//   before:           the same demo from a worktree of the old dashboard (main before the rework)
import { launch, record, sleep, dashboard, lastHour, fit, blackboard, snapshot, decisionsOf, palette } from './lib.mjs';

const PORTS = {
  escalate: 8461, vote: 8462, shadow: 8463, explain: 8464, tournament: 8465,
  checklist: 8466, coverage: 8467, review: 8469,
  lanes: 8470, focus: 8470, palette: 8470, theme: 8470, after: 8470, before: 8471,
  ...JSON.parse(process.env.PORTS || '{}'),
};
const only = process.argv.slice(2);
const browser = await launch();

async function clip(name, prepare, act, { seconds = 6, ready = 'text=Live' } = {}) {
  if (only.length && !only.includes(name)) return;
  const page = await dashboard(browser, PORTS[name], { ready });
  const ctx = await prepare(page);
  await sleep(1200);
  const rec = await record(page, `clip-${name}`);
  await sleep(900);
  rec.mark('act');  // the stage cuts each clip from this moment
  await act(page, ctx);
  await sleep(seconds * 1000);
  console.log(name, 'frames', await rec.stop());
  await page.context().close();
}

// The lane of the newest decision that passes `test`, scrolled into view
const laneOf = (port, test, label = null) => async (page) => {
  const candidates = decisionsOf(await snapshot(port)).filter(test).reverse();
  await lastHour(page);  // examples publish slowly: the default 10 minutes may hold none
  await blackboard(page);
  for (const decision of candidates) {
    const lane = page.getByRole('region', { name: `Run ${decision.cid.slice(0, 4)}` }).first();
    if (!(await lane.count())) continue;
    await lane.scrollIntoViewIfNeeded();
    const card = lane.locator(label ? `[role=button][aria-label*="${label}"]` : `[role=button][aria-label^="◆ ${decision.question}"]`).first();
    await card.scrollIntoViewIfNeeded();
    return { lane, card, decision };
  }
  throw new Error(`no lane on the board for ${candidates.length} candidates`);
};
// Unfold the card, then bring `focus` (a section label) to the middle: unfolded
// cards are taller than the window
const unfold = (focus = null) => async (page, { card, lane }) => {
  await card.click();
  await sleep(1000);
  const article = lane.locator('article[class*="unfolded"]').first();
  const target = focus ? article.getByText(focus).first() : article;
  await target.evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
};
const closer = async (page, zoomIns = 1) => {
  await fit(page); await sleep(600);
  for (let i = 0; i < zoomIns; i++) { await page.locator('[aria-label="Zoom in"]').click(); await sleep(400); }
};

// Decisions (fake models, no keys)
await clip('escalate', laneOf(PORTS.escalate, (d) => d.tier === 1 && d.choice !== 'UNSURE' && d.attempts?.[0]?.choice && d.attempts[0].choice !== d.choice), unfold(/^escalation$/i));
await clip('vote', laneOf(PORTS.vote, (d) => d.choice !== 'UNSURE' && d.votes?.length >= 3), unfold(/^vote$/i));
await clip('shadow', laneOf(PORTS.shadow, (d) => d.shadow && !d.shadow.error && d.shadow.choice !== d.choice), unfold(/^shadow$/i));
await clip('explain', laneOf(PORTS.explain, (d) => d.explanation), unfold(/^explanation$/i));
await clip('tournament', laneOf(PORTS.tournament, (d) => d.rounds?.length, 'by tournament'), async (page, ctx) => {
  await unfold()(page, ctx);
  await sleep(1500);
  await ctx.lane.locator('article[class*="unfolded"]').first().getByRole('button', { name: /bracket/i }).first().click();
}, { seconds: 7 });
await clip('checklist', async (page) => { await lastHour(page); await fit(page); }, async (page) => {
  await page.locator('.react-flow__node[data-id="audit"]').click();  // unfold: answers, runs, tokens
});
await clip('coverage', async (page) => { await lastHour(page); await fit(page); }, async () => {}, { seconds: 5 });
await clip('review', async (page) => { await lastHour(page); await fit(page); }, async (page) => {
  await page.locator('.react-flow__node:has-text("UNSURE")').first().click();  // the decider's review queue
  await sleep(1800);
  const button = page.locator('[aria-label^="Review as"]').first();
  await button.hover(); await sleep(700); await button.click();
});

// The dashboard (the triage demo)
// Long: the board moves as runs arrive; the stage takes the calmest seconds (check_motion.py --calm)
await clip('lanes', async () => {}, async (page) => { await blackboard(page); }, { seconds: 16 });
await clip('focus', async (page) => { await fit(page); }, async (page) => {
  await page.locator('.react-flow__node[data-id="triage"]').dblclick();
});
await clip('palette', async (page) => { await fit(page); }, async (page) => {
  await page.keyboard.press('Control+k');
  await sleep(500);
  for (const ch of 'tech') { await page.keyboard.type(ch); await sleep(220); }
  await sleep(1800);
  await page.keyboard.press('ArrowDown'); await sleep(450);
}, { seconds: 4 });
await clip('theme', async (page) => { await closer(page, 2); }, async (page) => {
  await palette(page, 'paper');
  await sleep(2200);
  await palette(page, 'graphite');
}, { seconds: 3 });

// Before and after: the same demo on the old and the new dashboard
await clip('before', async (page) => {
  const close = page.locator('[aria-label="Close publish panel"]');  // the old one opened it on load
  if (await close.count()) { await close.click(); await sleep(800); }
  await page.locator('.react-flow__controls-fitview').click(); await sleep(800);
  await page.locator('.react-flow__controls-zoomin').click(); await sleep(600);
}, async () => {}, { ready: null });
await clip('after', async (page) => { await closer(page, 1); }, async () => {});

await browser.close();
