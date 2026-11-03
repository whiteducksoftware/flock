import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useFilterStore } from '../../store/filterStore';
import { ACTIVITY_REFRESH_MS, useActivity } from './useActivity';

const histogram = (total: number) => ({
  start: '2026-10-11T12:00:00Z',
  end: '2026-10-11T13:00:00Z',
  bucket_seconds: 60,
  counts: Array.from({ length: 60 }, (_, index) => (index === 0 ? total : 0)),
  errors: Array.from({ length: 60 }, () => 0),
  total,
});

/** A fetch whose answers the test hands out. */
const pending = () => {
  const answers: ((response: Response) => void)[] = [];
  const fetch = vi.fn(() => new Promise<Response>((resolve) => answers.push(resolve)));
  vi.stubGlobal('fetch', fetch);
  return { fetch, answer: (index: number, response: Response) => answers[index]!(response) };
};

const settle = () => act(async () => {});

describe('useActivity', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useFilterStore.setState({ timeRange: { preset: 'last10min' }, correlationId: null });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    useFilterStore.setState({ timeRange: { preset: 'last10min' }, correlationId: null });
  });

  it('lets a slow answer arrive instead of asking again every ten seconds', async () => {
    const { fetch, answer } = pending();
    const { result } = renderHook(() => useActivity(60));

    act(() => vi.advanceTimersByTime(ACTIVITY_REFRESH_MS * 2));
    expect(fetch).toHaveBeenCalledTimes(1);

    answer(0, new Response(JSON.stringify(histogram(7))));
    await settle();
    expect(result.current.activity?.total).toBe(7);

    // Once it is in, time moves it on
    act(() => vi.advanceTimersByTime(ACTIVITY_REFRESH_MS));
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('drops the counts of other filters, and says when the new ones are not available', async () => {
    const { answer } = pending();
    const { result } = renderHook(() => useActivity(60));
    answer(0, new Response(JSON.stringify(histogram(7))));
    await settle();
    expect(result.current.activity?.total).toBe(7);

    act(() => useFilterStore.setState({ correlationId: 'c-2' }));
    expect(result.current.activity).toBeNull();
    expect(result.current.failed).toBe(false);

    answer(1, new Response('', { status: 503 }));
    await settle();
    expect(result.current).toMatchObject({ activity: null, failed: true });
  });
});
