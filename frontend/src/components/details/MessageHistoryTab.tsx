import React, { useMemo, useState } from 'react';
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
  correlationId: string;
}

const MessageHistoryTab: React.FC<MessageHistoryTabProps> = ({ nodeId, nodeType }) => {
  const messages = useGraphStore((state) => state.messages);
  const agents = useGraphStore((state) => state.agents);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // Build message history based on node type
  const messageHistory = useMemo(() => {
    const history: MessageHistoryEntry[] = [];

    if (nodeType === 'agent') {
      const agent = agents.get(nodeId);
      if (!agent) return history;

      // Get all messages
      messages.forEach((message) => {
        // Check if this agent consumed this message
        const isConsumed = agent.subscriptions.includes(message.type);

        // Check if this agent published this message
        const isPublished = message.producedBy === nodeId;

        if (isConsumed) {
          history.push({
            id: message.id,
            type: message.type,
            direction: 'consumed',
            payload: message.payload,
            timestamp: message.timestamp,
            correlationId: message.correlationId,
          });
        }

        if (isPublished) {
          history.push({
            id: `${message.id}-published`,
            type: message.type,
            direction: 'published',
            payload: message.payload,
            timestamp: message.timestamp,
            correlationId: message.correlationId,
          });
        }
      });
    } else if (nodeType === 'message') {
      // For message nodes, just show that single message
      const message = messages.get(nodeId);
      if (message) {
        history.push({
          id: message.id,
          type: message.type,
          direction: 'published',
          payload: message.payload,
          timestamp: message.timestamp,
          correlationId: message.correlationId,
        });
      }
    }

    // Sort by timestamp (most recent first)
    return history.sort((a, b) => b.timestamp - a.timestamp);
  }, [nodeId, nodeType, messages, agents]);

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
      {messageHistory.length === 0 ? (
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
