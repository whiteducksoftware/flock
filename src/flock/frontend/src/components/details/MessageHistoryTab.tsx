import React, { useEffect, useState, useRef } from 'react';
import { useGraphStore } from '../../store/graphStore';

interface MessageHistoryTabProps {
  nodeId: string;
  nodeType: 'agent' | 'message';
}

interface MessageHistoryEntry {
  id: string;
  type: string;
  direction: 'consumed' | 'published';
  payload: any;
  timestamp: number;
  correlationId: string | null;
  produced_by?: string;
  consumed_at?: string;
}

const MessageHistoryTab: React.FC<MessageHistoryTabProps> = ({ nodeId, nodeType: _nodeType }) => {
  const [messageHistory, setMessageHistory] = useState<MessageHistoryEntry[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isInitialLoad = useRef(true);

  // Subscribe to real-time events for this node
  const events = useGraphStore((state) => state.events);

  // Phase 4.1 Feature Gap Fix: Fetch complete message history from backend API
  // Includes both produced AND consumed messages for the node
  useEffect(() => {
    const fetchMessageHistory = async () => {
      // Only show loading spinner on initial load
      if (isInitialLoad.current) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const response = await fetch(`/api/artifacts/history/${nodeId}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch message history: ${response.statusText}`);
        }

        const data = await response.json();

        // Convert ISO timestamps to milliseconds
        const history = data.messages.map((msg: any) => ({
          id: msg.id,
          type: msg.type,
          direction: msg.direction,
          payload: msg.payload,
          timestamp: new Date(msg.consumed_at || msg.timestamp).getTime(),
          correlationId: msg.correlation_id,
          produced_by: msg.produced_by,
          consumed_at: msg.consumed_at,
        }));

        setMessageHistory(history);
      } catch (err) {
        console.error('Failed to fetch message history:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (isInitialLoad.current) {
          setIsLoading(false);
          isInitialLoad.current = false;
        }
      }
    };

    fetchMessageHistory();
  }, [nodeId]);

  // Real-time updates: Refetch when new events arrive for this node
  useEffect(() => {
    // Debounce refetch to avoid spamming API
    let refetchTimer: ReturnType<typeof setTimeout> | null = null;

    const scheduleRefetch = () => {
      if (refetchTimer !== null) {
        clearTimeout(refetchTimer);
      }

      refetchTimer = setTimeout(async () => {
        refetchTimer = null;

        try {
          const response = await fetch(`/api/artifacts/history/${nodeId}`);
          if (!response.ok) return;

          const data = await response.json();

          const history = data.messages.map((msg: any) => ({
            id: msg.id,
            type: msg.type,
            direction: msg.direction,
            payload: msg.payload,
            timestamp: new Date(msg.consumed_at || msg.timestamp).getTime(),
            correlationId: msg.correlation_id,
            produced_by: msg.produced_by,
            consumed_at: msg.consumed_at,
          }));

          setMessageHistory(history);
        } catch (err) {
          console.error('Failed to refetch message history:', err);
        }
      }, 500); // 500ms debounce
    };

    // Check if any recent event relates to this node
    const recentEvents = events.slice(-10); // Check last 10 events
    const hasRelevantEvent = recentEvents.some(
      (event: any) => event.producedBy === nodeId || event.consumedBy === nodeId
    );

    if (hasRelevantEvent) {
      scheduleRefetch();
    }

    return () => {
      if (refetchTimer !== null) {
        clearTimeout(refetchTimer);
      }
    };
  }, [events, nodeId]);

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatPayload = (payload: any) => {
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return String(payload);
    }
  };

  const toggleRowExpansion = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div
      data-testid={`message-history-${nodeId}`}
      style={{
        height: '100%',
        overflow: 'auto',
        background: 'var(--color-bg-elevated)',
        color: 'var(--color-text-primary)',
      }}
    >
      {isLoading ? (
        <div
          data-testid="loading-messages"
          style={{
            padding: 'var(--space-layout-md)',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-sans)',
            textAlign: 'center',
          }}
        >
          Loading message history...
        </div>
      ) : error ? (
        <div
          data-testid="error-messages"
          style={{
            padding: 'var(--space-layout-md)',
            color: 'var(--color-error-light)',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-sans)',
            textAlign: 'center',
          }}
        >
          Error: {error}
        </div>
      ) : messageHistory.length === 0 ? (
        <div
          data-testid="empty-messages"
          style={{
            padding: 'var(--space-layout-md)',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-sans)',
            textAlign: 'center',
          }}
        >
          No messages yet
        </div>
      ) : (
        <table
          data-testid="message-table"
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 'var(--font-size-caption)',
            fontFamily: 'var(--font-family-sans)',
          }}
        >
          <thead>
            <tr
              style={{
                background: 'var(--color-bg-surface)',
                borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                position: 'sticky',
                top: 0,
                zIndex: 1,
              }}
            >
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Time
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Direction
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Type
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Correlation ID
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Payload
              </th>
            </tr>
          </thead>
          <tbody>
            {messageHistory.map((msg) => {
              const isExpanded = expandedRows.has(msg.id);
              return (
                <React.Fragment key={msg.id}>
                  <tr
                    data-testid={`message-row-${msg.id}`}
                    style={{
                      borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                      cursor: 'pointer',
                      transition: 'var(--transition-colors)',
                    }}
                    onClick={() => toggleRowExpansion(msg.id)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--color-bg-surface)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <td
                      data-testid={`msg-time-${msg.id}`}
                      style={{
                        padding: 'var(--space-component-sm) var(--space-component-md)',
                        whiteSpace: 'nowrap',
                        color: 'var(--color-text-tertiary)',
                      }}
                    >
                      {formatTimestamp(msg.timestamp)}
                    </td>
                    <td
                      data-testid={`msg-direction-${msg.id}`}
                      style={{
                        padding: 'var(--space-component-sm) var(--space-component-md)',
                        color:
                          msg.direction === 'consumed'
                            ? 'var(--color-tertiary-400)'
                            : 'var(--color-success-light)',
                        fontWeight: 'var(--font-weight-semibold)',
                      }}
                    >
                      {msg.direction === 'consumed' ? '↓ Consumed' : '↑ Published'}
                    </td>
                    <td
                      data-testid={`msg-type-${msg.id}`}
                      style={{
                        padding: 'var(--space-component-sm) var(--space-component-md)',
                        fontFamily: 'var(--font-family-mono)',
                        color: 'var(--color-text-primary)',
                      }}
                    >
                      {msg.type}
                    </td>
                    <td
                      data-testid={`msg-correlation-${msg.id}`}
                      style={{
                        padding: 'var(--space-component-sm) var(--space-component-md)',
                        fontFamily: 'var(--font-family-mono)',
                        fontSize: 'var(--font-size-overline)',
                        color: 'var(--color-text-muted)',
                      }}
                    >
                      {msg.correlationId}
                    </td>
                    <td
                      data-testid={`msg-payload-${msg.id}`}
                      style={{
                        padding: 'var(--space-component-sm) var(--space-component-md)',
                        maxWidth: '300px',
                      }}
                    >
                      <pre
                        style={{
                          fontSize: 'var(--font-size-overline)',
                          fontFamily: 'var(--font-family-mono)',
                          maxHeight: isExpanded ? 'none' : '60px',
                          overflow: isExpanded ? 'visible' : 'hidden',
                          textOverflow: 'ellipsis',
                          margin: 0,
                          whiteSpace: isExpanded ? 'pre-wrap' : 'nowrap',
                          color: 'var(--color-text-secondary)',
                          background: 'var(--color-bg-base)',
                          padding: 'var(--spacing-1)',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        {formatPayload(msg.payload)}
                      </pre>
                    </td>
                  </tr>
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default MessageHistoryTab;
