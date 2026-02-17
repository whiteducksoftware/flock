import { describe, expect, it, vi } from 'vitest';
import {
  AUTO_LAYOUT_DEBOUNCE_MS,
  clearDebouncedAutoLayout,
  getNodeIdSet,
  hasNewNodeAdditions,
  scheduleDebouncedAutoLayout,
  type TimeoutRef,
} from './autoLayoutTrigger';

describe('autoLayoutTrigger', () => {
  it('does not detect topology change when node ids are unchanged (status-only refresh)', () => {
    const previous = new Set(['a', 'b', 'c']);
    const current = getNodeIdSet([{ id: 'c' }, { id: 'b' }, { id: 'a' }] as any);

    expect(hasNewNodeAdditions(previous, current)).toBe(false);
  });

  it('detects topology change when new nodes are added', () => {
    const previous = new Set(['a', 'b']);
    const current = getNodeIdSet([{ id: 'a' }, { id: 'b' }, { id: 'c' }] as any);

    expect(hasNewNodeAdditions(previous, current)).toBe(true);
  });

  it('treats missing previous topology baseline as no trigger', () => {
    const current = getNodeIdSet([{ id: 'a' }] as any);
    expect(hasNewNodeAdditions(null, current)).toBe(false);
  });

  it('debounces burst scheduling into a single callback invocation', () => {
    vi.useFakeTimers();

    const callback = vi.fn();
    const timerRef: TimeoutRef = { current: null };

    scheduleDebouncedAutoLayout(timerRef, callback);
    scheduleDebouncedAutoLayout(timerRef, callback);
    scheduleDebouncedAutoLayout(timerRef, callback);

    vi.advanceTimersByTime(AUTO_LAYOUT_DEBOUNCE_MS - 1);
    expect(callback).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(callback).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('can clear pending debounce before it fires', () => {
    vi.useFakeTimers();

    const callback = vi.fn();
    const timerRef: TimeoutRef = { current: null };

    scheduleDebouncedAutoLayout(timerRef, callback);
    clearDebouncedAutoLayout(timerRef);

    vi.advanceTimersByTime(AUTO_LAYOUT_DEBOUNCE_MS + 1);
    expect(callback).not.toHaveBeenCalled();

    vi.useRealTimers();
  });
});
