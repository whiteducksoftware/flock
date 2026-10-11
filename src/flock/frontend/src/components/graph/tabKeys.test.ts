import { describe, expect, it } from 'vitest';
import { nextTab } from './tabKeys';

describe('nextTab', () => {
  const tabs = ['overview', 'live', 'history'];

  it('moves with the arrows, wrapping around, and jumps with Home and End', () => {
    expect(nextTab(tabs, 'overview', 'ArrowRight')).toBe('live');
    expect(nextTab(tabs, 'history', 'ArrowRight')).toBe('overview');
    expect(nextTab(tabs, 'overview', 'ArrowLeft')).toBe('history');
    expect(nextTab(tabs, 'live', 'Home')).toBe('overview');
    expect(nextTab(tabs, 'live', 'End')).toBe('history');
    expect(nextTab(tabs, 'live', 'Enter')).toBeNull();
  });
});
