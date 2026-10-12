import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Node } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { AUTO_LAYOUT_DEBOUNCE_MS } from './autoLayoutTrigger';
import { MOVE_MS } from './animatePositions';
import { type CanvasCommands, SETTLE_MS, registerCanvas, whenOnBoard, withAgent, withCanvas } from './canvasCommands';

const commands = (kind: CanvasCommands['kind'] = 'flow'): CanvasCommands => ({
  kind,
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

  it('drops a waiting command when a newer one comes first', () => {
    vi.useFakeTimers();
    withCanvas((c) => c.show('triage'));
    const canvas = commands();
    const unregister = registerCanvas(canvas, 600);

    // The board is there before the wait is over: the newer request runs, the older one never
    withCanvas((c) => c.show('urgency'));
    vi.advanceTimersByTime(600);

    expect(vi.mocked(canvas.show).mock.calls).toEqual([['urgency']]);
    unregister();
  });

  it('drops what waits for the Flow when the view leaves it', () => {
    vi.useFakeTimers();
    useUIStore.setState({ mode: 'agent' });
    withCanvas((c) => c.show('triage'));
    const canvas = commands();
    const unregister = registerCanvas(canvas, 600);

    // Back to the Blackboard before the board settled: the Flow unmounts
    useUIStore.getState().setMode('blackboard');
    unregister();
    // A later visit to the Flow shows nothing on its own
    useUIStore.getState().setMode('agent');
    const later = registerCanvas(canvas, 600);
    vi.advanceTimersByTime(1000);

    expect(canvas.show).not.toHaveBeenCalled();
    later();
  });

  it('keeps a command for the Flow from the Blackboard graph, and gives it to the Flow', () => {
    vi.useFakeTimers();
    const graph = commands('graph');
    const unregisterGraph = registerCanvas(graph);

    // Show an agent: the graph is mounted until the switch to the Flow renders
    withCanvas((c) => c.show('triage'), 'flow');
    expect(graph.show).not.toHaveBeenCalled();
    unregisterGraph();

    const flow = commands('flow');
    const unregisterFlow = registerCanvas(flow, 600);
    vi.advanceTimersByTime(600);
    expect(flow.show).toHaveBeenCalledWith('triage');
    unregisterFlow();
  });

  it('runs a command for any canvas on the mounted one', () => {
    const graph = commands('graph');
    const unregister = registerCanvas(graph);

    withCanvas((c) => c.fit());

    expect(graph.fit).toHaveBeenCalled();
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

describe('withAgent', () => {
  const agent = (id: string) => ({ id, type: 'agent', data: {}, position: { x: 0, y: 0 } }) as Node;

  afterEach(() => {
    vi.useRealTimers();
    useGraphStore.setState({ nodes: [] });
  });

  it('runs once the agent is on the board, unless a newer request came meanwhile', () => {
    vi.useFakeTimers();
    const older = vi.fn();
    const newer = vi.fn();

    withAgent('triage', older);
    withAgent('urgency', newer);
    useGraphStore.setState({ nodes: [agent('triage'), agent('urgency')] });
    vi.advanceTimersByTime(1000);

    expect(older).not.toHaveBeenCalled();
    expect(newer).toHaveBeenCalledTimes(1);
  });

  it('drops a show that still waits for its agent when a newer request comes', () => {
    vi.useFakeTimers();
    const canvas = commands();
    vi.mocked(canvas.show).mockImplementation((id) => whenOnBoard(id, () => shown.push(id), 600));
    const shown: string[] = [];
    const unregister = registerCanvas(canvas);

    withCanvas((c) => c.show('triage'));
    withAgent('urgency', () => shown.push('unfold urgency'));
    useGraphStore.setState({ nodes: [agent('triage'), agent('urgency')] });
    vi.advanceTimersByTime(1000);

    expect(shown).toEqual(['unfold urgency']);
    unregister();
  });
});

describe('SETTLE_MS', () => {
  it('waits for a new board to be laid out and to glide there (#650)', () => {
    expect(SETTLE_MS).toBeGreaterThanOrEqual(AUTO_LAYOUT_DEBOUNCE_MS + MOVE_MS);
  });
});
