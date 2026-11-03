import { describe, expect, it } from 'vitest';
import { deciderLayout, questionColumns } from './DecisionDisplay';

const sizes = (count: number) => questionColumns(Array.from({ length: count }, (_, i) => i)).map((c) => c.length);

describe('questionColumns', () => {
  it('should keep up to three questions in one column', () => {
    expect(sizes(0)).toEqual([0]);
    expect(sizes(1)).toEqual([1]);
    expect(sizes(3)).toEqual([3]);
  });

  it('should spread more questions evenly over columns of at most three', () => {
    expect(sizes(4)).toEqual([2, 2]);
    expect(sizes(5)).toEqual([3, 2]);
    expect(sizes(6)).toEqual([3, 3]);
    expect(sizes(7)).toEqual([3, 2, 2]);
    expect(sizes(10)).toEqual([3, 3, 2, 2]);
  });

  it('should keep the questions in order', () => {
    expect(questionColumns(['a', 'b', 'c', 'd', 'e'])).toEqual([
      ['a', 'b', 'c'],
      ['d', 'e'],
    ]);
  });

  it('should switch to compact rows from seven questions, in columns of at most twelve', () => {
    const layout = (count: number) => {
      const { compact, columns } = deciderLayout(Array.from({ length: count }, (_, i) => i));
      return { compact, sizes: columns.map((c) => c.length) };
    };
    expect(layout(3)).toEqual({ compact: false, sizes: [3] });
    expect(layout(6)).toEqual({ compact: false, sizes: [3, 3] });
    expect(layout(7)).toEqual({ compact: true, sizes: [7] });
    expect(layout(12)).toEqual({ compact: true, sizes: [12] });
    expect(layout(13)).toEqual({ compact: true, sizes: [7, 6] });
  });
});
