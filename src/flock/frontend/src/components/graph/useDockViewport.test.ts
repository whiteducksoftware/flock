import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useDockViewport } from './useDockViewport';

const flow = { fitView: vi.fn(), getViewport: vi.fn(() => ({ x: 10, y: -400, zoom: 0.8 })), setViewport: vi.fn() };
vi.mock('@xyflow/react', () => ({ useReactFlow: () => flow }));

describe('useDockViewport', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('fits the graph into the strip the expanded dock leaves, and gives the view back when it collapses', () => {
    vi.useFakeTimers();
    const { rerender } = renderHook(({ open }) => useDockViewport(open), { initialProps: { open: false } });
    expect(flow.fitView).not.toHaveBeenCalled();

    rerender({ open: true });
    vi.advanceTimersByTime(50);
    expect(flow.fitView).toHaveBeenCalledOnce();

    rerender({ open: false });
    expect(flow.setViewport).toHaveBeenCalledWith({ x: 10, y: -400, zoom: 0.8 }, expect.anything());
  });
});
