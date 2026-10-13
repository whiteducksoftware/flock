// The flock video stage (../README.md): scenes over time, rendered frame by frame (window.renderFrame).
// Any format: ?w=1920&h=1080 (16:9), 1080x1920 (9:16), 1080x1080 (1:1), 1080x1350 (4:5).
const params = new URLSearchParams(location.search);
const W = Number(params.get('w') || 1920), H = Number(params.get('h') || 1080);
const FPS = 30;
const U = Math.min(W, H) / 1080;          // one unit of type and spacing
const SHAPE = W / H > 1.3 ? 'wide' : W / H < 0.8 ? 'tall' : 'square';
const M = (SHAPE === 'wide' ? 64 : 56) * U; // outer margin
const FRAMES = '../frames/';
const VERSION = 'v0.5.8';
const stage = document.getElementById('stage');
stage.style.width = W + 'px';
stage.style.height = H + 'px';

// ---------------------------------------------------------------- time and easing
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const lerp = (a, b, x) => a + (b - a) * x;
const outCubic = (x) => 1 - Math.pow(1 - x, 3);
const inOutCubic = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const outExpo = (x) => (x === 1 ? 1 : 1 - Math.pow(2, -10 * x));
const outBack = (x) => { const c = 1.5; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
// 0 -> 1 from `a`, back to 0 at `b`, `d` seconds each way
const inOut = (t, a, b, d = 0.45) => Math.min(outCubic(seg(t, a, a + d)), 1 - inOutCubic(seg(t, b - d, b)));

// ---------------------------------------------------------------- DOM helpers
function el(tag, cls, parent, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  (parent || stage).appendChild(e);
  return e;
}
function place(e, r) {
  e.style.left = `${r.x}px`; e.style.top = `${r.y}px`;
  if (r.w != null) e.style.width = `${r.w}px`;
  if (r.h != null) e.style.height = `${r.h}px`;
}
function set(e, { o = 1, x = 0, y = 0, s = 1, blur = 0 } = {}) {
  e.style.opacity = o;
  e.style.transform = `translate(${x}px, ${y}px) scale(${s})`;
  e.style.filter = blur > 0.05 ? `blur(${blur}px)` : 'none';
  e.style.visibility = o <= 0.002 ? 'hidden' : 'visible';
}

// A title whose words rise into view one after another
// A title stays on one line: wider than the frame (a tall or square format), it gets smaller
function title(parent, html, size, maxWidth = W - 2 * M) {
  const e = el('div', 'abs title', parent);
  e.style.fontSize = `${size}px`;
  let font = size, fitted = false;
  // Scenes are built before the fonts load: fit on the first frame after
  const fit = () => {
    if (fitted || document.fonts.status !== 'loaded') return;
    fitted = true;
    if (e.offsetWidth > maxWidth) {
      font = (size * maxWidth) / e.offsetWidth;
      e.style.fontSize = `${font}px`;
    }
  };
  // Words split on spaces; *word is amber, ~word blue
  const tint = (w) => (w[0] === '*' ? `<span class="amber">${w.slice(1)}</span>` : w[0] === '~' ? `<span class="blue">${w.slice(1)}</span>` : w);
  e.innerHTML = html.split(' ').map((w) => `<span class="w"><span>${tint(w)}</span></span>`).join(' ');
  const words = [...e.querySelectorAll('.w > span')];
  return {
    e,
    size: () => (fit(), { w: e.offsetWidth, h: e.offsetHeight }),
    font: () => (fit(), font),
    words(t, at, out = null, stagger = 0.07, d = 0.6) {
      fit();
      words.forEach((s, i) => {
        const a = outExpo(seg(t, at + i * stagger, at + i * stagger + d));
        const b = out == null ? 0 : inOutCubic(seg(t, out + i * 0.035, out + i * 0.035 + 0.35));
        s.style.transform = `translateY(${(1 - a) * 110 - b * 110}%)`;
      });
      e.style.visibility = t >= at - 0.02 && (out == null || t < out + 0.7) ? 'visible' : 'hidden';
    },
  };
}

// A chip: a headline with a dot and a line of code below, sliding in and out
function chip(parent, head, sub, size, dot = '') {
  const e = el('div', 'abs chip', parent, `<div class="head"><span class="dot ${dot}"></span>${head}</div>${sub ? `<div class="sub">${sub}</div>` : ''}`);
  e.style.fontSize = `${size}px`;
  return {
    e,
    size: () => ({ w: e.offsetWidth, h: e.offsetHeight }),
    show(t, at, out, from = 1) {
      const a = outBack(seg(t, at, at + 0.55));
      const b = inOutCubic(seg(t, out - 0.4, out));
      set(e, { o: Math.min(seg(t, at, at + 0.25), 1 - b), x: (1 - a) * 70 * U * from - b * 40 * U * from, s: lerp(0.94, 1, a) });
    },
  };
}

// ---------------------------------------------------------------- recordings
const recordings = {};
async function load(name) {
  const x = await (await fetch(`${FRAMES}${name}-raw/index.json`)).json();
  const first = new Image();
  first.src = `${FRAMES}${name}-raw/${x.frames[0].file}`;
  await first.decode();
  recordings[name] = {
    frames: x.frames,
    marks: Object.fromEntries(x.marks.map((m) => [m.name, m.t])),
    w: first.naturalWidth,
    h: first.naturalHeight,
  };
}
const mark = (name, m) => recordings[name].marks[m];

// The frame of `name` shown at absolute time `abs`: the last one painted by
// then. No dissolves: the dashboard's own motion is what shows (a dissolve
// after a pause was cut short by the next frame and read as a jerk)
function frameAt(name, abs) {
  const { frames } = recordings[name];
  if (abs <= frames[0].t) return { cur: frames[0], prev: null, a: 1 };
  let lo = 0, hi = frames.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (frames[mid].t <= abs) lo = mid; else hi = mid - 1; }
  return { cur: frames[lo], prev: null, a: 1 };
}

const pending = new Set();
// A window that shows a recording through a camera: `zoom` over the cover
// fit, centred on (cx, cy) of the recording (0..1), never past its edges. The
// camera keeps still while a recording plays: a slow zoom rescales every
// frame a little and makes the UI shimmer
function panel(parent, { radius = 16 } = {}) {
  const e = el('div', 'panel', parent);
  e.style.borderRadius = `${radius}px`;
  const inner = el('div', 'inner', e);
  const back = el('img', '', inner), front = el('img', '', inner);
  for (const img of [back, front]) img.style.objectFit = 'fill';
  const src = (name, f) => `${FRAMES}${name}-raw/${f.file}`;
  const use = (img, url) => {
    if (img.dataset.url !== url) { img.dataset.url = url; img.src = url; pending.add(img); }
  };
  return {
    e,
    show(name, abs, zoom = 1, cx = 0.5, cy = 0.5) {
      const f = frameAt(name, abs);
      if (f.prev) { use(back, src(name, f.prev)); back.style.opacity = 1; } else back.style.opacity = 0;
      use(front, src(name, f.cur));
      front.style.opacity = f.a;
      const pw = e.offsetWidth, ph = e.offsetHeight, rec = recordings[name];
      const k = Math.max(pw / rec.w, ph / rec.h) * zoom;
      const rw = rec.w * k, rh = rec.h * k;
      const x = clamp(pw / 2 - cx * rw, pw - rw, 0), y = clamp(ph / 2 - cy * rh, ph - rh, 0);
      inner.style.inset = 'auto';
      place(inner, { x, y, w: rw, h: rh });
    },
  };
}

// Two windows of aspects `a` and `b`: side by side unless the frame is tall;
// a tall frame stacks them by `shares` of its height, cropped (a clip's `tall`
// camera picks what shows)
function twoPanels(a, b, top, gap = 40 * U, shares = [0.55, 0.45]) {
  const x0 = M, y0 = top, aw = W - 2 * M, ah = H - M - top;
  if (SHAPE === 'tall') {
    const ha = (ah - gap) * shares[0], hb = (ah - gap) * shares[1];
    return [{ x: x0, y: y0, w: aw, h: ha }, { x: x0, y: y0 + ha + gap, w: aw, h: hb }];
  }
  const h = Math.min(ah, (aw - gap) / (a + b));
  const wa = h * a, wb = h * b, x = x0 + (aw - wa - wb - gap) / 2, y = y0 + (ah - h) / 2;
  return [{ x, y, w: wa, h }, { x: x + wa + gap, y, w: wb, h }];
}

// ---------------------------------------------------------------- background
const bg = el('div', 'layer');
const dots = el('div', 'dots', bg);
const glowA = el('div', 'glow', bg), glowB = el('div', 'glow', bg);
place(glowA, { x: -W * 0.1, y: -H * 0.2, w: W * 0.6, h: W * 0.6 });
place(glowB, { x: W * 0.55, y: H * 0.45, w: W * 0.5, h: W * 0.5 });
glowA.style.background = 'rgba(242,163,58,0.07)';
glowB.style.background = 'rgba(123,168,245,0.06)';
el('div', 'vignette', bg);
function background(t) {
  dots.style.transform = `translate(${(t * 6) % 24}px, ${(t * 3) % 24}px)`;
  glowA.style.transform = `translate(${Math.sin(t / 7) * 60 * U}px, ${Math.cos(t / 9) * 40 * U}px)`;
  glowB.style.transform = `translate(${Math.cos(t / 8) * 70 * U}px, ${Math.sin(t / 6) * 50 * U}px)`;
}

// ---------------------------------------------------------------- the mark
const MARK = (size, amber = 'var(--signal)') => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path class="c1" d="M8 3.5l4 3-4 3" stroke="currentColor"/><path class="c2" d="M8 14.5l4 3-4 3" stroke="currentColor"/><path class="c3" d="M15 9l4 3-4 3" stroke="${amber}"/></svg>`;

// ---------------------------------------------------------------- scenes
const scenes = [];
function scene(name, dur, build) {
  const root = el('div', 'layer');
  root.dataset.scene = name;
  scenes.push({ name, dur, root, update: build(root, dur) });
}

// 1 Intro: the chevrons fly in as a flock, the wordmark and the version follow
scene('intro', 5.2, (root) => {
  const size = (SHAPE === 'wide' ? 190 : 170) * U;
  const group = el('div', 'abs', root);
  group.style.display = 'flex'; group.style.alignItems = 'center'; group.style.gap = `${28 * U}px`;
  const mark = el('div', '', group, MARK(size));
  mark.style.color = 'var(--text)';
  const word = el('div', 'title', group, 'flock');
  word.style.fontSize = `${size * 0.82}px`;
  const version = el('div', 'abs mono', root);
  version.style.fontSize = `${44 * U}px`; version.style.color = 'var(--text-2)';
  const tag = el('div', 'abs label', root, 'what is new since decision models');
  tag.style.fontSize = `${22 * U}px`;
  const chevrons = [...mark.querySelectorAll('path')];
  return (t) => {
    const gw = group.offsetWidth, gh = group.offsetHeight;
    place(group, { x: (W - gw) / 2, y: (H - gh) / 2 - 40 * U });
    // Each chevron glides in on its own arc, then they settle as the mark
    chevrons.forEach((p, i) => {
      const a = outExpo(seg(t, 0.15 + i * 0.16, 1.35 + i * 0.16));
      const dx = (1 - a) * (-700 - i * 160) * U / (size / 24), dy = (1 - a) * Math.sin((i + 1) * 1.7) * 220 * U / (size / 24);
      p.style.transform = `translate(${dx}px, ${dy}px)`;
      p.style.opacity = seg(t, 0.15 + i * 0.16, 0.5 + i * 0.16);
    });
    const w = outExpo(seg(t, 1.25, 2.0));
    set(word, { o: w, x: (1 - w) * -30 * U, blur: (1 - w) * 8 });
    const typed = Math.floor(seg(t, 2.1, 2.9) * VERSION.length);
    version.textContent = VERSION.slice(0, typed) + (t > 2.1 && t < 4.2 && Math.floor(t * 2.5) % 2 ? '▍' : '');
    place(version, { x: (W - version.offsetWidth) / 2, y: (H + gh) / 2 - 10 * U });
    set(tag, { o: outCubic(seg(t, 3.0, 3.6)), y: (1 - outCubic(seg(t, 3.0, 3.6))) * 14 * U });
    place(tag, { x: (W - tag.offsetWidth) / 2, y: (H + gh) / 2 + 70 * U });
  };
});

// A scene with a big title that moves into the header, then two recorded windows
function twoWindowScene(name, dur, { html, aspects, clips, chips, chipSide = 'b' }) {
  scene(name, dur, (root) => {
    const big = (SHAPE === 'wide' ? 150 : 118) * U, small = (SHAPE === 'wide' ? 58 : 52) * U;
    const head = title(root, html, big);
    head.e.style.transformOrigin = '0 0';
    const top = (SHAPE === 'wide' ? 150 : 170) * U;
    const rects = twoPanels(aspects[0], aspects[1], top);
    const panels = rects.map((r) => { const p = panel(root); place(p.e, r); return p; });
    const made = chips.map((c) => ({ ...c, chip: chip(root, c.head, c.sub, (SHAPE === 'wide' ? 26 : 30) * U, c.dot) }));
    return (t) => {
      const { w, h } = head.size();
      const m = inOutCubic(seg(t, 2.1, 2.9));
      const k = lerp(1, small / head.font(), m);
      head.e.style.left = '0px'; head.e.style.top = '0px';
      const x = lerp((W - w) / 2, M, m), y = lerp((H - h) / 2, 48 * U, m);
      head.e.style.transform = `translate(${x}px, ${y}px) scale(${k})`;
      head.words(t, 0.15, dur - 0.8);
      rects.forEach((r, i) => {
        const a = outExpo(seg(t, 2.5 + i * 0.15, 3.4 + i * 0.15));
        set(panels[i].e, { o: a, y: (1 - a) * 80 * U, s: lerp(0.96, 1, a) });
        // A tall frame crops: the clip's `tall` camera frames what matters
        const c = SHAPE === 'tall' && clips[i].tall ? { ...clips[i], ...clips[i].tall } : clips[i];
        panels[i].show(c.rec, c.at(t), c.zoom ? c.zoom(t) : 1, c.cx ?? 0.5, c.cy ?? 0.5);
      });
      // Chips stack at the bottom of the chosen window
      const r = chipSide === 'b' ? rects[1] : rects[0];
      for (const c of made) {
        const s = c.chip.size();
        place(c.chip.e, { x: SHAPE === 'wide' ? r.x + r.w - s.w - 28 * U : (W - s.w) / 2, y: r.y + r.h - s.h - 28 * U });
        c.chip.show(t, c.at, c.out);
      }
    };
  });
}

// 2 PLAY: Snake on a decision model, the Flow beside it
twoWindowScene('play', 18, {
  html: 'FLOCK CAN NOW *PLAY!',
  aspects: [528 / 880, 1280 / 860],
  clips: [
    { rec: 'snake-game', at: (t) => mark('snake-game', 'start') - 2.4 + t, tall: { cy: 0.3 } },
    { rec: 'snake-board', at: (t) => mark('snake-board', 'start') - 2.4 + t, cy: 0.5 },
  ],
  chips: [
    { head: 'Decision models', sub: 'calibrated probabilities · azure/decision-1', at: 4.2, out: 8.2, dot: 'blue' },
    { head: 'HTTP POST to your app', sub: 'flock.sink("game").post("game:/move")', at: 8.6, out: 12.6 },
    { head: 'One run per game', sub: 'follows=[decision_id]', at: 13.0, out: 17.4, dot: 'blue' },
  ],
});

// 3 SEE: Quick, Draw! on a decision model with vision, every stroke a thumbnail in the node
// Two cuts of one recording: the first drawing, then the last (the prompts are random)
const drawStarts = (rec) => Object.entries(recordings[rec].marks)
  .filter(([name]) => name.startsWith('start:')).map(([, t]) => t).sort((a, b) => a - b);
const drawAt = (rec) => (t) => {
  const starts = drawStarts(rec);
  return t < 9 ? starts[0] - 2.2 + t : starts.at(-1) - 0.4 + (t - 9);
};
twoWindowScene('see', 19, {
  html: 'FLOCK CAN NOW ~SEE!',
  aspects: [1080 / 700, 520 / 860],
  clips: [
    { rec: 'draw-app', at: drawAt('draw-app'), tall: { cx: 0.45 } },
    // Full height: the guesser grows with every guess, Auto-arrange keeps it in the middle
    { rec: 'draw-board', at: drawAt('draw-board'), zoom: () => 1, cy: 0.5 },
  ],
  chipSide: 'a',
  chips: [
    { head: 'Images via REST', sub: 'POST /api/v1/artifacts/upload', at: 4.0, out: 8.4 },
    { head: 'Image view in the node', sub: 'every stroke, filed under its guess', at: 9.6, out: 14.0, dot: 'blue' },
    { head: 'Any decision model with vision', sub: 'openai/gpt-6-luna', at: 14.4, out: 18.4 },
  ],
});

// 4 Before and after: the old dashboard and the new one, wiped
scene('dashboard', 8, (root) => {
  const head = title(root, 'A NEW *DASHBOARD', (SHAPE === 'wide' ? 64 : 58) * U);
  const top = (SHAPE === 'wide' ? 150 : 200) * U;
  const aw = W - 2 * M, ah = H - M - top;
  const aspect = SHAPE === 'wide' ? 16 / 9 : SHAPE === 'square' ? 1.25 : 0.85;
  const h = Math.min(ah, aw / aspect), w = h * aspect;
  const r = { x: (W - w) / 2, y: top + (ah - h) / 2, w, h };
  const before = panel(root), after = panel(root);
  place(before.e, r); place(after.e, r);
  const line = el('div', 'abs', root);
  line.style.width = `${3 * U}px`; line.style.background = 'var(--signal)'; line.style.boxShadow = '0 0 24px rgba(242,163,58,0.6)';
  const lb = el('div', 'abs label', root, 'before'), la = el('div', 'abs label', root, 'after · Unfold');
  lb.style.fontSize = la.style.fontSize = `${20 * U}px`; la.style.color = 'var(--signal-ink)';
  return (t) => {
    const { h: th } = head.size();
    place(head.e, { x: M, y: (top - th) / 2 });
    head.words(t, 0.1, 7.2);
    const a = outExpo(seg(t, 0.3, 1.1));
    set(before.e, { o: a, y: (1 - a) * 60 * U });
    before.show('clip-before', mark('clip-before', 'act') + 0.5 + t);
    after.show('clip-after', mark('clip-after', 'act') + t - 2);
    const wipe = inOutCubic(seg(t, 3.0, 4.6));     // the new one sweeps in from the right
    after.e.style.clipPath = `inset(0 0 0 ${(1 - wipe) * 100}%)`;
    set(after.e, { o: a });
    place(line, { x: r.x + r.w * (1 - wipe) - 1.5 * U, y: r.y, h: r.h });
    set(line, { o: Math.min(seg(t, 2.8, 3.0), 1 - seg(t, 4.6, 4.9)) });
    place(lb, { x: r.x + 18 * U, y: r.y - 34 * U });
    place(la, { x: r.x + r.w - la.offsetWidth - 18 * U, y: r.y - 34 * U });
    set(lb, { o: a * (1 - seg(t, 3.6, 4.2)) });
    set(la, { o: seg(t, 3.4, 4.0) });
  };
});

// 5 ALSO: one anchor per feature; the camera frames the feature in each recording
// [recording, verb (last word tinted), code, line, camera x, camera y, zoom]
const ANCHORS = [
  ['clip-escalate', 'ESCALATE', 'escalate=["openai/gpt-6-luna"]', 'not sure? the next model answers', 0.58, 0.52, 1.45],
  ['clip-vote', 'VOTE', 'models=[…], vote="majority"', 'three models, one decision', 0.58, 0.56, 1.45],
  ['clip-shadow', 'SHADOW', 'shadow="openai/gpt-6-luna"', 'try a model without routing on it', 0.58, 0.5, 1.45],
  ['clip-explain', 'EXPLAIN ITSELF', '.explains(model=…)', 'an LLM writes why', 0.58, 0.42, 1.3],
  ['clip-tournament', 'RUN TOURNAMENTS', 'Tournament(group_size=20, keep=3)', 'hundreds of options, in rounds', 0.25, 0.42, 1.4],
  ['clip-checklist', 'TICK CHECKLISTS', 'Checklist: one yes/no per item', 'with tokens and cost per run', 0.6, 0.48, 1.35],
  ['clip-coverage', 'ROLL UP COVERAGE', '.aggregates(by="organisation")', 'checklists across documents', 0.69, 0.48, 1.08],
  ['clip-review', 'ASK A HUMAN', 'flock.review(decision_id, choice=…)', 'unsure decisions wait in a queue', 0.63, 0.55, 1.35],
  ['clip-lanes', 'SHOW EVERY RUN', 'the Blackboard as run lanes', 'live, one lane per correlation', 0.3, 0.45, 1.1],
  ['clip-focus', 'FOCUS', 'double-click any agent', 'lineage, live output, runs, traces', 0.36, 0.45, 1.0],
  ['clip-palette', 'FIND ANYTHING', 'Ctrl / ⌘ + K', 'agents, types, runs and commands', 0.5, 0.22, 1.3],
  ['clip-theme', 'CHANGE ITS LOOK', 'Graphite · Paper · terminal themes', 'and every shortcut in one dialog', 0.6, 0.5, 1.3],
];
const PER = 4.0, LEAD = 1.8;
scene('also', LEAD + ANCHORS.length * PER, (root, dur) => {
  const intro = title(root, 'FLOCK CAN *ALSO …', (SHAPE === 'wide' ? 150 : 120) * U);
  const kicker = el('div', 'abs label', root, 'flock can also');
  kicker.style.fontSize = `${24 * U}px`; kicker.style.color = 'var(--signal-ink)';
  // Wide: text on the left, the window on the right; otherwise the window on top
  const win = SHAPE === 'wide'
    ? { x: W * 0.37, y: M, w: W * 0.63 - M, h: H - 2 * M }
    : { x: M, y: M + 40 * U, w: W - 2 * M, h: (W - 2 * M) / (SHAPE === 'tall' ? 0.8 : 1.75) };
  const col = SHAPE === 'wide'
    ? { x: M, w: W * 0.37 - M - 40 * U }
    : { x: M, w: W - 2 * M };
  const verbSize = (SHAPE === 'wide' ? 88 : SHAPE === 'square' ? 76 : 92) * U;
  const items = ANCHORS.map(([rec, verb, code, line, cx, cy, zoom], i) => {
    const p = panel(root);
    place(p.e, win);
    const words = verb.split(' ');
    const tinted = words.map((w, k) => (k === words.length - 1 ? (i % 2 ? '~' : '*') + w : w)).join(' ');
    const v = title(root, tinted, verbSize);
    v.e.style.whiteSpace = 'normal'; v.e.style.width = `${col.w}px`; v.e.style.lineHeight = '1.0';
    const c = chip(root, code, line, (SHAPE === 'wide' ? 24 : 30) * U, i % 2 ? 'blue' : '');
    return { rec, p, v, c, cx, cy, zoom };
  });
  return (t) => {
    const { w, h } = intro.size();
    place(intro.e, { x: (W - w) / 2, y: (H - h) / 2 });
    intro.words(t, 0.05, LEAD - 0.45);
    set(kicker, { o: Math.min(seg(t, LEAD - 0.2, LEAD + 0.2), 1 - seg(t, dur - 0.7, dur - 0.3)) });
    items.forEach((it, i) => {
      const a = LEAD + i * PER, b = a + PER;
      const lt = t - a;
      const on = t > a - 0.5 && t < b + 0.5;
      it.p.e.style.display = it.v.e.style.display = it.c.e.style.display = on ? '' : 'none';
      if (!on) return;
      // The window: the next one slides over the last; the camera pushes in slowly
      const enter = outExpo(seg(lt, -0.4, 0.5));
      set(it.p.e, { o: seg(lt, -0.4, 0.0), x: (1 - enter) * 120 * U, s: lerp(1.03, 1, enter) });
      it.p.e.style.zIndex = 1 + i;
      it.p.show(it.rec, mark(it.rec, 'act') - 0.4 + lt, it.zoom, it.cx, it.cy);
      // The text block: kicker, verb, chip, centred in the column (below the window when not wide)
      const vs = it.v.size(), cs = it.c.size();
      const block = 40 * U + vs.h + 26 * U + cs.h;
      const top = SHAPE === 'wide' ? (H - block) / 2 : win.y + win.h + 40 * U;
      if (i === 0 || (lt > -0.5 && lt < PER)) place(kicker, { x: col.x, y: top });
      place(it.v.e, { x: col.x, y: top + 40 * U });
      it.v.words(lt, 0.0, PER - 0.3, 0.06, 0.5);
      place(it.c.e, { x: col.x, y: top + 40 * U + vs.h + 26 * U });
      it.c.show(lt, 0.4, PER - 0.1, -1);
    });
  };
});

// 6 LIGHTER: torch -> ONNX, size and install time (uv sync --extra semantic, PR #461)
scene('lighter', 8, (root) => {
  const head = title(root, 'FLOCK GOT *LIGHTER', (SHAPE === 'wide' ? 120 : 96) * U);
  const rows = [
    { label: 'install size', before: 7.48, after: 0.404, fmt: (v) => (v >= 1 ? `${v.toFixed(2)} GB` : `${Math.round(v * 1000)} MB`) },
    { label: 'install time', before: 302.3, after: 10.3, fmt: (v) => `${v.toFixed(v < 100 ? 1 : 0)} s` },
  ];
  const width = W - 2 * M - (SHAPE === 'wide' ? 420 * U : 300 * U);
  const made = rows.map((r) => {
    const label = el('div', 'abs label', root, r.label); label.style.fontSize = `${26 * U}px`;
    const torch = el('div', 'bar', root); torch.style.background = 'var(--surface-3)';
    const onnx = el('div', 'bar', root); onnx.style.background = 'var(--sure)';
    const tv = el('div', 'abs mono', root); tv.style.fontSize = `${48 * U}px`; tv.style.color = 'var(--text-2)';
    const ov = el('div', 'abs mono', root); ov.style.fontSize = `${48 * U}px`; ov.style.color = 'var(--sure-ink)';
    const tn = el('div', 'abs label', root, 'with torch'); tn.style.fontSize = `${22 * U}px`; tn.style.color = 'var(--text-2)';
    const on = el('div', 'abs label', root, 'with ONNX'); on.style.fontSize = `${22 * U}px`; on.style.color = 'var(--sure-ink)';
    return { ...r, label, torch, onnx, tv, ov, tn, on };
  });
  const result = el('div', 'abs title', root, '<span class="blue">18.5×</span> smaller · <span class="blue">29×</span> faster');
  result.style.fontSize = `${(SHAPE === 'wide' ? 104 : 80) * U}px`;
  const caption = el('div', 'abs mono', root, 'uv sync --extra semantic · fresh container · semantic matching on ONNX (fastembed)');
  caption.style.fontSize = `${24 * U}px`; caption.style.color = 'var(--text-3)';
  return (t) => {
    const { h } = head.size();
    place(head.e, { x: M, y: 70 * U });
    head.words(t, 0.1, 7.2);
    const bh = 70 * U, rowH = 44 * U + 2 * bh + 18 * U + 56 * U;
    let y = Math.max(70 * U + h + 60 * U, (H - (2 * rowH + 220 * U)) / 2 + 40 * U);
    made.forEach((r, i) => {
      const t0 = 0.8 + i * 0.5;
      place(r.label, { x: M, y: y + 4 * U }); set(r.label, { o: seg(t, t0, t0 + 0.3) });
      const grow = outExpo(seg(t, t0 + 0.2, t0 + 1.3));
      const tw = width * grow;
      place(r.torch, { x: M, y: y + 40 * U, w: tw, h: bh }); set(r.torch, { o: seg(t, t0, t0 + 0.2) });
      place(r.tn, { x: M + 20 * U, y: y + 40 * U + bh / 2 - 13 * U }); set(r.tn, { o: seg(t, t0 + 0.6, t0 + 0.9) });
      r.tv.textContent = r.fmt(r.before * grow);
      place(r.tv, { x: M + tw + 24 * U, y: y + 40 * U + (bh - 58 * U) / 2 }); set(r.tv, { o: seg(t, t0 + 0.2, t0 + 0.4) });
      // ONNX: the tiny bar below, the number counts down from torch's
      const t1 = 3.0 + i * 0.4;
      const shrink = outExpo(seg(t, t1, t1 + 1.2));
      const ow = width * lerp(1, r.after / r.before, shrink);
      place(r.onnx, { x: M, y: y + 40 * U + bh + 18 * U, w: ow, h: bh }); set(r.onnx, { o: seg(t, t1, t1 + 0.15) });
      r.ov.textContent = r.fmt(lerp(r.before, r.after, shrink));
      place(r.ov, { x: M + ow + 24 * U, y: y + 40 * U + bh + 18 * U + (bh - 58 * U) / 2 }); set(r.ov, { o: seg(t, t1, t1 + 0.2) });
      place(r.on, { x: M + ow + 24 * U + r.ov.offsetWidth + 22 * U, y: y + 40 * U + bh + 18 * U + bh / 2 - 13 * U }); set(r.on, { o: seg(t, t1 + 1.0, t1 + 1.3) });
      y += rowH;
    });
    const rr = outBack(seg(t, 5.0, 5.7));
    place(result, { x: M, y }); set(result, { o: seg(t, 5.0, 5.3), s: lerp(0.9, 1, rr) });
    result.style.transformOrigin = '0 50%';
    place(caption, { x: M, y: y + result.offsetHeight + 26 * U }); set(caption, { o: seg(t, 5.5, 6.0) });
  };
});

// 7 Credits
scene('credits', 6, (root) => {
  const size = (SHAPE === 'wide' ? 170 : 150) * U;
  const group = el('div', 'abs', root);
  group.style.display = 'flex'; group.style.alignItems = 'center'; group.style.gap = `${26 * U}px`;
  el('div', '', group, MARK(size)).style.color = 'var(--text)';
  const word = el('div', 'title', group, 'flock'); word.style.fontSize = `${size * 0.82}px`;
  const lines = [
    ...(SHAPE === 'wide'
      ? [['mono', `${VERSION} · decisions · images · sinks · a new dashboard`, 32, 'var(--text-2)']]
      : [['mono', VERSION, 32, 'var(--text-2)'], ['mono', 'decisions · images · sinks · a new dashboard', 26, 'var(--text-2)']]),
    ['mono', 'github.com/whiteducksoftware/flock', SHAPE === 'wide' ? 40 : 34, 'var(--text)'],
    ['label', 'built by white duck', 28, 'var(--signal-ink)'],
  ].map(([cls, text, s, color]) => { const e = el('div', `abs ${cls}`, root, text); e.style.fontSize = `${s * U}px`; e.style.color = color; return e; });
  return (t) => {
    const gw = group.offsetWidth, gh = group.offsetHeight;
    const a = outExpo(seg(t, 0.1, 0.9));
    place(group, { x: (W - gw) / 2, y: H / 2 - gh - 30 * U });
    set(group, { o: a * (1 - seg(t, 5.2, 6)), s: lerp(0.92, 1, a) });
    let y = H / 2 + 10 * U;
    lines.forEach((e, i) => {
      const b = outCubic(seg(t, 0.6 + i * 0.25, 1.2 + i * 0.25));
      place(e, { x: (W - e.offsetWidth) / 2, y });
      set(e, { o: b * (1 - seg(t, 5.2, 6)), y: (1 - b) * 16 * U });
      y += e.offsetHeight + 22 * U;
    });
  };
});

// ---------------------------------------------------------------- the timeline
const OVERLAP = 0.5;
let cursor = 0;
for (const s of scenes) { s.start = cursor; cursor += s.dur - OVERLAP; }
const DURATION = cursor + OVERLAP;

window.renderFrame = async (n) => {
  const t = n / FPS;
  background(t);
  for (const s of scenes) {
    const lt = t - s.start;
    const on = lt >= -0.001 && lt <= s.dur;
    s.root.style.display = on ? '' : 'none';
    if (!on) continue;
    // Crossfade where scenes overlap
    const fadeIn = s === scenes[0] ? 1 : seg(lt, 0, OVERLAP);
    const fadeOut = s === scenes.at(-1) ? 1 : 1 - seg(lt, s.dur - OVERLAP, s.dur);
    s.root.style.opacity = Math.min(fadeIn, fadeOut);
    s.update(lt);
  }
  const waits = [...pending].map((img) => img.decode().catch(() => {}));
  pending.clear();
  await Promise.all(waits);
  return t;
};

window.ready = (async () => {
  await document.fonts.ready;
  const names = ['snake-game', 'snake-board', 'draw-app', 'draw-board', 'clip-before', 'clip-after', ...ANCHORS.map((a) => a[0])];
  await Promise.all(names.map(load));
  window.DURATION = DURATION;
  window.TOTAL = Math.round(DURATION * FPS);
  window.FORMAT = { W, H, SHAPE };
  await window.renderFrame(0);
  return window.TOTAL;
})();
