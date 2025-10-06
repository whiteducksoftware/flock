import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useStreamStore, StreamingOutputData } from '../../store/streamStore';
import { getWebSocketClient } from '../../services/websocket';

interface LiveOutputTabProps {
  nodeId: string;
  nodeType: 'agent' | 'message';
}

// Stable empty array to avoid re-renders
const EMPTY_OUTPUTS: StreamingOutputData[] = [];

const LiveOutputTab: React.FC<LiveOutputTabProps> = ({ nodeId, nodeType }) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  // Use direct Map access to avoid infinite re-renders
  const outputs = useStreamStore((state) => state.outputs.get(nodeId) ?? EMPTY_OUTPUTS);
  const addOutput = useStreamStore((state) => state.addOutput);

  // Fetch historical streaming output on mount
  useEffect(() => {
    if (nodeType !== 'agent') return;

    const fetchHistory = async () => {
      setIsLoadingHistory(true);
      try {
        const response = await fetch(`/api/streaming-history/${nodeId}`);
        if (response.ok) {
          const data = await response.json();
          // Load historical events into the store
          if (data.events && Array.isArray(data.events)) {
            data.events.forEach((event: StreamingOutputData) => {
              addOutput(nodeId, event);
            });
          }
        }
      } catch (error) {
        console.error(`Failed to fetch streaming history for ${nodeId}:`, error);
      } finally {
        setIsLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [nodeId, nodeType, addOutput]);

  // Subscribe to WebSocket streaming_output events
  useEffect(() => {
    if (nodeType !== 'agent') return;

    const wsClient = getWebSocketClient();

    const handleStreamingOutput = (data: StreamingOutputData) => {
      // Filter by agent name (nodeId is the agent name)
      if (data.agent_name === nodeId) {
        addOutput(nodeId, data);
      }
    };

    wsClient.on('streaming_output', handleStreamingOutput);

    return () => {
      wsClient.off('streaming_output', handleStreamingOutput);
    };
  }, [nodeId, nodeType, addOutput]);

  // Concatenate all llm_tokens into continuous text, logs/stdout/stderr on separate lines
  const displayContent = useMemo(() => {
    let text = '';
    for (const output of outputs) {
      if (output.output_type === 'llm_token') {
        // Append tokens inline without line breaks
        text += output.content;
      } else {
        // Add line break before log/stdout/stderr if previous content doesn't end with one
        if (text && !text.endsWith('\n')) text += '\n';
        text += output.content;
        text += '\n'
      }
    }
    return text;
  }, [outputs]);

  const containerEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new output arrives
  useEffect(() => {
    if (autoScroll && containerEndRef.current) {
      containerEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [displayContent, autoScroll]);

  const hasFinalOutput = outputs.some((o) => o.is_final);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--color-bg-elevated)',
      }}
    >
      {/* Auto-scroll toggle */}
      <div
        style={{
          padding: 'var(--space-component-sm) var(--space-component-md)',
          background: 'var(--color-bg-surface)',
          borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            color: 'var(--color-text-tertiary)',
            fontSize: 'var(--font-size-caption)',
            fontWeight: 'var(--font-weight-medium)',
            fontFamily: 'var(--font-family-sans)',
          }}
        >
          {outputs.length} {outputs.length === 1 ? 'event' : 'events'}
        </span>
        <label
          style={{
            color: 'var(--color-text-tertiary)',
            fontSize: 'var(--font-size-caption)',
            fontFamily: 'var(--font-family-sans)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--gap-sm)',
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: 'var(--color-primary-500)' }}
          />
          Auto-scroll
        </label>
      </div>

      {/* Output display */}
      <div
        data-testid={`live-output-${nodeId}`}
        style={{
          flex: 1,
          overflow: 'auto',
          position: 'relative',
          padding: 'var(--spacing-2)',
        }}
      >
        {isLoadingHistory ? (
          <div
            style={{
              padding: 'var(--space-layout-md)',
              color: 'var(--color-text-muted)',
              fontSize: 'var(--font-size-body-sm)',
              fontFamily: 'var(--font-family-sans)',
              textAlign: 'center',
            }}
          >
            Loading history...
          </div>
        ) : outputs.length === 0 ? (
          <div
            data-testid="empty-output"
            style={{
              padding: 'var(--space-layout-md)',
              color: 'var(--color-text-muted)',
              fontSize: 'var(--font-size-body-sm)',
              fontFamily: 'var(--font-family-sans)',
              textAlign: 'center',
            }}
          >
            Idle - no output
          </div>
        ) : (
          <>
            <pre
              style={{
                margin: 0,
                color: 'var(--color-tertiary-400)',
                fontFamily: 'var(--font-family-mono)',
                fontSize: 'var(--font-size-caption)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                lineHeight: 'var(--line-height-relaxed)',
              }}
            >
              {displayContent}
            </pre>
            {hasFinalOutput && (
              <div
                data-testid="final-marker"
                style={{
                  color: 'var(--color-text-muted)',
                  fontSize: 'var(--font-size-caption)',
                  fontFamily: 'var(--font-family-mono)',
                  padding: 'var(--spacing-2) 0',
                  borderTop: 'var(--border-width-1) solid var(--color-border-subtle)',
                  marginTop: 'var(--spacing-2)',
                }}
              >
                --- End of output ---
              </div>
            )}
            <div ref={containerEndRef} />
          </>
        )}
      </div>
    </div>
  );
};

export default LiveOutputTab;
