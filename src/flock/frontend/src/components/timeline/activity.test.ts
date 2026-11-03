import { describe, expect, it } from 'vitest';
import { brushOf, domainOf, histogramUrl, rangeFromBrush, ticksOf } from './activity';

const MIN = 60_000;
const now = Date.parse('2026-10-11T13:25:00Z');

describe('domainOf', () => {
  it('shows the last hour, or reaches back to where an older custom range starts', () => {
    expect(domainOf({ preset: 'last10min' }, now)).toEqual({ start: now - 60 * MIN, end: now });
    expect(domainOf({ preset: 'custom', start: now - 90 * MIN, end: now - 80 * MIN }, now)).toEqual({ start: now - 90 * MIN, end: now });
  });
});

describe('brushOf', () => {
  const domain = { start: now - 60 * MIN, end: now };

  it('places the time filter on the domain, as shares of its width', () => {
    expect(brushOf({ preset: 'last10min' }, domain, now)).toEqual({ from: 50 / 60, to: 1 });
    expect(brushOf({ preset: 'last1hour' }, domain, now)).toEqual({ from: 0, to: 1 });
    expect(brushOf({ preset: 'all' }, domain, now)).toEqual({ from: 0, to: 1 });
    expect(brushOf({ preset: 'custom', start: now - 30 * MIN, end: now - 15 * MIN }, domain, now)).toEqual({ from: 0.5, to: 0.75 });
    // Open-ended: until now
    expect(brushOf({ preset: 'custom', start: now - 15 * MIN }, domain, now)).toEqual({ from: 0.75, to: 1 });
  });
});

describe('rangeFromBrush', () => {
  const bucket = MIN;

  it('calls a brush to now as long as a preset that preset, so both make the same filter', () => {
    expect(rangeFromBrush(now - 10 * MIN, now, now, bucket)).toEqual({ preset: 'last10min' });
    expect(rangeFromBrush(now - 5 * MIN - 20_000, now - 10_000, now, bucket)).toEqual({ preset: 'last5min' });
    expect(rangeFromBrush(now - 60 * MIN, now, now, bucket)).toEqual({ preset: 'last1hour' });
    // Over five hours a bar is five minutes: ten minutes are still the ten-minute preset
    expect(rangeFromBrush(now - 10 * MIN, now, now, 5 * MIN)).toEqual({ preset: 'last10min' });
  });

  it('keeps any other brush to now open, so it stays live, and a brush in the past fixed', () => {
    expect(rangeFromBrush(now - 23 * MIN, now, now, bucket)).toEqual({ preset: 'custom', start: now - 23 * MIN });
    expect(rangeFromBrush(now - 30 * MIN, now - 20 * MIN, now, bucket)).toEqual({
      preset: 'custom',
      start: now - 30 * MIN,
      end: now - 20 * MIN,
    });
  });
});

describe('ticksOf', () => {
  it('labels the domain evenly and calls its end now', () => {
    const ticks = ticksOf({ start: now - 60 * MIN, end: now }, 4);

    expect(ticks).toHaveLength(5);
    expect(ticks[4]).toEqual({ at: now, label: 'now' });
    expect(ticks[0]!.at).toBe(now - 60 * MIN);
  });
});

describe('histogramUrl', () => {
  it('asks for the domain with the filters of the board', () => {
    const url = histogramUrl(
      { start: now - 60 * MIN, end: now },
      60,
      { correlationId: 'c-1', selectedArtifactTypes: ['app.Ticket'], selectedProducers: ['external'], selectedTags: [], selectedVisibility: ['Public'] },
    );

    expect(url).toBe(
      '/api/v1/artifacts/histogram?from=2026-10-11T12%3A25%3A00.000Z&to=2026-10-11T13%3A25%3A00.000Z&buckets=60' +
        '&correlation_id=c-1&type=app.Ticket&produced_by=external&visibility=Public',
    );
  });
});

describe('a stored range with a broken bound', () => {
  const none = { correlationId: null, selectedArtifactTypes: [], selectedProducers: [], selectedTags: [], selectedVisibility: [] };

  it('reads it as no bound, so nothing throws (an older dashboard stored NaN, which is null after a reload)', () => {
    for (const start of [NaN, null as unknown as number]) {
      const domain = domainOf({ preset: 'custom', start }, now);
      expect(domain.start).toBe(now - 60 * MIN);
      expect(() => histogramUrl(domain, 60, none)).not.toThrow();
      expect(brushOf({ preset: 'custom', start }, domain, now)).toEqual({ from: 0, to: 1 });
    }
  });
});
