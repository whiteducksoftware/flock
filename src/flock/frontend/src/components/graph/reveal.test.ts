import { afterEach, describe, expect, it, vi } from 'vitest';
import { easeOut, MOVE_MS } from './animatePositions';
import { revealGlide, revealViewport } from './reveal';

describe('revealViewport', () => {
  const pane = { width: 1000, height: 600 };

  it('leaves the board where it is when the box is in view', () => {
    expect(revealViewport({ x: 0, y: 0, zoom: 1 }, { x: 100, y: 100, width: 300, height: 200 }, pane)).toBeNull();
  });

  it('pans as little as it takes to show the box, with a margin', () => {
    // The box ends 100 px below the pane at zoom 1: the board moves up by that and the margin
    expect(revealViewport({ x: 0, y: 0, zoom: 1 }, { x: 100, y: 200, width: 300, height: 500 }, pane)).toEqual({ x: 0, y: -124, zoom: 1 });
  });

  it('shows the start of a box too big for the pane', () => {
    expect(revealViewport({ x: 0, y: 0, zoom: 2 }, { x: 100, y: 100, width: 300, height: 400 }, pane)).toEqual({ x: 0, y: -176, zoom: 2 });
  });
});

describe('revealGlide', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('pans like the nodes that make room glide: same time and easing, in a straight line (#648)', () => {
    expect(revealGlide()).toEqual({ duration: MOVE_MS, ease: easeOut, interpolate: 'linear' });
  });

  it('pans at once for people who ask for less motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    expect(revealGlide().duration).toBe(0);
  });
});

describe('easeOut', () => {
  it('starts fast and ends slow (cubic)', () => {
    expect(easeOut(0)).toBe(0);
    expect(easeOut(0.5)).toBe(0.875);
    expect(easeOut(1)).toBe(1);
  });
});
