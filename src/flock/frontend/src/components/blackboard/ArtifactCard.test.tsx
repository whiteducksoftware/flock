import { describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { useUIStore } from '../../store/uiStore';
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

  it("shows a decider's decisions about one artifact as one card with a row per question (#668)", () => {
    const answer = (id: string, question: string, choice: string, probability: number): LaneCard => ({
      id,
      type: `Decision[app.${question}]`,
      producedBy: 'facets_a',
      timestamp: 1000,
      state: 'done',
      data: {
        decision: {
          question,
          kind: 'choice',
          choice,
          bestGuess: choice === 'UNSURE' ? 'grid' : choice,
          probabilities: choice === 'UNSURE' ? { grid: probability, text: 1 - probability } : { [choice]: probability },
          confidence: probability,
          threshold: 0.6,
          model: 'azure/decision-1',
          latencyMs: 40,
          options: ['grid', 'text'],
        },
      },
    });
    const bundle: LaneCard = {
      id: 'bundle:a1',
      type: null,
      producedBy: 'facets_a',
      timestamp: 1000,
      state: 'done',
      data: {},
      decisions: [answer('a1', 'Action', 'connect', 0.74), answer('a2', 'Board', 'UNSURE', 0.4)],
    };
    render(<ArtifactCard card={bundle} />);

    const folded = screen.getByRole('button', { name: '◆ facets_a · 2 questions · 1 unsure' });
    const rows = screen.getAllByTestId('bundle-row');
    expect(rows.map((row) => row.textContent)).toEqual(['Actionconnect0.74', 'Boardgrid0.40']);
    // The unsure answer is its best guess, marked unsure and named so in its title
    expect(rows[1]).toHaveAttribute('data-unsure', 'true');
    expect(rows[1]).toHaveAttribute('title', 'Board: UNSURE, best guess grid 0.40');

    // Unfolded: the decision that waits for a review is open with its review, the others open on a click
    fireEvent.click(folded);
    expect(useUIStore.getState().unfoldedArtifactId).toBe('bundle:a1');
    const board = screen.getByRole('region', { name: '◆ Board' });
    expect(within(board).getByRole('button', { name: 'Review as grid' })).toBeInTheDocument();
    const action = screen.getByRole('region', { name: '◆ Action' });
    const toggle = within(action).getByRole('button', { expanded: false });
    expect(within(action).queryByText('azure/decision-1', { exact: false })).toBeNull();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(within(action).getByText(/azure\/decision-1/)).toBeInTheDocument();
    expect(within(action).queryByRole('button', { name: /Review as/ })).toBeNull();

    // Unfolding one of its decisions (from elsewhere) opens the bundle too
    act(() => useUIStore.getState().unfoldArtifact('a2'));
    expect(screen.getByRole('article', { name: '◆ facets_a · 2 questions · 1 unsure' })).toBeInTheDocument();
    act(() => useUIStore.getState().foldArtifact());
  });
});
