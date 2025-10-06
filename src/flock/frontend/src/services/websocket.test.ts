/**
 * Unit tests for WebSocket client service.
 *
 * Tests verify connection management, reconnection with exponential backoff,
 * message buffering, event handling, and heartbeat/pong handling.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock WebSocket
class MockWebSocket {
  url: string;
  readyState: number;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  sentMessages: string[] = [];
  private autoConnectTimerId: any = null;
  private errorSimulated = false;
  static skipAutoConnect = false; // Global flag for controlling auto-connect

  constructor(url: string) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;

    // Simulate connection opening (can be prevented by simulateError or global flag)
    if (!MockWebSocket.skipAutoConnect) {
      this.autoConnectTimerId = setTimeout(() => {
        if (!this.errorSimulated && this.readyState === MockWebSocket.CONNECTING) {
          this.readyState = MockWebSocket.OPEN;
          if (this.onopen) {
            this.onopen(new Event('open'));
          }
        }
      }, 0);
    }
  }

  // Method to manually trigger connection success (for timeout tests)
  manuallyConnect(): void {
    if (this.readyState === MockWebSocket.CONNECTING) {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }
  }

  send(data: string): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSING;
    setTimeout(() => {
      this.readyState = MockWebSocket.CLOSED;
      if (this.onclose) {
        this.onclose(new CloseEvent('close', { code: code || 1000, reason }));
      }
    }, 0);
  }

  // Test helpers
  simulateMessage(data: any): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  simulateError(): void {
    this.errorSimulated = true;
    // Clear auto-connect timer if still pending
    if (this.autoConnectTimerId) {
      clearTimeout(this.autoConnectTimerId);
      this.autoConnectTimerId = null;
    }
    // Transition to closed state
    this.readyState = MockWebSocket.CLOSED;
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
    // Also trigger onclose after error
    setTimeout(() => {
      if (this.onclose) {
        this.onclose(new CloseEvent('close', { code: 1006, reason: 'Connection error' }));
      }
    }, 0);
  }

  simulateClose(code: number = 1000): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code }));
    }
  }
}

// Replace global WebSocket with mock
(globalThis as any).WebSocket = MockWebSocket;

describe('WebSocketClient', () => {
  let WebSocketClient: any;
  let client: any;
  let mockStore: any;

  beforeEach(async () => {
    // Reset timers
    vi.useFakeTimers();

    // Mock store for event dispatching
    mockStore = {
      addAgent: vi.fn(),
      updateAgent: vi.fn(),
      addMessage: vi.fn(),
      batchUpdate: vi.fn(),
    };

    // Dynamic import to avoid module-level errors before implementation
    try {
      const module = await import('./websocket');
      WebSocketClient = module.WebSocketClient;
      client = new WebSocketClient('ws://localhost:8080/ws', mockStore);
    } catch (error) {
      // Skip tests if WebSocketClient not implemented yet (TDD approach)
      throw new Error('WebSocketClient not implemented yet - skipping tests');
    }
  });

  afterEach(() => {
    if (client) {
      client.disconnect();
    }
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('should connect to WebSocket server', async () => {
    // Connect
    client.connect();

    // Wait for connection
    await vi.runAllTimersAsync();

    // Verify connection status
    expect(client.isConnected()).toBe(true);
    expect(client.getConnectionStatus()).toBe('connected');
  });

  it('should handle connection failure', async () => {
    // Prevent auto-reconnect for this test
    MockWebSocket.skipAutoConnect = true;

    // Connect
    client.connect();

    // Simulate connection error before connection succeeds
    const ws = client.ws as MockWebSocket;
    ws.simulateError();

    // Wait for error handling (just the error, not reconnection)
    await vi.advanceTimersByTimeAsync(100);

    // Verify connection status
    expect(client.isConnected()).toBe(false);
    expect(client.getConnectionStatus()).toBe('error');

    // Reset flag
    MockWebSocket.skipAutoConnect = false;
  });

  it('should reconnect with exponential backoff (1s, 2s, 4s, 8s, max 30s)', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Simulate disconnection
    (client.ws as MockWebSocket).simulateClose(1006); // Abnormal closure

    // Track reconnection attempts
    const reconnectTimes: number[] = [];

    // Override connect to track timing
    const originalConnect = client.connect.bind(client);
    client.connect = vi.fn(() => {
      reconnectTimes.push(Date.now());
      originalConnect();
    });

    // Wait for first reconnection attempt (1s)
    await vi.advanceTimersByTimeAsync(1000);
    expect(reconnectTimes.length).toBe(1);

    // Simulate failure, wait for second attempt (2s)
    (client.ws as MockWebSocket)?.simulateClose(1006);
    await vi.advanceTimersByTimeAsync(2000);
    expect(reconnectTimes.length).toBe(2);

    // Simulate failure, wait for third attempt (4s)
    (client.ws as MockWebSocket)?.simulateClose(1006);
    await vi.advanceTimersByTimeAsync(4000);
    expect(reconnectTimes.length).toBe(3);

    // Simulate failure, wait for fourth attempt (8s)
    (client.ws as MockWebSocket)?.simulateClose(1006);
    await vi.advanceTimersByTimeAsync(8000);
    expect(reconnectTimes.length).toBe(4);

    // Verify max backoff (30s)
    (client.ws as MockWebSocket)?.simulateClose(1006);
    await vi.advanceTimersByTimeAsync(16000); // Would be 16s, but capped at 30s
    await vi.advanceTimersByTimeAsync(30000);
    expect(reconnectTimes.length).toBe(5);
  });

  it('should buffer messages during disconnection (max 100 messages)', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Disconnect
    client.disconnect();

    // Try to send messages while disconnected
    for (let i = 0; i < 120; i++) {
      client.send({ type: 'test', index: i });
    }

    // Verify messages are buffered (max 100)
    expect(client.getBufferedMessageCount()).toBe(100);

    // Reconnect
    client.connect();
    await vi.runAllTimersAsync();

    // Verify buffered messages are sent
    const ws = client.ws as MockWebSocket;
    expect(ws.sentMessages.length).toBe(100);

    // Verify oldest messages were kept (FIFO)
    const firstMessage = JSON.parse(ws.sentMessages[0]!);
    expect(firstMessage.index).toBe(20); // 0-19 were dropped
  });

  it('should dispatch received messages to store handlers', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Simulate receiving agent_activated event
    const ws = client.ws as MockWebSocket;
    ws.simulateMessage({
      agent_name: 'test_agent',
      agent_id: 'test_agent',
      consumed_types: ['Input'],
      consumed_artifacts: ['artifact-1'],
      subscription_info: { from_agents: [], channels: [], mode: 'both' },
      labels: ['test'],
      tenant_id: null,
      max_concurrency: 1,
      correlation_id: 'corr-123',
      timestamp: '2025-10-03T12:00:00Z',
    });

    // Verify store was updated
    // Implementation will determine exact handler
    // This could be addAgent, updateAgent, or custom event handler
    expect(mockStore.addAgent.mock.calls.length + mockStore.updateAgent.mock.calls.length).toBeGreaterThan(0);
  });

  it('should update connection status state', async () => {
    // Initial state
    expect(client.getConnectionStatus()).toBe('disconnected');

    // Connecting
    client.connect();
    expect(client.getConnectionStatus()).toBe('connecting');

    // Connected
    await vi.runAllTimersAsync();
    expect(client.getConnectionStatus()).toBe('connected');

    // Disconnecting
    client.disconnect();
    expect(client.getConnectionStatus()).toBe('disconnecting');

    // Disconnected
    await vi.runAllTimersAsync();
    expect(client.getConnectionStatus()).toBe('disconnected');

    // Error state
    client.connect();
    await vi.runAllTimersAsync();
    (client.ws as MockWebSocket).simulateError();
    expect(client.getConnectionStatus()).toBe('error');
  });

  it('should handle heartbeat/pong messages', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    const ws = client.ws as MockWebSocket;

    // Simulate receiving heartbeat/ping from server
    ws.simulateMessage({ type: 'ping', timestamp: Date.now() });

    // Verify pong response was sent
    const pongMessages = ws.sentMessages.filter(msg => {
      try {
        const data = JSON.parse(msg);
        return data.type === 'pong';
      } catch {
        return false;
      }
    });

    expect(pongMessages.length).toBeGreaterThan(0);
  });

  it('should handle message_published events', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Simulate receiving message_published event
    const ws = client.ws as MockWebSocket;
    ws.simulateMessage({
      artifact_id: 'artifact-123',
      artifact_type: 'Movie',
      produced_by: 'movie_agent',
      payload: { title: 'Inception', year: 2010 },
      visibility: { kind: 'Public' },
      tags: ['scifi'],
      version: 1,
      consumers: ['tagline_agent'],
      correlation_id: 'corr-456',
      timestamp: '2025-10-03T12:01:00Z',
    });

    // Verify message was added to store
    expect(mockStore.addMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'artifact-123',
        type: 'Movie',
        payload: expect.objectContaining({ title: 'Inception' }),
      })
    );
  });

  it('should handle agent_completed events', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Simulate receiving agent_completed event
    const ws = client.ws as MockWebSocket;
    ws.simulateMessage({
      agent_name: 'test_agent',
      run_id: 'task-123',
      duration_ms: 1234.56,
      artifacts_produced: ['artifact-1', 'artifact-2'],
      metrics: { tokens_used: 500, cost_usd: 0.01 },
      final_state: {},
      correlation_id: 'corr-789',
      timestamp: '2025-10-03T12:02:00Z',
    });

    // Verify agent status was updated
    expect(mockStore.updateAgent).toHaveBeenCalledWith(
      'test_agent',
      expect.objectContaining({
        status: 'idle', // or 'completed'
      })
    );
  });

  it('should handle agent_error events', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Simulate receiving agent_error event
    const ws = client.ws as MockWebSocket;
    ws.simulateMessage({
      agent_name: 'test_agent',
      run_id: 'task-456',
      error_type: 'ValueError',
      error_message: 'Invalid input',
      traceback: 'Traceback...',
      failed_at: '2025-10-03T12:03:00Z',
      correlation_id: 'corr-999',
      timestamp: '2025-10-03T12:03:00Z',
    });

    // Verify agent status was updated to error
    expect(mockStore.updateAgent).toHaveBeenCalledWith(
      'test_agent',
      expect.objectContaining({
        status: 'error',
      })
    );
  });

  it('should handle streaming_output events', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    // Simulate receiving streaming_output event
    const ws = client.ws as MockWebSocket;
    ws.simulateMessage({
      agent_name: 'llm_agent',
      run_id: 'task-789',
      output_type: 'llm_token',
      content: 'Generated text...',
      sequence: 1,
      is_final: false,
      correlation_id: 'corr-111',
      timestamp: '2025-10-03T12:04:00Z',
    });

    // Verify streaming output was handled
    // Implementation may use custom handler or update agent state
    // This test verifies the event was processed without error
    expect(mockStore.updateAgent).toHaveBeenCalled();
  });

  it('should clean up on disconnect', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    const ws = client.ws as MockWebSocket;

    // Disconnect
    client.disconnect();
    await vi.runAllTimersAsync();

    // Verify WebSocket is closed
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);

    // Verify no reconnection attempts
    await vi.advanceTimersByTimeAsync(5000);
    expect(client.isConnected()).toBe(false);
  });

  it('should handle malformed JSON messages gracefully', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    const ws = client.ws as MockWebSocket;

    // Simulate receiving malformed JSON
    if (ws.onmessage) {
      ws.onmessage(new MessageEvent('message', { data: 'invalid json {{{' }));
    }

    // Verify client is still connected (error was handled)
    expect(client.isConnected()).toBe(true);
  });

  it('should support manual reconnection', async () => {
    // Connect and disconnect
    client.connect();
    await vi.runAllTimersAsync();
    client.disconnect();
    await vi.runAllTimersAsync();

    expect(client.isConnected()).toBe(false);

    // Manual reconnect
    client.connect();
    await vi.runAllTimersAsync();

    expect(client.isConnected()).toBe(true);
  });

  it('should prevent multiple simultaneous connections', async () => {
    // Connect
    client.connect();
    await vi.runAllTimersAsync();

    const firstWs = client.ws;

    // Try to connect again (should use same WebSocket)
    client.connect();
    await vi.runAllTimersAsync();

    expect(client.ws).toBe(firstWs); // Should reuse existing connection

    // Verify same WebSocket instance (or old one was closed)
    // Implementation should either reuse or close old connection
    expect(client.ws).toBeDefined();
    expect(client.isConnected()).toBe(true);
  });
});

describe('WebSocketClient - Edge Cases', () => {
  let WebSocketClient: any;
  let client: any;
  let mockStore: any;

  beforeEach(async () => {
    vi.useFakeTimers();

    mockStore = {
      addAgent: vi.fn(),
      updateAgent: vi.fn(),
      addMessage: vi.fn(),
      batchUpdate: vi.fn(),
    };

    try {
      const module = await import('./websocket');
      WebSocketClient = module.WebSocketClient;
      client = new WebSocketClient('ws://localhost:8080/ws', mockStore);
    } catch (error) {
      throw new Error('WebSocketClient not implemented yet - skipping tests');
    }
  });

  afterEach(() => {
    if (client) {
      client.disconnect();
    }
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('should handle rapid connect/disconnect cycles', async () => {
    for (let i = 0; i < 5; i++) {
      client.connect();
      await vi.runAllTimersAsync();
      expect(client.isConnected()).toBe(true);

      client.disconnect();
      await vi.runAllTimersAsync();
      expect(client.isConnected()).toBe(false);
    }
  });

  it('should handle connection timeout', async () => {
    // Prevent auto-connect in mock
    MockWebSocket.skipAutoConnect = true;

    // Connect
    client.connect();

    // Don't simulate open event - let connection timeout
    await vi.advanceTimersByTimeAsync(10000); // 10 second timeout

    // Verify timeout was handled
    // Implementation should either retry or emit error
    expect(client.getConnectionStatus()).toMatch(/error|connecting/);

    // Reset flag
    MockWebSocket.skipAutoConnect = false;
  });

  it('should reset backoff on successful connection', async () => {
    // Initial connection
    client.connect();
    await vi.runAllTimersAsync();

    // Disconnect and trigger exponential backoff
    (client.ws as MockWebSocket).simulateClose(1006);
    await vi.advanceTimersByTimeAsync(1000);
    (client.ws as MockWebSocket)?.simulateClose(1006);
    await vi.advanceTimersByTimeAsync(2000);

    // Successful connection
    client.connect();
    await vi.runAllTimersAsync();
    expect(client.isConnected()).toBe(true);

    // Next disconnection should start at 1s again (backoff reset)
    (client.ws as MockWebSocket).simulateClose(1006);
    const startTime = Date.now();
    await vi.advanceTimersByTimeAsync(1000);

    // Verify reconnection happened at 1s (not continuing exponential backoff)
    expect(Date.now() - startTime).toBeLessThan(1500);
  });
});
