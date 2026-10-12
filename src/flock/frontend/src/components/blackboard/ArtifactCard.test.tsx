import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import ArtifactCard from './ArtifactCard';
import type { LaneCard } from './lanes';

const card = (type: string, payload: Record<string, unknown>): LaneCard => ({
  id: 'r-1',
  type,
  producedBy: 'billing-api',
  timestamp: 1000,
  data: { payload },
  state: 'done',
});

describe('ArtifactCard', () => {
  it('shows a delivery receipt as one line', () => {
    render(
      <ArtifactCard
        card={card('flock.sinks.models.Delivered', { sink: 'billing-api', method: 'POST', target: 'myapp:/billing', status: 200, attempts: 1, latency_ms: 41 })}
      />,
    );

    const receipt = screen.getByTestId('receipt');
    expect(receipt.textContent).toBe('toPOST myapp:/billinganswer200 · 41 ms');
    expect(receipt.dataset.ok).toBe('true');
  });

  it('marks a failed delivery', () => {
    render(
      <ArtifactCard
        card={card('flock.sinks.models.DeliveryFailed', { sink: 'billing-api', method: 'POST', target: 'myapp:/billing', status: 400, attempts: 1, error: 'HTTP 400: no such customer' })}
      />,
    );

    expect(screen.getByTestId('receipt').textContent).toBe('toPOST myapp:/billinganswerHTTP 400');
    expect(screen.getByRole('button', { name: 'DeliveryFailed by billing-api' }).dataset.failed).toBe('true');
  });
});
