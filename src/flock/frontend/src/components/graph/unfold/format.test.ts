import { describe, expect, it } from 'vitest';
import { duration, shortId, usd } from './format';

describe('unfolded node formats', () => {
  it('writes costs so that a tiny one is not zero', () => {
    expect(usd(0)).toBe('$0');
    expect(usd(0.00002)).toBe('<$0.0001');
    expect(usd(0.0012)).toBe('$0.0012');
    expect(usd(1.254)).toBe('$1.25');
  });

  it('writes durations and short ids', () => {
    expect(duration(61)).toBe('61 ms');
    expect(duration(1500)).toBe('1.5 s');
    expect(duration(150_000)).toBe('2.5 m');
    expect(shortId('9c3450bb-1234')).toBe('9c3450');
    expect(shortId(null)).toBe('');
  });
});
