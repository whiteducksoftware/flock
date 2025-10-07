import React, { useEffect, useMemo, useState } from 'react';
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

interface TraceModuleGrafanaProps {
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
  rootOperation: string;
}

interface ServiceMetrics {
  service: string;
  totalSpans: number;
  errorSpans: number;
  avgDuration: number;
  p95Duration: number;
  rate: number;
}

type ViewMode = 'traces' | 'metrics' | 'dependencies';

const TraceModuleGrafana: React.FC<TraceModuleGrafanaProps> = () => {
  const [traces, setTraces] = useState<Span[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTraceIds, setSelectedTraceIds] = useState<Set<string>>(new Set());
  const [expandedSpans, setExpandedSpans] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<ViewMode>('traces');

  // Filters
  const [serviceFilter, setServiceFilter] = useState<string>('');
  const [operationFilter, setOperationFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [minDuration, setMinDuration] = useState<string>('');
  const [maxDuration, setMaxDuration] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Service colors
  const serviceColors = useMemo(() => {
    const colors = [
      '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
      '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
    ];
    const colorMap = new Map<string, string>();
    const services = Array.from(new Set(traces.map(s => s.name.split('.')[0] || 'unknown')));
    services.forEach((service, idx) => {
      colorMap.set(service, colors[idx % colors.length] || '#6366f1');
    });
    return colorMap;
  }, [traces]);

  const getServiceColor = (serviceName: string): string => {
    return serviceColors.get(serviceName) || '#6366f1';
  };

  useEffect(() => {
    fetchTraces();
    const interval = setInterval(fetchTraces, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchTraces = async () => {
    try {
      const response = await fetch('/api/traces');
      const data = await response.json();
      setTraces(data);
      setError(null);
    } catch (err) {
      setError('Failed to load traces');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Group spans into traces
  const traceGroups = useMemo<TraceGroup[]>(() => {
    const groups = new Map<string, Span[]>();

    traces.forEach(span => {
      const traceId = span.context.trace_id;
      if (!groups.has(traceId)) {
        groups.set(traceId, []);
      }
      groups.get(traceId)!.push(span);
    });

    return Array.from(groups.entries()).map(([traceId, spans]) => {
      const startTime = Math.min(...spans.map(s => s.start_time));
      const endTime = Math.max(...spans.map(s => s.end_time));
      const duration = (endTime - startTime) / 1_000_000;
      const services = new Set(spans.map(s => s.name.split('.')[0] || 'unknown'));
      const hasError = spans.some(s => s.status.status_code === 'ERROR');
      const rootSpan = spans.find(s => !s.parent_id);
      const rootOperation = rootSpan?.name || spans[0]?.name || 'unknown';

      return {
        traceId,
        spans,
        startTime,
        endTime,
        duration,
        spanCount: spans.length,
        hasError,
        services,
        rootOperation,
      };
    });
  }, [traces]);

  // Filter traces
  const filteredTraces = useMemo(() => {
    let result = traceGroups;

    // Service filter
    if (serviceFilter) {
      result = result.filter(trace =>
        Array.from(trace.services).some(s => s.toLowerCase().includes(serviceFilter.toLowerCase()))
      );
    }

    // Operation filter
    if (operationFilter) {
      result = result.filter(trace =>
        trace.rootOperation.toLowerCase().includes(operationFilter.toLowerCase())
      );
    }

    // Status filter
    if (statusFilter) {
      if (statusFilter === 'error') {
        result = result.filter(trace => trace.hasError);
      } else if (statusFilter === 'ok') {
        result = result.filter(trace => !trace.hasError);
      }
    }

    // Duration filters
    if (minDuration) {
      const min = parseFloat(minDuration);
      if (!isNaN(min)) {
        result = result.filter(trace => trace.duration >= min);
      }
    }
    if (maxDuration) {
      const max = parseFloat(maxDuration);
      if (!isNaN(max)) {
        result = result.filter(trace => trace.duration <= max);
      }
    }

    // Search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(trace =>
        trace.traceId.toLowerCase().includes(query) ||
        trace.rootOperation.toLowerCase().includes(query) ||
        trace.spans.some(span =>
          span.name.toLowerCase().includes(query) ||
          Object.values(span.attributes).some(val =>
            typeof val === 'string' && val.toLowerCase().includes(query)
          )
        )
      );
    }

    return result.sort((a, b) => b.startTime - a.startTime);
  }, [traceGroups, serviceFilter, operationFilter, statusFilter, minDuration, maxDuration, searchQuery]);

  // Calculate RED metrics
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
          rate: 0,
        });
      }

      const metrics = metricsMap.get(service)!;
      metrics.totalSpans++;
      if (span.status.status_code === 'ERROR') {
        metrics.errorSpans++;
      }
    });

    // Calculate durations
    metricsMap.forEach((metrics, service) => {
      const serviceSpans = traces.filter(s => (s.name.split('.')[0] || 'unknown') === service);
      const durations = serviceSpans.map(s => (s.end_time - s.start_time) / 1_000_000);
      durations.sort((a, b) => a - b);

      metrics.avgDuration = durations.reduce((sum, d) => sum + d, 0) / durations.length || 0;
      metrics.p95Duration = durations[Math.floor(durations.length * 0.95)] || 0;

      // Calculate rate (spans per second) - approximation
      if (serviceSpans.length > 1) {
        const timeSpan = (Math.max(...serviceSpans.map(s => s.end_time)) -
                         Math.min(...serviceSpans.map(s => s.start_time))) / 1_000_000_000;
        metrics.rate = serviceSpans.length / timeSpan;
      }
    });

    return Array.from(metricsMap.values()).sort((a, b) => b.totalSpans - a.totalSpans);
  }, [traces]);

  // Build service dependency graph
  const serviceDependencies = useMemo(() => {
    const deps = new Map<string, Set<string>>();

    traceGroups.forEach(trace => {
      trace.spans.forEach(span => {
        const service = span.name.split('.')[0] || 'unknown';

        if (span.parent_id) {
          const parent = trace.spans.find(s => s.context.span_id === span.parent_id);
          if (parent) {
            const parentService = parent.name.split('.')[0] || 'unknown';
            if (parentService !== service) {
              if (!deps.has(parentService)) {
                deps.set(parentService, new Set());
              }
              deps.get(parentService)!.add(service);
            }
          }
        }
      });
    });

    return deps;
  }, [traceGroups]);

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
      if (span.parent_id) {
        const parent = spanMap.get(span.parent_id);
        if (parent) {
          parent.children.push(node);
          node.depth = parent.depth + 1;
        } else {
          roots.push(node);
        }
      } else {
        roots.push(node);
      }
    });

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

  const renderSpanNode = (node: SpanNode, traceStartTime: number, traceDuration: number): React.ReactElement => {
    const isExpanded = expandedSpans.has(node.context.span_id);
    const hasChildren = node.children.length > 0;
    const serviceName = node.name.split('.')[0] || 'unknown';
    const operation = node.name.split('.').slice(1).join('.') || node.name;
    const serviceColor = getServiceColor(serviceName);
    const spanDuration = (node.end_time - node.start_time) / 1_000_000;
    const spanOffset = (node.start_time - traceStartTime) / 1_000_000;
    const barWidth = (spanDuration / traceDuration) * 100;
    const barLeft = (spanOffset / traceDuration) * 100;

    return (
      <div key={node.context.span_id}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '300px 1fr',
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            minHeight: '32px',
          }}
        >
          {/* Left: Span name */}
          <div
            onClick={() => hasChildren && toggleSpanExpand(node.context.span_id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              paddingLeft: `${node.depth * 20 + 8}px`,
              paddingRight: '8px',
              cursor: hasChildren ? 'pointer' : 'default',
              fontSize: 'var(--font-size-body-xs)',
            }}
          >
            {hasChildren && (
              <span style={{ fontSize: '10px', userSelect: 'none' }}>
                {isExpanded ? '▼' : '▶'}
              </span>
            )}
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '2px',
                backgroundColor: serviceColor,
                flexShrink: 0,
              }}
            />
            <span style={{ color: serviceColor, fontWeight: 'var(--font-weight-medium)' }}>
              {serviceName}
            </span>
            <span style={{ color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              .{operation}
            </span>
          </div>

          {/* Right: Timeline bar */}
          <div style={{ position: 'relative', padding: '8px 0' }}>
            <div
              style={{
                position: 'absolute',
                left: `${barLeft}%`,
                width: `${barWidth}%`,
                height: '16px',
                backgroundColor: node.status.status_code === 'ERROR' ? '#ef4444' : serviceColor,
                borderRadius: '2px',
                display: 'flex',
                alignItems: 'center',
                paddingLeft: '4px',
                fontSize: '10px',
                color: 'white',
                fontWeight: 'var(--font-weight-medium)',
              }}
              title={`${spanDuration.toFixed(2)}ms`}
            >
              {barWidth > 3 && `${spanDuration.toFixed(1)}ms`}
            </div>
          </div>
        </div>

        {/* Expanded: Show attributes */}
        {isExpanded && Object.keys(node.attributes).length > 0 && (
          <div
            style={{
              padding: 'var(--space-component-sm)',
              paddingLeft: `${node.depth * 20 + 32}px`,
              background: 'rgba(255, 255, 255, 0.02)',
              borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            }}
          >
            <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
              Attributes:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 'var(--gap-xs)', fontSize: 'var(--font-size-body-xs)' }}>
              {Object.entries(node.attributes).map(([key, value]) => (
                <React.Fragment key={key}>
                  <div style={{ color: 'var(--color-text-tertiary)', alignSelf: 'start' }}>{key}:</div>
                  <div>
                    <JsonAttributeRenderer value={value} />
                  </div>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {/* Render children */}
        {isExpanded && node.children.map(child => renderSpanNode(child, traceStartTime, traceDuration))}
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-component-lg)', color: 'var(--color-text-secondary)' }}>
        Loading traces...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 'var(--space-component-lg)', color: 'var(--color-error)' }}>
        {error}
      </div>
    );
  }

  const activeFilterCount = [serviceFilter, operationFilter, statusFilter, minDuration, maxDuration].filter(Boolean).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--color-bg-base)' }}>
      {/* Header with view mode buttons */}
      <div style={{
        display: 'flex',
        gap: '8px',
        padding: 'var(--space-component-md)',
        borderBottom: '1px solid var(--color-border-subtle)',
      }}>
        <button
          onClick={() => setViewMode('traces')}
          style={{
            padding: '6px 12px',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-md)',
            background: viewMode === 'traces' ? 'var(--color-primary-500)' : 'var(--color-bg-base)',
            color: viewMode === 'traces' ? 'white' : 'var(--color-text-primary)',
            fontSize: 'var(--font-size-body-sm)',
            cursor: 'pointer',
            fontWeight: 'var(--font-weight-medium)',
          }}
        >
          Traces
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
          RED Metrics
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
          Dependencies
        </button>
      </div>

      {/* Filters (only in traces view) */}
      {viewMode === 'traces' && (
        <div style={{
          padding: 'var(--space-component-md)',
          borderBottom: '1px solid var(--color-border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--gap-sm)',
        }}>
          {/* Search and basic filters */}
          <div style={{ display: 'flex', gap: 'var(--gap-sm)' }}>
            <input
              type="text"
              placeholder="🔎 Search traces..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                padding: '8px 12px',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-sm)',
              }}
            />
          </div>

          {/* Advanced filters */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 'var(--gap-sm)' }}>
            <input
              type="text"
              placeholder="Service..."
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-xs)',
              }}
            />
            <input
              type="text"
              placeholder="Operation..."
              value={operationFilter}
              onChange={(e) => setOperationFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-xs)',
              }}
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-xs)',
              }}
            >
              <option value="">All statuses</option>
              <option value="ok">OK only</option>
              <option value="error">Errors only</option>
            </select>
            <input
              type="number"
              placeholder="Min duration (ms)"
              value={minDuration}
              onChange={(e) => setMinDuration(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-xs)',
              }}
            />
            <input
              type="number"
              placeholder="Max duration (ms)"
              value={maxDuration}
              onChange={(e) => setMaxDuration(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-xs)',
              }}
            />
          </div>

          {/* Active filters indicator */}
          {activeFilterCount > 0 && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--gap-xs)',
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-tertiary)',
            }}>
              <span>{activeFilterCount} active filter{activeFilterCount !== 1 ? 's' : ''}</span>
              <button
                onClick={() => {
                  setServiceFilter('');
                  setOperationFilter('');
                  setStatusFilter('');
                  setMinDuration('');
                  setMaxDuration('');
                }}
                style={{
                  padding: '2px 6px',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  background: 'transparent',
                  color: 'var(--color-text-tertiary)',
                  fontSize: 'var(--font-size-body-xs)',
                  cursor: 'pointer',
                }}
              >
                Clear all
              </button>
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {viewMode === 'traces' && (
          <div>
            <div style={{
              padding: 'var(--space-component-sm)',
              borderBottom: '1px solid var(--color-border-subtle)',
              fontSize: 'var(--font-size-body-xs)',
              color: 'var(--color-text-tertiary)',
            }}>
              {filteredTraces.length} trace{filteredTraces.length !== 1 ? 's' : ''} found
            </div>

            {filteredTraces.map(trace => (
              <div
                key={trace.traceId}
                style={{
                  borderBottom: '1px solid var(--color-border-subtle)',
                }}
              >
                {/* Trace header */}
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
                    display: 'grid',
                    gridTemplateColumns: '400px 80px 100px 1fr',
                    gap: 'var(--gap-sm)',
                    padding: 'var(--space-component-sm)',
                    cursor: 'pointer',
                    background: selectedTraceIds.has(trace.traceId) ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                  }}
                >
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-secondary)', marginBottom: '2px' }}>
                      {trace.rootOperation}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-family-mono)' }}>
                      {trace.traceId.substring(0, 16)}...
                    </div>
                  </div>
                  <div style={{ fontSize: 'var(--font-size-body-xs)', color: trace.hasError ? 'var(--color-error)' : 'var(--color-success)' }}>
                    {trace.hasError ? '❌ ERROR' : '✓ OK'}
                  </div>
                  <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                    {trace.duration.toFixed(2)}ms
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {Array.from(trace.services).map(service => (
                      <span
                        key={service}
                        style={{
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-xs)',
                          fontSize: '10px',
                          backgroundColor: getServiceColor(service) + '20',
                          color: getServiceColor(service),
                          fontWeight: 'var(--font-weight-medium)',
                        }}
                      >
                        {service}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Trace details (expanded) */}
                {selectedTraceIds.has(trace.traceId) && (
                  <div style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
                    {buildSpanTree(trace.spans).map(node => renderSpanNode(node, trace.startTime, trace.duration))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {viewMode === 'metrics' && (
          <div style={{ padding: 'var(--space-component-md)' }}>
            <div style={{
              fontSize: 'var(--font-size-body-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-component-sm)',
            }}>
              RED Metrics (Rate, Errors, Duration) by Service
            </div>

            <div style={{ display: 'grid', gap: 'var(--gap-sm)' }}>
              {serviceMetrics.map(metrics => (
                <div
                  key={metrics.service}
                  style={{
                    padding: 'var(--space-component-md)',
                    background: 'var(--color-bg-elevated)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border-subtle)',
                  }}
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--gap-sm)',
                    marginBottom: 'var(--gap-sm)',
                  }}>
                    <div
                      style={{
                        width: '12px',
                        height: '12px',
                        borderRadius: '3px',
                        backgroundColor: getServiceColor(metrics.service),
                      }}
                    />
                    <span style={{
                      fontSize: 'var(--font-size-body-md)',
                      color: 'var(--color-text-primary)',
                      fontWeight: 'var(--font-weight-medium)',
                    }}>
                      {metrics.service}
                    </span>
                  </div>

                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: 'var(--gap-md)',
                  }}>
                    <div>
                      <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                        Rate
                      </div>
                      <div style={{ fontSize: 'var(--font-size-body-lg)', color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                        {metrics.rate.toFixed(2)} req/s
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                        Error Rate
                      </div>
                      <div style={{
                        fontSize: 'var(--font-size-body-lg)',
                        color: metrics.errorSpans > 0 ? 'var(--color-error)' : 'var(--color-success)',
                        fontWeight: 'var(--font-weight-medium)',
                      }}>
                        {((metrics.errorSpans / metrics.totalSpans) * 100).toFixed(1)}%
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                        Avg Duration
                      </div>
                      <div style={{ fontSize: 'var(--font-size-body-lg)', color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                        {metrics.avgDuration.toFixed(2)}ms
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                        P95 Duration
                      </div>
                      <div style={{ fontSize: 'var(--font-size-body-lg)', color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                        {metrics.p95Duration.toFixed(2)}ms
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                        Total Spans
                      </div>
                      <div style={{ fontSize: 'var(--font-size-body-lg)', color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-medium)' }}>
                        {metrics.totalSpans}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {viewMode === 'dependencies' && (
          <div style={{ padding: 'var(--space-component-md)' }}>
            <div style={{
              fontSize: 'var(--font-size-body-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-component-sm)',
            }}>
              Service Dependencies
            </div>

            {serviceDependencies.size === 0 ? (
              <div style={{
                padding: 'var(--space-component-lg)',
                textAlign: 'center',
                color: 'var(--color-text-tertiary)',
                fontSize: 'var(--font-size-body-sm)',
              }}>
                No service dependencies detected
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 'var(--gap-sm)' }}>
                {Array.from(serviceDependencies.entries()).map(([parent, children]) => (
                  <div
                    key={parent}
                    style={{
                      padding: 'var(--space-component-md)',
                      background: 'var(--color-bg-elevated)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--gap-sm)',
                      marginBottom: 'var(--gap-sm)',
                    }}>
                      <div
                        style={{
                          width: '12px',
                          height: '12px',
                          borderRadius: '3px',
                          backgroundColor: getServiceColor(parent),
                        }}
                      />
                      <span style={{
                        fontSize: 'var(--font-size-body-md)',
                        color: 'var(--color-text-primary)',
                        fontWeight: 'var(--font-weight-medium)',
                      }}>
                        {parent}
                      </span>
                      <span style={{ fontSize: 'var(--font-size-body-xs)', color: 'var(--color-text-tertiary)' }}>
                        calls
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', paddingLeft: '28px' }}>
                      {Array.from(children).map(child => (
                        <div
                          key={child}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            background: getServiceColor(child) + '15',
                            borderRadius: 'var(--radius-md)',
                            border: `1px solid ${getServiceColor(child)}40`,
                          }}
                        >
                          <div
                            style={{
                              width: '8px',
                              height: '8px',
                              borderRadius: '2px',
                              backgroundColor: getServiceColor(child),
                            }}
                          />
                          <span style={{
                            fontSize: 'var(--font-size-body-sm)',
                            color: getServiceColor(child),
                            fontWeight: 'var(--font-weight-medium)',
                          }}>
                            {child}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TraceModuleGrafana;
