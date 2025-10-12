import React, { useEffect, useState } from 'react';

interface RunStatusTabProps {
  nodeId: string;
  nodeType: 'agent' | 'message';
}

interface RunStatusEntry {
  runId: string;
  startTime: number;
  endTime: number;
  duration: number;
  status: 'idle' | 'processing' | 'error';
  metrics: {
    tokensUsed?: number;
    costUsd?: number;
    artifactsProduced?: number;
  };
  errorMessage?: string;
}

const RunStatusTab: React.FC<RunStatusTabProps> = ({ nodeId, nodeType: _nodeType }) => {
  const [runHistory, setRunHistory] = useState<RunStatusEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Phase 4.1 Feature Gap Fix: Fetch agent run history from backend API
  useEffect(() => {
    const fetchRunHistory = async () => {
      if (_nodeType !== 'agent') {
        setRunHistory([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/agents/${nodeId}/runs`);
        if (!response.ok) {
          throw new Error(`Failed to fetch run history: ${response.statusText}`);
        }

        const data = await response.json();

        // Convert API response to RunStatusEntry format
        const history = data.runs.map((run: any) => ({
          runId: run.run_id,
          startTime: new Date(run.start_time).getTime(),
          endTime: new Date(run.end_time).getTime(),
          duration: run.duration_ms,
          status: run.status === 'completed' ? 'idle' : run.status === 'active' ? 'processing' : 'error',
          metrics: {
            tokensUsed: run.metrics?.tokens_used,
            costUsd: run.metrics?.cost_usd,
            artifactsProduced: run.metrics?.artifacts_produced,
          },
          errorMessage: run.error_message,
        }));

        setRunHistory(history);
      } catch (err) {
        console.error('Failed to fetch run history:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };

    fetchRunHistory();
  }, [nodeId, _nodeType]);

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) {
      return `${ms}ms`;
    } else if (ms < 60000) {
      return `${(ms / 1000).toFixed(2)}s`;
    } else {
      return `${(ms / 60000).toFixed(2)}m`;
    }
  };

  const getStatusColor = (status: RunStatusEntry['status']) => {
    switch (status) {
      case 'idle':
        return 'var(--color-success-light)';
      case 'processing':
        return 'var(--color-tertiary-400)';
      case 'error':
        return 'var(--color-error-light)';
      default:
        return 'var(--color-text-primary)';
    }
  };

  const getStatusLabel = (status: RunStatusEntry['status']) => {
    switch (status) {
      case 'idle':
        return 'Completed';
      case 'processing':
        return 'Processing';
      case 'error':
        return 'Error';
      default:
        return status;
    }
  };

  return (
    <div
      data-testid={`run-status-${nodeId}`}
      style={{
        height: '100%',
        overflow: 'auto',
        background: 'var(--color-bg-elevated)',
        color: 'var(--color-text-primary)',
      }}
    >
      {isLoading ? (
        <div
          data-testid="loading-runs"
          style={{
            padding: 'var(--space-layout-md)',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-sans)',
            textAlign: 'center',
          }}
        >
          Loading run history...
        </div>
      ) : error ? (
        <div
          data-testid="error-runs"
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
      ) : runHistory.length === 0 ? (
        <div
          data-testid="empty-runs"
          style={{
            padding: 'var(--space-layout-md)',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-body-sm)',
            fontFamily: 'var(--font-family-sans)',
            textAlign: 'center',
          }}
        >
          <div style={{ marginBottom: 'var(--space-component-sm)' }}>
            🚧 Run tracking coming soon!
          </div>
          <div style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-tertiary)' }}>
            This feature will track individual agent executions with timing and metrics.
            <br />
            For now, check the Message History tab to see consumed and published messages.
          </div>
        </div>
      ) : (
        <table
          data-testid="run-table"
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
                Run ID
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Start Time
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Duration
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Status
              </th>
              <th
                style={{
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  textAlign: 'left',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                Metrics
              </th>
            </tr>
          </thead>
          <tbody>
            {runHistory.map((run) => (
              <tr
                key={run.runId}
                data-testid={`run-row-${run.runId}`}
                style={{
                  borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
                  transition: 'var(--transition-colors)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--color-bg-surface)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <td
                  data-testid={`run-id-${run.runId}`}
                  style={{
                    padding: 'var(--space-component-sm) var(--space-component-md)',
                    fontFamily: 'var(--font-family-mono)',
                    fontSize: 'var(--font-size-overline)',
                    maxWidth: '150px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  {run.runId}
                </td>
                <td
                  data-testid={`run-start-${run.runId}`}
                  style={{
                    padding: 'var(--space-component-sm) var(--space-component-md)',
                    whiteSpace: 'nowrap',
                    color: 'var(--color-text-tertiary)',
                  }}
                >
                  {formatTimestamp(run.startTime)}
                </td>
                <td
                  data-testid={`run-duration-${run.runId}`}
                  style={{
                    padding: 'var(--space-component-sm) var(--space-component-md)',
                    fontFamily: 'var(--font-family-mono)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  {formatDuration(run.duration)}
                </td>
                <td
                  data-testid={`run-status-${run.runId}`}
                  style={{
                    padding: 'var(--space-component-sm) var(--space-component-md)',
                    color: getStatusColor(run.status),
                    fontWeight: 'var(--font-weight-semibold)',
                  }}
                >
                  {getStatusLabel(run.status)}
                  {run.errorMessage && (
                    <div
                      style={{
                        fontSize: 'var(--font-size-overline)',
                        color: 'var(--color-text-muted)',
                        marginTop: 'var(--spacing-1)',
                        fontStyle: 'italic',
                      }}
                    >
                      {run.errorMessage}
                    </div>
                  )}
                </td>
                <td
                  data-testid={`run-metrics-${run.runId}`}
                  style={{
                    padding: 'var(--space-component-sm) var(--space-component-md)',
                  }}
                >
                  <div
                    style={{
                      fontSize: 'var(--font-size-overline)',
                      fontFamily: 'var(--font-family-mono)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    {run.metrics.tokensUsed !== undefined && (
                      <div>Tokens: {run.metrics.tokensUsed}</div>
                    )}
                    {run.metrics.costUsd !== undefined && (
                      <div>Cost: ${run.metrics.costUsd.toFixed(4)}</div>
                    )}
                    {run.metrics.artifactsProduced !== undefined && (
                      <div>Artifacts: {run.metrics.artifactsProduced}</div>
                    )}
                    {Object.keys(run.metrics).length === 0 && <div>-</div>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default RunStatusTab;
