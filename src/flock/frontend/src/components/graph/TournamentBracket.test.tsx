import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TournamentBracket } from './TournamentBracket';
import type { TournamentRound } from './DecisionDisplay';

// 12 options -> 3 groups of 4 (keep 2) -> 6 survivors -> 2 groups of 3 (keep 1) -> final of 2
const rounds: TournamentRound[] = [
  {
    candidates: 12,
    groups: 3,
    group_size: 4,
    refused_groups: 1,
    survivors: ['a', 'b', 'e', 'f'],
    group_results: [
      { size: 4, refused: false, top: [['a', 0.7], ['b', 0.2], ['c', 0.05], ['d', 0.05]] },
      { size: 4, refused: false, top: [['e', 0.6], ['f', 0.3], ['g', 0.1]] },
      { size: 4, refused: true, top: [] },
    ],
  },
  {
    candidates: 4,
    groups: 2,
    group_size: 2,
    refused_groups: 0,
    survivors: ['a', 'e'],
    group_results: [
      { size: 2, refused: false, top: [['a', 0.8], ['b', 0.2]] },
      { size: 2, refused: false, top: [['e', 0.55], ['f', 0.45]] },
    ],
  },
];

describe('TournamentBracket', () => {
  const renderBracket = (onClose = vi.fn()) =>
    render(
      <TournamentBracket
        question="Requirement"
        rounds={rounds}
        final={{ a: 0.9, e: 0.1 }}
        champion="a"
        onClose={onClose}
      />
    );

  it('should draw one column per round plus the final', () => {
    renderBracket();
    const columns = screen.getAllByTestId('bracket-column');
    expect(columns.map((c) => c.dataset.title)).toEqual(['Round 1', 'Round 2', 'Final']);
    expect(screen.getAllByTestId('bracket-group')).toHaveLength(3 + 2 + 1);
  });

  it('should mark survivors, the refused group and hidden options', () => {
    renderBracket();
    const roundOne = screen.getAllByTestId('bracket-option').filter((o) => o.dataset.column === '0');
    expect(roundOne.filter((o) => o.dataset.survivor === 'true').map((o) => o.dataset.option)).toEqual([
      'a',
      'b',
      'e',
      'f',
    ]);
    expect(screen.getByText('refused: no option fits')).toBeInTheDocument();
    expect(screen.getByText('+1 more')).toBeInTheDocument(); // group 2 shows 3 of 4
  });

  it("should highlight the champion's path through every round", () => {
    renderBracket();
    const path = screen
      .getAllByTestId('bracket-option')
      .filter((o) => o.dataset.winner === 'true')
      .map((o) => o.dataset.column);
    expect(path).toEqual(['0', '1', '2']);
  });

  it('should close with Escape and with the close button', () => {
    const onClose = vi.fn();
    renderBracket(onClose);
    fireEvent.keyDown(window, { key: 'Escape' });
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
