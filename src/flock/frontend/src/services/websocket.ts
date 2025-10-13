import { useWSStore } from '../store/wsStore';
import { useGraphStore } from '../store/graphStore';
import { useFilterStore } from '../store/filterStore';

interface WebSocketMessage {
  event_type: 'agent_activated' | 'message_published' | 'streaming_output' | 'agent_completed' | 'agent_error' | 'correlation_group_updated' | 'batch_item_added';
  timestamp: string;
  correlation_id: string;
  session_id: string;
  data: any;
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
  private enableHeartbeat: boolean;

  // UI Optimization Migration (Phase 2 - Spec 002): Debounced graph refresh
  private refreshTimer: number | null = null;
  private refreshDebounceMs = 500; // 500ms batching window

  constructor(url: string) {
    this.url = url;
    // Phase 11 Fix: Disable heartbeat entirely - it causes unnecessary disconnects
    // WebSocket auto-reconnects on real network issues without needing heartbeat
    // The heartbeat was closing connections every 2min when backend didn't respond to pings
    this.enableHeartbeat = false;
    this.setupEventHandlers();
  }

  /**
   * UI Optimization Migration (Phase 2 - Spec 002): Debounced graph refresh
   *
   * Batch multiple graph-changing events within 500ms window, then fetch fresh
   * snapshot from backend. This replaces immediate regenerateGraph() calls.
   */
  private scheduleGraphRefresh(): void {
    if (this.refreshTimer !== null) {
      clearTimeout(this.refreshTimer);
    }

    this.refreshTimer = window.setTimeout(() => {
      this.refreshTimer = null;
      // Call the NEW async refreshCurrentView() method
      useGraphStore.getState().refreshCurrentView().catch((error) => {
        console.error('[WebSocket] Graph refresh failed:', error);
      });
    }, this.refreshDebounceMs);
  }

  private updateFilterStateFromPublishedMessage(data: any): void {
    const filterStore = useFilterStore.getState();

    const artifactType = typeof data.artifact_type === 'string' ? data.artifact_type : '';
    const producer = typeof data.produced_by === 'string' ? data.produced_by : '';
    const tags = Array.isArray(data.tags) ? data.tags.filter((tag: unknown) => typeof tag === 'string' && tag.length > 0) : [];
    const visibilityKind =
      (typeof data.visibility === 'object' && data.visibility && typeof data.visibility.kind === 'string'
        ? data.visibility.kind
        : undefined) ||
      (typeof data.visibility_kind === 'string' ? data.visibility_kind : undefined) ||
      (typeof data.visibility === 'string' ? data.visibility : undefined) ||
      '';

    const nextArtifactTypes = artifactType
      ? [...filterStore.availableArtifactTypes, artifactType]
      : [...filterStore.availableArtifactTypes];
    const nextProducers = producer
      ? [...filterStore.availableProducers, producer]
      : [...filterStore.availableProducers];
    const nextTags = tags.length > 0 ? [...filterStore.availableTags, ...tags] : [...filterStore.availableTags];
    const nextVisibility = visibilityKind
      ? [...filterStore.availableVisibility, visibilityKind]
      : [...filterStore.availableVisibility];

    filterStore.updateAvailableFacets({
      artifactTypes: nextArtifactTypes,
      producers: nextProducers,
      tags: nextTags,
      visibilities: nextVisibility,
    });

    const baseSummary =
      filterStore.summary ?? {
        total: 0,
        by_type: {} as Record<string, number>,
        by_producer: {} as Record<string, number>,
        by_visibility: {} as Record<string, number>,
        tag_counts: {} as Record<string, number>,
        earliest_created_at: null as string | null,
        latest_created_at: null as string | null,
      };

    const timestampIso =
      (typeof data.timestamp === 'string' ? data.timestamp : undefined) ?? new Date().toISOString();

    const updatedSummary = {
      total: baseSummary.total + 1,
      by_type: { ...baseSummary.by_type },
      by_producer: { ...baseSummary.by_producer },
      by_visibility: { ...baseSummary.by_visibility },
      tag_counts: { ...baseSummary.tag_counts },
      earliest_created_at:
        baseSummary.earliest_created_at === null || timestampIso < baseSummary.earliest_created_at
          ? timestampIso
          : baseSummary.earliest_created_at,
      latest_created_at:
        baseSummary.latest_created_at === null || timestampIso > baseSummary.latest_created_at
          ? timestampIso
          : baseSummary.latest_created_at,
    };

    if (artifactType) {
      updatedSummary.by_type[artifactType] = (updatedSummary.by_type[artifactType] || 0) + 1;
    }
    if (producer) {
      updatedSummary.by_producer[producer] = (updatedSummary.by_producer[producer] || 0) + 1;
    }
    if (visibilityKind) {
      updatedSummary.by_visibility[visibilityKind] = (updatedSummary.by_visibility[visibilityKind] || 0) + 1;
    }
    tags.forEach((tag: string) => {
      updatedSummary.tag_counts[tag] = (updatedSummary.tag_counts[tag] || 0) + 1;
    });

    filterStore.setSummary(updatedSummary);

    if (typeof data.correlation_id === 'string' && data.correlation_id.length > 0) {
      const timestampMs =
        typeof data.timestamp === 'string' ? new Date(data.timestamp).getTime() : Date.now();
      const existing = filterStore.availableCorrelationIds.find(
        (item) => item.correlation_id === data.correlation_id
      );
      const updatedRecord = existing
        ? {
            ...existing,
            artifact_count: existing.artifact_count + 1,
            first_seen: Math.min(existing.first_seen, timestampMs),
          }
        : {
            correlation_id: data.correlation_id,
            first_seen: timestampMs,
            artifact_count: 1,
            run_count: 0,
          };
      const nextMetadata = [
        ...filterStore.availableCorrelationIds.filter((item) => item.correlation_id !== data.correlation_id),
        updatedRecord,
      ];
      filterStore.updateAvailableCorrelationIds(nextMetadata);
    }
  }

  private setupEventHandlers(): void {
    // Handler for agent_activated: create/update agent in graph AND create Run
    this.on('agent_activated', (data) => {
      // UI Optimization Migration (Phase 2 - Spec 002): DEPRECATED client-side agent tracking
      // Backend now handles all agent data. Frontend only tracks real-time status overlay.
      // OLD CODE REMOVED: agents Map, receivedByType tracking, addAgent(), recordConsumption()
      // NEW BEHAVIOR: Backend refresh will include updated agent data

      // Update real-time status (fast, local)
      useGraphStore.getState().updateAgentStatus(data.agent_name, 'running');

      // Schedule debounced refresh (batches within 500ms, then fetches backend snapshot)
      this.scheduleGraphRefresh();
    });

    // Handler for message_published: update existing streaming message or create new one
    this.on('message_published', (data) => {
      // UI Optimization Migration (Phase 2 - Spec 002): DEPRECATED client-side message tracking
      // Backend now handles all message/artifact data. Frontend only tracks events for display.
      // OLD CODE REMOVED: messages Map, addMessage(), updateMessage(), finalizeStreamingMessage(),
      //                   agent counter updates, run tracking
      // NEW BEHAVIOR: Backend refresh will include all updated data

      // Phase 6: Finalize streaming message node if it exists
      if (data.artifact_id) {
        useGraphStore.getState().finalizeStreamingMessageNode(data.artifact_id);
      }

      // Update filter state (still needed for filter UI)
      this.updateFilterStateFromPublishedMessage(data);

      // Add to events array for Event Log display
      const message = {
        id: data.artifact_id,
        type: data.artifact_type,
        payload: data.payload,
        timestamp: data.timestamp ? new Date(data.timestamp).getTime() : Date.now(),
        correlationId: data.correlation_id || '',
        producedBy: data.produced_by,
        tags: Array.isArray(data.tags) ? data.tags : [],
        visibilityKind: data.visibility?.kind || data.visibility_kind || 'Unknown',
        partitionKey: data.partition_key ?? null,
        version: data.version ?? 1,
        isStreaming: false,
      };
      useGraphStore.getState().addEvent(message);

      // Schedule debounced refresh (batches multiple events within 500ms)
      // This will replace the streaming node with the full backend snapshot
      this.scheduleGraphRefresh();
    });

    // Handler for streaming_output: update live output (Phase 6)
    this.on('streaming_output', (data) => {
      // Phase 6: Only log start (sequence=0) and finish (is_final=true) to reduce noise
      if (data.sequence === 0 || data.is_final) {
        console.log('[WebSocket] Streaming output:', data.is_final ? 'FINAL' : 'START', data);
      }

      // Phase 6: Agent streaming tokens (for yellow ticker in agent nodes)
      // Note: artifact_id is now always present (Phase 6), so we removed the !artifact_id check
      if (data.agent_name && data.output_type === 'llm_token') {
        const { streamingTokens } = useGraphStore.getState();
        const currentTokens = streamingTokens.get(data.agent_name) || [];

        // Keep only last 6 tokens (news ticker effect)
        const updatedTokens = [...currentTokens, data.content].slice(-6);

        useGraphStore.getState().updateStreamingTokens(data.agent_name, updatedTokens);
      }

      // Phase 6: Message streaming preview (for streaming textbox in message nodes)
      if (data.artifact_id && data.output_type === 'llm_token') {
        // Create or update streaming message node
        useGraphStore.getState().createOrUpdateStreamingMessageNode(
          data.artifact_id,
          data.content,
          {
            agent_name: data.agent_name,
            correlation_id: data.correlation_id,
            artifact_type: data.artifact_type,  // Phase 6: Artifact type name for node header
          }
        );

        // Finalize when streaming is complete (is_final=true)
        if (data.is_final) {
          useGraphStore.getState().finalizeStreamingMessageNode(data.artifact_id);
        }
      }

      // Note: The actual output storage is handled by LiveOutputTab's event listener
      // This handler is for real-time token updates only
    });

    // Handler for agent_completed: update agent status to idle
    this.on('agent_completed', (data) => {
      // UI Optimization Migration (Phase 2 - Spec 002): Use NEW updateAgentStatus()
      // for FAST real-time updates without backend calls
      useGraphStore.getState().updateAgentStatus(data.agent_name, 'idle');
      useGraphStore.getState().updateStreamingTokens(data.agent_name, []); // Clear news ticker

      // OLD CODE REMOVED: Run status tracking (runs Map, batchUpdate)
      // Backend handles run data now
    });

    // Handler for agent_error: update agent status to error
    this.on('agent_error', (data) => {
      // UI Optimization Migration (Phase 2 - Spec 002): Use NEW updateAgentStatus()
      // for FAST real-time updates without backend calls
      useGraphStore.getState().updateAgentStatus(data.agent_name, 'error');

      // OLD CODE REMOVED: Run status tracking (runs Map, batchUpdate)
      // Backend handles run data now
    });

    // Handler for ping: respond with pong
    this.on('ping', () => {
      this.send({ type: 'pong', timestamp: Date.now() });
    });

    // Phase 1.3: Handler for correlation_group_updated - update logic operations state
    this.on('correlation_group_updated', (data) => {
      const { agent_name, subscription_index, correlation_key, elapsed_seconds, expires_in_seconds, waiting_for } = data;

      console.log('[WebSocket] Correlation group updated:', {
        agent: agent_name,
        key: correlation_key,
        waiting_for,
        elapsed: elapsed_seconds,
        expires_in: expires_in_seconds,
      });

      // Get current logic operations for this agent
      const graphStore = useGraphStore.getState();
      const currentLogicOps = graphStore.agentLogicOperations.get(agent_name) || [];

      // Find the subscription's logic operations
      const updatedLogicOps = currentLogicOps.map((logicOp) => {
        if (logicOp.subscription_index === subscription_index && logicOp.join) {
          // Update waiting_state with correlation group data
          const correlationGroup = {
            correlation_key: data.correlation_key,
            created_at: data.timestamp,
            elapsed_seconds: data.elapsed_seconds,
            expires_in_seconds: data.expires_in_seconds,
            expires_in_artifacts: data.expires_in_artifacts,
            collected_types: data.collected_types,
            required_types: data.required_types,
            waiting_for: data.waiting_for,
            is_complete: data.is_complete,
            is_expired: false,
          };

          return {
            ...logicOp,
            waiting_state: {
              is_waiting: true,
              correlation_groups: [correlationGroup],
            },
          };
        }
        return logicOp;
      });

      // Update graph store with new logic operations state
      if (updatedLogicOps.length > 0) {
        graphStore.updateAgentLogicOperations(agent_name, updatedLogicOps);
      }
    });

    // Phase 1.3: Handler for batch_item_added - update logic operations state
    this.on('batch_item_added', (data) => {
      const { agent_name, subscription_index, items_collected, items_target, timeout_remaining_seconds, will_flush } = data;

      console.log('[WebSocket] Batch item added:', {
        agent: agent_name,
        collected: items_collected,
        target: items_target,
        timeout_remaining: timeout_remaining_seconds,
        will_flush,
      });

      // Get current logic operations for this agent
      const graphStore = useGraphStore.getState();
      const currentLogicOps = graphStore.agentLogicOperations.get(agent_name) || [];

      // Find the subscription's logic operations
      const updatedLogicOps = currentLogicOps.map((logicOp) => {
        if (logicOp.subscription_index === subscription_index && logicOp.batch) {
          // Update waiting_state with batch data
          const batchState = {
            created_at: data.timestamp,
            elapsed_seconds: data.elapsed_seconds,
            items_collected: data.items_collected,
            items_target: data.items_target,
            items_remaining: data.items_remaining,
            timeout_seconds: data.timeout_seconds,
            timeout_remaining_seconds: data.timeout_remaining_seconds,
            will_flush: data.will_flush,
          };

          return {
            ...logicOp,
            waiting_state: {
              is_waiting: true,
              batch_state: batchState,
            },
          };
        }
        return logicOp;
      });

      // Update graph store with new logic operations state
      if (updatedLogicOps.length > 0) {
        graphStore.updateAgentLogicOperations(agent_name, updatedLogicOps);
      }
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
        // IMPORTANT: Check streaming_output BEFORE message_published since streaming events
        // now have artifact_id + artifact_type (Phase 6) but also have run_id + output_type
        if (data.agent_id && data.consumed_types) {
          eventType = 'agent_activated';
        } else if (data.run_id && data.output_type) {
          eventType = 'streaming_output';
        } else if (data.artifact_id && data.artifact_type) {
          eventType = 'message_published';
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
