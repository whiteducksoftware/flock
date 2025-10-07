import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ModuleContext } from './ModuleRegistry';
import JsonAttributeRenderer from './JsonAttributeRenderer';

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
    'service.name'?: string;
  };
}

interface SpanNode extends Span {
  children: SpanNode[];
  depth: number;
}

interface TraceModuleJaegerProps {
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
  services: Set<string>;
}

type ViewMode = 'timeline' | 'statistics';

const TraceModuleJaeger: React.FC<TraceModuleJaegerProps> = () => {
  const [traces, setTraces] = useState<Span[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTraceIds, setSelectedTraceIds] = useState<Set<string>>(new Set());
  const [expandedSpans, setExpandedSpans] = useState<Set<string>>(new Set());
  const [collapsedSpans, setCollapsedSpans] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('timeline');
  const [focusedSpanId, setFocusedSpanId] = useState<string | null>(null);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const lastTraceCountRef = useRef<number>(0);

  // Service colors - assign consistent colors per service or span type
  const serviceColors = useMemo(() => {
    const colors = [
      '#3b82f6', // blue
      '#10b981', // green
      '#f59e0b', // amber
      '#ef4444', // red
      '#8b5cf6', // purple
      '#ec4899', // pink
      '#06b6d4', // cyan
      '#f97316', // orange
    ];

    const colorMap = new Map<string, string>();
    const services: string[] = [];
    const spanTypes: string[] = [];

    traces.forEach(span => {
      // Extract service from span name (e.g., "Flock.publish" -> service: "Flock")
      const serviceName = span.name.split('.')[0] || span.resource['service.name'] || 'unknown';
      if (serviceName && !services.includes(serviceName)) {
        services.push(serviceName);
      }

      // Also track span types for color coding (use full span name for more granular types)
      const spanType = span.name.split('.')[0] || span.name; // Get class name
      if (spanType && !spanTypes.includes(spanType)) {
        spanTypes.push(spanType);
      }
    });

    // If all spans have the same service, color by span type instead
    if (services.length === 1) {
      spanTypes.forEach((type, idx) => {
        const color = colors[idx % colors.length] || '#6366f1';
        colorMap.set(type, color);
      });
    } else {
      services.forEach((service, idx) => {
        const color = colors[idx % colors.length] || '#6366f1';
        colorMap.set(service!, color);
      });
    }

    return { colorMap, useSpanType: services.length === 1 };
  }, [traces]);

  useEffect(() => {
    const fetchTraces = async () => {
      try {
        if (traces.length === 0) {
          setLoading(true);
        }

        const response = await fetch('/api/traces');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();

        if (JSON.stringify(data) !== JSON.stringify(traces)) {
          const scrollTop = scrollContainerRef.current?.scrollTop || 0;
          setTraces(data);
          setError(null);

          requestAnimationFrame(() => {
            if (scrollContainerRef.current && data.length === lastTraceCountRef.current) {
              scrollContainerRef.current.scrollTop = scrollTop;
            }
          });

          lastTraceCountRef.current = data.length;
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load traces');
      } finally {
        setLoading(false);
      }
    };

    fetchTraces();
    const interval = setInterval(fetchTraces, 5000);
    return () => clearInterval(interval);
  }, [traces]);

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
      const duration = (endTime - startTime) / 1_000_000;
      const hasError = spans.some(s => s.status.status_code === 'ERROR');
      const services = new Set(spans.map(s => s.name.split('.')[0] || s.resource['service.name'] || 'unknown'));

      return {
        traceId,
        spans: spans.sort((a, b) => a.start_time - b.start_time),
        startTime,
        endTime,
        duration,
        spanCount: spans.length,
        hasError,
        services,
      };
    });
  }, [traces]);

  const filteredTraces = useMemo(() => {
    let result = traceGroups;

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(trace =>
        trace.traceId.toLowerCase().includes(query) ||
        trace.spans.some(span =>
          span.name.toLowerCase().includes(query) ||
          Object.values(span.attributes).some(val =>
            typeof val === 'string' && val.toLowerCase().includes(query)
          )
        )
      );
    }

    return result.sort((a, b) => b.startTime - a.startTime);
  }, [traceGroups, searchQuery]);

  const buildSpanTree = (spans: Span[]): SpanNode[] => {
    const spanMap = new Map<string, SpanNode>();
    const roots: SpanNode[] = [];

    spans.forEach(span => {
      spanMap.set(span.context.span_id, {
        ...span,
        children: [],
        depth: 0,
      });
    });

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

    const sortChildren = (node: SpanNode) => {
      node.children.sort((a, b) => a.start_time - b.start_time);
      node.children.forEach(sortChildren);
    };
    roots.forEach(sortChildren);

    return roots;
  };

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

  const toggleSpanCollapse = (spanId: string) => {
    setCollapsedSpans(prev => {
      const newSet = new Set(prev);
      if (newSet.has(spanId)) {
        newSet.delete(spanId);
      } else {
        newSet.add(spanId);
      }
      return newSet;
    });
  };

  const getServiceColor = (serviceName: string | undefined, spanName: string): string => {
    if (serviceColors.useSpanType) {
      // Color by span type if all services are the same
      const spanType = spanName.split('.')[0] || spanName;
      return serviceColors.colorMap.get(spanType) || '#6366f1';
    }
    if (!serviceName) return '#6366f1';
    return serviceColors.colorMap.get(serviceName) || '#6366f1';
  };

  const renderStatisticsView = (trace: TraceGroup) => {
    return (
      <div style={{
        marginTop: 'var(--space-component-md)',
        background: 'var(--color-bg-base)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
      }}>
        <table style={{
          width: '100%',
          fontSize: 'var(--font-size-body-sm)',
          fontFamily: 'var(--font-family-mono)',
          borderCollapse: 'collapse',
        }}>
          <thead>
            <tr style={{
              background: 'var(--color-bg-surface)',
              borderBottom: '2px solid var(--color-border-subtle)',
            }}>
              <th style={{ padding: '12px', textAlign: 'left', color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-bold)' }}>Service</th>
              <th style={{ padding: '12px', textAlign: 'left', color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-bold)' }}>Operation</th>
              <th style={{ padding: '12px', textAlign: 'right', color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-bold)' }}>Duration</th>
              <th style={{ padding: '12px', textAlign: 'right', color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-bold)' }}>Start Time</th>
              <th style={{ padding: '12px', textAlign: 'center', color: 'var(--color-text-secondary)', fontWeight: 'var(--font-weight-bold)' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {trace.spans.map((span, idx) => {
              const duration = (span.end_time - span.start_time) / 1_000_000;
              const startOffset = (span.start_time - trace.startTime) / 1_000_000;
              const serviceName = span.name.split('.')[0] || span.resource['service.name'] || 'unknown';

              return (
                <tr
                  key={span.context.span_id}
                  style={{
                    background: idx % 2 === 0 ? 'transparent' : 'var(--color-bg-surface)',
                    borderBottom: '1px solid var(--color-border-subtle)',
                  }}
                >
                  <td style={{ padding: '10px' }}>
                    <span style={{
                      display: 'inline-block',
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: getServiceColor(serviceName, span.name),
                      marginRight: '8px',
                    }} />
                    {serviceName}
                  </td>
                  <td style={{ padding: '10px', color: 'var(--color-text-primary)' }}>{span.name}</td>
                  <td style={{ padding: '10px', textAlign: 'right', color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                    {duration.toFixed(2)}ms
                  </td>
                  <td style={{ padding: '10px', textAlign: 'right', color: 'var(--color-text-tertiary)' }}>
                    +{startOffset.toFixed(2)}ms
                  </td>
                  <td style={{ padding: '10px', textAlign: 'center' }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 'var(--font-size-body-xs)',
                      fontWeight: 'var(--font-weight-medium)',
                      background: span.status.status_code === 'ERROR' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                      color: span.status.status_code === 'ERROR' ? '#ef4444' : '#10b981',
                    }}>
                      {span.status.status_code}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  const renderSpanNode = (
    node: SpanNode,
    traceStartTime: number,
    scaleDuration: number
  ): React.ReactElement => {
    const spanStartOffset = (node.start_time - traceStartTime) / 1_000_000;
    const spanDuration = (node.end_time - node.start_time) / 1_000_000;

    const leftPercent = Math.min((spanStartOffset / scaleDuration) * 100, 100);
    const widthPercent = Math.min((spanDuration / scaleDuration) * 100, 100 - leftPercent);
    const displayWidthPercent = Math.max(widthPercent, 0.5);

    const isExpanded = expandedSpans.has(node.context.span_id);
    const isCollapsed = collapsedSpans.has(node.context.span_id);
    const hasChildren = node.children.length > 0;
    const serviceName = node.name.split('.')[0] || node.resource['service.name'] || 'unknown';
    const serviceColor = getServiceColor(serviceName, node.name);
    const isFocused = focusedSpanId === node.context.span_id;

    return (
      <div key={node.context.span_id} style={{ marginBottom: '1px', opacity: isFocused ? 1 : (focusedSpanId ? 0.4 : 1) }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '400px 1fr',
            alignItems: 'center',
            background: isExpanded ? 'var(--color-bg-elevated)' : 'transparent',
            borderBottom: '1px solid rgba(255, 255, 255, 0.03)',
          }}
        >
          {/* Left side: Hierarchy */}
          <div style={{
            padding: '8px 12px',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-mono)',
            color: 'var(--color-text-primary)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            paddingLeft: `${12 + node.depth * 20}px`,
            borderRight: '1px solid var(--color-border-subtle)',
          }}>
            {hasChildren && (
              <span
                onClick={() => toggleSpanCollapse(node.context.span_id)}
                style={{
                  cursor: 'pointer',
                  userSelect: 'none',
                  width: '12px',
                  opacity: 0.6,
                  fontSize: '10px',
                }}
              >
                {isCollapsed ? '►' : '▼'}
              </span>
            )}
            {!hasChildren && <span style={{ width: '12px' }} />}

            <span
              style={{
                display: 'inline-block',
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: serviceColor,
                flexShrink: 0,
              }}
            />

            <span
              onClick={(e) => {
                if (e.shiftKey) {
                  setFocusedSpanId(isFocused ? null : node.context.span_id);
                } else {
                  toggleSpanExpand(node.context.span_id);
                }
              }}
              style={{
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
              title={`${node.name}\nShift+click to focus`}
            >
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{node.name}</span>
            </span>

            <span style={{
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-tertiary)',
              flexShrink: 0,
            }}>
              {spanDuration.toFixed(1)}ms
            </span>
          </div>

          {/* Right side: Gantt chart */}
          <div style={{
            padding: '8px 12px',
            height: '32px',
          }}>
            <div style={{
              position: 'relative',
              height: '18px',
              width: '100%',
            }}>
              <div
                style={{
                  position: 'absolute',
                  left: `${leftPercent}%`,
                  width: `${displayWidthPercent}%`,
                  height: '100%',
                  background: serviceColor,
                  border: node.status.status_code === 'ERROR' ? '2px solid #ef4444' : 'none',
                  borderRadius: '2px',
                  display: 'flex',
                  alignItems: 'center',
                  paddingLeft: '4px',
                  fontSize: '10px',
                  color: 'white',
                  fontWeight: 'var(--font-weight-medium)',
                  cursor: 'pointer',
                  boxSizing: 'border-box',
                }}
                onClick={() => toggleSpanExpand(node.context.span_id)}
                title={`${node.name}\nService: ${serviceName || 'unknown'}\n${spanDuration.toFixed(2)}ms\nStart: +${spanStartOffset.toFixed(2)}ms`}
              />
            </div>
          </div>
        </div>

        {isExpanded && (
          <div style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderLeft: `4px solid ${serviceColor}`,
            margin: '0 12px 8px 12px',
            padding: 'var(--space-component-sm)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--font-size-body-xs)',
            fontFamily: 'var(--font-family-mono)',
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '6px', color: 'var(--color-text-secondary)' }}>
              <div style={{ color: 'var(--color-text-tertiary)', fontWeight: 'var(--font-weight-medium)' }}>Service:</div>
              <div>{serviceName}</div>

              <div style={{ color: 'var(--color-text-tertiary)', fontWeight: 'var(--font-weight-medium)' }}>Span ID:</div>
              <div style={{ wordBreak: 'break-all' }}>{node.context.span_id}</div>

              {node.parent_id && (
                <>
                  <div style={{ color: 'var(--color-text-tertiary)', fontWeight: 'var(--font-weight-medium)' }}>Parent ID:</div>
                  <div style={{ wordBreak: 'break-all' }}>{node.parent_id}</div>
                </>
              )}

              <div style={{ color: 'var(--color-text-tertiary)', fontWeight: 'var(--font-weight-medium)' }}>Duration:</div>
              <div>{spanDuration.toFixed(3)}ms</div>

              <div style={{ color: 'var(--color-text-tertiary)', fontWeight: 'var(--font-weight-medium)' }}>Start Time:</div>
              <div>+{spanStartOffset.toFixed(3)}ms</div>

              <div style={{ color: 'var(--color-text-tertiary)', fontWeight: 'var(--font-weight-medium)' }}>Status:</div>
              <div style={{
                color: node.status.status_code === 'ERROR' ? '#ef4444' : '#10b981',
                fontWeight: 'var(--font-weight-bold)',
              }}>
                {node.status.status_code}
              </div>

              {Object.entries(node.attributes).length > 0 && (
                <>
                  <div style={{
                    gridColumn: '1 / -1',
                    borderTop: '1px solid var(--color-border-subtle)',
                    margin: '8px 0 4px 0',
                    paddingTop: '8px',
                    color: 'var(--color-text-secondary)',
                    fontWeight: 'var(--font-weight-medium)',
                  }}>
                    Tags:
                  </div>
                  {Object.entries(node.attributes).map(([key, value]) => (
                    <React.Fragment key={key}>
                      <div style={{ color: 'var(--color-text-tertiary)', alignSelf: 'start' }}>{key}:</div>
                      <div>
                        <JsonAttributeRenderer value={value} />
                      </div>
                    </React.Fragment>
                  ))}
                </>
              )}
            </div>
          </div>
        )}

        {hasChildren && !isCollapsed && (
          <div>
            {node.children.map(child => renderSpanNode(child, traceStartTime, scaleDuration))}
          </div>
        )}
      </div>
    );
  };

  const renderTimelineView = (trace: TraceGroup) => {
    const maxEndOffset = Math.max(...trace.spans.map(s => (s.end_time - trace.startTime) / 1_000_000));
    const scaleDuration = Math.max(maxEndOffset, trace.duration);
    const spanTree = buildSpanTree(trace.spans);

    return (
      <div style={{
        marginTop: 'var(--space-component-md)',
        background: 'var(--color-bg-base)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
      }}>
        {/* Header with timeline scale */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '400px 1fr',
          background: 'var(--color-bg-surface)',
          borderBottom: '2px solid var(--color-border-subtle)',
          fontSize: 'var(--font-size-body-xs)',
          color: 'var(--color-text-tertiary)',
          fontWeight: 'var(--font-weight-medium)',
        }}>
          <div style={{ padding: '10px 12px', borderRight: '1px solid var(--color-border-subtle)' }}>
            Service & Operation
          </div>
          <div style={{ padding: '10px 12px' }}>
            Timeline (0ms - {scaleDuration.toFixed(0)}ms)
          </div>
        </div>

        {spanTree.map(node => renderSpanNode(node, trace.startTime, scaleDuration))}
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
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)', opacity: 0.5 }}>🔎</div>
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
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)' }}>⚠️</div>
          <div>{error}</div>
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
      <div style={{
        padding: 'var(--space-component-md)',
        borderBottom: '1px solid var(--color-border-subtle)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--gap-md)',
      }}>
        <input
          type="text"
          placeholder="🔎 Find traces (Jaeger style)"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            flex: 1,
            padding: 'var(--space-component-sm)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-bg-base)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-body-sm)',
          }}
        />

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setViewMode('timeline')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'timeline' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'timeline' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            Timeline
          </button>
          <button
            onClick={() => setViewMode('statistics')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'statistics' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'statistics' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            Statistics
          </button>
        </div>

        <div style={{
          fontSize: 'var(--font-size-body-xs)',
          color: 'var(--color-text-secondary)',
        }}>
          {filteredTraces.length} trace{filteredTraces.length !== 1 ? 's' : ''}
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        style={{ flex: 1, overflow: 'auto', padding: 'var(--space-component-md)' }}
      >
        {filteredTraces.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: 'var(--space-component-xl)',
            color: 'var(--color-text-secondary)',
          }}>
            <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)', opacity: 0.5 }}>🔎</div>
            <div>No traces found</div>
          </div>
        ) : (
          filteredTraces.map((trace) => (
            <div
              key={trace.traceId}
              style={{
                marginBottom: 'var(--space-component-lg)',
                background: 'var(--color-bg-elevated)',
                borderRadius: 'var(--radius-lg)',
                border: `1px solid ${trace.hasError ? '#ef4444' : 'var(--color-border-subtle)'}`,
                overflow: 'hidden',
              }}
            >
              <div
                onClick={() => {
                  setSelectedTraceIds(prev => {
                    const newSet = new Set(prev);
                    if (newSet.has(trace.traceId)) {
                      newSet.delete(trace.traceId);
                    } else {
                      newSet.add(trace.traceId);
                    }
                    return newSet;
                  });
                }}
                style={{
                  padding: 'var(--space-component-md)',
                  background: trace.hasError ? 'rgba(239, 68, 68, 0.1)' : 'var(--color-bg-surface)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-md)' }}>
                  <div style={{ fontSize: '14px', opacity: 0.5 }}>
                    {selectedTraceIds.has(trace.traceId) ? '▼' : '►'}
                  </div>
                  <div>
                    <div style={{
                      fontSize: 'var(--font-size-body-sm)',
                      fontFamily: 'var(--font-family-mono)',
                      color: 'var(--color-text-primary)',
                      fontWeight: 'var(--font-weight-medium)',
                    }}>
                      {trace.traceId.slice(0, 16)}...
                    </div>
                    <div style={{
                      display: 'flex',
                      gap: 'var(--gap-sm)',
                      fontSize: 'var(--font-size-body-xs)',
                      color: 'var(--color-text-tertiary)',
                      marginTop: '4px',
                    }}>
                      <span>{trace.spanCount} spans</span>
                      <span>•</span>
                      <span>{trace.services.size} service{trace.services.size !== 1 ? 's' : ''}</span>
                      <span>•</span>
                      <span>{new Date(trace.startTime / 1_000_000).toLocaleTimeString()}</span>
                    </div>
                  </div>
                </div>
                <div style={{
                  fontSize: 'var(--font-size-body-lg)',
                  fontWeight: 'var(--font-weight-bold)',
                  color: trace.hasError ? '#ef4444' : 'var(--color-text-primary)',
                }}>
                  {trace.duration.toFixed(2)}ms
                </div>
              </div>

              {selectedTraceIds.has(trace.traceId) && (
                <div style={{ padding: 'var(--space-component-md)', paddingTop: 0 }}>
                  {viewMode === 'timeline' && renderTimelineView(trace)}
                  {viewMode === 'statistics' && renderStatisticsView(trace)}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TraceModuleJaeger;
