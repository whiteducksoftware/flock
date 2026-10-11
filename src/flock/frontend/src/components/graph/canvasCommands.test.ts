import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Node } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { type CanvasCommands, registerCanvas, whenOnBoard, withCanvas } from './canvasCommands';

const commands = (): CanvasCommands => ({
  zoomIn: vi.fn(),
  zoomOut: vi.fn(),
  fit: vi.fn(),
  layout: vi.fn(),
  show: vi.fn(),
});

describe('canvasCommands', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('runs a command on the mounted canvas at once', () => {
    const canvas = commands();
    const unregister = registerCanvas(canvas);

    withCanvas((c) => c.fit());

    expect(canvas.fit).toHaveBeenCalledTimes(1);
    unregister();
  });

  it('keeps a command until a canvas mounts, then runs it once the board settled', () => {
    vi.useFakeTimers();
    withCanvas((c) => c.show('triage'));

    const canvas = commands();
    const unregister = registerCanvas(canvas, 600);
    expect(canvas.show).not.toHaveBeenCalled();

    vi.advanceTimersByTime(600);
    expect(canvas.show).toHaveBeenCalledWith('triage');

    // Only once, also when the canvas registers again
    unregister();
    const again = registerCanvas(canvas, 600);
    vi.advanceTimersByTime(600);
    expect(canvas.show).toHaveBeenCalledTimes(1);
    again();
  });

  it('hands a waiting command on when the canvas unmounts before it ran', () => {
    vi.useFakeTimers();
    withCanvas((c) => c.show('triage'));

    // Strict mode: mounted, unmounted and mounted again at once
    const canvas = commands();
    registerCanvas(canvas, 600)();
    const unregister = registerCanvas(canvas, 600);
    vi.advanceTimersByTime(600);

    expect(canvas.show).toHaveBeenCalledTimes(1);
    unregister();
  });

  it('forgets an unmounted canvas, and a newer one wins', () => {
    const first = commands();
    const second = commands();
    const unregisterFirst = registerCanvas(first);
    const unregisterSecond = registerCanvas(second);
    // The first one unmounting late does not unregister the second
    unregisterFirst();

    withCanvas((c) => c.zoomIn());

    expect(second.zoomIn).toHaveBeenCalled();
    expect(first.zoomIn).not.toHaveBeenCalled();
    unregisterSecond();
  });
});

describe('whenOnBoard', () => {
  const agent = (id: string) => ({ id, type: 'agent', data: {}, position: { x: 0, y: 0 } }) as Node;

  afterEach(() => {
    vi.useRealTimers();
    useGraphStore.setState({ nodes: [] });
  });

  it('runs at once for an agent on the board', () => {
    useGraphStore.setState({ nodes: [agent('triage')] });
    const run = vi.fn();

    whenOnBoard('triage', run, 600);

    expect(run).toHaveBeenCalledTimes(1);
  });

  it('waits for the agent to arrive, then for the board to settle', () => {
    vi.useFakeTimers();
    useGraphStore.setState({ nodes: [{ ...agent('a-1'), type: 'artifact' } as Node] });
    const run = vi.fn();

    whenOnBoard('triage', run, 600);
    useGraphStore.setState({ nodes: [agent('urgency')] });
    vi.advanceTimersByTime(1000);
    expect(run).not.toHaveBeenCalled();

    useGraphStore.setState({ nodes: [agent('urgency'), agent('triage')] });
    vi.advanceTimersByTime(599);
    expect(run).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(run).toHaveBeenCalledTimes(1);

    // Once
    useGraphStore.setState({ nodes: [agent('triage')] });
    vi.advanceTimersByTime(1000);
    expect(run).toHaveBeenCalledTimes(1);
  });

  it('gives up on an agent that never arrives', () => {
    vi.useFakeTimers();
    const run = vi.fn();

    whenOnBoard('ghost', run, 600, 5000);
    vi.advanceTimersByTime(5000);
    useGraphStore.setState({ nodes: [agent('ghost')] });
    vi.advanceTimersByTime(1000);

    expect(run).not.toHaveBeenCalled();
  });
});
