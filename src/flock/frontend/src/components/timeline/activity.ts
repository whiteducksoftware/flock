/**
 * The activity histogram of the timeline dock: the stretch of time it shows,
 * where the time filter sits on it, and the filter a brush makes
 * (docs/internal/design-system/README.md, Layout).
 */

import type { TimeRange } from '../../types/filters';

const MINUTE = 60_000;

export interface Domain {
  start: number;
  end: number;
}

/** The presets a brush to now can be, by length. */
const PRESETS: { preset: TimeRange['preset']; ms: number }[] = [
  { preset: 'last5min', ms: 5 * MINUTE },
  { preset: 'last10min', ms: 10 * MINUTE },
  { preset: 'last1hour', ms: 60 * MINUTE },
];

/** The last hour, reaching further back when a custom range starts earlier. */
export function domainOf(range: TimeRange, now: number): Domain {
  const hour = now - 60 * MINUTE;
  const start = range.preset === 'custom' && range.start !== undefined ? Math.min(range.start, hour) : hour;
  return { start, end: now };
}

/** Where the time filter sits on the domain, as shares of its width (0 to 1). */
export function brushOf(range: TimeRange, domain: Domain, now: number): { from: number; to: number } {
  const span = domain.end - domain.start;
  const share = (at: number) => Math.min(1, Math.max(0, (at - domain.start) / span));
  const preset = PRESETS.find((entry) => entry.preset === range.preset);
  if (preset) return { from: share(now - preset.ms), to: 1 };
  if (range.preset === 'custom' && range.start !== undefined) {
    return { from: share(range.start), to: range.end === undefined ? 1 : share(range.end) };
  }
  return { from: 0, to: 1 };
}

/**
 * The time filter of a brush from `start` to `end`. A brush that reaches now
 * (within a bucket) stays open, so it follows the time; one as long as a
 * preset is that preset, so brushing and picking it make the same filter.
 */
export function rangeFromBrush(start: number, end: number, now: number, bucketMs: number): TimeRange {
  if (now - end > bucketMs) return { preset: 'custom', start, end };
  const length = now - start;
  // The closest preset, within a bar (over five hours a bar is five minutes)
  const closest = PRESETS.reduce((best, entry) => (Math.abs(entry.ms - length) < Math.abs(best.ms - length) ? entry : best));
  return Math.abs(closest.ms - length) <= bucketMs ? { preset: closest.preset } : { preset: 'custom', start };
}

const clock = (at: number) => new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

/** `count + 1` evenly spaced labels; the last is "now". */
export function ticksOf(domain: Domain, count: number): { at: number; label: string }[] {
  return Array.from({ length: count + 1 }, (_, index) => {
    const at = domain.start + ((domain.end - domain.start) * index) / count;
    return { at, label: index === count ? 'now' : clock(at) };
  });
}

export interface HistogramFilters {
  correlationId: string | null;
  selectedArtifactTypes: string[];
  selectedProducers: string[];
  selectedTags: string[];
  selectedVisibility: string[];
}

/** The histogram endpoint's URL for the domain and the board's filters (not its time filter: the brush shows that). */
export function histogramUrl(domain: Domain, buckets: number, filters: HistogramFilters): string {
  const params = new URLSearchParams({
    from: new Date(domain.start).toISOString(),
    to: new Date(domain.end).toISOString(),
    buckets: String(buckets),
  });
  if (filters.correlationId) params.append('correlation_id', filters.correlationId);
  filters.selectedArtifactTypes.forEach((type) => params.append('type', type));
  filters.selectedProducers.forEach((producer) => params.append('produced_by', producer));
  filters.selectedTags.forEach((tag) => params.append('tag', tag));
  filters.selectedVisibility.forEach((visibility) => params.append('visibility', visibility));
  return `/api/v1/artifacts/histogram?${params.toString()}`;
}
