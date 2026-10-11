import { render, waitFor } from '@testing-library/react';
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
});
