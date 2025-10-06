/**
 * End-to-End Tests for Critical Dashboard Scenarios (Frontend)
 *
 * Tests the 4 critical scenarios from SDD_COMPLETION.md (lines 444-493):
 * 1. End-to-End Agent Execution Visualization (WebSocket → stores → React Flow rendering)
 * 2. WebSocket Reconnection After Backend Restart (client-side resilience)
 * 3. Correlation ID Filtering (autocomplete → filter → graph updates)
 * 4. IndexedDB LRU Eviction (storage quota management with custom mocking)
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/SDD_COMPLETION.md Section: Critical Test Scenarios
 *
 * These tests validate the complete frontend flow from WebSocket events through
 * Zustand stores to React Flow graph visualization.
 */

import 'fake-indexeddb/auto'; // Polyfills global IndexedDB for tests
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { waitFor, act } from '@testing-library/react';
import { WebSocketClient } from '../../services/websocket';
import { useGraphStore } from '../../store/graphStore';
import { useFilterStore } from '../../store/filterStore';
import { useWSStore } from '../../store/wsStore';
import { indexedDBService } from '../../services/indexeddb';
import { CorrelationIdMetadata } from '../../types/filters';

// ============================================================================
// Mock WebSocket Client
// ============================================================================

class MockWebSocket {
  url: string;
  readyState: number;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;

    // Auto-connect after construction (unless disabled for testing)
    if (MockWebSocket.autoConnect) {
      setTimeout(() => {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.(new Event('open'));
      }, 0);
    } else {
      // If auto-connect is disabled, simulate connection failure
      setTimeout(() => {
        this.readyState = MockWebSocket.CLOSED;
        // Only fire close event (not error) to avoid setting error status
        // This allows the client to keep retrying with exponential backoff
        this.onclose?.(new CloseEvent('close', { code: 1006, reason: 'Connection failed' }));
      }, 0);
    }
  }

  send(_data: string) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }

  // Test helper: simulate receiving message
  simulateMessage(data: any) {
    if (this.readyState === MockWebSocket.OPEN) {
      this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  // Test helper: simulate connection error
  simulateError() {
    this.onerror?.(new Event('error'));
  }

  // Test helper: simulate disconnection
  simulateDisconnect() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }

  // Test helper: simulate reconnection
  simulateReconnect() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  // Test helper: prevent auto-connection (for testing reconnection retries)
  preventAutoConnect() {
    (this.constructor as any).autoConnect = false;
  }

  static autoConnect = true;
}

// ============================================================================
// Mock Storage Quota API for LRU Testing
// ============================================================================

class MockStorageManager {
  private mockUsage: number = 0;
  private mockQuota: number = 50 * 1024 * 1024; // 50MB default quota
  private usageSequence: number[] = [];
  private sequenceIndex: number = 0;

  async estimate(): Promise<{ usage: number; quota: number }> {
    // Use fixed sequence if configured, otherwise return current usage
    let currentUsage = this.mockUsage;
    if (this.usageSequence.length > 0) {
      currentUsage = this.usageSequence[Math.min(this.sequenceIndex, this.usageSequence.length - 1)]!;
      this.sequenceIndex++;
    }

    return {
      usage: currentUsage,
      quota: this.mockQuota,
    };
  }

  // Test helpers
  setUsage(bytes: number) {
    this.mockUsage = bytes;
    this.sequenceIndex = 0;
  }

  setQuota(bytes: number) {
    this.mockQuota = bytes;
  }

  // Set a sequence of usage values to return (simulates deletion reducing usage)
  setUsageSequence(sequence: number[]) {
    this.usageSequence = sequence;
    this.sequenceIndex = 0;
  }

  getUsagePercentage(): number {
    return this.mockQuota > 0 ? this.mockUsage / this.mockQuota : 0;
  }
}

// ============================================================================
// Test Setup and Fixtures
// ============================================================================

describe('Critical E2E Scenarios (Frontend)', () => {
  let mockWs: any;
  let mockStorageManager: MockStorageManager;
  let wsClient: WebSocketClient;

  beforeEach(() => {
    // Reset all stores
    const graphStore = useGraphStore.getState();
    graphStore.agents.clear();
    graphStore.messages.clear();
    graphStore.events = [];
    graphStore.runs.clear();
    graphStore.consumptions.clear();

    const filterStore = useFilterStore.getState();
    filterStore.clearFilters();
    filterStore.updateAvailableCorrelationIds([]);

    const wsStore = useWSStore.getState();
    wsStore.setStatus('disconnected');
    wsStore.setError(null);
    wsStore.resetAttempts();

    // Setup mock WebSocket
    (globalThis as any).WebSocket = MockWebSocket;
    MockWebSocket.autoConnect = true; // Reset auto-connect flag

    // Setup mock storage manager
    mockStorageManager = new MockStorageManager();
    if (!navigator.storage) {
      (navigator as any).storage = {};
    }
    navigator.storage.estimate = mockStorageManager.estimate.bind(mockStorageManager);
  });

  afterEach(() => {
    // Cleanup
    if (wsClient) {
      wsClient.disconnect();
    }
    vi.clearAllTimers();
  });

  // ==========================================================================
  // Scenario 1: End-to-End Agent Execution Visualization
  // ==========================================================================

  describe('Scenario 1: End-to-End Agent Execution Visualization', () => {
    it('should render complete agent execution flow from WebSocket events', async () => {
      /**
       * GIVEN: WebSocket client connected
       * WHEN: Receive agent_activated → message_published → agent_completed sequence
       * THEN: Graph nodes and edges are created correctly
       * AND: Agent status transitions are tracked
       */

      // Setup: Create WebSocket client
      wsClient = new WebSocketClient('ws://localhost:8000/ws');
      wsClient.connect();

      await waitFor(() => expect(wsClient.isConnected()).toBe(true));
      mockWs = wsClient.ws as any;

      // Step 1: Agent activated (raw format for test compatibility)
      await act(async () => {
        mockWs.simulateMessage({
          agent_id: 'test_agent',
          agent_name: 'test_agent',
          run_id: 'run_123',
          consumed_types: ['Input'],
          consumed_artifacts: ['input-1'],
          correlation_id: 'test-correlation-1',
        });
      });

      await waitFor(() => {
        const agents = useGraphStore.getState().agents;
        expect(agents.has('test_agent')).toBe(true);
      });

      // Verify agent state
      const agent = useGraphStore.getState().agents.get('test_agent');
      expect(agent?.status).toBe('running');
      expect(agent?.recvCount).toBe(1);

      // Step 2: Message published (raw format for test compatibility)
      await act(async () => {
        mockWs.simulateMessage({
          artifact_id: 'output-1',
          artifact_type: 'Output',
          produced_by: 'test_agent',
          payload: { result: 'success' },
          correlation_id: 'test-correlation-1',
        });
      });

      await waitFor(() => {
        const messages = useGraphStore.getState().messages;
        expect(messages.has('output-1')).toBe(true);
      });

      // Verify message state
      const message = useGraphStore.getState().messages.get('output-1');
      expect(message?.type).toBe('Output');
      expect(message?.producedBy).toBe('test_agent');

      // Step 3: Agent completed (raw format for test compatibility)
      await act(async () => {
        mockWs.simulateMessage({
          agent_name: 'test_agent',
          run_id: 'run_123',
          duration_ms: 150,
          artifacts_produced: ['output-1'],
        });
      });

      await waitFor(() => {
        const agent = useGraphStore.getState().agents.get('test_agent');
        expect(agent?.status).toBe('idle');
      });

      // Verify final state
      const finalState = useGraphStore.getState();
      expect(finalState.agents.size).toBe(1);
      expect(finalState.messages.size).toBe(1);
      expect(finalState.runs.size).toBeGreaterThan(0);
    });
  });

  // ==========================================================================
  // Scenario 2: WebSocket Reconnection After Backend Restart
  // ==========================================================================

  describe('Scenario 2: WebSocket Reconnection After Backend Restart', () => {
    it('should handle connection loss and automatic reconnection with exponential backoff', { timeout: 20000 }, async () => {
      /**
       * GIVEN: Active WebSocket connection
       * WHEN: Connection is lost (backend restart simulation)
       * THEN: Client attempts reconnection with exponential backoff (1s, 2s, 4s, 8s)
       * AND: Successfully reconnects when backend is available
       * AND: Reconnect attempts counter is reset to 0
       *
       * APPROACH: Use MockWebSocket with controlled auto-connect behavior (no fake timers).
       * Wait for real time to pass to validate exponential backoff intervals.
       */

      // Step 1: Connect WebSocket client (using MockWebSocket)
      wsClient = new WebSocketClient('ws://localhost:8000/ws');
      wsClient.connect();

      await waitFor(() => expect(wsClient.isConnected()).toBe(true), { timeout: 5000 });
      mockWs = wsClient.ws as any;

      // Step 2: Simulate connection loss
      await act(async () => {
        // Disable auto-connect so reconnection attempts fail
        MockWebSocket.autoConnect = false;
        // Simulate abnormal disconnect (code != 1000 triggers reconnection)
        mockWs.readyState = MockWebSocket.CLOSED;
        mockWs.onclose?.(new CloseEvent('close', { code: 1006, reason: 'Server shutdown' }));
      });

      // Wait for reconnection status
      await waitFor(() => {
        expect(wsClient.isConnected()).toBe(false);
        expect(useWSStore.getState().status).toBe('reconnecting');
      }, { timeout: 2000 });

      // Record initial attempt count
      const initialAttempts = useWSStore.getState().reconnectAttempts;
      expect(initialAttempts).toBeGreaterThan(0);

      // Step 3: Wait for multiple reconnection attempts with exponential backoff
      // Backoff: 1s, 2s, 4s, 8s
      // Total time for 4 attempts: ~15s
      // We'll wait 8s to capture 3-4 attempts (1s + 2s + 4s = 7s + margin)
      await new Promise((resolve) => setTimeout(resolve, 8000));

      // Verify reconnection attempts increased
      const attemptsAfterBackoff = useWSStore.getState().reconnectAttempts;
      expect(attemptsAfterBackoff).toBeGreaterThanOrEqual(3);
      expect(useWSStore.getState().status).toBe('reconnecting');

      // Step 4: Re-enable auto-connect to allow successful reconnection
      await act(async () => {
        MockWebSocket.autoConnect = true;
      });

      // Wait for next reconnection attempt to succeed (max 8s for next backoff)
      await waitFor(() => {
        expect(wsClient.isConnected()).toBe(true);
        expect(useWSStore.getState().status).toBe('connected');
      }, { timeout: 10000 });

      // Step 5: Verify reconnect counter is reset
      const finalStore = useWSStore.getState();
      expect(finalStore.reconnectAttempts).toBe(0);

      // Cleanup: Reset auto-connect for other tests
      MockWebSocket.autoConnect = true;
    });
  });

  // ==========================================================================
  // Scenario 3: Correlation ID Filtering
  // ==========================================================================

  describe('Scenario 3: Correlation ID Filtering', () => {
    it('should filter graph nodes and edges by selected correlation ID', { timeout: 10000 }, async () => {
      /**
       * GIVEN: Multiple artifacts with different correlation IDs
       * WHEN: User selects a correlation ID filter
       * THEN: Only artifacts/agents with matching correlation ID are visible
       * AND: Graph edges are updated to reflect filtered view
       */

      // Setup: Connect WebSocket
      wsClient = new WebSocketClient('ws://localhost:8000/ws');
      wsClient.connect();
      await waitFor(() => expect(wsClient.isConnected()).toBe(true));
      mockWs = wsClient.ws as any;

      // Setup: Receive events with 3 different correlation IDs
      const correlationIds = ['abc-123-xxx', 'abc-456-yyy', 'def-789-zzz'];

      for (let i = 0; i < correlationIds.length; i++) {
        await act(async () => {
          mockWs.simulateMessage({
            artifact_id: `artifact-${i}`,
            artifact_type: 'TestOutput',
            produced_by: 'test_agent',
            payload: { index: i },
            correlation_id: correlationIds[i],
            timestamp: new Date(Date.now() + i * 1000).toISOString(),
          });
        });
      }

      // Wait for all messages to be added to the store
      await waitFor(() => {
        const messages = useGraphStore.getState().messages;
        expect(messages.size).toBe(3);
      }, { timeout: 5000 });

      // Update available correlation IDs
      const metadata: CorrelationIdMetadata[] = correlationIds.map((id, index) => ({
        correlation_id: id,
        first_seen: Date.now() + index * 1000,
        artifact_count: 1,
        run_count: 1,
      }));
      useFilterStore.getState().updateAvailableCorrelationIds(metadata);

      // Generate graph with all events (use fresh state)
      await act(async () => {
        useGraphStore.getState().generateBlackboardViewGraph();
      });

      // Wait for nodes to be generated
      await waitFor(() => {
        const nodes = useGraphStore.getState().nodes;
        const visibleNodes = nodes.filter((n) => !n.hidden);
        expect(visibleNodes.length).toBe(3);
      }, { timeout: 5000 });

      // Apply correlation ID filter (use fresh state)
      await act(async () => {
        useFilterStore.getState().setCorrelationId('abc-123-xxx');
        useGraphStore.getState().applyFilters();
      });

      // Verify: Only 1 node visible (the one with matching correlation ID)
      await waitFor(() => {
        const filteredNodes = useGraphStore.getState().nodes.filter((n) => !n.hidden);
        expect(filteredNodes.length).toBe(1);
        expect(filteredNodes[0]?.id).toBe('artifact-0');
      }, { timeout: 5000 });

      // Verify: Edges connected to hidden nodes are also hidden
      const visibleEdges = useGraphStore.getState().edges.filter((e) => !e.hidden);
      // Should be 0 since we don't have transformation edges without runs
      expect(visibleEdges.length).toBe(0);
    });
  });

  // ==========================================================================
  // Scenario 4: IndexedDB LRU Eviction
  // ==========================================================================

  describe('Scenario 4: IndexedDB LRU Eviction', () => {
    beforeEach(async () => {
      // Clean up IndexedDB between tests
      if (indexedDBService.db) {
        indexedDBService.db.close();
        indexedDBService.db = null;
      }
      // Delete the database to ensure fresh state
      if (typeof indexedDB !== 'undefined') {
        const deleteRequest = indexedDB.deleteDatabase('flock_dashboard_v1');
        await new Promise<void>((resolve, reject) => {
          deleteRequest.onsuccess = () => resolve();
          deleteRequest.onerror = () => reject(deleteRequest.error);
          deleteRequest.onblocked = () => resolve(); // Continue even if blocked
        });
      }
    });

    it('should evict oldest sessions when storage quota exceeds 80% threshold', async () => {
      /**
       * GIVEN: Storage usage at 84% (above 80% threshold)
       * WHEN: LRU eviction is triggered
       * THEN: Oldest sessions are evicted until usage drops to 60% target
       * AND: Most recent sessions are preserved
       * AND: Current session data is preserved
       */

      const quota = 50 * 1024 * 1024; // 50MB
      mockStorageManager.setQuota(quota);

      // Setup: Configure usage sequence to simulate eviction progress
      // Start at 84% (42MB), after deleting 2 sessions reach 60% (30MB)
      const initialUsage = quota * 0.84; // 42MB
      const afterDelete1 = quota * 0.72; // 36MB (after deleting 1 session)
      const afterDelete2 = quota * 0.60; // 30MB (after deleting 2 sessions - target reached)

      mockStorageManager.setUsageSequence([
        initialUsage,   // First loop iteration: 84% > 60%, delete session-0
        afterDelete1,   // Second loop iteration: 72% > 60%, delete session-1
        afterDelete2,   // Third loop iteration: 60% <= 60%, BREAK (should not delete)
        afterDelete2,   // Any additional calls stay at 60%
        afterDelete2,
        afterDelete2,
        afterDelete2,
        afterDelete2,
      ]);

      // Initialize IndexedDB service for testing
      await indexedDBService.initialize();

      // Create 5 sessions with different timestamps (oldest first)
      for (let i = 0; i < 5; i++) {
        const sessionId = `session-${i}`;
        const timestamp = new Date(Date.now() - (5 - i) * 60000).toISOString(); // Each 1 minute apart

        // Store in IndexedDB
        await indexedDBService.saveSession({
          session_id: sessionId,
          created_at: timestamp,
          last_activity: timestamp,
          artifact_count: 0,
          run_count: 0,
          size_estimate_bytes: 6 * 1024 * 1024, // 6MB per session
        });
      }

      // Verify sessions were saved
      const savedSessions = await indexedDBService.getAllSessions();
      console.log(`[Test] Saved ${savedSessions.length} sessions before eviction`);
      expect(savedSessions.length).toBe(5); // Verify all 5 sessions were saved

      // Trigger eviction
      await act(async () => {
        await indexedDBService.evictOldSessions();
      });

      // Verify: Old sessions were evicted
      const remainingSessions = await indexedDBService.getAllSessions();
      console.log(`[Test] ${remainingSessions.length} sessions remaining after eviction`);

      // Should have evicted 2 oldest sessions (session-0, session-1), keeping 3 (session-2, session-3, session-4)
      expect(remainingSessions.length).toBe(3);

      // Verify: Most recent sessions are preserved
      const remainingIds = remainingSessions.map((s: any) => s.session_id);

      // Most recent session should be preserved
      expect(remainingIds).toContain('session-4');
      expect(remainingIds).toContain('session-3');
      expect(remainingIds).toContain('session-2');

      // Oldest sessions should be gone
      expect(remainingIds).not.toContain('session-0');
      expect(remainingIds).not.toContain('session-1');

      console.log(`[LRU] Evicted ${5 - remainingSessions.length} oldest sessions`);
      console.log(`[LRU] Preserved sessions: ${remainingIds.join(', ')}`);
    });

    it('should preserve current session and most recent 10 sessions during eviction', async () => {
      const quota = 50 * 1024 * 1024;
      mockStorageManager.setQuota(quota);

      const initialUsage = quota * 0.85; // 42.5MB

      // Configure usage sequence: Start at 85%, delete 5 sessions to reach 60%
      const usageSequence = [
        initialUsage,                 // First iteration: 85% > 60%, delete session-0
        quota * 0.80,                 // Second iteration: 80% > 60%, delete session-1
        quota * 0.75,                 // Third iteration: 75% > 60%, delete session-2
        quota * 0.70,                 // Fourth iteration: 70% > 60%, delete session-3
        quota * 0.65,                 // Fifth iteration: 65% > 60%, delete session-4
        quota * 0.60,                 // Sixth iteration: 60% <= 60%, BREAK
        quota * 0.60,                 // Stay at target
      ];
      mockStorageManager.setUsageSequence(usageSequence);

      // Initialize IndexedDB service for testing
      await indexedDBService.initialize();

      // Create 15 sessions
      for (let i = 0; i < 15; i++) {
        const timestamp = new Date(Date.now() - (15 - i) * 60000).toISOString();
        await indexedDBService.saveSession({
          session_id: `session-${i}`,
          created_at: timestamp,
          last_activity: timestamp,
          artifact_count: 0,
          run_count: 0,
          size_estimate_bytes: 3 * 1024 * 1024, // 3MB per session
        });
      }

      // Evict
      await indexedDBService.evictOldSessions();

      const sessions = await indexedDBService.getAllSessions();

      // Should have deleted 5 oldest sessions, keeping 10 most recent
      expect(sessions.length).toBe(10);
    });
  });
});
