import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HistoricalArtifactsModule from './HistoricalArtifactsModule';
import { fetchArtifacts } from '../../services/api';
import { useFilterStore } from '../../store/filterStore';

vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  fetchArtifacts: vi.fn(async () => ({ items: [], pagination: { limit: 100, offset: 0, total: 0 } })),
  fetchArtifactSummary: vi.fn(async () => ({ total: 0 })),
}));

describe('HistoricalArtifactsModule', () => {
  beforeEach(() => {
    vi.mocked(fetchArtifacts).mockClear();
  });

  it.each(['last5min', 'last10min', 'last1hour'] as const)(
    'asks for %s without an end, so artifacts stamped after the browser clock show',
    async (preset) => {
      useFilterStore.setState({ timeRange: { preset } });

      render(<HistoricalArtifactsModule />);

      await waitFor(() => expect(fetchArtifacts).toHaveBeenCalled());
      const options = vi.mocked(fetchArtifacts).mock.calls[0]![0]!;
      expect(options.from).toBeDefined();
      expect(options.to).toBeUndefined();
    }
  );

  it('leaves out a broken bound instead of failing', async () => {
    useFilterStore.setState({ timeRange: { preset: 'custom', start: NaN, end: null as unknown as number } });

    render(<HistoricalArtifactsModule />);

    await waitFor(() => expect(fetchArtifacts).toHaveBeenCalled());
    const options = vi.mocked(fetchArtifacts).mock.calls[0]![0]!;
    expect(options.from).toBeUndefined();
    expect(options.to).toBeUndefined();
  });

  it('asks a range brushed up to now from its start, without an end', async () => {
    const start = Date.parse('2026-10-11T12:00:00Z');
    useFilterStore.setState({ timeRange: { preset: 'custom', start } });

    render(<HistoricalArtifactsModule />);

    await waitFor(() => expect(fetchArtifacts).toHaveBeenCalled());
    const options = vi.mocked(fetchArtifacts).mock.calls[0]![0]!;
    expect(options.from).toBe('2026-10-11T12:00:00.000Z');
    expect(options.to).toBeUndefined();
  });

  it('shows the newest artifacts first, and loads older ones on demand', async () => {
    // The store keeps artifacts oldest first: 250 of them, a0 the oldest
    vi.mocked(fetchArtifacts).mockImplementation(async (options) => {
      const offset = options?.offset ?? 0;
      const limit = options?.limit ?? 100;
      const items = Array.from({ length: Math.max(0, Math.min(limit, 250 - offset)) }, (_, k) => ({
        id: `a${offset + k}`,
        type: 'app.Item',
        payload: {},
        produced_by: `producer-${offset + k}`,
        created_at: new Date(Date.UTC(2026, 9, 11, 12, 0, 0, offset + k)).toISOString(),
        correlation_id: null,
        partition_key: null,
        tags: [],
        visibility: { kind: 'Public' },
      }));
      return { items, pagination: { limit, offset, total: 250 } };
    });
    useFilterStore.setState({ timeRange: { preset: 'all' } });
    render(<HistoricalArtifactsModule />);
    const pages = () => vi.mocked(fetchArtifacts).mock.calls.map(([options]) => [options!.offset, options!.limit]);

    await waitFor(() => expect(screen.getAllByRole('button', { name: /producer-/ })[0]!.textContent).toContain('producer-249'));
    expect(pages()).toEqual([[0, 100], [150, 100]]);

    fireEvent.click(screen.getByRole('button', { name: 'Load Older' }));
    await waitFor(() => expect(pages()).toEqual([[0, 100], [150, 100], [50, 100]]));
    fireEvent.click(screen.getByRole('button', { name: 'Load Older' }));
    await waitFor(() => expect(pages()).toEqual([[0, 100], [150, 100], [50, 100], [0, 50]]));
    // All 250, newest first, and nothing older left
    await waitFor(() => expect((screen.getByRole('button', { name: 'Load Older' }) as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getAllByRole('button', { name: /producer-/ })[0]!.textContent).toContain('producer-249');
  });
});
