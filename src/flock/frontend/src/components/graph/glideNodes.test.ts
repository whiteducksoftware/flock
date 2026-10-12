import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Node, XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { afterGlide, glideNodes, movedByHand } from './glideNodes';

const card = (id: string, x: number, y: number): Node => ({ id, type: 'agent', position: { x, y }, data: {} });
const positions = () => Object.fromEntries(useGraphStore.getState().nodes.map((node) => [node.id, node.position]));
const moving = () => [...useGraphStore.getState().moving].sort();
const to = (entries: [string, XYPosition][]) => new Map(entries);
const drag = (id: string, position: XYPosition, dragging: boolean) =>
  useGraphStore.setState((state) => ({ nodes: state.nodes.map((node) => (node.id === id ? { ...node, position, dragging } : node)) }));

describe('glideNodes', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useGraphStore.setState({ nodes: [card('intake', 0, 0), card('triage', 300, 0)], moving: new Set() });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    useGraphStore.setState(useGraphStore.getInitialState(), true);
  });

  it('glides the nodes there and names them as moving until they are there (#650)', () => {
    glideNodes(to([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]]));
    const during = moving();
    vi.advanceTimersByTime(300);

    expect(during).toEqual(['intake', 'triage']);
    expect(positions()).toEqual({ intake: { x: 100, y: 0 }, triage: { x: 400, y: 0 } });
    expect(moving()).toEqual([]);
  });

  it('glides one at a time: a new glide takes over, and the old one clears nothing of it', () => {
    const first = glideNodes(to([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]]));
    vi.advanceTimersByTime(50);
    glideNodes(to([['intake', { x: -100, y: 0 }]]));
    first.stop();
    const during = moving();
    vi.advanceTimersByTime(300);

    expect(during).toEqual(['intake']);
    expect(positions().intake).toEqual({ x: -100, y: 0 });
    // triage stays where the first glide left it
    expect(positions().triage!.x).toBeGreaterThan(300);
    expect(positions().triage!.x).toBeLessThan(400);
    expect(moving()).toEqual([]);
  });

  it('stops where the nodes are and lets go of them', () => {
    const glide = glideNodes(to([['intake', { x: 100, y: 0 }]]));
    vi.advanceTimersByTime(50);
    glide.stop();
    const stopped = positions().intake;
    vi.advanceTimersByTime(300);

    expect(positions().intake).toEqual(stopped);
    expect(moving()).toEqual([]);
  });

  it('leaves a node someone drags during the glide where it is dropped, also when it finishes at once', () => {
    const glide = glideNodes(to([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]]));
    vi.advanceTimersByTime(50);
    drag('intake', { x: 20, y: 300 }, true);
    vi.advanceTimersByTime(20);
    drag('intake', { x: 30, y: 320 }, false);
    glide.finish();
    vi.advanceTimersByTime(300);

    expect(positions()).toEqual({ intake: { x: 30, y: 320 }, triage: { x: 400, y: 0 } });
    expect(moving()).toEqual([]);
  });

  it('puts the nodes there at once for people who ask for less motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    glideNodes(to([['intake', { x: 100, y: 0 }]]));

    expect(positions().intake).toEqual({ x: 100, y: 0 });
    expect(moving()).toEqual([]);
  });

  it('runs what needs the nodes still (a fit) a frame after the glide ended, or at once (#650)', () => {
    const now = vi.fn();
    afterGlide(now);
    expect(now).toHaveBeenCalledOnce();

    glideNodes(to([['intake', { x: 100, y: 0 }]]));
    const fit = vi.fn();
    afterGlide(fit);
    vi.advanceTimersByTime(150);
    expect(fit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(150);
    expect(fit).toHaveBeenCalledOnce();
  });

  it('lets what waits wait for a glide that took over', () => {
    glideNodes(to([['intake', { x: 100, y: 0 }]]));
    const fit = vi.fn();
    afterGlide(fit);
    vi.advanceTimersByTime(100);
    glideNodes(to([['intake', { x: 300, y: 0 }]]));
    vi.advanceTimersByTime(150);
    expect(fit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(150);
    expect(fit).toHaveBeenCalledOnce();
  });

  it('drops what waits when it is cancelled', () => {
    glideNodes(to([['intake', { x: 100, y: 0 }]]));
    const fit = vi.fn();
    const cancel = afterGlide(fit);
    cancel();
    vi.advanceTimersByTime(400);
    expect(fit).not.toHaveBeenCalled();
  });

  it('leaves a node moved by hand where it is (the arrow keys, a drag between two frames)', () => {
    glideNodes(to([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]]));
    vi.advanceTimersByTime(50);
    movedByHand('intake');
    drag('intake', { x: 10, y: 10 }, false);
    vi.advanceTimersByTime(300);

    expect(positions()).toEqual({ intake: { x: 10, y: 10 }, triage: { x: 400, y: 0 } });
  });
});

