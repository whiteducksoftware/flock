import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchArtifactSummary, fetchArtifacts, type ArtifactListItem, type ArtifactQueryOptions } from '../../services/api';
import { mapArtifactToMessage } from '../../utils/artifacts';
import { useFilterStore } from '../../store/filterStore';
import { useGraphStore } from '../../store/graphStore';
import type { ModuleContext } from './ModuleRegistry';
import styles from './HistoricalArtifactsModule.module.css';

const PAGE_SIZE = 100;

type TimeRangeSelection = ReturnType<typeof useFilterStore.getState>['timeRange'];

type HistoricalArtifactsModuleProps = {
  context: ModuleContext;
};

const resolveTimeRangeToIso = (range: TimeRangeSelection): { from?: string; to?: string } => {
  const now = Date.now();
  if (range.preset === 'last5min') {
    return {
      from: new Date(now - 5 * 60 * 1000).toISOString(),
      to: new Date(now).toISOString(),
    };
  }
  if (range.preset === 'last10min') {
    return {
      from: new Date(now - 10 * 60 * 1000).toISOString(),
      to: new Date(now).toISOString(),
    };
  }
  if (range.preset === 'last1hour') {
    return {
      from: new Date(now - 60 * 60 * 1000).toISOString(),
      to: new Date(now).toISOString(),
    };
  }
  if (range.preset === 'custom' && range.start && range.end) {
    return {
      from: new Date(range.start).toISOString(),
      to: new Date(range.end).toISOString(),
    };
  }
  return {};
};

const HistoricalArtifactsModule: React.FC<HistoricalArtifactsModuleProps> = ({ context }) => {
  // Context reserved for future extensions (module lifecycle expects prop)
  void context;
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const selectedArtifactTypes = useFilterStore((state) => state.selectedArtifactTypes);
  const selectedProducers = useFilterStore((state) => state.selectedProducers);
  const selectedTags = useFilterStore((state) => state.selectedTags);
  const selectedVisibility = useFilterStore((state) => state.selectedVisibility);
  const setSummary = useFilterStore((state) => state.setSummary);
  const updateAvailableCorrelationIds = useFilterStore((state) => state.updateAvailableCorrelationIds);
  const summary = useFilterStore((state) => state.summary);

  const [artifacts, setArtifacts] = useState<ArtifactListItem[]>([]);
  const [nextOffset, setNextOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasMore = total > nextOffset;

  const buildQueryOptions = useCallback(
    (offset: number): ArtifactQueryOptions => {
      const range = resolveTimeRangeToIso(timeRange);
      return {
        types: selectedArtifactTypes,
        producers: selectedProducers,
        tags: selectedTags,
        visibility: selectedVisibility,
        correlationId,
        from: range.from,
        to: range.to,
        limit: PAGE_SIZE,
        offset,
      };
    },
    [timeRange, selectedArtifactTypes, selectedProducers, selectedTags, selectedVisibility, correlationId]
  );

  const mergeCorrelationMetadata = useCallback(
    (items: ArtifactListItem[]) => {
      if (items.length === 0) return;

      const existing = useFilterStore.getState().availableCorrelationIds;
      const merged = new Map(existing.map((item) => [item.correlation_id, { ...item }]));

      items.forEach((item) => {
        if (!item.correlation_id) return;
        const timestamp = new Date(item.created_at).getTime();
        const current = merged.get(item.correlation_id);
        if (current) {
          current.artifact_count += 1;
          current.first_seen = Math.min(current.first_seen, timestamp);
        } else {
          merged.set(item.correlation_id, {
            correlation_id: item.correlation_id,
            first_seen: timestamp,
            artifact_count: 1,
            run_count: 0,
          });
        }
      });

      updateAvailableCorrelationIds(Array.from(merged.values()));
    },
    [updateAvailableCorrelationIds]
  );

  const loadArtifacts = useCallback(
    async (reset: boolean) => {
      setLoading(true);
      try {
        const offset = reset ? 0 : nextOffset;
        const queryOptions = buildQueryOptions(offset);
        const response = await fetchArtifacts(queryOptions);

        setArtifacts((prev) => (reset ? response.items : [...prev, ...response.items]));
        setNextOffset(offset + response.pagination.limit);
        setTotal(response.pagination.total);
        setError(null);

        mergeCorrelationMetadata(response.items);

        if (response.items.length > 0) {
          const graphStore = useGraphStore.getState();
          graphStore.batchUpdate({ messages: response.items.map(mapArtifactToMessage) });
        }

        const summaryResponse = await fetchArtifactSummary({
          ...queryOptions,
          limit: undefined,
          offset: undefined,
        });
        setSummary(summaryResponse);
      } catch (err) {
        console.error('[HistoricalArtifactsModule] Failed to load artifacts', err);
        setError('Failed to load artifacts');
      } finally {
        setLoading(false);
      }
    },
    [buildQueryOptions, mergeCorrelationMetadata, nextOffset, setSummary]
  );

  useEffect(() => {
    loadArtifacts(true);
  }, [loadArtifacts]);

  const rows = useMemo(
    () =>
      artifacts.map((artifact) => ({
        id: artifact.id,
        timestamp: new Date(artifact.created_at).toLocaleString(),
        type: artifact.type,
        producedBy: artifact.produced_by,
        correlationId: artifact.correlation_id ?? '—',
        tags: artifact.tags.join(', ') || '—',
        visibility: artifact.visibility_kind || artifact.visibility?.kind || 'Unknown',
      })),
    [artifacts]
  );

  const handleLoadMore = () => {
    if (!loading && hasMore) {
      loadArtifacts(false);
    }
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.metrics}>
          <div>
            <span className={styles.metricLabel}>Artifacts</span>
            <span className={styles.metricValue}>{total}</span>
          </div>
          <div>
            <span className={styles.metricLabel}>Earliest</span>
            <span className={styles.metricValue}>
              {summary?.earliest_created_at ? new Date(summary.earliest_created_at).toLocaleString() : '—'}
            </span>
          </div>
          <div>
            <span className={styles.metricLabel}>Latest</span>
            <span className={styles.metricValue}>
              {summary?.latest_created_at ? new Date(summary.latest_created_at).toLocaleString() : '—'}
            </span>
          </div>
        </div>
        <div className={styles.actions}>
          <button type="button" onClick={() => loadArtifacts(true)} disabled={loading}>
            Refresh
          </button>
          <button type="button" onClick={handleLoadMore} disabled={loading || !hasMore}>
            Load Older
          </button>
        </div>
      </header>

      {error && <div className={styles.error}>{error}</div>}

      {!loading && artifacts.length === 0 && !error && (
        <div className={styles.emptyState}>No artifacts found for current filters.</div>
      )}

      {artifacts.length > 0 && (
        <div className={styles.tableContainer}>
          <div className={styles.headerRow}>
            <span>Timestamp</span>
            <span>Type</span>
            <span>Produced By</span>
            <span>Correlation ID</span>
            <span>Tags</span>
            <span>Visibility</span>
          </div>
          <div className={styles.rows}>
            {rows.map((row) => (
              <div key={row.id} className={styles.dataRow}>
                <span>{row.timestamp}</span>
                <span>{row.type}</span>
                <span>{row.producedBy}</span>
                <span>{row.correlationId}</span>
                <span>{row.tags}</span>
                <span>{row.visibility}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading && <div className={styles.loading}>Loading…</div>}
    </div>
  );
};

export default HistoricalArtifactsModule;
