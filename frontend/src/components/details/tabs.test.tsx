/**
 * Unit tests for MessageHistoryTab and RunStatusTab components.
 *
 * Tests verify message history display, run status metrics, tab switching,
 * and default tab preference handling.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useUIStore } from '../../store/uiStore';

// Message data types
interface MessageHistoryEntry {
  id: string;
  type: string;
  direction: 'consumed' | 'published';
  payload: any;
  timestamp: number;
  correlationId: string;
}

// Run status data types
interface RunStatusEntry {
  runId: string;
  startTime: number;
  endTime: number;
  duration: number;
  status: 'completed' | 'error' | 'running';
  metrics: {
    tokensUsed?: number;
    costUsd?: number;
    artifactsProduced?: number;
  };
  errorMessage?: string;
}

// Mock MessageHistoryTab component
const MockMessageHistoryTab = ({
  nodeId,
  messages,
}: {
  nodeId: string;
  messages: MessageHistoryEntry[];
}) => {
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

  return (
    <div data-testid={`message-history-${nodeId}`}>
      {messages.length === 0 ? (
        <div data-testid="empty-messages">No messages yet</div>
      ) : (
        <table data-testid="message-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Direction</th>
              <th>Type</th>
              <th>Correlation ID</th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {messages.map((msg) => (
              <tr key={msg.id} data-testid={`message-row-${msg.id}`}>
                <td data-testid={`msg-time-${msg.id}`}>{formatTimestamp(msg.timestamp)}</td>
                <td
                  data-testid={`msg-direction-${msg.id}`}
                  style={{
                    color: msg.direction === 'consumed' ? '#8be9fd' : '#50fa7b',
                  }}
                >
                  {msg.direction === 'consumed' ? '↓ Consumed' : '↑ Published'}
                </td>
                <td data-testid={`msg-type-${msg.id}`}>{msg.type}</td>
                <td data-testid={`msg-correlation-${msg.id}`}>{msg.correlationId}</td>
                <td data-testid={`msg-payload-${msg.id}`}>
                  <pre style={{ fontSize: '10px', maxHeight: '100px', overflow: 'auto' }}>
                    {formatPayload(msg.payload)}
                  </pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

// Mock RunStatusTab component
const MockRunStatusTab = ({
  nodeId,
  runs,
}: {
  nodeId: string;
  runs: RunStatusEntry[];
}) => {
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div data-testid={`run-status-${nodeId}`}>
      {runs.length === 0 ? (
        <div data-testid="empty-runs">No runs yet</div>
      ) : (
        <table data-testid="run-table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Start Time</th>
              <th>Duration</th>
              <th>Status</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Artifacts</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.runId} data-testid={`run-row-${run.runId}`}>
                <td data-testid={`run-id-${run.runId}`}>{run.runId}</td>
                <td data-testid={`run-start-${run.runId}`}>
                  {formatTimestamp(run.startTime)}
                </td>
                <td data-testid={`run-duration-${run.runId}`}>
                  {formatDuration(run.duration)}
                </td>
                <td
                  data-testid={`run-status-${run.runId}`}
                  style={{
                    color:
                      run.status === 'completed'
                        ? '#50fa7b'
                        : run.status === 'error'
                          ? '#ff5555'
                          : '#f1fa8c',
                  }}
                >
                  {run.status}
                </td>
                <td data-testid={`run-tokens-${run.runId}`}>
                  {run.metrics.tokensUsed ?? '-'}
                </td>
                <td data-testid={`run-cost-${run.runId}`}>
                  {run.metrics.costUsd ? `$${run.metrics.costUsd.toFixed(4)}` : '-'}
                </td>
                <td data-testid={`run-artifacts-${run.runId}`}>
                  {run.metrics.artifactsProduced ?? '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

// Mock tab container component
const MockTabContainer = ({
  nodeId,
  messages,
  runs,
}: {
  nodeId: string;
  messages: MessageHistoryEntry[];
  runs: RunStatusEntry[];
}) => {
  const window = useUIStore((state) => state.detailWindows.get(nodeId));
  const updateDetailWindow = useUIStore((state) => state.updateDetailWindow);

  if (!window) return null;

  const activeTab = window.activeTab;

  const handleTabClick = (tab: 'liveOutput' | 'messageHistory' | 'runStatus') => {
    updateDetailWindow(nodeId, { activeTab: tab });
  };

  return (
    <div data-testid={`tab-container-${nodeId}`}>
      <div data-testid="tab-buttons">
        <button
          data-testid="tab-live-output"
          onClick={() => handleTabClick('liveOutput')}
          data-active={activeTab === 'liveOutput'}
          style={{
            fontWeight: activeTab === 'liveOutput' ? 'bold' : 'normal',
          }}
        >
          Live Output
        </button>
        <button
          data-testid="tab-message-history"
          onClick={() => handleTabClick('messageHistory')}
          data-active={activeTab === 'messageHistory'}
          style={{
            fontWeight: activeTab === 'messageHistory' ? 'bold' : 'normal',
          }}
        >
          Message History
        </button>
        <button
          data-testid="tab-run-status"
          onClick={() => handleTabClick('runStatus')}
          data-active={activeTab === 'runStatus'}
          style={{
            fontWeight: activeTab === 'runStatus' ? 'bold' : 'normal',
          }}
        >
          Run Status
        </button>
      </div>

      <div data-testid="tab-content">
        {activeTab === 'liveOutput' && (
          <div data-testid="live-output-content">Live Output Tab</div>
        )}
        {activeTab === 'messageHistory' && (
          <MockMessageHistoryTab nodeId={nodeId} messages={messages} />
        )}
        {activeTab === 'runStatus' && (
          <MockRunStatusTab nodeId={nodeId} runs={runs} />
        )}
      </div>
    </div>
  );
};

describe('MessageHistoryTab', () => {
  beforeEach(() => {
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      detailWindows: new Map(),
      defaultTab: 'liveOutput',
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
    });
  });

  describe('Display', () => {
    it('should render empty state when no messages', () => {
      render(<MockMessageHistoryTab nodeId="agent-1" messages={[]} />);

      expect(screen.getByTestId('empty-messages')).toBeInTheDocument();
      expect(screen.getByText('No messages yet')).toBeInTheDocument();
    });

    it('should display messages in table format', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          direction: 'consumed',
          payload: { title: 'Inception' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      expect(screen.getByTestId('message-table')).toBeInTheDocument();
      expect(screen.getByTestId('message-row-msg-1')).toBeInTheDocument();
    });

    it('should display consumed messages with correct styling', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Input',
          direction: 'consumed',
          payload: { data: 'test' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      const direction = screen.getByTestId('msg-direction-msg-1');
      expect(direction).toHaveTextContent('↓ Consumed');
      expect(direction).toHaveStyle({ color: '#8be9fd' });
    });

    it('should display published messages with correct styling', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Output',
          direction: 'published',
          payload: { result: 'success' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      const direction = screen.getByTestId('msg-direction-msg-1');
      expect(direction).toHaveTextContent('↑ Published');
      expect(direction).toHaveStyle({ color: '#50fa7b' });
    });

    it('should display message type', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          direction: 'consumed',
          payload: {},
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      expect(screen.getByTestId('msg-type-msg-1')).toHaveTextContent('Movie');
    });

    it('should display correlation ID', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Test',
          direction: 'consumed',
          payload: {},
          timestamp: Date.now(),
          correlationId: 'corr-123-abc',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      expect(screen.getByTestId('msg-correlation-msg-1')).toHaveTextContent('corr-123-abc');
    });

    it('should format and display payload as JSON', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          direction: 'consumed',
          payload: { title: 'Inception', year: 2010 },
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      const payload = screen.getByTestId('msg-payload-msg-1');
      expect(payload.textContent).toContain('title');
      expect(payload.textContent).toContain('Inception');
      expect(payload.textContent).toContain('2010');
    });

    it('should display timestamp in readable format', () => {
      const timestamp = Date.now();
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Test',
          direction: 'consumed',
          payload: {},
          timestamp,
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      const timeElement = screen.getByTestId('msg-time-msg-1');
      expect(timeElement.textContent).toBeTruthy();
      expect(timeElement.textContent).not.toBe(String(timestamp));
    });
  });

  describe('Multiple Messages', () => {
    it('should display multiple messages in order', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Input',
          direction: 'consumed',
          payload: { data: 1 },
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
        {
          id: 'msg-2',
          type: 'Output',
          direction: 'published',
          payload: { result: 1 },
          timestamp: Date.now() + 1000,
          correlationId: 'corr-2',
        },
        {
          id: 'msg-3',
          type: 'Input',
          direction: 'consumed',
          payload: { data: 2 },
          timestamp: Date.now() + 2000,
          correlationId: 'corr-3',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      expect(screen.getByTestId('message-row-msg-1')).toBeInTheDocument();
      expect(screen.getByTestId('message-row-msg-2')).toBeInTheDocument();
      expect(screen.getByTestId('message-row-msg-3')).toBeInTheDocument();
    });

    it('should handle mixed consumed and published messages', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          direction: 'consumed',
          payload: {},
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
        {
          id: 'msg-2',
          type: 'Tagline',
          direction: 'published',
          payload: {},
          timestamp: Date.now() + 1000,
          correlationId: 'corr-2',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      expect(screen.getByTestId('msg-direction-msg-1')).toHaveTextContent('↓ Consumed');
      expect(screen.getByTestId('msg-direction-msg-2')).toHaveTextContent('↑ Published');
    });
  });

  describe('Edge Cases', () => {
    it('should handle complex nested payload', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Complex',
          direction: 'consumed',
          payload: {
            nested: {
              deeply: {
                value: 'test',
                array: [1, 2, 3],
              },
            },
          },
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      const payload = screen.getByTestId('msg-payload-msg-1');
      expect(payload.textContent).toContain('nested');
      expect(payload.textContent).toContain('deeply');
    });

    it('should handle null payload', () => {
      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Test',
          direction: 'consumed',
          payload: null,
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      expect(() => {
        render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);
      }).not.toThrow();
    });

    it('should handle large payloads with scrolling', () => {
      const largePayload = {
        data: Array.from({ length: 100 }, (_, i) => ({ id: i, value: `Item ${i}` })),
      };

      const messages: MessageHistoryEntry[] = [
        {
          id: 'msg-1',
          type: 'Large',
          direction: 'consumed',
          payload: largePayload,
          timestamp: Date.now(),
          correlationId: 'corr-1',
        },
      ];

      render(<MockMessageHistoryTab nodeId="agent-1" messages={messages} />);

      const payload = screen.getByTestId('msg-payload-msg-1');
      const pre = payload.querySelector('pre');
      expect(pre).toHaveStyle({ maxHeight: '100px', overflow: 'auto' });
    });
  });
});

describe('RunStatusTab', () => {
  beforeEach(() => {
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      detailWindows: new Map(),
      defaultTab: 'liveOutput',
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
    });
  });

  describe('Display', () => {
    it('should render empty state when no runs', () => {
      render(<MockRunStatusTab nodeId="agent-1" runs={[]} />);

      expect(screen.getByTestId('empty-runs')).toBeInTheDocument();
      expect(screen.getByText('No runs yet')).toBeInTheDocument();
    });

    it('should display runs in table format', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: { tokensUsed: 100, costUsd: 0.01 },
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-table')).toBeInTheDocument();
      expect(screen.getByTestId('run-row-run-1')).toBeInTheDocument();
    });

    it('should display run ID', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-abc-123',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-id-run-abc-123')).toHaveTextContent('run-abc-123');
    });

    it('should display start time in readable format', () => {
      const startTime = Date.now();
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime,
          endTime: startTime + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      const startElement = screen.getByTestId('run-start-run-1');
      expect(startElement.textContent).toBeTruthy();
      expect(startElement.textContent).not.toBe(String(startTime));
    });

    it('should format duration in milliseconds', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 500,
          duration: 500,
          status: 'completed',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-duration-run-1')).toHaveTextContent('500ms');
    });

    it('should format duration in seconds', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 2500,
          duration: 2500,
          status: 'completed',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-duration-run-1')).toHaveTextContent('2.50s');
    });

    it('should display completed status with green color', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      const status = screen.getByTestId('run-status-run-1');
      expect(status).toHaveTextContent('completed');
      expect(status).toHaveStyle({ color: '#50fa7b' });
    });

    it('should display error status with red color', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'error',
          metrics: {},
          errorMessage: 'Test error',
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      const status = screen.getByTestId('run-status-run-1');
      expect(status).toHaveTextContent('error');
      expect(status).toHaveStyle({ color: '#ff5555' });
    });

    it('should display running status with yellow color', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'running',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      const status = screen.getByTestId('run-status-run-1');
      expect(status).toHaveTextContent('running');
      expect(status).toHaveStyle({ color: '#f1fa8c' });
    });
  });

  describe('Metrics', () => {
    it('should display tokens used', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: { tokensUsed: 500 },
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-tokens-run-1')).toHaveTextContent('500');
    });

    it('should display cost in USD', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: { costUsd: 0.0123 },
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-cost-run-1')).toHaveTextContent('$0.0123');
    });

    it('should display artifacts produced', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: { artifactsProduced: 3 },
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-artifacts-run-1')).toHaveTextContent('3');
    });

    it('should show dash for missing metrics', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-tokens-run-1')).toHaveTextContent('-');
      expect(screen.getByTestId('run-cost-run-1')).toHaveTextContent('-');
      expect(screen.getByTestId('run-artifacts-run-1')).toHaveTextContent('-');
    });

    it('should display all metrics together', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {
            tokensUsed: 750,
            costUsd: 0.025,
            artifactsProduced: 5,
          },
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-tokens-run-1')).toHaveTextContent('750');
      expect(screen.getByTestId('run-cost-run-1')).toHaveTextContent('$0.0250');
      expect(screen.getByTestId('run-artifacts-run-1')).toHaveTextContent('5');
    });
  });

  describe('Multiple Runs', () => {
    it('should display multiple runs in order', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
        {
          runId: 'run-2',
          startTime: Date.now() + 2000,
          endTime: Date.now() + 3000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
        {
          runId: 'run-3',
          startTime: Date.now() + 4000,
          endTime: Date.now() + 5000,
          duration: 1000,
          status: 'running',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-row-run-1')).toBeInTheDocument();
      expect(screen.getByTestId('run-row-run-2')).toBeInTheDocument();
      expect(screen.getByTestId('run-row-run-3')).toBeInTheDocument();
    });

    it('should show runs with different statuses', () => {
      const runs: RunStatusEntry[] = [
        {
          runId: 'run-1',
          startTime: Date.now(),
          endTime: Date.now() + 1000,
          duration: 1000,
          status: 'completed',
          metrics: {},
        },
        {
          runId: 'run-2',
          startTime: Date.now() + 2000,
          endTime: Date.now() + 3000,
          duration: 1000,
          status: 'error',
          metrics: {},
        },
      ];

      render(<MockRunStatusTab nodeId="agent-1" runs={runs} />);

      expect(screen.getByTestId('run-status-run-1')).toHaveTextContent('completed');
      expect(screen.getByTestId('run-status-run-2')).toHaveTextContent('error');
    });
  });
});

describe('Tab Switching', () => {
  beforeEach(() => {
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      detailWindows: new Map(),
      defaultTab: 'liveOutput',
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
    });
  });

  it('should switch between tabs', () => {
    useUIStore.getState().openDetailWindow('agent-1');

    const { rerender } = render(
      <MockTabContainer nodeId="agent-1" messages={[]} runs={[]} />
    );

    // Initially on liveOutput
    expect(screen.getByTestId('tab-live-output')).toHaveAttribute('data-active', 'true');
    expect(screen.getByTestId('live-output-content')).toBeInTheDocument();

    // Switch to message history
    fireEvent.click(screen.getByTestId('tab-message-history'));
    rerender(<MockTabContainer nodeId="agent-1" messages={[]} runs={[]} />);

    expect(screen.getByTestId('tab-message-history')).toHaveAttribute('data-active', 'true');
    expect(screen.getByTestId('message-history-agent-1')).toBeInTheDocument();

    // Switch to run status
    fireEvent.click(screen.getByTestId('tab-run-status'));
    rerender(<MockTabContainer nodeId="agent-1" messages={[]} runs={[]} />);

    expect(screen.getByTestId('tab-run-status')).toHaveAttribute('data-active', 'true');
    expect(screen.getByTestId('run-status-agent-1')).toBeInTheDocument();
  });

  it('should highlight active tab', () => {
    useUIStore.getState().openDetailWindow('agent-1');
    render(<MockTabContainer nodeId="agent-1" messages={[]} runs={[]} />);

    const liveOutputButton = screen.getByTestId('tab-live-output');
    const messageHistoryButton = screen.getByTestId('tab-message-history');

    expect(liveOutputButton).toHaveStyle({ fontWeight: 'bold' });
    expect(messageHistoryButton).toHaveStyle({ fontWeight: 'normal' });

    // Switch tab
    fireEvent.click(messageHistoryButton);

    expect(screen.getByTestId('tab-message-history')).toHaveStyle({ fontWeight: 'bold' });
  });

  it('should persist active tab in store', () => {
    useUIStore.getState().openDetailWindow('agent-1');
    render(<MockTabContainer nodeId="agent-1" messages={[]} runs={[]} />);

    // Switch to message history
    fireEvent.click(screen.getByTestId('tab-message-history'));

    const window = useUIStore.getState().detailWindows.get('agent-1');
    expect(window?.activeTab).toBe('messageHistory');
  });

  it('should maintain tab state across window updates', () => {
    useUIStore.getState().openDetailWindow('agent-1');

    // Set tab to messageHistory
    useUIStore.getState().updateDetailWindow('agent-1', {
      activeTab: 'messageHistory',
    });

    render(<MockTabContainer nodeId="agent-1" messages={[]} runs={[]} />);

    expect(screen.getByTestId('tab-message-history')).toHaveAttribute('data-active', 'true');
    expect(screen.getByTestId('message-history-agent-1')).toBeInTheDocument();

    // Update window position (shouldn't affect tab)
    useUIStore.getState().updateDetailWindow('agent-1', {
      position: { x: 200, y: 200 },
    });

    const window = useUIStore.getState().detailWindows.get('agent-1');
    expect(window?.activeTab).toBe('messageHistory');
  });
});

describe('Default Tab Preference', () => {
  beforeEach(() => {
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      detailWindows: new Map(),
      defaultTab: 'liveOutput',
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
    });
  });

  it('should use liveOutput as default tab', () => {
    useUIStore.setState({ defaultTab: 'liveOutput' });
    useUIStore.getState().openDetailWindow('agent-1');

    const window = useUIStore.getState().detailWindows.get('agent-1');
    expect(window?.activeTab).toBe('liveOutput');
  });

  it('should use messageHistory as default tab when configured', () => {
    useUIStore.setState({ defaultTab: 'messageHistory' });
    useUIStore.getState().openDetailWindow('agent-1');

    const window = useUIStore.getState().detailWindows.get('agent-1');
    expect(window?.activeTab).toBe('messageHistory');
  });

  it('should use runStatus as default tab when configured', () => {
    useUIStore.setState({ defaultTab: 'runStatus' });
    useUIStore.getState().openDetailWindow('agent-1');

    const window = useUIStore.getState().detailWindows.get('agent-1');
    expect(window?.activeTab).toBe('runStatus');
  });

  it('should apply default tab to newly opened windows', () => {
    useUIStore.setState({ defaultTab: 'messageHistory' });

    useUIStore.getState().openDetailWindow('agent-1');
    useUIStore.getState().openDetailWindow('agent-2');
    useUIStore.getState().openDetailWindow('agent-3');

    expect(
      useUIStore.getState().detailWindows.get('agent-1')?.activeTab
    ).toBe('messageHistory');
    expect(
      useUIStore.getState().detailWindows.get('agent-2')?.activeTab
    ).toBe('messageHistory');
    expect(
      useUIStore.getState().detailWindows.get('agent-3')?.activeTab
    ).toBe('messageHistory');
  });

  it('should respect default tab preference change', () => {
    useUIStore.setState({ defaultTab: 'liveOutput' });
    useUIStore.getState().openDetailWindow('agent-1');

    expect(
      useUIStore.getState().detailWindows.get('agent-1')?.activeTab
    ).toBe('liveOutput');

    // Close and reopen with different preference
    useUIStore.getState().closeDetailWindow('agent-1');
    useUIStore.setState({ defaultTab: 'runStatus' });
    useUIStore.getState().openDetailWindow('agent-1');

    expect(
      useUIStore.getState().detailWindows.get('agent-1')?.activeTab
    ).toBe('runStatus');
  });
});
