import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchArtifactSummary, fetchArtifacts, type ArtifactListItem, type ArtifactQueryOptions } from '../../services/api';
import { useFilterStore } from '../../store/filterStore';
import type { ModuleContext } from './ModuleRegistry';
import JsonAttributeRenderer from './JsonAttributeRenderer';
import styles from './HistoricalArtifactsModule.module.css';

const PAGE_SIZE = 100;
const ITEM_HEIGHT = 48;
const MIN_VISIBLE_ITEMS = 8;

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
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);

  const lastAutoLoadIndex = useRef(-1);
  const virtualScrollRef = useRef<HTMLDivElement | null>(null);
  const [virtualRange, setVirtualRange] = useState({ start: 0, end: MIN_VISIBLE_ITEMS });

  const selectedArtifact = useMemo(
    () => artifacts.find((artifact) => artifact.id === selectedArtifactId) ?? null,
    [artifacts, selectedArtifactId]
  );

  const hasMore = total > nextOffset;

  useEffect(() => {
    if (selectedArtifactId && !artifacts.some((artifact) => artifact.id === selectedArtifactId)) {
      setSelectedArtifactId(null);
    }
  }, [artifacts, selectedArtifactId]);

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
        embedMeta: true,
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

        // UI Optimization Migration (Phase 2/4 - Spec 002): Backend-driven architecture
        // Graph updates happen automatically via GraphCanvas useEffect when filters change
        // This module only manages the artifact table view, not the graph
        // No need to manually trigger graph updates here

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
    lastAutoLoadIndex.current = -1;
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
        consumedCount: artifact.consumptions?.length ?? 0,
      })),
    [artifacts]
  );

  const handleLoadMore = () => {
    if (!loading && hasMore) {
      lastAutoLoadIndex.current = -1;
      loadArtifacts(false);
    }
  };
  const listHeight = useMemo(() => Math.max(MIN_VISIBLE_ITEMS, Math.min(rows.length || MIN_VISIBLE_ITEMS, 12)) * ITEM_HEIGHT, [rows.length]);

  useEffect(() => {
    const container = virtualScrollRef.current;
    if (!container) {
      return;
    }

    const handleScroll = () => {
      const totalItems = rows.length;
      if (totalItems === 0) {
        setVirtualRange({ start: 0, end: MIN_VISIBLE_ITEMS });
        return;
      }

      const scrollTop = container.scrollTop;
      const viewportHeight = container.clientHeight;
      const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - 5);
      const endIndex = Math.min(totalItems, Math.ceil((scrollTop + viewportHeight) / ITEM_HEIGHT) + 5);
      setVirtualRange({ start: startIndex, end: endIndex });

      if (hasMore && !loading && endIndex >= totalItems - 5 && lastAutoLoadIndex.current !== endIndex) {
        lastAutoLoadIndex.current = endIndex;
        handleLoadMore();
      }
    };

    handleScroll();
    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [handleLoadMore, hasMore, loading, rows.length]);

  useEffect(() => {
    const container = virtualScrollRef.current;
    if (container) {
      container.scrollTop = 0;
    }
    setVirtualRange({ start: 0, end: Math.max(MIN_VISIBLE_ITEMS, Math.min(rows.length, MIN_VISIBLE_ITEMS * 2)) });
    lastAutoLoadIndex.current = -1;
  }, [rows.length]);

  const retentionInfo = useMemo(() => {
    if (!summary?.earliest_created_at || !summary?.latest_created_at) {
      return null;
    }
    const earliest = new Date(summary.earliest_created_at);
    const latest = new Date(summary.latest_created_at);
    const spanMs = Math.max(0, latest.getTime() - earliest.getTime());
    const spanDays = spanMs / (1000 * 60 * 60 * 24);
    let spanLabel: string;
    if (spanDays >= 2) {
      spanLabel = `${spanDays.toFixed(1)} days`;
    } else if (spanDays >= 0.5) {
      spanLabel = `${(spanDays * 24).toFixed(0)} hours`;
    } else {
      spanLabel = `${Math.max(1, Math.round(spanMs / (1000 * 60)))} minutes`;
    }
    return {
      earliest: earliest.toLocaleString(),
      latest: latest.toLocaleString(),
      spanLabel,
    };
  }, [summary]);

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

      {retentionInfo && (
        <div className={styles.retentionBanner}>
          <span>
            Historical window: <strong>{retentionInfo.spanLabel}</strong> (oldest artifact {retentionInfo.earliest})
          </span>
          <span>
            Latest artifact recorded at <strong>{retentionInfo.latest}</strong>.{' '}
            {hasMore ? 'Use “Load Older” to fetch additional retained history.' : 'You are viewing the full retained history.'}
          </span>
        </div>
      )}

      {error && <div className={styles.error}>{error}</div>}

      {!loading && artifacts.length === 0 && !error && (
        <div className={styles.emptyState}>No artifacts found for current filters.</div>
      )}

      {artifacts.length > 0 && (
        <div className={styles.contentArea}>
          <div className={styles.tableContainer}>
            <div className={styles.headerRow}>
              <span>Timestamp</span>
              <span>Type</span>
              <span>Produced By</span>
              <span>Correlation ID</span>
              <span>Tags</span>
              <span>Visibility</span>
              <span>Consumed</span>
            </div>
            <div
              ref={virtualScrollRef}
              className={styles.virtualViewport}
              style={{ height: listHeight }}
            >
              <div style={{ height: rows.length * ITEM_HEIGHT, position: 'relative' }}>
                <div
                  style={{
                    position: 'absolute',
                    top: virtualRange.start * ITEM_HEIGHT,
                    left: 0,
                    right: 0,
                  }}
                >
                  {rows.slice(virtualRange.start, virtualRange.end).map((row, idx) => {
                    const absoluteIndex = virtualRange.start + idx;
                    const isSelected = row.id === selectedArtifactId;
                    const classes = [styles.dataRow];
                    if (absoluteIndex % 2 === 1) {
                      classes.push(styles.dataRowStripe);
                    }
                    if (isSelected) {
                      classes.push(styles.dataRowSelected);
                    }
                    return (
                      <div
                        key={row.id}
                        className={classes.join(' ')}
                        style={{ height: ITEM_HEIGHT }}
                        role="button"
                        tabIndex={0}
                        aria-selected={isSelected}
                        onClick={() => setSelectedArtifactId(row.id)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            setSelectedArtifactId(row.id);
                          }
                        }}
                      >
                        <span>{row.timestamp}</span>
                        <span>{row.type}</span>
                        <span>{row.producedBy}</span>
                        <span>{row.correlationId}</span>
                        <span>{row.tags}</span>
                        <span>{row.visibility}</span>
                        <span>{row.consumedCount}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
          <aside className={styles.detailPanel}>
            {selectedArtifact ? (
              <>
                <div className={styles.detailHeader}>
                  <div>
                    <h3>{selectedArtifact.type}</h3>
                    <p>{new Date(selectedArtifact.created_at).toLocaleString()}</p>
                  </div>
                  <button type="button" onClick={() => setSelectedArtifactId(null)}>
                    Clear
                  </button>
                </div>
                <div className={styles.detailSection}>
                  <h4>Metadata</h4>
                  <dl className={styles.detailList}>
                    <div>
                      <dt>Produced By</dt>
                      <dd>{selectedArtifact.produced_by}</dd>
                    </div>
                    <div>
                      <dt>Correlation</dt>
                      <dd>{selectedArtifact.correlation_id || '—'}</dd>
                    </div>
                    <div>
                      <dt>Partition</dt>
                      <dd>{selectedArtifact.partition_key || '—'}</dd>
                    </div>
                    <div>
                      <dt>Tags</dt>
                      <dd>{selectedArtifact.tags.length ? selectedArtifact.tags.join(', ') : '—'}</dd>
                    </div>
                    <div>
                      <dt>Visibility</dt>
                      <dd>{selectedArtifact.visibility_kind || selectedArtifact.visibility?.kind || 'Unknown'}</dd>
                    </div>
                    <div>
                      <dt>Consumed By</dt>
                      <dd>{selectedArtifact.consumed_by?.length ? selectedArtifact.consumed_by.join(', ') : '—'}</dd>
                    </div>
                  </dl>
                </div>
                <div className={styles.detailSection}>
                  <h4>Payload</h4>
                  <JsonAttributeRenderer
                    value={JSON.stringify(selectedArtifact.payload, null, 2)}
                    maxStringLength={Number.POSITIVE_INFINITY}
                  />
                </div>
                <div className={styles.detailSection}>
                  <h4>Consumption History</h4>
                  {selectedArtifact.consumptions && selectedArtifact.consumptions.length > 0 ? (
                    <ul className={styles.consumptionList}>
                      {selectedArtifact.consumptions.map((entry) => (
                        <li key={`${entry.consumer}-${entry.consumed_at}`}>
                          <span className={styles.consumerName}>{entry.consumer}</span>
                          <span>{new Date(entry.consumed_at).toLocaleString()}</span>
                          {entry.run_id ? <span className={styles.runBadge}>Run {entry.run_id}</span> : null}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className={styles.emptyConsumption}>No consumers recorded for this artifact.</p>
                  )}
                </div>
              </>
            ) : (
              <div className={styles.emptyDetail}>Select an artifact to inspect payload and history.</div>
            )}
          </aside>
        </div>
      )}

      {loading && <div className={styles.loading}>Loading…</div>}
    </div>
  );
};

export default HistoricalArtifactsModule;
