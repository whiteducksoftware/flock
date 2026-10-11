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

export function useActivity(buckets: number): { activity: Activity | null; domain: Domain } {
  const timeRange = useFilterStore((state) => state.timeRange);
  const correlationId = useFilterStore((state) => state.correlationId);
  const types = useFilterStore((state) => state.selectedArtifactTypes);
  const producers = useFilterStore((state) => state.selectedProducers);
  const tags = useFilterStore((state) => state.selectedTags);
  const visibility = useFilterStore((state) => state.selectedVisibility);
  const [now, setNow] = useState(() => Date.now());
  const [activity, setActivity] = useState<Activity | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), ACTIVITY_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, []);

  const domain = domainOf(timeRange, now);
  const url = histogramUrl(domain, buckets, {
    correlationId,
    selectedArtifactTypes: types,
    selectedProducers: producers,
    selectedTags: tags,
    selectedVisibility: visibility,
  });

  useEffect(() => {
    let current = true;
    fetch(url)
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { counts?: number[]; errors?: number[]; total?: number; bucket_seconds?: number } | null) => {
        // Only a histogram is one (an older server answers without the endpoint)
        if (!current || !Array.isArray(data?.counts)) return;
        setActivity({
          counts: data.counts,
          errors: Array.isArray(data.errors) ? data.errors : [],
          total: data.total ?? data.counts.reduce((sum, count) => sum + count, 0),
          bucketSeconds: data.bucket_seconds ?? 60,
        });
      })
      .catch(() => {});
    return () => {
      current = false;
    };
  }, [url]);

  return { activity, domain };
}
