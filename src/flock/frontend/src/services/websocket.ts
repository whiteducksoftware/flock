import { useWSStore } from '../store/wsStore';
import { useGraphStore } from '../store/graphStore';

interface WebSocketMessage {
  event_type: 'agent_activated' | 'message_published' | 'streaming_output' | 'agent_completed' | 'agent_error';
  timestamp: string;
  correlation_id: string;
  session_id: string;
  data: any;
}

interface StoreInterface {
  addAgent: (agent: any) => void;
  updateAgent: (id: string, updates: any) => void;
  addMessage: (message: any) => void;
  updateMessage: (id: string, updates: any) => void;
  batchUpdate?: (update: any) => void;
}

export class WebSocketClient {
  ws: WebSocket | null = null;
  private reconnectTimeout: number | null = null;
  private reconnectAttempt = 0;
  private maxReconnectDelay = 30000; // 30 seconds
  private connectionTimeout: number | null = null;
  private connectionTimeoutMs = 10000; // 10 seconds
  private messageBuffer: any[] = [];
  private maxBufferSize = 100;
  private eventHandlers: Map<string, ((data: any) => void)[]> = new Map();
  private url: string;
  private shouldReconnect = true;
  private heartbeatInterval: number | null = null;
  private heartbeatTimeout: number | null = null;
  private connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'disconnecting' | 'error' = 'disconnected';
  private store: StoreInterface;
  private enableHeartbeat: boolean;

  constructor(url: string, mockStore?: StoreInterface) {
    this.url = url;
    this.store = mockStore || {
      addAgent: (agent: any) => useGraphStore.getState().addAgent(agent),
      updateAgent: (id: string, updates: any) => useGraphStore.getState().updateAgent(id, updates),
      addMessage: (message: any) => useGraphStore.getState().addMessage(message),
      updateMessage: (id: string, updates: any) => useGraphStore.getState().updateMessage(id, updates),
      batchUpdate: (update: any) => useGraphStore.getState().batchUpdate(update),
    };
    // Phase 11 Fix: Disable heartbeat entirely - it causes unnecessary disconnects
    // WebSocket auto-reconnects on real network issues without needing heartbeat
    // The heartbeat was closing connections every 2min when backend didn't respond to pings
    this.enableHeartbeat = false;
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    // Handler for agent_activated: create/update agent in graph AND create Run
    this.on('agent_activated', (data) => {
      const agents = useGraphStore.getState().agents;
      const messages = useGraphStore.getState().messages;
      const existingAgent = agents.get(data.agent_id);

      // Count received messages by type
      const receivedByType = { ...(existingAgent?.receivedByType || {}) };
      if (data.consumed_artifacts && data.consumed_artifacts.length > 0) {
        // Look up each consumed artifact and count by type
        data.consumed_artifacts.forEach((artifactId: string) => {
          const message = messages.get(artifactId);
          if (message) {
            receivedByType[message.type] = (receivedByType[message.type] || 0) + 1;
          }
        });
      }

      // Bug Fix #2: Preserve sentCount/recvCount if agent already exists
      // Otherwise counters get reset to 0 on each activation
      const agent = {
        id: data.agent_id,
        name: data.agent_name,
        status: 'running' as const,
        subscriptions: data.consumed_types || [],
        lastActive: Date.now(),
        sentCount: existingAgent?.sentCount || 0, // Preserve existing count
        recvCount: (existingAgent?.recvCount || 0) + (data.consumed_artifacts?.length || 0), // Add new consumed artifacts
        outputTypes: data.produced_types || [], // Get output types from backend
        receivedByType, // Track per-type received counts
        sentByType: existingAgent?.sentByType || {}, // Preserve sent counts
      };
      this.store.addAgent(agent);

      // Phase 11 Bug Fix: Record actual consumption to track filtering
      // This enables showing "(3, filtered: 1)" on edges
      if (data.consumed_artifacts && data.consumed_artifacts.length > 0) {
        useGraphStore.getState().recordConsumption(data.consumed_artifacts, data.agent_id);
      }

      // Create Run object for Blackboard View edges
      // Bug Fix: Use run_id from backend (unique per agent activation) instead of correlation_id
      const run = {
        run_id: data.run_id || `run_${Date.now()}`, // data.run_id is ctx.task_id from backend
        agent_name: data.agent_name,
        correlation_id: data.correlation_id, // Separate field for grouping runs
        status: 'active' as const,
        consumed_artifacts: data.consumed_artifacts || [],
        produced_artifacts: [], // Will be populated on message_published
        started_at: new Date().toISOString(),
      };
      if (this.store.batchUpdate) {
        this.store.batchUpdate({ runs: [run] });
      }
    });

    // Handler for message_published: update existing streaming message or create new one
    this.on('message_published', (data) => {
      // Finalize or create the message
      const messages = useGraphStore.getState().messages;
      const streamingMessageId = `streaming_${data.produced_by}_${data.correlation_id}`;
      const existingMessage = messages.get(streamingMessageId);

      if (existingMessage) {
        // Update existing streaming message with final data
        const finalMessage = {
          ...existingMessage,
          id: data.artifact_id, // Replace temp ID with real artifact ID
          type: data.artifact_type,
          payload: data.payload,
          isStreaming: false, // Streaming complete
          streamingText: '', // Clear streaming text
        };

        // Use store action to properly update (triggers graph regeneration)
        useGraphStore.getState().finalizeStreamingMessage(streamingMessageId, finalMessage);
      } else {
        // No streaming message - create new message directly
        const message = {
          id: data.artifact_id,
          type: data.artifact_type,
          payload: data.payload,
          timestamp: data.timestamp ? new Date(data.timestamp).getTime() : Date.now(),
          correlationId: data.correlation_id || '',
          producedBy: data.produced_by,
          isStreaming: false,
        };
        this.store.addMessage(message);
      }

      // Update producer agent counters (outputTypes come from agent_activated event now)
      const producer = useGraphStore.getState().agents.get(data.produced_by);
      if (producer) {
        // Track sent count by type
        const sentByType = { ...(producer.sentByType || {}) };
        sentByType[data.artifact_type] = (sentByType[data.artifact_type] || 0) + 1;

        this.store.updateAgent(data.produced_by, {
          sentCount: (producer.sentCount || 0) + 1,
          lastActive: Date.now(),
          sentByType,
        });
      } else {
        // Producer doesn't exist as a registered agent - create virtual agent
        // This handles orchestrator-published artifacts (e.g., initial Idea from dashboard PublishControl)
        this.store.addAgent({
          id: data.produced_by,
          name: data.produced_by,
          status: 'idle' as const,
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 1,
          recvCount: 0,
          outputTypes: [data.artifact_type], // Virtual agents get type from their first message
          sentByType: { [data.artifact_type]: 1 },
          receivedByType: {},
        });
      }

      // Phase 11 Bug Fix: Increment consumers' recv count instead of setting to 1
      if (data.consumers && Array.isArray(data.consumers)) {
        const agents = useGraphStore.getState().agents;
        data.consumers.forEach((consumerId: string) => {
          const consumer = agents.get(consumerId);
          if (consumer) {
            this.store.updateAgent(consumerId, {
              recvCount: (consumer.recvCount || 0) + 1,
              lastActive: Date.now(),
            });
          }
        });
      }

      // Update Run with produced artifact for Blackboard View edges
      // Bug Fix: Find Run by agent_name + correlation_id since run_id is not in message_published event
      if (data.correlation_id && this.store.batchUpdate) {
        const runs = useGraphStore.getState().runs;
        // Find the active Run for this agent + correlation_id
        const run = Array.from(runs.values()).find(
          r => r.agent_name === data.produced_by &&
               r.correlation_id === data.correlation_id &&
               r.status === 'active'
        );
        if (run) {
          // Add artifact to produced_artifacts if not already present
          if (!run.produced_artifacts.includes(data.artifact_id)) {
            const updatedRun = {
              ...run,
              produced_artifacts: [...run.produced_artifacts, data.artifact_id],
            };
            this.store.batchUpdate({ runs: [updatedRun] });
          }
        }
      }
    });

    // Handler for streaming_output: update live output (Phase 6)
    this.on('streaming_output', (data) => {
      // Phase 6: Update detail window live output
      console.log('[WebSocket] Streaming output:', data);
      // Update agent to show it's active and track streaming tokens for news ticker
      if (data.agent_name && data.output_type === 'llm_token') {
        const agents = useGraphStore.getState().agents;
        const agent = agents.get(data.agent_name);
        const currentTokens = agent?.streamingTokens || [];

        // Keep only last 6 tokens (news ticker effect)
        const updatedTokens = [...currentTokens, data.content].slice(-6);

        this.store.updateAgent(data.agent_name, {
          lastActive: Date.now(),
          streamingTokens: updatedTokens,
        });
      }

      // Create/update streaming message node for blackboard view
      if (data.output_type === 'llm_token' && data.agent_name && data.correlation_id) {
        const messages = useGraphStore.getState().messages;
        // Use agent_name + correlation_id as temporary ID
        const streamingMessageId = `streaming_${data.agent_name}_${data.correlation_id}`;
        const existingMessage = messages.get(streamingMessageId);

        if (existingMessage) {
          // Append token to existing streaming message using updateMessage
          // This updates the messages Map without flooding the events array
          this.store.updateMessage(streamingMessageId, {
            streamingText: (existingMessage.streamingText || '') + data.content,
            timestamp: data.timestamp ? new Date(data.timestamp).getTime() : Date.now(),
          });
        } else if (data.sequence === 0 || !existingMessage) {
          // Look up agent's typical output type
          const agents = useGraphStore.getState().agents;
          const agent = agents.get(data.agent_name);
          const outputType = agent?.outputTypes?.[0] || 'output';

          // Create new streaming message on first token
          const streamingMessage = {
            id: streamingMessageId,
            type: outputType, // Use agent's known output type
            payload: {},
            timestamp: data.timestamp ? new Date(data.timestamp).getTime() : Date.now(),
            correlationId: data.correlation_id || '',
            producedBy: data.agent_name,
            isStreaming: true,
            streamingText: data.content,
          };
          this.store.addMessage(streamingMessage);
        }
      }

      // Note: The actual output storage is handled by LiveOutputTab's event listener
      // This handler is for store updates only
    });

    // Handler for agent_completed: update agent status to idle
    this.on('agent_completed', (data) => {
      this.store.updateAgent(data.agent_name, {
        status: 'idle',
        lastActive: Date.now(),
        streamingTokens: [], // Clear news ticker on completion
      });

      // Update Run status to completed for Blackboard View edges
      // Bug Fix: Use run_id from event data (agent_completed has run_id)
      if (data.run_id && this.store.batchUpdate) {
        const runs = useGraphStore.getState().runs;
        const run = runs.get(data.run_id);
        if (run) {
          const updatedRun = {
            ...run,
            status: 'completed' as const,
            completed_at: new Date().toISOString(),
            duration_ms: data.duration_ms,
          };
          this.store.batchUpdate({ runs: [updatedRun] });
        }
      }
    });

    // Handler for agent_error: update agent status to error
    this.on('agent_error', (data) => {
      this.store.updateAgent(data.agent_name, {
        status: 'error',
        lastActive: Date.now(),
      });

      // Update Run status to error
      // Bug Fix: Use run_id from event data (agent_error has run_id)
      if (data.run_id && this.store.batchUpdate) {
        const runs = useGraphStore.getState().runs;
        const run = runs.get(data.run_id);
        if (run) {
          const updatedRun = {
            ...run,
            status: 'error' as const,
            completed_at: new Date().toISOString(),
            error_message: data.error_message || 'Unknown error',
          };
          this.store.batchUpdate({ runs: [updatedRun] });
        }
      }
    });

    // Handler for ping: respond with pong
    this.on('ping', () => {
      this.send({ type: 'pong', timestamp: Date.now() });
    });
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    try {
      this.connectionStatus = 'connecting';
      if (typeof useWSStore !== 'undefined') {
        useWSStore.getState().setStatus('connecting');
      }

      this.ws = new WebSocket(this.url);

      // Set connection timeout
      this.connectionTimeout = window.setTimeout(() => {
        console.warn('[WebSocket] Connection timeout');
        if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
          this.ws.close();
          this.connectionStatus = 'error';
          if (typeof useWSStore !== 'undefined') {
            useWSStore.getState().setStatus('disconnected');
            useWSStore.getState().setError('Connection timeout');
          }
          if (this.shouldReconnect) {
            this.reconnect();
          }
        }
      }, this.connectionTimeoutMs);

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected');

        // Clear connection timeout
        if (this.connectionTimeout !== null) {
          clearTimeout(this.connectionTimeout);
          this.connectionTimeout = null;
        }

        this.connectionStatus = 'connected';
        if (typeof useWSStore !== 'undefined') {
          useWSStore.getState().setStatus('connected');
          useWSStore.getState().setError(null);
          useWSStore.getState().resetAttempts();
        }
        this.reconnectAttempt = 0;
        this.flushBuffer();
        if (this.enableHeartbeat) {
          this.startHeartbeat();
        }
      };

      this.ws.onmessage = (event: MessageEvent) => {
        this.handleMessage(event);
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        // Keep connection status as error even after close event
        this.connectionStatus = 'error';
        if (typeof useWSStore !== 'undefined') {
          useWSStore.getState().setError('Connection error');
          useWSStore.getState().setStatus('disconnected');
        }
      };

      this.ws.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason);
        this.stopHeartbeat();

        // Don't override error status
        if (this.connectionStatus !== 'error') {
          if (this.shouldReconnect && event.code !== 1000) {
            this.connectionStatus = 'connecting'; // Will be reconnecting
            if (typeof useWSStore !== 'undefined') {
              useWSStore.getState().setStatus('reconnecting');
            }
            this.reconnect();
          } else {
            this.connectionStatus = 'disconnected';
            if (typeof useWSStore !== 'undefined') {
              useWSStore.getState().setStatus('disconnected');
            }
          }
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      this.connectionStatus = 'error';
      if (typeof useWSStore !== 'undefined') {
        useWSStore.getState().setStatus('disconnected');
        useWSStore.getState().setError(error instanceof Error ? error.message : 'Connection failed');
      }
      if (this.shouldReconnect) {
        this.reconnect();
      }
    }
  }

  private reconnect(): void {
    if (this.reconnectTimeout !== null) {
      return; // Already scheduled
    }

    // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempt), this.maxReconnectDelay);

    if (typeof useWSStore !== 'undefined') {
      useWSStore.getState().incrementAttempts();
    }
    this.reconnectAttempt++;

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempt})`);

    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectTimeout = null;
      this.connect();
    }, delay);
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data);

      // Handle direct type field (for ping/pong)
      if (data.type === 'ping') {
        this.send({ type: 'pong', timestamp: Date.now() });
        return;
      }

      if (data.type === 'pong') {
        this.resetHeartbeatTimeout();
        return;
      }

      // Handle WebSocketMessage envelope
      const message: WebSocketMessage = data;

      // Handle pong as event_type
      if (message.event_type === 'pong' as any) {
        this.resetHeartbeatTimeout();
        return;
      }

      // Determine if this is an envelope or raw data
      // If it has event_type, it's an envelope; use message.data
      // Otherwise, it's raw data (for tests)
      const eventData = message.event_type ? message.data : data;

      // Try to detect event type from data
      let eventType = message.event_type;
      if (!eventType) {
        // Infer event type from data structure for test compatibility
        if (data.agent_id && data.consumed_types) {
          eventType = 'agent_activated';
        } else if (data.artifact_id && data.artifact_type) {
          eventType = 'message_published';
        } else if (data.run_id && data.output_type) {
          eventType = 'streaming_output';
        } else if (data.run_id && data.duration_ms !== undefined) {
          eventType = 'agent_completed';
        } else if (data.run_id && data.error_type) {
          eventType = 'agent_error';
        }
      }

      // Dispatch to registered handlers
      if (eventType) {
        const handlers = this.eventHandlers.get(eventType);
        if (handlers) {
          handlers.forEach((handler) => {
            try {
              handler(eventData);
            } catch (error) {
              console.error(`[WebSocket] Handler error for ${eventType}:`, error);
            }
          });
        }
      }
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error);
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('[WebSocket] Send failed:', error);
        this.bufferMessage(message);
      }
    } else {
      this.bufferMessage(message);
    }
  }

  private bufferMessage(message: any): void {
    if (this.messageBuffer.length >= this.maxBufferSize) {
      this.messageBuffer.shift(); // Remove oldest message
    }
    this.messageBuffer.push(message);
  }

  private flushBuffer(): void {
    if (this.messageBuffer.length === 0) {
      return;
    }

    console.log(`[WebSocket] Flushing ${this.messageBuffer.length} buffered messages`);

    const messages = [...this.messageBuffer];
    this.messageBuffer = [];

    messages.forEach((message) => {
      // Send directly to avoid re-buffering
      if (this.ws?.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify(message));
        } catch (error) {
          console.error('[WebSocket] Failed to send buffered message:', error);
        }
      }
    });
  }

  on(eventType: string, handler: (data: any) => void): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);
  }

  off(eventType: string, handler: (data: any) => void): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();

    // Send ping every 2 minutes
    this.heartbeatInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' });

        // Set timeout for pong response (10 seconds)
        this.heartbeatTimeout = window.setTimeout(() => {
          console.warn('[WebSocket] Heartbeat timeout, closing connection');
          this.ws?.close();
        }, 10000);
      }
    }, 120000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.heartbeatTimeout !== null) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  private resetHeartbeatTimeout(): void {
    if (this.heartbeatTimeout !== null) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.connectionStatus = 'disconnecting';

    if (this.reconnectTimeout !== null) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.connectionTimeout !== null) {
      clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
    }

    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    // Status will be set to 'disconnected' by onclose handler
    // Don't override it here to maintain proper status flow
  }

  reconnectManually(): void {
    this.shouldReconnect = true;
    this.reconnectAttempt = 0;
    if (typeof useWSStore !== 'undefined') {
      useWSStore.getState().resetAttempts();
    }
    this.connect();
  }

  // Test helper methods
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN && this.connectionStatus !== 'error';
  }

  getConnectionStatus(): string {
    return this.connectionStatus;
  }

  getBufferedMessageCount(): number {
    return this.messageBuffer.length;
  }

  getStatus(): string {
    if (!this.ws) return 'disconnected';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
        return 'disconnecting';
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'disconnected';
    }
  }
}

// Singleton instance
let wsClient: WebSocketClient | null = null;

export const getWebSocketClient = (url?: string): WebSocketClient => {
  if (!wsClient && url) {
    wsClient = new WebSocketClient(url);
  }
  if (!wsClient) {
    throw new Error('WebSocket client not initialized');
  }
  return wsClient;
};

export const initializeWebSocket = (url: string): WebSocketClient => {
  if (wsClient) {
    wsClient.disconnect();
  }
  wsClient = new WebSocketClient(url);
  return wsClient;
};
