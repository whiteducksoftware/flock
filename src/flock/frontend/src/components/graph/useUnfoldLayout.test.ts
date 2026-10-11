import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { Edge, Node } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { cardSizes } from './cardSizes';
import { UNFOLDED_SIZE } from './unfoldLayout';
import { useUnfoldLayout } from './useUnfoldLayout';

const CARD = { width: 260, height: 120 };
const card = (id: string, x: number, y: number): Node => ({ id, type: 'agent', position: { x, y }, data: {} });

// A grid: the free layouts keep their arrangement, so the positions are exact
const board = () => [card('intake', 0, 0), card('triage', 400, 0), card('billing', 800, 0), card('urgency', 400, 300)];
const edges: Edge[] = [];
const positions = () => Object.fromEntries(useGraphStore.getState().nodes.map((node) => [node.id, node.position]));

describe('useUnfoldLayout', () => {
  const relayout = vi.fn();
  const reveal = vi.fn();
  const layoutDue = { current: false };
  const render = () =>
    renderHook(() =>
      useUnfoldLayout({
        mode: 'grid',
        collectDimensions: () => Object.fromEntries(useGraphStore.getState().nodes.map((node) => [node.id, CARD])),
        relayout,
        reveal,
        layoutDue,
      }),
    );

  beforeEach(() => {
    // Positions jump, as for people who ask for less motion
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    useGraphStore.setState({ nodes: board(), edges, transientPositions: null });
    useUIStore.setState({ unfoldedNodeId: null });
    board().forEach((node) => cardSizes.set(node.id, CARD));
    relayout.mockReset();
    reveal.mockReset();
    layoutDue.current = false;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    cardSizes.clear();
    useGraphStore.setState(useGraphStore.getInitialState(), true);
  });

  it('makes room around the unfolded node and keeps it where it was', () => {
    render();

    act(() => useUIStore.getState().unfold('triage'));

    const wider = UNFOLDED_SIZE.width - CARD.width;
    const taller = UNFOLDED_SIZE.height - CARD.height;
    expect(positions()).toEqual({
      intake: { x: 0, y: 0 },
      triage: { x: 400, y: 0 },
      billing: { x: 800 + wider, y: 0 },
      urgency: { x: 400, y: 300 + taller },
    });
    // A snapshot refresh keeps them there
    expect(Object.fromEntries(useGraphStore.getState().transientPositions!)).toEqual(positions());
    // The board shows all of it
    expect(reveal).toHaveBeenCalledWith({ x: 400, y: 0, ...UNFOLDED_SIZE });
  });

  it('makes room from a card size when the node was never measured as a card', () => {
    // It only rendered as a chip; its element is unfolded by now
    cardSizes.delete('triage');
    renderHook(() =>
      useUnfoldLayout({
        mode: 'grid',
        collectDimensions: () =>
          Object.fromEntries(
            useGraphStore.getState().nodes.map((node) => [node.id, node.id === 'triage' ? UNFOLDED_SIZE : CARD]),
          ),
        relayout,
      }),
    );

    act(() => useUIStore.getState().unfold('triage'));

    expect(positions().billing!.x).toBeGreaterThan(800);
    expect(positions().urgency!.y).toBeGreaterThan(300);
  });

  it('puts every node back when it folds', () => {
    render();
    act(() => useUIStore.getState().unfold('triage'));

    act(() => useUIStore.getState().fold());

    expect(positions()).toEqual(Object.fromEntries(board().map((node) => [node.id, node.position])));
    expect(useGraphStore.getState().transientPositions).toBeNull();
  });

  it('unfolds another node from where the board was before', () => {
    render();
    act(() => useUIStore.getState().unfold('triage'));

    act(() => useUIStore.getState().unfold('intake'));

    const wider = UNFOLDED_SIZE.width - CARD.width;
    expect(positions()).toMatchObject({
      intake: { x: 0, y: 0 },
      triage: { x: 400 + wider, y: 0 },
      billing: { x: 800 + wider, y: 0 },
    });
  });

  it('puts the nodes back and leaves one that came meanwhile, when no layout came due (auto layout off)', () => {
    render();
    act(() => useUIStore.getState().unfold('triage'));
    act(() => useGraphStore.setState({ nodes: [...useGraphStore.getState().nodes, card('pager', 1500, 900)] }));

    act(() => useUIStore.getState().fold());

    expect(relayout).not.toHaveBeenCalled();
    expect(positions()).toEqual({
      ...Object.fromEntries(board().map((node) => [node.id, node.position])),
      pager: { x: 1500, y: 900 },
    });
  });

  it('lays the board out on folding when a layout came due meanwhile, such as for a new edge', () => {
    render();
    act(() => useUIStore.getState().unfold('triage'));
    layoutDue.current = true;

    act(() => useUIStore.getState().fold());

    expect(relayout).toHaveBeenCalledOnce();
    expect(layoutDue.current).toBe(false);
  });

  it('folds without moving anything when the node leaves the board', () => {
    render();
    act(() => useUIStore.getState().unfold('triage'));
    // A layout came due meanwhile; it goes with the board it was due for
    layoutDue.current = true;
    const blackboard = [card('artifact-1', 10, 10)];

    act(() => useGraphStore.setState({ nodes: blackboard }));

    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
    expect(useGraphStore.getState().nodes).toEqual(blackboard);
    expect(useGraphStore.getState().transientPositions).toBeNull();
    expect(relayout).not.toHaveBeenCalled();
    expect(layoutDue.current).toBe(false);
  });
});
