import { afterEach, describe, expect, it, vi } from 'vitest';
import type { XYPosition } from '@xyflow/react';
import { animatePositions } from './animatePositions';

const from = new Map<string, XYPosition>([['triage', { x: 0, y: 0 }]]);
const to = new Map<string, XYPosition>([['triage', { x: 100, y: 200 }]]);

describe('animatePositions', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('moves the nodes there within 200 ms, frame by frame', () => {
    vi.useFakeTimers();
    const frames: XYPosition[] = [];

    animatePositions(from, to, (positions) => frames.push(positions.get('triage')!));
    vi.advanceTimersByTime(100);
    const halfway = frames[frames.length - 1]!;
    vi.advanceTimersByTime(150);

    expect(halfway.x).toBeGreaterThan(0);
    expect(halfway.x).toBeLessThan(100);
    expect(frames[frames.length - 1]).toEqual({ x: 100, y: 200 });
  });

  it('stops where it is when cancelled', () => {
    vi.useFakeTimers();
    const apply = vi.fn();

    const stop = animatePositions(from, to, apply);
    vi.advanceTimersByTime(50);
    stop();
    const calls = apply.mock.calls.length;
    vi.advanceTimersByTime(300);

    expect(apply).toHaveBeenCalledTimes(calls);
  });

  it('jumps there for people who ask for less motion', () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query === '(prefers-reduced-motion: reduce)' }));
    const apply = vi.fn();

    animatePositions(from, to, apply);

    expect(apply).toHaveBeenCalledOnce();
    expect(apply).toHaveBeenCalledWith(to);
  });
});
