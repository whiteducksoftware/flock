/**
 * Phase 5: Integration Tests for Backend Snapshot Consumption
 *
 * Tests the complete flow from backend API to UI rendering, including:
 * - Initial graph loading from backend
 * - WebSocket-triggered debounced refreshes
 * - Position persistence
 * - Filter application
 * - Error handling
 * - Empty states
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from '@testing-library/react';
import { useGraphStore } from '../../store/graphStore';
import { useFilterStore } from '../../store/filterStore';
import { GraphSnapshot } from '../../types/graph';

// Mock the graph service
vi.mock('../../services/graphService', () => ({
  fetchGraphSnapshot: vi.fn(),
  mergeNodePositions: vi.fn((backendNodes) => backendNodes),
  overlayWebSocketState: vi.fn((nodes) => nodes),
}));

// Mock IndexedDB for persistence tests
const mockIndexedDB = {
  open: vi.fn(),
  databases: vi.fn().mockResolvedValue([]),
};
globalThis.indexedDB = mockIndexedDB as any;

import * as graphService from '../../services/graphService';

describe('Graph Snapshot Integration', () => {
  // Sample backend snapshot fixture
  const createMockSnapshot = (overrides?: Partial<GraphSnapshot>): GraphSnapshot => ({
    generatedAt: '2025-10-11T00:00:00Z',
    viewMode: 'agent',
    filters: {
      correlation_id: null,
      time_range: { preset: 'last10min' },
      artifactTypes: [],
      producers: [],
      tags: [],
      visibility: [],
    },
    nodes: [
      {
        id: 'pizza_master',
        type: 'agent',
        data: { name: 'pizza_master', status: 'idle' },
        position: { x: 100, y: 100 },
        hidden: false,
      },
      {
        id: 'topping_picker',
        type: 'agent',
        data: { name: 'topping_picker', status: 'idle' },
        position: { x: 300, y: 200 },
        hidden: false,
      },
    ],
    edges: [
      {
        id: 'edge-1',
        source: 'pizza_master',
        target: 'topping_picker',
        type: 'message_flow',
        label: 'Pizza',
        data: {},
        hidden: false,
      },
    ],
    statistics: {
      producedByAgent: {
        pizza_master: { total: 5, byType: { Pizza: 5 } },
      },
      consumedByAgent: {
        topping_picker: { total: 5, byType: { Pizza: 5 } },
      },
      artifactSummary: {
        total: 10,
        by_type: { Pizza: 10 },
        by_producer: { pizza_master: 10 },
        by_visibility: { public: 10 },
        tag_counts: {},
        earliest_created_at: '2025-10-11T00:00:00Z',
        latest_created_at: '2025-10-11T00:05:00Z',
      },
    },
    totalArtifacts: 10,
    truncated: false,
    ...overrides,
  });

  beforeEach(() => {
    // Reset all stores before each test
    useGraphStore.setState({
      agentStatus: new Map(),
      streamingTokens: new Map(),
      nodes: [],
      edges: [],
      statistics: null,
      events: [],
      viewMode: 'agent',
      isLoading: false,
      error: null,
    });

    useFilterStore.setState({
      correlationId: null,
      timeRange: { preset: 'last10min' },
      selectedArtifactTypes: [],
      selectedProducers: [],
      selectedTags: [],
      selectedVisibility: [],
      availableArtifactTypes: [],
      availableProducers: [],
      availableTags: [],
      availableVisibility: [],
    });

    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Test 1: Initial Graph Loading', () => {
    it('should fetch agent view graph from backend on mount', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      // Trigger graph generation
      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      // Verify backend was called with correct request
      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledWith({
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        options: { include_statistics: true },
      });

      // Verify store was updated with snapshot data
      const state = useGraphStore.getState();
      expect(state.nodes).toHaveLength(2);
      expect(state.edges).toHaveLength(1);
      expect(state.statistics).toBeTruthy();
      expect(state.viewMode).toBe('agent');
    });

    it('should fetch blackboard view graph from backend', async () => {
      const mockSnapshot = createMockSnapshot({ viewMode: 'blackboard' });
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      await act(async () => {
        await useGraphStore.getState().generateBlackboardViewGraph();
      });

      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledWith({
        viewMode: 'blackboard',
        filters: expect.any(Object),
        options: { include_statistics: true },
      });

      const state = useGraphStore.getState();
      expect(state.viewMode).toBe('blackboard');
    });

    it('should call fetchGraphSnapshot only once on initial load', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledTimes(1);
    });
  });

  describe('Test 2: WebSocket Event Handling', () => {
    it('should update agent status immediately without backend fetch', () => {
      // Set up initial nodes
      useGraphStore.setState({
        nodes: [
          {
            id: 'pizza_master',
            type: 'agent',
            data: { name: 'pizza_master', status: 'idle' },
            position: { x: 100, y: 100 },
          },
        ],
      });

      // Update status (simulating WebSocket event)
      act(() => {
        useGraphStore.getState().updateAgentStatus('pizza_master', 'running');
      });

      // Verify status updated immediately
      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'pizza_master');
      expect(node?.data.status).toBe('running');

      // Verify NO backend fetch happened (fast path)
      expect(graphService.fetchGraphSnapshot).not.toHaveBeenCalled();
    });

    it('should update streaming tokens without backend fetch', () => {
      useGraphStore.setState({
        nodes: [
          {
            id: 'pizza_master',
            type: 'agent',
            data: { name: 'pizza_master', streamingTokens: [] },
            position: { x: 100, y: 100 },
          },
        ],
      });

      act(() => {
        useGraphStore.getState().updateStreamingTokens('pizza_master', ['token1', 'token2', 'token3']);
      });

      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'pizza_master');
      expect(node?.data.streamingTokens).toEqual(['token1', 'token2', 'token3']);

      // No backend fetch for streaming tokens (fast path)
      expect(graphService.fetchGraphSnapshot).not.toHaveBeenCalled();
    });

    it('should keep only last 6 streaming tokens', () => {
      useGraphStore.setState({
        nodes: [
          {
            id: 'pizza_master',
            type: 'agent',
            data: { streamingTokens: [] },
            position: { x: 100, y: 100 },
          },
        ],
      });

      const tokens = ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8'];
      act(() => {
        useGraphStore.getState().updateStreamingTokens('pizza_master', tokens);
      });

      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'pizza_master');
      expect(node?.data.streamingTokens).toHaveLength(6);
      expect(node?.data.streamingTokens).toEqual(['t3', 't4', 't5', 't6', 't7', 't8']);
    });
  });

  describe('Test 3: View Refresh', () => {
    it('should call appropriate view generator based on viewMode', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      // Set agent view mode
      useGraphStore.setState({ viewMode: 'agent' });

      await act(async () => {
        await useGraphStore.getState().refreshCurrentView();
      });

      // Should call agent view
      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledWith(
        expect.objectContaining({ viewMode: 'agent' })
      );
    });

    it('should refresh blackboard view when viewMode is blackboard', async () => {
      const mockSnapshot = createMockSnapshot({ viewMode: 'blackboard' });
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      // Set blackboard view mode
      useGraphStore.setState({ viewMode: 'blackboard' });

      await act(async () => {
        await useGraphStore.getState().refreshCurrentView();
      });

      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledWith(
        expect.objectContaining({ viewMode: 'blackboard' })
      );
    });

    it('should accumulate events from multiple addEvent calls', () => {
      // Simulate multiple message published events
      act(() => {
        useGraphStore.getState().addEvent({
          id: 'msg1',
          type: 'Pizza',
          producedBy: 'pizza_master',
          timestamp: Date.now(),
        } as any);

        useGraphStore.getState().addEvent({
          id: 'msg2',
          type: 'Pizza',
          producedBy: 'pizza_master',
          timestamp: Date.now(),
        } as any);

        useGraphStore.getState().addEvent({
          id: 'msg3',
          type: 'Pizza',
          producedBy: 'pizza_master',
          timestamp: Date.now(),
        } as any);
      });

      // Verify all 3 events in store
      const state = useGraphStore.getState();
      expect(state.events).toHaveLength(3);
    });
  });

  describe('Test 4: Position Persistence', () => {
    it('should merge saved positions with backend nodes', async () => {
      // Mock persistence to return saved positions
      vi.mocked(graphService.mergeNodePositions).mockImplementation(
        (backendNodes, saved) => {
          return backendNodes.map((node) => ({
            ...node,
            position: saved.get(node.id) || node.position,
          }));
        }
      );

      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      // Verify mergeNodePositions was called with saved positions
      expect(graphService.mergeNodePositions).toHaveBeenCalled();
    });

    it('should update node position when user drags node', () => {
      useGraphStore.setState({
        nodes: [
          {
            id: 'pizza_master',
            type: 'agent',
            data: {},
            position: { x: 100, y: 100 },
          },
        ],
      });

      // Simulate user dragging node to new position
      act(() => {
        useGraphStore.getState().updateNodePosition('pizza_master', { x: 250, y: 350 });
      });

      // Verify position updated in store
      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'pizza_master');
      expect(node?.position).toEqual({ x: 250, y: 350 });
    });
  });

  describe('Test 5: Filter Application', () => {
    it('should trigger backend fetch when filters applied', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      // Update filters using correct method names
      act(() => {
        useFilterStore.getState().setArtifactTypes(['Pizza']);
        useFilterStore.getState().setProducers(['pizza_master']);
      });

      // Apply filters
      await act(async () => {
        await useFilterStore.getState().applyFilters();
      });

      // Verify backend called with updated filters
      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledWith({
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: expect.objectContaining({ preset: 'last10min' }),
          artifactTypes: ['Pizza'],
          producers: ['pizza_master'],
          tags: [],
          visibility: [],
        },
        options: { include_statistics: true },
      });
    });

    it('should update available facets from backend statistics', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      // Verify filter facets updated from backend
      const filterState = useFilterStore.getState();
      expect(filterState.availableArtifactTypes).toContain('Pizza');
      expect(filterState.availableProducers).toContain('pizza_master');
      expect(filterState.availableVisibility).toContain('public');
    });
  });

  describe('Test 6: Error Handling', () => {
    it('should handle backend API errors gracefully', async () => {
      vi.mocked(graphService.fetchGraphSnapshot).mockRejectedValue(
        new Error('Backend API unavailable')
      );

      // Verify error is thrown
      await expect(async () => {
        await act(async () => {
          await useGraphStore.getState().generateAgentViewGraph();
        });
      }).rejects.toThrow('Backend API unavailable');

      // Verify error state was set
      const state = useGraphStore.getState();
      expect(state.error).toBe('Backend API unavailable');
      expect(state.isLoading).toBe(false);
    });

    it('should not crash when fetchGraphSnapshot returns invalid data', async () => {
      // Mock returns empty snapshot
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue({
        generatedAt: '2025-10-11T00:00:00Z',
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        nodes: [],
        edges: [],
        statistics: null,
        totalArtifacts: 0,
        truncated: false,
      });

      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      // Should handle empty data gracefully
      const state = useGraphStore.getState();
      expect(state.nodes).toEqual([]);
      expect(state.edges).toEqual([]);
    });
  });

  describe('Test 7: Empty State', () => {
    it('should handle empty graph from backend', async () => {
      const emptySnapshot = createMockSnapshot({
        nodes: [],
        edges: [],
        statistics: null,
        totalArtifacts: 0,
      });

      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(emptySnapshot);

      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      const state = useGraphStore.getState();
      expect(state.nodes).toEqual([]);
      expect(state.edges).toEqual([]);
      expect(state.statistics).toBeNull();
    });

    it('should clear events when limit exceeded', () => {
      useGraphStore.setState({ events: [] });

      // Add 101 events (limit is 100)
      act(() => {
        for (let i = 0; i < 101; i++) {
          useGraphStore.getState().addEvent({
            id: `msg${i}`,
            type: 'Pizza',
            producedBy: 'pizza_master',
            timestamp: Date.now() + i,
          } as any);
        }
      });

      // Should keep only last 100
      const state = useGraphStore.getState();
      expect(state.events).toHaveLength(100);
      expect(state.events[0]?.id).toBe('msg100'); // Most recent first
    });
  });

  describe('Test 8: View Mode Switching', () => {
    it('should switch between agent and blackboard views', async () => {
      const agentSnapshot = createMockSnapshot({ viewMode: 'agent' });
      const blackboardSnapshot = createMockSnapshot({ viewMode: 'blackboard' });

      vi.mocked(graphService.fetchGraphSnapshot)
        .mockResolvedValueOnce(agentSnapshot)
        .mockResolvedValueOnce(blackboardSnapshot);

      // Load agent view
      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      expect(useGraphStore.getState().viewMode).toBe('agent');

      // Switch to blackboard view
      await act(async () => {
        await useGraphStore.getState().generateBlackboardViewGraph();
      });

      expect(useGraphStore.getState().viewMode).toBe('blackboard');
      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledTimes(2);
    });

    it('should update viewMode state', () => {
      act(() => {
        useGraphStore.getState().setViewMode('blackboard');
      });

      expect(useGraphStore.getState().viewMode).toBe('blackboard');

      act(() => {
        useGraphStore.getState().setViewMode('agent');
      });

      expect(useGraphStore.getState().viewMode).toBe('agent');
    });
  });

  describe('Test 9: Debounced Refresh (Critical Optimization)', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should batch multiple rapid events into single backend fetch after 100ms', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      // Load initial graph
      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      vi.clearAllMocks();

      // Simulate 5 rapid scheduleRefresh() calls (like rapid WebSocket events)
      act(() => {
        for (let i = 0; i < 5; i++) {
          useGraphStore.getState().scheduleRefresh();
        }
      });

      // No fetch yet (debounce delay)
      expect(graphService.fetchGraphSnapshot).not.toHaveBeenCalled();

      // Advance timers by 100ms (debounce threshold)
      await act(async () => {
        vi.advanceTimersByTime(100);
        // Wait for any pending promises
        await Promise.resolve();
      });

      // Should have triggered exactly ONE backend fetch (batching worked!)
      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledTimes(1);
    });

    it('should reset debounce timer if new event arrives within 100ms', async () => {
      const mockSnapshot = createMockSnapshot();
      vi.mocked(graphService.fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

      await act(async () => {
        await useGraphStore.getState().generateAgentViewGraph();
      });

      vi.clearAllMocks();

      // First scheduleRefresh call
      act(() => {
        useGraphStore.getState().scheduleRefresh();
      });

      // Advance 50ms (not enough to trigger)
      act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(graphService.fetchGraphSnapshot).not.toHaveBeenCalled();

      // Second scheduleRefresh call (resets timer)
      act(() => {
        useGraphStore.getState().scheduleRefresh();
      });

      // Advance another 50ms (100ms total, but timer was reset at 50ms)
      act(() => {
        vi.advanceTimersByTime(50);
      });

      // Still no fetch (timer was reset)
      expect(graphService.fetchGraphSnapshot).not.toHaveBeenCalled();

      // Advance final 50ms (100ms since last scheduleRefresh)
      await act(async () => {
        vi.advanceTimersByTime(50);
        await Promise.resolve();
      });

      // Now it should fetch (100ms of quiet time)
      expect(graphService.fetchGraphSnapshot).toHaveBeenCalledTimes(1);
    });
  });
});
