/**
 * Showing a box on the board (an unfolded node): where the board pans to, and
 * how it gets there.
 */

import type { Viewport } from '@xyflow/react';
import { easeOut, motionMs, MOVE_MS } from './animatePositions';

/** The space kept around the box */
const MARGIN = 24;

/**
 * The viewport that shows the box (flow coordinates) in a pane of this size,
 * panned as little as it takes and with a margin; the start of a box too big
 * for the pane. Null when the box is in view.
 */
export function revealViewport(
  viewport: Viewport,
  box: { x: number; y: number; width: number; height: number },
  pane: { width: number; height: number },
): Viewport | null {
  const { x, y, zoom } = viewport;
  const shift = (start: number, size: number, room: number) => {
    const from = start * zoom;
    const to = from + size * zoom;
    if (to - from > room - 2 * MARGIN) return MARGIN - from; // Too big: show its start
    if (from < MARGIN) return MARGIN - from;
    if (to > room - MARGIN) return room - MARGIN - to;
    return 0;
  };
  const dx = shift(box.x + x / zoom, box.width, pane.width);
  const dy = shift(box.y + y / zoom, box.height, pane.height);
  return dx || dy ? { x: x + dx, y: y + dy, zoom } : null;
}

/**
 * The pan glides like the nodes that make room: the same time and easing, in
 * a straight line (React Flow's default eases in and out along a "smooth" path
 * that zooms out on the way), so each card on the screen moves along one path
 * instead of one way with the layout and back with the camera (#648)
 */
export const revealGlide = () => ({ duration: motionMs(MOVE_MS), ease: easeOut, interpolate: 'linear' as const });
