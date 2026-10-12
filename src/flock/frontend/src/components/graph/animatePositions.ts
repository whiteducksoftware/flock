import type { XYPosition } from '@xyflow/react';

/** How long nodes take to make room or go back (docs/internal/design-system/README.md). */
export const MOVE_MS = 200;

export const prefersLessMotion = (): boolean =>
  typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** A movement's duration, none for people who ask for less motion (the board panning, fitting). */
export const motionMs = (ms: number): number => (prefersLessMotion() ? 0 : ms);

/** How nodes move: fast at first, slowing down (cubic) */
export const easeOut = (t: number): number => 1 - (1 - t) ** 3;

/**
 * Moves nodes from `from` to `to` in `duration` ms, easing out, handing
 * every frame's positions to `apply`; at once for people who ask for less
 * motion. Returns a function that stops it where it is.
 */
export function animatePositions(
  from: Map<string, XYPosition>,
  to: Map<string, XYPosition>,
  apply: (positions: Map<string, XYPosition>) => void,
  duration = MOVE_MS,
): () => void {
  if (duration <= 0 || prefersLessMotion()) {
    apply(to);
    return () => {};
  }

  const start = performance.now();
  let frame = 0;
  const step = (now: number) => {
    const t = Math.min(1, Math.max(0, (now - start) / duration));
    const eased = easeOut(t);
    apply(
      new Map(
        [...to].map(([id, end]) => {
          const begin = from.get(id) ?? end;
          return [id, { x: begin.x + (end.x - begin.x) * eased, y: begin.y + (end.y - begin.y) * eased }];
        }),
      ),
    );
    if (t < 1) frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
  return () => cancelAnimationFrame(frame);
}
