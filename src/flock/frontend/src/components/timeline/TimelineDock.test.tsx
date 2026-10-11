import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useFilterStore } from '../../store/filterStore';
import { useUIStore } from '../../store/uiStore';
import TimelineDock from './TimelineDock';

const histogram = {
  start: '2026-10-11T12:25:00Z',
  end: '2026-10-11T13:25:00Z',
  bucket_seconds: 60,
  counts: Array.from({ length: 60 }, (_, index) => (index % 10 === 0 ? 3 : 1)),
  errors: Array.from({ length: 60 }, (_, index) => (index === 42 ? 1 : 0)),
  total: 78,
};

const serve = () => {
  const fetch = vi.fn(async (url: string) => {
    if (url.startsWith('/api/v1/artifacts/histogram')) return new Response(JSON.stringify(histogram));
    if (url.startsWith('/api/traces')) return new Response(JSON.stringify([]));
    return new Response(JSON.stringify({ artifacts: [], items: [], total: 0 }));
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
};

describe('TimelineDock', () => {
  beforeEach(() => {
    serve();
    useUIStore.setState({ dockOpen: false, dockTab: 'traces', traceSearch: '' });
    useFilterStore.setState({ timeRange: { preset: 'last10min' } });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useUIStore.setState({ dockOpen: false, traceSearch: '' });
    useFilterStore.setState({ timeRange: { preset: 'last10min' } });
  });

  it('shows the last hour of activity with the time filter on it, errors and now', async () => {
    render(<TimelineDock />);

    expect(await screen.findByText('78 artifacts')).toBeTruthy();
    expect(screen.getByText('· last hour')).toBeTruthy();
    const activity = screen.getByTestId('activity');
    expect(activity.querySelectorAll('[title$="artifact"], [title$="artifacts"]')).toHaveLength(60);
    expect(activity.querySelector('[title="1 error"]')).toBeTruthy();
    // Last 10 min of the last hour
    const brush = screen.getByTestId('brush');
    expect(parseFloat(brush.style.left)).toBeCloseTo((50 / 60) * 100, 1);
    expect(brush.style.right).toBe('0%');
    expect(screen.getByText('now')).toBeTruthy();
  });

  it('sets the time filter by brushing, and calls a brush to now of a preset\'s length that preset', async () => {
    render(<TimelineDock />);
    const activity = await screen.findByTestId('activity');
    vi.spyOn(activity, 'getBoundingClientRect').mockReturnValue({ left: 0, width: 600, top: 0, height: 36 } as DOMRect);

    // From 30 to 15 minutes ago: a fixed range
    fireEvent.pointerDown(activity, { button: 0, clientX: 300, pointerId: 1 });
    fireEvent.pointerMove(activity, { clientX: 450, pointerId: 1 });
    fireEvent.pointerUp(activity, { clientX: 450, pointerId: 1 });
    const range = useFilterStore.getState().timeRange;
    expect(range.preset).toBe('custom');
    expect(range.end! - range.start!).toBeCloseTo(15 * 60_000, -4);

    // The last 5 minutes: the preset
    fireEvent.pointerDown(activity, { button: 0, clientX: 550, pointerId: 1 });
    fireEvent.pointerUp(activity, { clientX: 600, pointerId: 1 });
    expect(useFilterStore.getState().timeRange).toEqual({ preset: 'last5min' });
  });

  it('opens on History or Traces, moves between tabs with the keys, and collapses', async () => {
    render(<TimelineDock />);

    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    expect(useUIStore.getState()).toMatchObject({ dockOpen: true, dockTab: 'history' });
    expect(screen.getByRole('tab', { name: 'History' }).getAttribute('aria-selected')).toBe('true');

    fireEvent.keyDown(screen.getByRole('tab', { name: 'History' }), { key: 'ArrowRight' });
    expect(screen.getByRole('tab', { name: 'Metrics' }).getAttribute('aria-selected')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: 'Collapse timeline dock' }));
    expect(useUIStore.getState().dockOpen).toBe(false);
    expect(screen.getByRole('contentinfo', { name: 'Timeline' })).toBeTruthy();
  });

  it('opens Traces on a run\'s correlation, as a failed card asks', async () => {
    render(<TimelineDock />);

    useUIStore.getState().openDock('traces', 'c-123');

    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Search traces' }) as HTMLInputElement).value).toBe('c-123'));
  });
});
