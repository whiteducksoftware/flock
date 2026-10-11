import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import RunStatusTab from './RunStatusTab';

describe('RunStatusTab', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows the tokens of a run whose model has no price', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          runs: [
            {
              run_id: 'run-1',
              start_time: '2026-10-11T10:00:00Z',
              end_time: '2026-10-11T10:00:01Z',
              duration_ms: 1000,
              status: 'completed',
              // The backend sends null when a model has no price
              metrics: { tokens_used: 12, cost_usd: null, unpriced_models: ['local/x'] },
            },
          ],
        }),
      })),
    );

    render(<RunStatusTab nodeId="writer" nodeType="agent" />);

    expect(await screen.findByText('Tokens: 12')).toBeTruthy();
    expect(screen.queryByText(/Cost:/)).toBeNull();
  });
});
