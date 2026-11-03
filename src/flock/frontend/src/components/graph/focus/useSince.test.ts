import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useSince } from './useSince';

describe('useSince', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('counts on with the monotonic clock when the wall clock steps back', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-11T12:00:10Z'));
    const { result } = renderHook(() => useSince('2026-10-11T12:00:09Z'));
    expect(result.current).toBe(1);

    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toBe(2);

    // A VM time sync moves the wall clock back by 1.9 s
    vi.setSystemTime(new Date(Date.now() - 1900));
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toBe(3);
  });

  it('knows no time without a start', () => {
    const { result } = renderHook(() => useSince(null));
    expect(result.current).toBeNull();
  });
});
