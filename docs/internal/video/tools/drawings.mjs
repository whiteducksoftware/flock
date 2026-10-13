// Strokes for Quick, Draw! on a 480x480 canvas: each drawing is a list of
// strokes, each stroke a list of points, with a little hand-drawn wobble.
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647 - 0.5);
const wob = (pts, a = 2.5) => pts.map(([x, y]) => [x + rnd() * a, y + rnd() * a]);

const arc = (cx, cy, rx, ry, a0, a1, n = 36) =>
  Array.from({ length: n + 1 }, (_, i) => {
    const a = a0 + ((a1 - a0) * i) / n;
    return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)];
  });
const line = (x0, y0, x1, y1, n = 12) =>
  Array.from({ length: n + 1 }, (_, i) => [x0 + ((x1 - x0) * i) / n, y0 + ((y1 - y0) * i) / n]);
const poly = (pts, n = 10) => pts.slice(1).flatMap((p, i) => line(...pts[i], ...p, n).slice(i ? 1 : 0));
const T = 2 * Math.PI;

export const DRAWINGS = {
  sun: () => [
    wob(arc(240, 240, 78, 78, 0, T)),
    ...Array.from({ length: 8 }, (_, i) => {
      const a = (i * T) / 8;
      return wob(line(240 + 100 * Math.cos(a), 240 + 100 * Math.sin(a), 240 + 160 * Math.cos(a), 240 + 160 * Math.sin(a)), 1.5);
    }),
  ],
  house: () => [
    wob(poly([[130, 230], [130, 400], [350, 400], [350, 230]])),
    wob(poly([[110, 240], [240, 110], [370, 240]])),
    wob(poly([[215, 400], [215, 320], [265, 320], [265, 400]])),
    wob(poly([[155, 260], [155, 300], [195, 300], [195, 260], [155, 260]])),
    wob(poly([[300, 150], [300, 110], [325, 110], [325, 175]])),
  ],
  star: () => [
    wob(poly(Array.from({ length: 11 }, (_, i) => {
      const a = -Math.PI / 2 + (i * T * 2) / 5;
      return [240 + 170 * Math.cos(a), 250 + 170 * Math.sin(a)];
    }), 8)),
  ],
  fish: () => [
    wob(arc(220, 240, 130, 75, 0, T, 48)),
    wob(poly([[345, 240], [430, 170], [430, 310], [345, 240]])),
    wob(arc(150, 220, 9, 9, 0, T, 12), 0.8),
    wob(arc(150, 250, 30, 40, -0.9, 0.9, 12), 1.2),
  ],
  tree: () => [
    wob(poly([[215, 420], [215, 300], [265, 300], [265, 420]])),
    wob([...arc(240, 210, 120, 100, Math.PI * 0.75, Math.PI * 2.25, 48)]),
    wob(poly([[150, 420], [330, 420]])),
  ],
  clock: () => [
    wob(arc(240, 240, 160, 160, 0, T, 60)),
    wob(line(240, 240, 240, 130)),
    wob(line(240, 240, 320, 270)),
    ...[0, 1, 2, 3].map(i => {
      const a = (i * T) / 4;
      return wob(line(240 + 140 * Math.cos(a), 240 + 140 * Math.sin(a), 240 + 155 * Math.cos(a), 240 + 155 * Math.sin(a), 4), 0.8);
    }),
  ],
  umbrella: () => [
    wob(arc(240, 230, 170, 140, Math.PI, T, 40)),
    wob([...arc(97, 230, 28, 20, Math.PI, 0, 8), ...arc(154, 230, 29, 20, Math.PI, 0, 8), ...arc(212, 230, 29, 20, Math.PI, 0, 8),
      ...arc(270, 230, 29, 20, Math.PI, 0, 8), ...arc(328, 230, 29, 20, Math.PI, 0, 8), ...arc(385, 230, 28, 20, Math.PI, 0, 8)].map(([x, y]) => [x, 460 - y]), 1.5),
    wob([...line(240, 90, 240, 390), ...arc(215, 390, 25, 25, 0, Math.PI, 10)]),
  ],
  flower: () => [
    wob(arc(240, 190, 28, 28, 0, T, 20)),
    ...Array.from({ length: 6 }, (_, i) => {
      const a = (i * T) / 6;
      return wob(arc(240 + 62 * Math.cos(a), 190 + 62 * Math.sin(a), 32, 32, a + Math.PI * 0.75, a + Math.PI * 2.25, 20), 1.5);
    }),
    wob(line(240, 255, 240, 440)),
    wob([...arc(275, 360, 35, 18, Math.PI, T, 12), ...arc(275, 360, 35, 18, 0, Math.PI, 12)]),
  ],
};

/** Draw `strokes` on the page's canvas with the mouse, like a hand. */
export async function draw(page, strokes, { box, pace = 9, pause = 700 } = {}) {
  for (const stroke of strokes) {
    const [x0, y0] = stroke[0];
    await page.mouse.move(box.x + x0, box.y + y0);
    await page.mouse.down();
    for (const [x, y] of stroke.slice(1)) {
      await page.mouse.move(box.x + x, box.y + y);
      await new Promise(r => setTimeout(r, pace));
    }
    await page.mouse.up();
    await new Promise(r => setTimeout(r, pause));
  }
}
