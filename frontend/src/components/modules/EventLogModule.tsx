import React, { useMemo, useState } from 'react';
import { Message, Agent } from '../../types/graph';
import { TimeRange } from '../../types/filters';

interface ModuleContext {
  agents: Map<string, Agent>;
  messages: Map<string, Message>;
  events: Message[];
  filters: {
    correlationId: string | null;
    timeRange: TimeRange;
  };
  publish: (artifact: any) => void;
  invoke: (agentName: string, inputs: any[]) => void;
}

interface EventLogModuleProps {
  context: ModuleContext;
}

type SortField = 'timestamp' | 'type' | 'agent' | 'correlationId';
type SortDirection = 'asc' | 'desc';

const getTimeRangeStart = (timeRange: TimeRange, now: number): number => {
  if (timeRange.preset === 'custom' && timeRange.start) {
    return timeRange.start;
  }

  switch (timeRange.preset) {
    case 'last5min':
      return now - 5 * 60 * 1000;
    case 'last10min':
      return now - 10 * 60 * 1000;
    case 'last1hour':
      return now - 60 * 60 * 1000;
    default:
      return now - 10 * 60 * 1000; // Default to 10 minutes
  }
};

const EventLogModule: React.FC<EventLogModuleProps> = ({ context }) => {
  const { events, filters } = context;
  const [expandedRowIds, setExpandedRowIds] = useState<Set<string>>(new Set());
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Apply filters
  const filteredEvents = useMemo(() => {
    let result = [...events];

    // Filter by correlation ID
    if (filters.correlationId) {
      result = result.filter((e) => e.correlationId === filters.correlationId);
    }

    // Filter by time range
    if (filters.timeRange) {
      const now = Date.now();
      const start = getTimeRangeStart(filters.timeRange, now);
      const end = filters.timeRange.preset === 'custom' && filters.timeRange.end
        ? filters.timeRange.end
        : now;

      result = result.filter((e) => e.timestamp >= start && e.timestamp <= end);
    }

    return result;
  }, [events, filters]);

  // Apply sorting
  const sortedEvents = useMemo(() => {
    const sorted = [...filteredEvents];

    sorted.sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'timestamp':
          comparison = a.timestamp - b.timestamp;
          break;
        case 'type':
          comparison = a.type.localeCompare(b.type);
          break;
        case 'agent':
          comparison = a.producedBy.localeCompare(b.producedBy);
          break;
        case 'correlationId':
          comparison = a.correlationId.localeCompare(b.correlationId);
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }, [filteredEvents, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // Toggle direction
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // New field, default to ascending
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleExpandToggle = (eventId: string) => {
    setExpandedRowIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(eventId)) {
        newSet.delete(eventId);
      } else {
        newSet.add(eventId);
      }
      return newSet;
    });
  };

  const handleExpandAll = () => {
    const allIds = new Set(sortedEvents.map(e => e.id));
    setExpandedRowIds(allIds);
  };

  const handleCollapseAll = () => {
    setExpandedRowIds(new Set());
  };

  const [hoveredRow, setHoveredRow] = useState<string | null>(null);

  return (
    <div
      className="event-log-module"
      style={{
        padding: '0',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--color-bg-surface)',
      }}
    >
      {/* Expand/Collapse All Button */}
      <div style={{
        padding: 'var(--space-component-sm) var(--space-component-md)',
        borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}>
        <button
          onClick={expandedRowIds.size > 0 ? handleCollapseAll : handleExpandAll}
          style={{
            padding: 'var(--space-component-xs) var(--space-component-sm)',
            cursor: 'pointer',
            border: 'var(--border-width-1) solid var(--color-primary-500)',
            borderRadius: 'var(--radius-md)',
            background: expandedRowIds.size > 0 ? 'var(--color-primary-500)' : 'transparent',
            color: expandedRowIds.size > 0 ? 'var(--color-bg-base)' : 'var(--color-primary-500)',
            fontSize: 'var(--font-size-body-sm)',
            fontWeight: 'var(--font-weight-medium)',
            transition: 'var(--transition-colors)',
          }}
        >
          {expandedRowIds.size > 0 ? 'Collapse All' : 'Expand All'}
        </button>
      </div>

      {/* Table Container */}
      <div style={{
        flex: 1,
        overflow: 'auto',
      }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 'var(--font-size-body-sm)',
          tableLayout: 'auto',
        }}>
        <thead>
          <tr style={{
            background: 'rgba(42, 42, 50, 0.5)',
            position: 'sticky',
            top: 0,
            zIndex: 1,
          }}>
            <th
              onClick={() => handleSort('timestamp')}
              style={{
                cursor: 'pointer',
                padding: 'var(--space-component-sm) var(--space-component-md)',
                borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                textAlign: 'left',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--color-text-primary)',
                transition: 'var(--transition-colors)',
                userSelect: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-elevated)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              Timestamp {sortField === 'timestamp' && (
                <span style={{ color: 'var(--color-primary-500)', marginLeft: 'var(--gap-xs)' }}>
                  {sortDirection === 'asc' ? '↑' : '↓'}
                </span>
              )}
            </th>
            <th
              onClick={() => handleSort('type')}
              style={{
                cursor: 'pointer',
                padding: 'var(--space-component-sm) var(--space-component-md)',
                borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                textAlign: 'left',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--color-text-primary)',
                transition: 'var(--transition-colors)',
                userSelect: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-elevated)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              Type {sortField === 'type' && (
                <span style={{ color: 'var(--color-primary-500)', marginLeft: 'var(--gap-xs)' }}>
                  {sortDirection === 'asc' ? '↑' : '↓'}
                </span>
              )}
            </th>
            <th
              onClick={() => handleSort('agent')}
              style={{
                cursor: 'pointer',
                padding: 'var(--space-component-sm) var(--space-component-md)',
                borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                textAlign: 'left',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--color-text-primary)',
                transition: 'var(--transition-colors)',
                userSelect: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-elevated)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              Agent {sortField === 'agent' && (
                <span style={{ color: 'var(--color-primary-500)', marginLeft: 'var(--gap-xs)' }}>
                  {sortDirection === 'asc' ? '↑' : '↓'}
                </span>
              )}
            </th>
            <th
              onClick={() => handleSort('correlationId')}
              style={{
                cursor: 'pointer',
                padding: 'var(--space-component-sm) var(--space-component-md)',
                borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                textAlign: 'left',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--color-text-primary)',
                transition: 'var(--transition-colors)',
                userSelect: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-elevated)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              Correlation ID {sortField === 'correlationId' && (
                <span style={{ color: 'var(--color-primary-500)', marginLeft: 'var(--gap-xs)' }}>
                  {sortDirection === 'asc' ? '↑' : '↓'}
                </span>
              )}
            </th>
            <th style={{
              padding: 'var(--space-component-sm) var(--space-component-md)',
              borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
              textAlign: 'left',
              fontWeight: 'var(--font-weight-semibold)',
              color: 'var(--color-text-primary)',
            }}>
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedEvents.map((event) => (
            <React.Fragment key={event.id}>
              <tr
                style={{
                  borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                  background: hoveredRow === event.id ? 'var(--color-bg-elevated)' : 'transparent',
                  transition: 'var(--transition-colors)',
                }}
                onMouseEnter={() => setHoveredRow(event.id)}
                onMouseLeave={() => setHoveredRow(null)}
              >
                <td style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  color: 'var(--color-text-secondary)',
                  fontFamily: 'var(--font-family-mono)',
                }}>
                  {new Date(event.timestamp).toLocaleString()}
                </td>
                <td style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  color: 'var(--color-success)',
                  fontWeight: 'var(--font-weight-medium)',
                }}>
                  {event.type}
                </td>
                <td style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  color: 'var(--color-warning)',
                }}>
                  {event.producedBy}
                </td>
                <td style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  color: 'var(--color-text-secondary)',
                  fontFamily: 'var(--font-family-mono)',
                  fontSize: 'var(--font-size-body-xs)',
                  wordBreak: 'break-all',
                }}>
                  {event.correlationId}
                </td>
                <td style={{ padding: 'var(--space-component-sm) var(--space-component-md)' }}>
                  <button
                    onClick={() => handleExpandToggle(event.id)}
                    style={{
                      padding: 'var(--space-component-xs) var(--space-component-sm)',
                      cursor: 'pointer',
                      border: 'var(--border-width-1) solid var(--color-primary-500)',
                      borderRadius: 'var(--radius-md)',
                      background: expandedRowIds.has(event.id) ? 'var(--color-primary-500)' : 'transparent',
                      color: expandedRowIds.has(event.id) ? 'var(--color-bg-base)' : 'var(--color-primary-500)',
                      fontSize: 'var(--font-size-body-xs)',
                      fontWeight: 'var(--font-weight-medium)',
                      transition: 'var(--transition-colors)',
                    }}
                    onMouseEnter={(e) => {
                      if (!expandedRowIds.has(event.id)) {
                        e.currentTarget.style.background = 'var(--color-primary-500-alpha-10)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!expandedRowIds.has(event.id)) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    {expandedRowIds.has(event.id) ? 'Collapse ▲' : 'Expand ▼'}
                  </button>
                </td>
              </tr>
              {expandedRowIds.has(event.id) && (
                <tr>
                  <td colSpan={5} style={{
                    padding: 'var(--space-component-md)',
                    background: 'var(--color-bg-base)',
                    borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                  }}>
                    <pre style={{
                      margin: 0,
                      fontSize: 'var(--font-size-body-xs)',
                      color: 'var(--color-text-primary)',
                      fontFamily: 'var(--font-family-mono)',
                      lineHeight: '1.6',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      overflowWrap: 'break-word',
                    }}>
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
      {sortedEvents.length === 0 && (
        <div style={{
          padding: 'var(--space-component-xl)',
          textAlign: 'center',
          color: 'var(--color-text-secondary)',
          fontSize: 'var(--font-size-body-sm)',
        }}>
          <div style={{ fontSize: '32px', marginBottom: 'var(--gap-md)', opacity: 0.5 }}>📋</div>
          <div>No events to display</div>
          <div style={{ fontSize: 'var(--font-size-body-xs)', marginTop: 'var(--gap-sm)', opacity: 0.7 }}>
            Events will appear here as they occur
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default EventLogModule;
