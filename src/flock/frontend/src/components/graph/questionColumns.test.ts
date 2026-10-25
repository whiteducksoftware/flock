import { describe, expect, it } from 'vitest';
import { questionColumns } from './DecisionDisplay';

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
});
