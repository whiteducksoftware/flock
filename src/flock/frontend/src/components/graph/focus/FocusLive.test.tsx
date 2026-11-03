import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { decisionOf, MessageCard, preview } from './FocusLive';
import type { Message } from '../unfold/messageHistory';

const items = Array.from({ length: 1000 }, (_, i) => `C${String(i).padStart(4, '0')}`);
const checklist: Message = {
  id: 'd-1',
  type: 'flock.decisions.Decision[__main__.Controls]',
  direction: 'published',
  payload: {
    question: 'Controls',
    kind: 'checklist',
    choice: 'failed',
    best_guess: 'failed',
    probabilities: Object.fromEntries(items.map((item, i) => [item, i % 2 ? 0.97 : 0.03])),
    results: Object.fromEntries(items.map((item, i) => [item, i % 2 ? 'yes' : 'no'])),
    refused_items: [],
    threshold: 0.8,
    model: 'fake/checklist',
    latency_ms: 426,
  },
  at: '2026-10-25T17:30:57Z',
  correlationId: 'doc1',
};

describe('FocusLive', () => {
  it('previews long lists and maps with the number left out', () => {
    expect(preview('text')).toBe('text');
    expect(preview([1, 2, 3])).toBe('[1,2,3]');
    expect(preview(Array.from({ length: 10 }, (_, i) => i))).toBe('[0,1,2,3,4,5,6,7, … 2 more]');
    expect(preview(Object.fromEntries(items.slice(0, 9).map((item) => [item, 1])))).toBe(
      '{"C0000":1,"C0001":1,"C0002":1,"C0003":1,"C0004":1,"C0005":1,"C0006":1,"C0007":1, … 1 more}',
    );
  });

  it('reads a decision payload as the decision view, also with the module path in the type', () => {
    const decision = decisionOf(checklist)!;
    expect(decision).toMatchObject({ question: 'Controls', kind: 'checklist', choice: 'failed', model: 'fake/checklist', latencyMs: 426 });
    expect(decision.items).toHaveLength(1000);
    expect(decisionOf({ ...checklist, type: '__main__.Reply' })).toBeNull();
  });

  it('shows a decision output as decision bars, not as its payload', () => {
    render(<MessageCard title="Output" message={checklist} />);
    expect(screen.getByText('yes 500')).toBeInTheDocument();
    expect(screen.getByText('no 500')).toBeInTheDocument();
    expect(screen.queryByText(/"C0001":0\.97/)).not.toBeInTheDocument();
  });

  it("takes a scale's levels from the decider's question, and keeps a scale without them as its payload", () => {
    // A review of a three-level scale carries only the chosen level
    const review: Message = {
      ...checklist,
      type: 'flock.decisions.Decision[__main__.Risk]',
      payload: { question: 'Risk', kind: 'scale', choice: 'high', best_guess: 'high', probabilities: { high: 1.0 }, score: 2, model: 'review' },
    };
    const risk = { name: 'Risk', kind: 'scale' as const, options: ['low', 'medium', 'high'], counts: {} };
    expect(decisionOf(review, [risk])).toMatchObject({ kind: 'scale', levels: ['low', 'medium', 'high'], score: 2 });
    expect(decisionOf(review)).toBeNull();
  });

  it("orders a checklist's items as the decider's question does", () => {
    const controls = { name: 'Controls', kind: 'checklist' as const, options: [...items].reverse(), counts: {} };
    expect(decisionOf(checklist, [controls])!.items![0]).toBe('C0999');
  });
});
