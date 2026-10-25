import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { reviewDecision } from '../../../services/api';
import type { DeciderInfo } from '../DecisionDisplay';
import OverviewTab from './OverviewTab';

vi.mock('../../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/api')>()),
  reviewDecision: vi.fn(async (_id: string, choice: string) => ({ artifact_id: 'r-1', choice, correlation_id: 'c-1' })),
}));

const entry = (id: string, subjectTitle: string, correlationId: string, best: string, second: string) => ({
  id,
  question: 'Route',
  correlationId,
  bestGuess: best,
  probabilities: { [best]: 0.52, [second]: 0.38, tech: 0.1 },
  options: ['billing', 'shipping', 'tech'],
  subjectTitle,
});

const decider: DeciderInfo = {
  model: 'azure/decision-1',
  threshold: 0.8,
  questions: [{ name: 'Route', kind: 'choice', options: ['billing', 'shipping', 'tech'], counts: { billing: 3, shipping: 1, tech: 1, UNSURE: 3 } }],
  needsReview: [
    entry('d-1', 'Change plan and address', '4e7b1c2d-0000-4000-8000-000000000000', 'shipping', 'billing'),
    entry('d-2', 'Something odd with my account', 'b20c9a8e-0000-4000-8000-000000000000', 'billing', 'shipping'),
  ],
  needsReviewCount: 3,
};

describe('OverviewTab', () => {
  afterEach(() => {
    vi.mocked(reviewDecision).mockClear();
  });

  it('lists the unsure decisions that wait for a person, with their best guesses', () => {
    render(<OverviewTab runs={[]} states={null} decider={decider} />);

    const queue = screen.getByRole('region', { name: 'Needs review' });
    expect(queue.textContent).toContain('Needs review · 3');
    expect(queue.textContent).toContain('Answers below the 0.80 threshold route to Route.UNSURE and wait here for a person.');
    const [first, second] = within(queue).getAllByRole('listitem');
    expect(first!.textContent).toContain('Change plan and address');
    expect(first!.textContent).toContain('4e7b');
    expect(first!.textContent).toContain('best guess shipping 0.52 · billing 0.38');
    expect(second!.textContent).toContain('Something odd with my account');
    // One more than it shows
    expect(queue.textContent).toContain('and 1 more');
  });

  it('reviews a decision from the queue', async () => {
    render(<OverviewTab runs={[]} states={null} decider={decider} />);

    const [first] = within(screen.getByRole('region', { name: 'Needs review' })).getAllByRole('listitem');
    fireEvent.click(within(first!).getByRole('button', { name: 'Review as billing' }));

    expect(reviewDecision).toHaveBeenCalledWith('d-1', 'billing');
    await waitFor(() => expect(first!.textContent).toContain('after review'));
  });

  it('names the question when the decider asks several about one artifact', () => {
    const urgent = { ...entry('d-3', 'Change plan and address', '4e7b1c2d-0000-4000-8000-000000000000', 'no', 'yes'), question: 'Urgent' };
    render(
      <OverviewTab
        runs={[]}
        states={null}
        decider={{
          ...decider,
          questions: [...decider.questions, { name: 'Urgent', kind: 'yesno', options: ['yes', 'no'], counts: { yes: 1, no: 1, UNSURE: 1 } }],
          needsReview: [decider.needsReview![0]!, urgent],
          needsReviewCount: 2,
        }}
      />,
    );

    const [route, urgentRow] = within(screen.getByRole('region', { name: 'Needs review' })).getAllByRole('listitem');
    expect(route!.textContent).toContain('◆ Route');
    expect(urgentRow!.textContent).toContain('◆ Urgent');
    expect(screen.getByRole('region', { name: 'Needs review' }).textContent).toContain('route to their UNSURE handles');
  });

  it('shows no queue when nothing waits', () => {
    render(<OverviewTab runs={[]} states={null} decider={{ ...decider, needsReview: [], needsReviewCount: 0 }} />);

    expect(screen.queryByRole('region', { name: 'Needs review' })).toBeNull();
  });

  it("counts a sink's deliveries and shows why the last one failed", () => {
    render(
      <OverviewTab
        runs={[]}
        states={null}
        sink={{
          method: 'POST',
          target: 'myapp:/billing',
          delivered: 12,
          failed: 1,
          last: { ok: false, status: 503, latencyMs: null, error: 'HTTP 503: down', at: '2026-10-12T08:24:00Z', correlationId: 'c-1' },
        }}
      />,
    );

    const deliveries = screen.getByRole('region', { name: 'Deliveries' });
    expect(within(deliveries).getByText('Delivered').nextSibling!.textContent).toBe('12');
    expect(within(deliveries).getByText('Failed').nextSibling!.textContent).toBe('1');
    expect(deliveries.textContent).toContain('HTTP 503: down');
  });

  it('keeps the questions of a decider in one column when unfolded', () => {
    const questions = ['Action', 'Board', 'Hidden', 'Time', 'Goal', 'Theme'].map((name) => ({
      name,
      kind: 'choice' as const,
      options: ['a', 'b'],
      counts: { a: 1, b: 0 },
    }));
    render(<OverviewTab runs={[]} states={null} decider={{ ...decider, questions }} />);
    expect(screen.queryByTestId('decider-columns')).not.toBeInTheDocument();
    expect(screen.getByText('Theme')).toBeInTheDocument();
  });
});
