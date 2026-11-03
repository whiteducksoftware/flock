/** The activity histogram of the board's filters over the dock's domain, refreshed as time goes on. */

import { useEffect, useState } from 'react';
import { useFilterStore } from '../../store/filterStore';
import { type Domain, domainOf, histogramUrl } from './activity';

export interface Activity {
  counts: number[];
  errors: number[];
  total: number;
  bucketSeconds: number;
}

/** How often the histogram moves on with the time. */
export const ACTIVITY_REFRESH_MS = 10_000;

interface Loaded {
  /** The filters it was read for */
  key: string;
  /** The stretch of time it covers, which the bars and the brush are drawn on */
  domain: Domain;
  activity: Activity | null;
}

/**
 * The histogram for the board's filters. It asks again every ten seconds,
 * once the last answer is in (a slow server would otherwise never answer in
 * time), and forgets the counts as soon as the filters change.
 */
export function useActivity(buckets: number): { activity: Activity | null; domain: Domain; failed: boolean } {
  const timeRange = useFilterStore((state) => state.timeRange);
  const correlationId = useFilterStore((state) => state.correlationId);
  const types = useFilterStore((state) => state.selectedArtifactTypes);
  const producers = useFilterStore((state) => state.selectedProducers);
  const tags = useFilterStore((state) => state.selectedTags);
  const visibility = useFilterStore((state) => state.selectedVisibility);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const key = JSON.stringify([buckets, timeRange, correlationId, types, producers, tags, visibility]);

  useEffect(() => {
    let current = true;
    let asking = false;
    const ask = () => {
      if (asking) return;
      asking = true;
      const domain = domainOf(timeRange, Date.now());
      fetch(
        histogramUrl(domain, buckets, {
          correlationId,
          selectedArtifactTypes: types,
          selectedProducers: producers,
          selectedTags: tags,
          selectedVisibility: visibility,
        }),
      )
        .then((response) => (response.ok ? response.json() : null))
        .catch(() => null)
        .then((data: { counts?: number[]; errors?: number[]; total?: number; bucket_seconds?: number } | null) => {
          asking = false;
          if (!current) return;
          // Only a histogram is one (an older server answers without the endpoint)
          const activity = Array.isArray(data?.counts)
            ? {
                counts: data.counts,
                errors: Array.isArray(data.errors) ? data.errors : [],
                total: data.total ?? data.counts.reduce((sum, count) => sum + count, 0),
                bucketSeconds: data.bucket_seconds ?? 60,
              }
            : null;
          // A failed refresh keeps the last counts for the same filters
          setLoaded((previous) => (activity || previous?.key !== key ? { key, domain, activity } : previous));
        });
    };
    ask();
    const timer = window.setInterval(ask, ACTIVITY_REFRESH_MS);
    return () => {
      current = false;
      window.clearInterval(timer);
    };
    // `key` stands for the filters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const mine = loaded?.key === key ? loaded : null;
  return {
    activity: mine?.activity ?? null,
    domain: mine?.domain ?? domainOf(timeRange, Date.now()),
    failed: mine !== null && mine.activity === null,
  };
}
