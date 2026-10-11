import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useDockViewport } from './useDockViewport';

const flow = { fitView: vi.fn(), getViewport: vi.fn(() => ({ x: 10, y: -400, zoom: 0.8 })), setViewport: vi.fn() };
const board = { height: 700, measured: true };
vi.mock('@xyflow/react', () => ({
  useReactFlow: () => flow,
  useStore: (select: (state: { height: number }) => number) => select({ height: board.height }),
  useNodesInitialized: () => board.measured,
}));

describe('useDockViewport', () => {
  afterEach(() => {
    vi.clearAllMocks();
    board.height = 700;
    board.measured = true;
  });

  it('fits the graph once the board has the strip\'s height, and gives the view back on collapse', () => {
    const { rerender } = renderHook(({ open }) => useDockViewport(open), { initialProps: { open: false } });

    rerender({ open: true });
    // React Flow still knows the old height: a fit now would center the graph below the strip
    expect(flow.fitView).not.toHaveBeenCalled();

    board.height = 220;
    rerender({ open: true });
    expect(flow.fitView).toHaveBeenCalledOnce();

    rerender({ open: false });
    expect(flow.setViewport).toHaveBeenCalledWith({ x: 10, y: -400, zoom: 0.8 }, expect.anything());
  });

  it('fits a graph that is still loading only when it is measured, and not after a collapse', () => {
    board.measured = false;
    const { rerender } = renderHook(({ open }) => useDockViewport(open), { initialProps: { open: false } });

    rerender({ open: true });
    board.height = 220;
    rerender({ open: true });
    expect(flow.fitView).not.toHaveBeenCalled();

    // Collapsed before the graph arrived: nothing waits to fit it
    rerender({ open: false });
    board.height = 700;
    board.measured = true;
    rerender({ open: false });
    expect(flow.fitView).not.toHaveBeenCalled();
  });
});
