import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ModuleContext } from './ModuleRegistry';

interface Span {
  name: string;
  context: {
    trace_id: string;
    span_id: string;
  };
  parent_id?: string;
  start_time: number;
  end_time: number;
  status: {
    status_code: string;
    description?: string;
  };
  attributes: Record<string, string>;
  kind: string;
  resource: {
    'service.name': string;
  };
}

interface SpanNode extends Span {
  children: SpanNode[];
  depth: number;
}

interface TraceModuleProps {
  context: ModuleContext;
}

interface TraceGroup {
  traceId: string;
  spans: Span[];
  startTime: number;
  endTime: number;
  duration: number;
  spanCount: number;
  hasError: boolean;
}

type SortField = 'timestamp' | 'duration' | 'spans' | 'traceId';
type SortDirection = 'asc' | 'desc';

const TraceModule: React.FC<TraceModuleProps> = () => {
  const [traces, setTraces] = useState<Span[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [expandedSpans, setExpandedSpans] = useState<Set<string>>(new Set());
  const [collapsedParentSpans, setCollapsedParentSpans] = useState<Set<string>>(new Set());
  const [sortField] = useState<SortField>('timestamp');
  const [sortDirection] = useState<SortDirection>('desc');
  const [searchQuery, setSearchQuery] = useState('');

  // Refs to prevent flickering and preserve scroll
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const lastTraceCountRef = useRef<number>(0);

  // Fetch traces from backend
  useEffect(() => {
    const fetchTraces = async () => {
      try {
        // Only show loading spinner on initial load, not on refreshes
        if (traces.length === 0) {
          setLoading(true);
        }

        const response = await fetch('/api/traces');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();

        // Only update if data has actually changed (prevents unnecessary re-renders)
        if (JSON.stringify(data) !== JSON.stringify(traces)) {
          // Save scroll position before update
          const scrollTop = scrollContainerRef.current?.scrollTop || 0;

          setTraces(data);
          setError(null);

          // Restore scroll position after render
          requestAnimationFrame(() => {
            if (scrollContainerRef.current && data.length === lastTraceCountRef.current) {
              scrollContainerRef.current.scrollTop = scrollTop;
            }
          });

          lastTraceCountRef.current = data.length;
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load traces');
        console.error('Error loading traces:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchTraces();
    // Refresh every 5 seconds
    const interval = setInterval(fetchTraces, 5000);
    return () => clearInterval(interval);
  }, [traces]);

  // Group spans by trace ID
  const traceGroups = useMemo((): TraceGroup[] => {
    const grouped = new Map<string, Span[]>();

    traces.forEach(span => {
      const traceId = span.context.trace_id;
      if (!grouped.has(traceId)) {
        grouped.set(traceId, []);
      }
      grouped.get(traceId)!.push(span);
    });

    return Array.from(grouped.entries()).map(([traceId, spans]) => {
      const startTime = Math.min(...spans.map(s => s.start_time));
      const endTime = Math.max(...spans.map(s => s.end_time));
      const duration = (endTime - startTime) / 1_000_000; // Convert to ms
      const hasError = spans.some(s => s.status.status_code === 'ERROR');

      return {
        traceId,
        spans: spans.sort((a, b) => a.start_time - b.start_time),
        startTime,
        endTime,
        duration,
        spanCount: spans.length,
        hasError,
      };
    });
  }, [traces]);

  // Filter traces
  const filteredTraces = useMemo(() => {
    let result = traceGroups;

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(trace =>
        trace.traceId.toLowerCase().includes(query) ||
        trace.spans.some(span =>
          span.name.toLowerCase().includes(query) ||
          Object.values(span.attributes).some(val =>
            val.toLowerCase().includes(query)
          )
        )
      );
    }

    return result;
  }, [traceGroups, searchQuery]);

  // Sort traces
  const sortedTraces = useMemo(() => {
    const sorted = [...filteredTraces];

    sorted.sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'timestamp':
          comparison = a.startTime - b.startTime;
          break;
        case 'duration':
          comparison = a.duration - b.duration;
          break;
        case 'spans':
          comparison = a.spanCount - b.spanCount;
          break;
        case 'traceId':
          comparison = a.traceId.localeCompare(b.traceId);
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }, [filteredTraces, sortField, sortDirection]);

  // Sort handler - can be used for future sorting features
  // const handleSort = (field: SortField) => {
  //   if (sortField === field) {
  //     setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
  //   } else {
  //     setSortField(field);
  //     setSortDirection('desc');
  //   }
  // };

  const toggleSpanExpand = (spanId: string) => {
    setExpandedSpans(prev => {
      const newSet = new Set(prev);
      if (newSet.has(spanId)) {
        newSet.delete(spanId);
      } else {
        newSet.add(spanId);
      }
      return newSet;
    });
  };

  const toggleParentCollapse = (spanId: string) => {
    setCollapsedParentSpans(prev => {
      const newSet = new Set(prev);
      if (newSet.has(spanId)) {
        newSet.delete(spanId);
      } else {
        newSet.add(spanId);
      }
      return newSet;
    });
  };

  // Build tree structure from flat span list
  const buildSpanTree = (spans: Span[]): SpanNode[] => {
    const spanMap = new Map<string, SpanNode>();
    const roots: SpanNode[] = [];

    // First pass: create all nodes
    spans.forEach(span => {
      spanMap.set(span.context.span_id, {
        ...span,
        children: [],
        depth: 0,
      });
    });

    // Second pass: build tree structure
    spans.forEach(span => {
      const node = spanMap.get(span.context.span_id)!;

      if (span.parent_id && spanMap.has(span.parent_id)) {
        const parent = spanMap.get(span.parent_id)!;
        parent.children.push(node);
        node.depth = parent.depth + 1;
      } else {
        roots.push(node);
      }
    });

    // Sort children by start time
    const sortChildren = (node: SpanNode) => {
      node.children.sort((a, b) => a.start_time - b.start_time);
      node.children.forEach(sortChildren);
    };
    roots.forEach(sortChildren);

    return roots;
  };

  const getSpanColor = (span: Span): string => {
    if (span.status.status_code === 'ERROR') return 'var(--color-error)';
    if (span.name.includes('Agent.execute')) return 'var(--color-primary-500)';
    if (span.name.includes('Engine')) return 'var(--color-success)';
    if (span.name.includes('Component')) return 'var(--color-warning)';
    return 'var(--color-info)';
  };

  const renderSpanNode = (
    node: SpanNode,
    traceStartTime: number,
    scaleDuration: number
  ): React.ReactElement => {
    const spanStartOffset = (node.start_time - traceStartTime) / 1_000_000; // ms
    const spanDuration = (node.end_time - node.start_time) / 1_000_000; // ms

    // Calculate percentages based on the actual scale, capped at 100%
    const leftPercent = Math.min((spanStartOffset / scaleDuration) * 100, 100);
    const widthPercent = Math.min((spanDuration / scaleDuration) * 100, 100 - leftPercent);

    // Ensure minimum visibility (at least 0.5% width for very small spans)
    const displayWidthPercent = Math.max(widthPercent, 0.5);

    const isExpanded = expandedSpans.has(node.context.span_id);
    const isCollapsed = collapsedParentSpans.has(node.context.span_id);
    const hasChildren = node.children.length > 0;
    const agentName = node.attributes['agent.name'] || '';

    // Indentation based on depth
    const indentWidth = node.depth * 24;

    return (
      <div key={node.context.span_id} style={{ marginBottom: 'var(--space-component-xs)' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: 'var(--space-component-xs)',
            borderRadius: 'var(--radius-md)',
            transition: 'var(--transition-colors)',
          }}
        >
          {/* Span name with tree structure */}
          <div style={{
            width: '300px',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-mono)',
            color: 'var(--color-text-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--gap-sm)',
            paddingLeft: `${indentWidth}px`,
          }}>
            {/* Tree expand/collapse icon */}
            {hasChildren && (
              <span
                onClick={() => toggleParentCollapse(node.context.span_id)}
                style={{
                  opacity: 0.5,
                  cursor: 'pointer',
                  userSelect: 'none',
                  width: '16px',
                  display: 'inline-block',
                }}
                title={isCollapsed ? 'Expand children' : 'Collapse children'}
              >
                {isCollapsed ? '▶' : '▼'}
              </span>
            )}
            {!hasChildren && <span style={{ width: '16px', display: 'inline-block' }} />}

            {/* Details expand icon */}
            <span
              onClick={() => toggleSpanExpand(node.context.span_id)}
              style={{ opacity: 0.5, cursor: 'pointer', userSelect: 'none' }}
              title={isExpanded ? 'Hide details' : 'Show details'}
            >
              {isExpanded ? '▽' : '▷'}
            </span>

            <span
              onClick={() => toggleSpanExpand(node.context.span_id)}
              style={{
                fontWeight: node.status.status_code === 'ERROR' ? 'var(--font-weight-bold)' : 'normal',
                cursor: 'pointer',
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {node.name}
            </span>

            {agentName && (
              <span style={{
                fontSize: 'var(--font-size-body-xs)',
                color: 'var(--color-warning)',
                background: 'var(--color-warning-alpha-10)',
                padding: '2px 6px',
                borderRadius: 'var(--radius-sm)',
                flexShrink: 0,
              }}>
                {agentName}
              </span>
            )}

            {hasChildren && (
              <span style={{
                fontSize: 'var(--font-size-body-xs)',
                color: 'var(--color-text-tertiary)',
                flexShrink: 0,
              }}>
                ({node.children.length})
              </span>
            )}
          </div>

          {/* Waterfall bar */}
          <div style={{
            flex: 1,
            position: 'relative',
            height: '24px',
            marginLeft: 'var(--space-component-md)',
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: 'var(--radius-sm)',
          }}>
            <div
              style={{
                position: 'absolute',
                left: `${leftPercent}%`,
                width: `${displayWidthPercent}%`,
                height: '100%',
                background: getSpanColor(node),
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 'var(--font-size-body-xs)',
                color: 'white',
                fontWeight: 'var(--font-weight-medium)',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
              }}
              title={`${node.name}: ${spanDuration.toFixed(2)}ms (${spanStartOffset.toFixed(2)}ms - ${(spanStartOffset + spanDuration).toFixed(2)}ms)`}
            >
              {displayWidthPercent > 5 ? `${spanDuration.toFixed(2)}ms` : ''}
            </div>
          </div>
        </div>

        {/* Expanded details */}
        {isExpanded && (
          <div style={{
            marginLeft: `${320 + indentWidth}px`,
            marginTop: 'var(--space-component-xs)',
            marginBottom: 'var(--space-component-sm)',
            padding: 'var(--space-component-sm)',
            background: 'var(--color-bg-surface)',
            borderLeft: `3px solid ${getSpanColor(node)}`,
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--font-size-body-xs)',
            fontFamily: 'var(--font-family-mono)',
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 'var(--gap-xs)', color: 'var(--color-text-secondary)' }}>
              <div style={{ color: 'var(--color-text-tertiary)' }}>Span ID:</div>
              <div>{node.context.span_id}</div>

              {node.parent_id && (
                <>
                  <div style={{ color: 'var(--color-text-tertiary)' }}>Parent ID:</div>
                  <div>{node.parent_id}</div>
                </>
              )}

              <div style={{ color: 'var(--color-text-tertiary)' }}>Status:</div>
              <div style={{
                color: node.status.status_code === 'ERROR' ? 'var(--color-error)' : 'var(--color-success)',
                fontWeight: 'var(--font-weight-medium)',
              }}>
                {node.status.status_code}
              </div>

              <div style={{ color: 'var(--color-text-tertiary)' }}>Kind:</div>
              <div>{node.kind}</div>

              {Object.entries(node.attributes).map(([key, value]) => (
                <React.Fragment key={key}>
                  <div style={{ color: 'var(--color-text-tertiary)' }}>{key}:</div>
                  <div>{value}</div>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {/* Render children if not collapsed */}
        {hasChildren && !isCollapsed && (
          <div>
            {node.children.map(child => renderSpanNode(child, traceStartTime, scaleDuration))}
          </div>
        )}
      </div>
    );
  };

  const renderWaterfall = (trace: TraceGroup) => {
    const traceStartTime = trace.startTime;
    const traceDuration = trace.duration;

    // Calculate the max end time to ensure proper scaling
    const maxEndOffset = Math.max(...trace.spans.map(s => (s.end_time - traceStartTime) / 1_000_000));
    const scaleDuration = Math.max(maxEndOffset, traceDuration);

    // Build tree structure
    const spanTree = buildSpanTree(trace.spans);

    return (
      <div style={{
        marginTop: 'var(--space-component-md)',
        background: 'var(--color-bg-base)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-component-md)',
      }}>
        {spanTree.map(node => renderSpanNode(node, traceStartTime, scaleDuration))}
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: 'var(--color-text-secondary)',
        fontSize: 'var(--font-size-body-sm)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)', opacity: 0.5 }}>🔍</div>
          <div>Loading traces...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: 'var(--color-error)',
        fontSize: 'var(--font-size-body-sm)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)' }}>⚠️</div>
          <div>{error}</div>
          <div style={{ fontSize: 'var(--font-size-body-xs)', marginTop: 'var(--gap-sm)', color: 'var(--color-text-secondary)' }}>
            Make sure auto-tracing is enabled: FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--color-bg-surface)',
    }}>
      {/* Header with search and controls */}
      <div style={{
        padding: 'var(--space-component-md)',
        borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--gap-md)',
      }}>
        <input
          type="text"
          placeholder="Search traces... (trace ID, span name, agent name)"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            flex: 1,
            padding: 'var(--space-component-sm)',
            border: 'var(--border-width-1) solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-bg-base)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-body-sm)',
          }}
        />
        <div style={{
          fontSize: 'var(--font-size-body-xs)',
          color: 'var(--color-text-secondary)',
        }}>
          {sortedTraces.length} trace{sortedTraces.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Trace list */}
      <div
        ref={scrollContainerRef}
        style={{ flex: 1, overflow: 'auto', padding: 'var(--space-component-md)' }}
      >
        {sortedTraces.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: 'var(--space-component-xl)',
            color: 'var(--color-text-secondary)',
          }}>
            <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)', opacity: 0.5 }}>📊</div>
            <div>No traces found</div>
            <div style={{ fontSize: 'var(--font-size-body-xs)', marginTop: 'var(--gap-sm)', opacity: 0.7 }}>
              Run your agents with FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
            </div>
          </div>
        ) : (
          sortedTraces.map((trace) => (
            <div
              key={trace.traceId}
              style={{
                marginBottom: 'var(--space-component-lg)',
                background: 'var(--color-bg-elevated)',
                borderRadius: 'var(--radius-lg)',
                border: `var(--border-width-1) solid ${trace.hasError ? 'var(--color-error)' : 'var(--color-border-subtle)'}`,
                overflow: 'hidden',
              }}
            >
              {/* Trace header */}
              <div
                onClick={() => setSelectedTraceId(selectedTraceId === trace.traceId ? null : trace.traceId)}
                style={{
                  padding: 'var(--space-component-md)',
                  background: trace.hasError ? 'var(--color-error-alpha-10)' : 'var(--color-bg-surface)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  transition: 'var(--transition-colors)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = trace.hasError
                    ? 'var(--color-error-alpha-20)'
                    : 'var(--color-bg-elevated)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = trace.hasError
                    ? 'var(--color-error-alpha-10)'
                    : 'var(--color-bg-surface)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-md)' }}>
                  <div style={{
                    fontSize: 'var(--font-size-body-lg)',
                    color: 'var(--color-text-secondary)',
                    opacity: 0.5,
                  }}>
                    {selectedTraceId === trace.traceId ? '▼' : '▶'}
                  </div>
                  <div>
                    <div style={{
                      fontSize: 'var(--font-size-body-sm)',
                      fontFamily: 'var(--font-family-mono)',
                      color: 'var(--color-text-primary)',
                      marginBottom: 'var(--gap-xs)',
                    }}>
                      {trace.traceId.slice(0, 16)}...
                    </div>
                    <div style={{
                      display: 'flex',
                      gap: 'var(--gap-sm)',
                      fontSize: 'var(--font-size-body-xs)',
                      color: 'var(--color-text-tertiary)',
                    }}>
                      <span>{new Date(trace.startTime / 1_000_000).toLocaleString()}</span>
                      <span>•</span>
                      <span>{trace.spanCount} spans</span>
                    </div>
                  </div>
                </div>
                <div style={{
                  fontSize: 'var(--font-size-body-md)',
                  fontWeight: 'var(--font-weight-bold)',
                  color: trace.hasError ? 'var(--color-error)' : 'var(--color-text-primary)',
                }}>
                  {trace.duration.toFixed(2)}ms
                  {trace.hasError && (
                    <span style={{ marginLeft: 'var(--gap-sm)', fontSize: 'var(--font-size-body-sm)' }}>⚠️ Error</span>
                  )}
                </div>
              </div>

              {/* Trace waterfall */}
              {selectedTraceId === trace.traceId && (
                <div style={{ padding: 'var(--space-component-md)' }}>
                  {renderWaterfall(trace)}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TraceModule;
