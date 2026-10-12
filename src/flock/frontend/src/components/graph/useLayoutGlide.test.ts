import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { Node, XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { useLayoutGlide } from './useLayoutGlide';

const card = (id: string, x: number, y: number): Node => ({ id, type: 'agent', position: { x, y }, data: {} });
const positions = () => Object.fromEntries(useGraphStore.getState().nodes.map((node) => [node.id, node.position]));
const layout = (entries: [string, XYPosition][]) => new Map(entries);

describe('useLayoutGlide', () => {
  beforeEach(() => {
    useGraphStore.setState({ nodes: [card('intake', 0, 0), card('triage', 300, 0)] });
    useUIStore.setState({ unfoldedNodeId: null });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    useUIStore.setState({ unfoldedNodeId: null });
    useGraphStore.setState(useGraphStore.getInitialState(), true);
  });

  it('glides the nodes to a new layout instead of jumping there (#650)', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]])));
    act(() => void vi.advanceTimersByTime(100));
    const halfway = positions().intake!.x;
    act(() => void vi.advanceTimersByTime(150));

    expect(halfway).toBeGreaterThan(0);
    expect(halfway).toBeLessThan(100);
    expect(positions()).toEqual({ intake: { x: 100, y: 0 }, triage: { x: 400, y: 0 } });
  });

  it('tells the board which nodes glide, so a snapshot keeps them on their way', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]])));
    const during = [...useGraphStore.getState().moving].sort();
    act(() => void vi.advanceTimersByTime(300));

    expect(during).toEqual(['intake', 'triage']);
    expect(useGraphStore.getState().moving.size).toBe(0);
  });

  it('leaves a node that is dragged during the glide where it is dropped', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]])));
    act(() => void vi.advanceTimersByTime(50));
    act(() =>
      useGraphStore.setState((state) => ({
        nodes: state.nodes.map((node) => (node.id === 'intake' ? { ...node, position: { x: 20, y: 300 }, dragging: true } : node)),
      })),
    );
    act(() => void vi.advanceTimersByTime(30));
    act(() =>
      useGraphStore.setState((state) => ({
        nodes: state.nodes.map((node) => (node.id === 'intake' ? { ...node, position: { x: 30, y: 320 }, dragging: false } : node)),
      })),
    );
    act(() => void vi.advanceTimersByTime(300));

    expect(positions()).toEqual({ intake: { x: 30, y: 320 }, triage: { x: 400, y: 0 } });
  });

  it('moves nothing when the layout is where the nodes are', () => {
    vi.useFakeTimers();
    const updates = vi.fn();
    const unsubscribe = useGraphStore.subscribe(updates);
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 0, y: 0.2 }], ['triage', { x: 300, y: 0 }]])));
    act(() => void vi.advanceTimersByTime(300));

    unsubscribe();
    expect(updates).not.toHaveBeenCalled();
  });

  it('finishes its glide when a node unfolds, so making room starts from the layout', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]])));
    act(() => void vi.advanceTimersByTime(50));
    act(() => useUIStore.getState().unfold('triage'));

    expect(positions()).toEqual({ intake: { x: 100, y: 0 }, triage: { x: 400, y: 0 } });
  });

  it('keeps a node dragged during the glide where it is dropped when an agent unfolds', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]])));
    act(() => void vi.advanceTimersByTime(50));
    act(() =>
      useGraphStore.setState((state) => ({
        nodes: state.nodes.map((node) => (node.id === 'intake' ? { ...node, position: { x: 30, y: 320 }, dragging: true } : node)),
      })),
    );
    act(() => void vi.advanceTimersByTime(20));
    act(() => useUIStore.getState().unfold('triage'));

    expect(positions()).toEqual({ intake: { x: 30, y: 320 }, triage: { x: 400, y: 0 } });
  });

  it('leaves a node moved after its glide ended where it is when one unfolds', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useLayoutGlide());

    act(() => result.current(layout([['intake', { x: 100, y: 0 }], ['triage', { x: 400, y: 0 }]])));
    act(() => void vi.advanceTimersByTime(300));
    act(() => useGraphStore.getState().setNodePositions(new Map([['intake', { x: 50, y: 500 }]])));
    act(() => useUIStore.getState().unfold('triage'));

    expect(positions().intake).toEqual({ x: 50, y: 500 });
  });
});
