import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ModuleContext } from './ModuleRegistry';
import JsonAttributeRenderer from './JsonAttributeRenderer';
import TracingSettings from '../settings/TracingSettings';

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

interface ServiceMetrics {
  service: string;
  totalSpans: number;
  errorSpans: number;
  avgDuration: number;
  p95Duration: number;
  p99Duration: number;
  rate: number;
}

interface OperationMetrics {
  operation: string;
  service: string;
  totalCalls: number;
  errorCalls: number;
  avgDuration: number;
  p95Duration: number;
}

interface DependencyEdge {
  from: string; // parent service
  to: string;   // child service
  operations: Map<string, OperationMetrics>; // parent.operation -> child.operation
}

type ViewMode = 'timeline' | 'statistics' | 'metrics' | 'dependencies' | 'sql' | 'configuration' | 'guide';

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
  const [expandedDeps, setExpandedDeps] = useState<Set<string>>(new Set());

  // SQL query state
  const [sqlQuery, setSqlQuery] = useState('SELECT * FROM spans LIMIT 10');
  const [sqlResults, setSqlResults] = useState<any[] | null>(null);
  const [sqlColumns, setSqlColumns] = useState<string[]>([]);
  const [sqlLoading, setSqlLoading] = useState(false);
  const [sqlError, setSqlError] = useState<string | null>(null);

  // Sort state for timeline/statistics
  type SortField = 'date' | 'spans' | 'duration';
  type SortOrder = 'asc' | 'desc';
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc'); // newest first by default

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const lastTraceCountRef = useRef<number>(0);

  // Execute SQL query
  const executeSqlQuery = async () => {
    setSqlLoading(true);
    setSqlError(null);
    try {
      const response = await fetch('/api/traces/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sqlQuery }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Query failed');
      }

      const data = await response.json();
      setSqlResults(data.results);
      setSqlColumns(data.columns);
    } catch (err) {
      setSqlError(err instanceof Error ? err.message : 'Unknown error');
      setSqlResults(null);
      setSqlColumns([]);
    } finally {
      setSqlLoading(false);
    }
  };

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

    // Apply sorting
    return [...result].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'date':
          comparison = a.startTime - b.startTime;
          break;
        case 'spans':
          comparison = a.spanCount - b.spanCount;
          break;
        case 'duration':
          comparison = a.duration - b.duration;
          break;
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [traceGroups, searchQuery, sortField, sortOrder]);

  // Calculate RED metrics per service
  const serviceMetrics = useMemo<ServiceMetrics[]>(() => {
    const metricsMap = new Map<string, ServiceMetrics>();

    traces.forEach(span => {
      const service = span.name.split('.')[0] || 'unknown';
      if (!metricsMap.has(service)) {
        metricsMap.set(service, {
          service,
          totalSpans: 0,
          errorSpans: 0,
          avgDuration: 0,
          p95Duration: 0,
          p99Duration: 0,
          rate: 0,
        });
      }

      const metrics = metricsMap.get(service)!;
      metrics.totalSpans++;
      if (span.status.status_code === 'ERROR') {
        metrics.errorSpans++;
      }
    });

    // Calculate durations and rate
    metricsMap.forEach((metrics, service) => {
      const serviceSpans = traces.filter(s => (s.name.split('.')[0] || 'unknown') === service);
      const durations = serviceSpans.map(s => (s.end_time - s.start_time) / 1_000_000).sort((a, b) => a - b);

      metrics.avgDuration = durations.reduce((sum, d) => sum + d, 0) / durations.length || 0;
      metrics.p95Duration = durations[Math.floor(durations.length * 0.95)] || 0;
      metrics.p99Duration = durations[Math.floor(durations.length * 0.99)] || 0;

      // Calculate rate (spans per second)
      if (serviceSpans.length > 1) {
        const timeSpan = (Math.max(...serviceSpans.map(s => s.end_time)) -
                         Math.min(...serviceSpans.map(s => s.start_time))) / 1_000_000_000;
        metrics.rate = serviceSpans.length / Math.max(timeSpan, 1);
      }
    });

    return Array.from(metricsMap.values()).sort((a, b) => b.totalSpans - a.totalSpans);
  }, [traces]);

  // Build service dependency graph with operation-level drill-down
  const serviceDependencies = useMemo(() => {
    const deps = new Map<string, DependencyEdge>();

    traceGroups.forEach(trace => {
      trace.spans.forEach(span => {
        if (span.parent_id) {
          const parent = trace.spans.find(s => s.context.span_id === span.parent_id);
          if (parent) {
            const parentService = parent.name.split('.')[0] || 'unknown';
            const childService = span.name.split('.')[0] || 'unknown';

            // Only track cross-service dependencies
            if (parentService !== childService) {
              const key = `${parentService}->${childService}`;

              if (!deps.has(key)) {
                deps.set(key, {
                  from: parentService,
                  to: childService,
                  operations: new Map(),
                });
              }

              const edge = deps.get(key)!;
              const opKey = `${parent.name} → ${span.name}`;

              if (!edge.operations.has(opKey)) {
                edge.operations.set(opKey, {
                  operation: opKey,
                  service: childService,
                  totalCalls: 0,
                  errorCalls: 0,
                  avgDuration: 0,
                  p95Duration: 0,
                });
              }

              const opMetrics = edge.operations.get(opKey)!;
              opMetrics.totalCalls++;
              if (span.status.status_code === 'ERROR') {
                opMetrics.errorCalls++;
              }
            }
          }
        }
      });
    });

    // Calculate operation metrics
    deps.forEach(edge => {
      edge.operations.forEach((opMetrics, opKey) => {
        const childOp = opKey.split(' → ')[1];
        const relevantSpans = traces.filter(s => s.name === childOp);
        const durations = relevantSpans.map(s => (s.end_time - s.start_time) / 1_000_000).sort((a, b) => a - b);

        opMetrics.avgDuration = durations.reduce((sum, d) => sum + d, 0) / durations.length || 0;
        opMetrics.p95Duration = durations[Math.floor(durations.length * 0.95)] || 0;
      });
    });

    return Array.from(deps.values());
  }, [traceGroups, traces]);

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
      {/* Two-row header */}
      <div style={{
        padding: 'var(--space-component-md)',
        borderBottom: '1px solid var(--color-border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--gap-sm)',
      }}>
        {/* Row 1: View mode buttons */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
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
            📅 Timeline
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
            📊 Statistics
          </button>
          <button
            onClick={() => setViewMode('metrics')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'metrics' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'metrics' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            🔴 RED Metrics
          </button>
          <button
            onClick={() => setViewMode('dependencies')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'dependencies' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'dependencies' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            🔗 Dependencies
          </button>
          <button
            onClick={() => setViewMode('sql')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'sql' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'sql' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            🗄️ DuckDB SQL
          </button>
          <button
            onClick={() => setViewMode('configuration')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'configuration' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'configuration' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            ⚙️ Configuration
          </button>
          <button
            onClick={() => setViewMode('guide')}
            style={{
              padding: '6px 12px',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: viewMode === 'guide' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
              color: viewMode === 'guide' ? 'white' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body-sm)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            📚 Guide
          </button>

          {/* Trace count */}
          {(viewMode === 'timeline' || viewMode === 'statistics') && (
            <div style={{
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-secondary)',
              marginLeft: 'auto',
            }}>
              {filteredTraces.length} trace{filteredTraces.length !== 1 ? 's' : ''}
            </div>
          )}
        </div>

        {/* Row 2: Search box */}
        <input
          type="text"
          placeholder="🔎 Find traces (Jaeger style) - Search by service, operation, trace ID, correlation ID, or error"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            width: '100%',
            padding: 'var(--space-component-sm)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-bg-base)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-body-sm)',
          }}
        />

        {/* Sort buttons for Timeline and Statistics */}
        {(viewMode === 'timeline' || viewMode === 'statistics') && (
          <div style={{
            display: 'flex',
            gap: 'var(--gap-xs)',
            alignItems: 'center',
            fontSize: 'var(--font-size-body-xs)',
          }}>
            <span style={{ color: 'var(--color-text-tertiary)', flexShrink: 0 }}>Sort:</span>
            {(['date', 'spans', 'duration'] as SortField[]).map((field) => {
              const isActive = sortField === field;
              const labels = { date: 'Date', spans: 'Spans', duration: 'Duration' };

              return (
                <button
                  key={field}
                  onClick={() => {
                    if (sortField === field) {
                      // Toggle order if same field
                      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                    } else {
                      // Switch field, use default order
                      setSortField(field);
                      setSortOrder(field === 'date' ? 'desc' : 'asc');
                    }
                  }}
                  style={{
                    padding: '4px 10px',
                    background: isActive ? 'var(--color-accent)' : 'var(--color-bg-elevated)',
                    color: isActive ? 'white' : 'var(--color-text-secondary)',
                    border: isActive ? 'none' : '1px solid var(--color-border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 'var(--font-size-body-xs)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontWeight: isActive ? 'var(--font-weight-medium)' : 'normal',
                  }}
                >
                  <span>{labels[field]}</span>
                  {isActive && (
                    <span style={{ fontSize: '10px' }}>
                      {sortOrder === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div
        ref={scrollContainerRef}
        style={{ flex: 1, overflow: 'auto', padding: 'var(--space-component-md)' }}
      >
        {/* RED Metrics View */}
        {viewMode === 'metrics' && (
          <div>
            <div style={{
              fontSize: 'var(--font-size-body-md)',
              fontWeight: 'var(--font-weight-medium)',
              color: 'var(--color-text-primary)',
              marginBottom: 'var(--space-component-md)',
            }}>
              RED Metrics by Service
            </div>
            {serviceMetrics.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 'var(--space-component-xl)', color: 'var(--color-text-tertiary)' }}>
                No metrics data available
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 'var(--gap-md)' }}>
                {serviceMetrics.map(metrics => {
                  const serviceColor = serviceColors.colorMap.get(metrics.service) || '#6366f1';
                  const errorRate = metrics.totalSpans > 0 ? (metrics.errorSpans / metrics.totalSpans) * 100 : 0;

                  return (
                    <div
                      key={metrics.service}
                      style={{
                        padding: 'var(--space-component-md)',
                        background: 'var(--color-bg-elevated)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-border-subtle)',
                        borderLeft: `4px solid ${serviceColor}`,
                      }}
                    >
                      <div style={{
                        fontSize: 'var(--font-size-body-lg)',
                        fontWeight: 'var(--font-weight-bold)',
                        color: serviceColor,
                        marginBottom: 'var(--space-component-sm)',
                      }}>
                        {metrics.service}
                      </div>

                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                        gap: 'var(--gap-md)',
                      }}>
                        <div>
                          <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
                            Rate
                          </div>
                          <div style={{ fontSize: 'var(--font-size-body-lg)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)' }}>
                            {metrics.rate.toFixed(2)} req/s
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
                            Error Rate
                          </div>
                          <div style={{
                            fontSize: 'var(--font-size-body-lg)',
                            fontWeight: 'var(--font-weight-medium)',
                            color: errorRate > 0 ? '#ef4444' : '#10b981',
                          }}>
                            {errorRate.toFixed(1)}%
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
                            Avg Duration
                          </div>
                          <div style={{ fontSize: 'var(--font-size-body-lg)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)' }}>
                            {metrics.avgDuration.toFixed(2)}ms
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
                            P95 Duration
                          </div>
                          <div style={{ fontSize: 'var(--font-size-body-lg)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)' }}>
                            {metrics.p95Duration.toFixed(2)}ms
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
                            P99 Duration
                          </div>
                          <div style={{ fontSize: 'var(--font-size-body-lg)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)' }}>
                            {metrics.p99Duration.toFixed(2)}ms
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
                            Total Spans
                          </div>
                          <div style={{ fontSize: 'var(--font-size-body-lg)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)' }}>
                            {metrics.totalSpans}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Dependencies View */}
        {viewMode === 'dependencies' && (
          <div>
            <div style={{
              fontSize: 'var(--font-size-body-md)',
              fontWeight: 'var(--font-weight-medium)',
              color: 'var(--color-text-primary)',
              marginBottom: 'var(--space-component-md)',
            }}>
              Service Dependencies with Operation Drill-down
            </div>
            {serviceDependencies.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 'var(--space-component-xl)', color: 'var(--color-text-tertiary)' }}>
                No service dependencies detected
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 'var(--gap-md)' }}>
                {serviceDependencies.map(dep => {
                  const depKey = `${dep.from}->${dep.to}`;
                  const isExpanded = expandedDeps.has(depKey);
                  const fromColor = serviceColors.colorMap.get(dep.from) || '#6366f1';
                  const toColor = serviceColors.colorMap.get(dep.to) || '#6366f1';

                  return (
                    <div
                      key={depKey}
                      style={{
                        padding: 'var(--space-component-md)',
                        background: 'var(--color-bg-elevated)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-border-subtle)',
                      }}
                    >
                      <div
                        onClick={() => {
                          setExpandedDeps(prev => {
                            const newSet = new Set(prev);
                            if (newSet.has(depKey)) {
                              newSet.delete(depKey);
                            } else {
                              newSet.add(depKey);
                            }
                            return newSet;
                          });
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 'var(--gap-md)',
                          cursor: 'pointer',
                          marginBottom: isExpanded ? 'var(--space-component-md)' : 0,
                        }}
                      >
                        <div style={{ fontSize: '14px', opacity: 0.5 }}>
                          {isExpanded ? '▼' : '►'}
                        </div>

                        <div
                          style={{
                            padding: '6px 16px',
                            borderRadius: 'var(--radius-md)',
                            background: fromColor,
                            color: 'white',
                            fontSize: 'var(--font-size-body-sm)',
                            fontWeight: 'var(--font-weight-bold)',
                          }}
                        >
                          {dep.from}
                        </div>

                        <div style={{ fontSize: 'var(--font-size-body-lg)', color: 'var(--color-text-tertiary)' }}>
                          →
                        </div>

                        <div
                          style={{
                            padding: '6px 16px',
                            borderRadius: 'var(--radius-md)',
                            background: toColor,
                            color: 'white',
                            fontSize: 'var(--font-size-body-sm)',
                            fontWeight: 'var(--font-weight-bold)',
                          }}
                        >
                          {dep.to}
                        </div>

                        <div style={{
                          fontSize: 'var(--font-size-body-xs)',
                          color: 'var(--color-text-tertiary)',
                          marginLeft: 'auto',
                        }}>
                          {dep.operations.size} operation{dep.operations.size !== 1 ? 's' : ''}
                        </div>
                      </div>

                      {/* Operation-level drill-down */}
                      {isExpanded && (
                        <div style={{
                          display: 'grid',
                          gap: 'var(--gap-sm)',
                          paddingLeft: '30px',
                        }}>
                          {Array.from(dep.operations.values()).map(opMetrics => {
                            const errorRate = opMetrics.totalCalls > 0 ? (opMetrics.errorCalls / opMetrics.totalCalls) * 100 : 0;

                            return (
                              <div
                                key={opMetrics.operation}
                                style={{
                                  padding: 'var(--space-component-sm)',
                                  background: 'var(--color-bg-surface)',
                                  borderRadius: 'var(--radius-md)',
                                  border: '1px solid var(--color-border-subtle)',
                                }}
                              >
                                <div style={{
                                  fontSize: 'var(--font-size-body-xs)',
                                  fontFamily: 'var(--font-family-mono)',
                                  color: 'var(--color-text-secondary)',
                                  marginBottom: 'var(--gap-xs)',
                                }}>
                                  {opMetrics.operation}
                                </div>

                                <div style={{
                                  display: 'flex',
                                  gap: 'var(--gap-lg)',
                                  fontSize: 'var(--font-size-body-xs)',
                                }}>
                                  <div>
                                    <span style={{ color: 'var(--color-text-tertiary)' }}>Calls: </span>
                                    <span style={{ color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                                      {opMetrics.totalCalls}
                                    </span>
                                  </div>

                                  <div>
                                    <span style={{ color: 'var(--color-text-tertiary)' }}>Errors: </span>
                                    <span style={{ color: errorRate > 0 ? '#ef4444' : '#10b981', fontWeight: 'var(--font-weight-medium)' }}>
                                      {errorRate.toFixed(1)}%
                                    </span>
                                  </div>

                                  <div>
                                    <span style={{ color: 'var(--color-text-tertiary)' }}>Avg: </span>
                                    <span style={{ color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                                      {opMetrics.avgDuration.toFixed(2)}ms
                                    </span>
                                  </div>

                                  <div>
                                    <span style={{ color: 'var(--color-text-tertiary)' }}>P95: </span>
                                    <span style={{ color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                                      {opMetrics.p95Duration.toFixed(2)}ms
                                    </span>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Configuration View */}
        {viewMode === 'configuration' && (
          <div>
            <TracingSettings />
          </div>
        )}

        {/* Guide View */}
        {viewMode === 'guide' && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--gap-lg)',
            padding: 'var(--space-component-md)',
          }}>
            <div>
              <h3 style={{
                fontSize: 'var(--font-size-heading-sm)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--gap-md)',
              }}>
                🚀 Quick Start Guide
              </h3>
              <div style={{
                display: 'grid',
                gap: 'var(--gap-md)',
                color: 'var(--color-text-secondary)',
                fontSize: 'var(--font-size-body-sm)',
              }}>
                <p>
                  The Trace Viewer provides comprehensive observability for your Flock applications using OpenTelemetry distributed tracing.
                </p>
              </div>
            </div>

            <div>
              <h4 style={{
                fontSize: 'var(--font-size-body-md)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--gap-sm)',
              }}>
                📊 View Modes
              </h4>
              <div style={{
                display: 'grid',
                gap: 'var(--gap-sm)',
              }}>
                {[
                  { icon: '📅', name: 'Timeline', desc: 'Waterfall view of spans showing execution flow and dependencies' },
                  { icon: '📈', name: 'Statistics', desc: 'Aggregated metrics including duration, error rates, and call counts' },
                  { icon: '🔴', name: 'RED Metrics', desc: 'Rate, Errors, Duration metrics for service health monitoring' },
                  { icon: '🔗', name: 'Dependencies', desc: 'Service-to-service communication patterns and operation drill-down' },
                  { icon: '🗄️', name: 'DuckDB SQL', desc: 'Write custom SQL queries against the trace database for advanced analysis' },
                  { icon: '⚙️', name: 'Configuration', desc: 'Configure tracing settings, service filters, and operation blacklists' },
                ].map((mode) => (
                  <div
                    key={mode.name}
                    style={{
                      padding: 'var(--space-component-sm)',
                      background: 'var(--color-bg-surface)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    <div style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-primary)', marginBottom: '4px' }}>
                      {mode.icon} {mode.name}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                      {mode.desc}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 style={{
                fontSize: 'var(--font-size-body-md)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--gap-sm)',
              }}>
                🔍 Search Tips
              </h4>
              <div style={{
                padding: 'var(--space-component-sm)',
                background: 'var(--color-bg-surface)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-subtle)',
                fontSize: 'var(--font-size-body-xs)',
                color: 'var(--color-text-secondary)',
              }}>
                <p style={{ marginBottom: 'var(--gap-xs)' }}>
                  The search box performs text matching across:
                </p>
                <ul style={{ marginLeft: '20px', marginBottom: 'var(--gap-xs)' }}>
                  <li>Trace IDs</li>
                  <li>Span names and operation names</li>
                  <li>Span attributes (key-value pairs)</li>
                </ul>
                <p style={{ fontStyle: 'italic', color: 'var(--color-text-tertiary)' }}>
                  For advanced queries, use the DuckDB SQL tab to write custom queries.
                </p>
              </div>
            </div>

            <div>
              <h4 style={{
                fontSize: 'var(--font-size-body-md)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--gap-sm)',
              }}>
                💡 DuckDB SQL Examples
              </h4>
              <div style={{
                display: 'grid',
                gap: 'var(--gap-sm)',
              }}>
                {[
                  { title: 'Find slow operations', query: 'SELECT service_name, name, duration_ms FROM spans WHERE duration_ms > 1000 ORDER BY duration_ms DESC LIMIT 10' },
                  { title: 'Error rate by service', query: 'SELECT service_name, COUNT(*) as total, SUM(CASE WHEN status_code = \'ERROR\' THEN 1 ELSE 0 END) as errors FROM spans GROUP BY service_name' },
                  { title: 'Recent traces', query: 'SELECT DISTINCT trace_id, MIN(timestamp) as start_time FROM spans GROUP BY trace_id ORDER BY start_time DESC LIMIT 20' },
                  { title: 'Operation hotspots', query: 'SELECT name, COUNT(*) as call_count, AVG(duration_ms) as avg_duration FROM spans GROUP BY name ORDER BY call_count DESC LIMIT 10' },
                ].map((example) => (
                  <div
                    key={example.title}
                    style={{
                      padding: 'var(--space-component-sm)',
                      background: 'var(--color-bg-surface)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    <div style={{
                      fontWeight: 'var(--font-weight-medium)',
                      color: 'var(--color-text-primary)',
                      marginBottom: '4px',
                      fontSize: 'var(--font-size-body-xs)',
                    }}>
                      {example.title}
                    </div>
                    <code style={{
                      display: 'block',
                      padding: '8px',
                      background: 'var(--color-bg-elevated)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 'var(--font-size-body-xs)',
                      fontFamily: 'var(--font-family-mono)',
                      color: 'var(--color-text-secondary)',
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}>
                      {example.query}
                    </code>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 style={{
                fontSize: 'var(--font-size-body-md)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--gap-sm)',
              }}>
                ⚡ Best Practices
              </h4>
              <div style={{
                display: 'grid',
                gap: 'var(--gap-xs)',
                fontSize: 'var(--font-size-body-xs)',
                color: 'var(--color-text-secondary)',
              }}>
                {[
                  'Use service filters to focus on specific components',
                  'Blacklist noisy operations to reduce clutter',
                  'Check RED metrics for quick health overview',
                  'Use Dependencies view to understand service communication',
                  'Write SQL queries for custom analysis and reporting',
                  'Monitor error traces to identify failure patterns',
                ].map((tip, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '8px 12px',
                      background: 'var(--color-bg-surface)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    ✓ {tip}
                  </div>
                ))}
              </div>
            </div>

            <div style={{
              padding: 'var(--space-component-sm)',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid #3b82f6',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-secondary)',
            }}>
              <div style={{ fontWeight: 'var(--font-weight-bold)', color: '#3b82f6', marginBottom: '4px' }}>
                📚 Full Documentation
              </div>
              For comprehensive tracing guides, see <code style={{ fontFamily: 'var(--font-family-mono)' }}>docs/how_to_use_tracing_effectively.md</code>
            </div>
          </div>
        )}

        {/* SQL Query View */}
        {viewMode === 'sql' && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--gap-sm)',
            height: '100%',
          }}>
            {/* Compact SQL Editor */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--gap-xs)',
              flexShrink: 0,
            }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 'var(--gap-sm)',
              }}>
                <div style={{
                  display: 'flex',
                  gap: 'var(--gap-xs)',
                  flexWrap: 'wrap',
                  flex: 1,
                  alignItems: 'center',
                }}>
                  <span style={{
                    fontSize: 'var(--font-size-body-xs)',
                    color: 'var(--color-text-tertiary)',
                    flexShrink: 0,
                  }}>
                    Quick:
                  </span>
                  {[
                    { label: 'All', query: 'SELECT * FROM spans LIMIT 10' },
                    { label: 'By Service', query: 'SELECT service_name, COUNT(*) FROM spans GROUP BY service_name' },
                    { label: 'Errors', query: 'SELECT * FROM spans WHERE status_code = \'ERROR\'' },
                    { label: 'Avg Duration', query: 'SELECT service_name, AVG(duration_ms) FROM spans GROUP BY service_name' },
                  ].map((example) => (
                    <button
                      key={example.label}
                      onClick={() => setSqlQuery(example.query)}
                      style={{
                        padding: '4px 8px',
                        background: 'var(--color-bg-elevated)',
                        color: 'var(--color-text-secondary)',
                        border: '1px solid var(--color-border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--font-size-body-xs)',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {example.label}
                    </button>
                  ))}
                </div>
                <button
                  onClick={executeSqlQuery}
                  disabled={sqlLoading}
                  style={{
                    padding: '6px 12px',
                    background: sqlLoading ? 'var(--color-bg-surface)' : 'var(--color-accent)',
                    color: sqlLoading ? 'var(--color-text-tertiary)' : 'white',
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--font-size-body-xs)',
                    fontWeight: 'var(--font-weight-medium)',
                    cursor: sqlLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    flexShrink: 0,
                  }}
                >
                  {sqlLoading ? (
                    <>
                      <span>⏳</span>
                      <span>Running...</span>
                    </>
                  ) : (
                    <>
                      <span>▶️</span>
                      <span>Run (Cmd+Enter)</span>
                    </>
                  )}
                </button>
              </div>

              <textarea
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault();
                    executeSqlQuery();
                  }
                }}
                placeholder="SELECT * FROM spans WHERE service_name = 'my-service' LIMIT 100"
                style={{
                  width: '100%',
                  minHeight: '60px',
                  maxHeight: '120px',
                  padding: '8px 12px',
                  fontFamily: 'var(--font-family-mono)',
                  fontSize: 'var(--font-size-body-xs)',
                  background: 'var(--color-bg-surface)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  resize: 'vertical',
                  lineHeight: '1.5',
                }}
              />
            </div>

            {/* Error Display */}
            {sqlError && (
              <div style={{
                padding: '8px 12px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #ef4444',
                borderRadius: 'var(--radius-md)',
                color: '#ef4444',
                fontSize: 'var(--font-size-body-xs)',
                fontFamily: 'var(--font-family-mono)',
                display: 'flex',
                gap: '8px',
                alignItems: 'center',
                flexShrink: 0,
              }}>
                <span>❌</span>
                <span>{sqlError}</span>
              </div>
            )}

            {/* Results Table */}
            {sqlResults && sqlResults.length > 0 && (
              <div style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--gap-xs)',
                minHeight: 0,
              }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <div style={{
                    fontSize: 'var(--font-size-body-sm)',
                    fontWeight: 'var(--font-weight-medium)',
                    color: 'var(--color-text-secondary)',
                  }}>
                    Results ({sqlResults.length} row{sqlResults.length !== 1 ? 's' : ''}, {sqlColumns.length} column{sqlColumns.length !== 1 ? 's' : ''})
                  </div>
                  <button
                    onClick={() => {
                      // Generate CSV
                      const csv = [
                        sqlColumns.join(','), // Header
                        ...sqlResults.map(row =>
                          sqlColumns.map(col => {
                            const val = row[col];
                            if (val === null || val === undefined) return '';
                            const str = String(val);
                            // Escape quotes and wrap in quotes if contains comma, quote, or newline
                            if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                              return `"${str.replace(/"/g, '""')}"`;
                            }
                            return str;
                          }).join(',')
                        )
                      ].join('\n');

                      // Download CSV
                      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                      const link = document.createElement('a');
                      const url = URL.createObjectURL(blob);
                      link.setAttribute('href', url);
                      link.setAttribute('download', `trace-query-${new Date().toISOString().split('T')[0]}.csv`);
                      link.style.visibility = 'hidden';
                      document.body.appendChild(link);
                      link.click();
                      document.body.removeChild(link);
                    }}
                    style={{
                      padding: '4px 10px',
                      background: 'var(--color-bg-elevated)',
                      color: 'var(--color-text-secondary)',
                      border: '1px solid var(--color-border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 'var(--font-size-body-xs)',
                      fontWeight: 'var(--font-weight-medium)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span>📥</span>
                    <span>Export CSV</span>
                  </button>
                </div>

                <div style={{
                  flex: 1,
                  overflow: 'auto',
                  background: 'var(--color-bg-surface)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: 'var(--radius-md)',
                }}>
                  <table style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: 'var(--font-size-body-xs)',
                  }}>
                    <thead style={{
                      position: 'sticky',
                      top: 0,
                      background: 'var(--color-bg-elevated)',
                      borderBottom: '2px solid var(--color-border-subtle)',
                      zIndex: 1,
                    }}>
                      <tr>
                        {sqlColumns.map((col) => (
                          <th
                            key={col}
                            style={{
                              padding: '10px 12px',
                              textAlign: 'left',
                              fontWeight: 'var(--font-weight-bold)',
                              color: 'var(--color-text-secondary)',
                              whiteSpace: 'nowrap',
                              borderRight: '1px solid var(--color-border-subtle)',
                            }}
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sqlResults.map((row, idx) => (
                        <tr
                          key={idx}
                          style={{
                            borderBottom: '1px solid var(--color-border-subtle)',
                            background: idx % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.02)',
                          }}
                        >
                          {sqlColumns.map((col) => (
                            <td
                              key={col}
                              style={{
                                padding: '8px 12px',
                                color: 'var(--color-text-primary)',
                                fontFamily: typeof row[col] === 'string' && row[col].length > 50 ? 'var(--font-family-mono)' : 'inherit',
                                maxWidth: '400px',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                borderRight: '1px solid var(--color-border-subtle)',
                              }}
                              title={String(row[col])}
                            >
                              {row[col] === null || row[col] === undefined ? (
                                <span style={{ color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>null</span>
                              ) : (
                                String(row[col])
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Empty State */}
            {!sqlLoading && !sqlError && (!sqlResults || sqlResults.length === 0) && (
              <div style={{
                textAlign: 'center',
                padding: 'var(--space-component-xl)',
                color: 'var(--color-text-secondary)',
              }}>
                <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)', opacity: 0.5 }}>📊</div>
                <div>Run a query to see results</div>
                <div style={{ fontSize: 'var(--font-size-body-xs)', marginTop: 'var(--gap-xs)', opacity: 0.7 }}>
                  Try one of the example queries above
                </div>
              </div>
            )}
          </div>
        )}

        {/* Traces View (Timeline & Statistics) */}
        {(viewMode === 'timeline' || viewMode === 'statistics') && (
          <>
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
                  flexDirection: 'column',
                  gap: 'var(--gap-sm)',
                }}
              >
                {/* Top row: Status, Duration, Services */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--gap-md)',
                }}>
                  <div style={{ fontSize: '14px', opacity: 0.5 }}>
                    {selectedTraceIds.has(trace.traceId) ? '▼' : '►'}
                  </div>

                  {/* Status indicator */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: 'var(--font-size-body-sm)',
                    fontWeight: 'var(--font-weight-medium)',
                    color: trace.hasError ? '#ef4444' : '#10b981',
                  }}>
                    <span>{trace.hasError ? '✗' : '✓'}</span>
                    <span>{trace.hasError ? 'ERROR' : 'OK'}</span>
                  </div>

                  {/* Duration */}
                  <div style={{
                    fontSize: 'var(--font-size-body-sm)',
                    fontWeight: 'var(--font-weight-medium)',
                    color: 'var(--color-text-primary)',
                  }}>
                    {trace.duration.toFixed(2)}ms
                  </div>

                  {/* Service badges */}
                  <div style={{
                    display: 'flex',
                    gap: '6px',
                    flex: 1,
                    flexWrap: 'wrap',
                  }}>
                    {Array.from(trace.services).map(service => {
                      const serviceColor = serviceColors.colorMap.get(service) || '#6366f1';
                      return (
                        <div
                          key={service}
                          style={{
                            padding: '4px 12px',
                            borderRadius: 'var(--radius-sm)',
                            background: serviceColor,
                            color: 'white',
                            fontSize: 'var(--font-size-body-xs)',
                            fontWeight: 'var(--font-weight-medium)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {service}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Bottom row: Trace ID, Span count, Timestamp */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--gap-md)',
                  paddingLeft: '30px',
                  fontSize: 'var(--font-size-body-xs)',
                  color: 'var(--color-text-tertiary)',
                }}>
                  <div style={{
                    fontFamily: 'var(--font-family-mono)',
                    color: 'var(--color-text-secondary)',
                  }}>
                    {trace.traceId.slice(0, 16)}...
                  </div>
                  <span>•</span>
                  <span>{trace.spanCount} spans</span>
                  <span>•</span>
                  <span>{trace.services.size} service{trace.services.size !== 1 ? 's' : ''}</span>
                  <span>•</span>
                  <span>{new Date(trace.startTime / 1_000_000).toLocaleTimeString()}</span>
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
          </>
        )}
      </div>
    </div>
  );
};

export default TraceModuleJaeger;
