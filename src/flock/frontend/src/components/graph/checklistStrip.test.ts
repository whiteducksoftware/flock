import { describe, expect, it } from 'vitest';
import { MAX_STRIP_CELLS, stripCells } from './DecisionDisplay';

const checklist = (count: number) => {
  const options = Array.from({ length: count }, (_, i) => `C${String(i).padStart(4, '0')}`);
  // Every item: 1 yes, 2 no, 3 unsure
  return { options, itemStats: options.map(() => [1, 2, 3]), descriptions: { C0000: 'MFA for remote access' } };
};

describe('stripCells', () => {
  it('should keep one cell per item up to the cap, with its description', () => {
    const cells = stripCells(checklist(MAX_STRIP_CELLS));
    expect(cells).toHaveLength(MAX_STRIP_CELLS);
    expect(cells[0]).toMatchObject({ label: 'C0000', yes: 1, no: 2, unsure: 3 });
    expect(cells[0]!.title).toBe('C0000: 1 yes · 2 no · 3 unsure — MFA for remote access');
  });

  it('should let consecutive items share a cell above the cap, answers summed and the range in the tooltip', () => {
    const cells = stripCells(checklist(1000));
    expect(cells).toHaveLength(MAX_STRIP_CELLS);
    // 1,000 = 68 × 14 + 48: the first 48 cells take 15 items, the rest 14
    expect(cells[0]).toMatchObject({ label: 'C0000–C0014', yes: 15, no: 30, unsure: 45 });
    expect(cells[0]!.title).toBe('C0000–C0014 (15 items): 15 yes · 30 no · 45 unsure');
    expect(cells[67]!.label).toBe('C0986–C0999');
    expect(cells.reduce((sum, cell) => sum + cell.yes, 0)).toBe(1000);
  });
});
