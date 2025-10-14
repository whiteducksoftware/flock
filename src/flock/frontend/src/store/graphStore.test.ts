/**
 * GraphStore Tests - NEW Simplified Architecture
 *
 * Tests for Phase 2: Backend snapshot consumption replacing client-side graph construction
 *
 * FOCUS: Backend integration, position merging, real-time WebSocket overlays
 * NOT: Edge derivation algorithms (now handled by backend)
 *
 * Specification: docs/specs/002-ui-optimization-migration/
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useGraphStore } from './graphStore';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from '../services/graphService';
import { useFilterStore } from './filterStore';
import { GraphSnapshot, GraphNode } from '../types/graph';
import { Node } from '@xyflow/react';

// Mock dependencies
vi.mock('../services/graphService', () => ({
  fetchGraphSnapshot: vi.fn(),
  mergeNodePositions: vi.fn(),
  overlayWebSocketState: vi.fn(),
}));

vi.mock('./filterStore', () => ({
  useFilterStore: {
    getState: vi.fn(),
  },
}));

vi.mock('../hooks/usePersistence', () => ({
  usePersistence: vi.fn(() => ({
    loadPositions: vi.fn().mockResolvedValue(new Map()),
    savePositions: vi.fn(),
  })),
}));

describe('graphStore - NEW Simplified Architecture', () => {
  beforeEach(() => {
    // Reset store state before each test
    useGraphStore.setState({
      agentStatus: new Map(),
      streamingTokens: new Map(),
      nodes: [],
      edges: [],
      statistics: null,
      events: [],
      viewMode: 'agent',
    });

    // Clear all mocks
    vi.clearAllMocks();

    // Setup default filter store mock
    vi.mocked(useFilterStore.getState).mockReturnValue({
      correlationId: null,
      timeRange: { preset: 'last10min' },
      selectedArtifactTypes: [],
      selectedProducers: [],
      selectedTags: [],
      selectedVisibility: [],
      updateFacets: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('generateAgentViewGraph()', () => {
    it('should fetch agent view graph from backend', async () => {
      const mockSnapshot: GraphSnapshot = {
        nodes: [
          { id: 'agent1', type: 'agent', data: { name: 'pizza_master' }, position: { x: 0, y: 0 }, hidden: false },
        ],
        edges: [
          { id: 'edge1', source: 'agent1', target: 'agent2', type: 'message_flow', data: {}, hidden: false },
        ],
        statistics: null,
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 1,
        truncated: false,
      };

      const mockMergedNodes: Node[] = [
        { id: 'agent1', type: 'agent', data: { name: 'pizza_master' }, position: { x: 100, y: 100 } } as Node,
      ];

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue(mockMergedNodes);
      vi.mocked(overlayWebSocketState).mockReturnValue(mockMergedNodes);

      await useGraphStore.getState().generateAgentViewGraph();

      // Verify backend API call
      expect(fetchGraphSnapshot).toHaveBeenCalledWith({
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

      // Verify state updated
      const state = useGraphStore.getState();
      expect(state.nodes).toHaveLength(1);
      expect(state.edges).toHaveLength(1);
      expect(state.viewMode).toBe('agent');
    });

    it('should pass filters from filterStore to backend', async () => {
      const mockFilters = {
        correlationId: 'test-correlation-id',
        timeRange: { preset: 'last1hour' as const },
        selectedArtifactTypes: ['Pizza', 'Order'],
        selectedProducers: ['pizza_master', 'waiter'],
        selectedTags: ['urgent'],
        selectedVisibility: ['public'],
        updateFacets: vi.fn(),
      };

      vi.mocked(useFilterStore.getState).mockReturnValue(mockFilters as any);

      const mockSnapshot: GraphSnapshot = {
        nodes: [],
        edges: [],
        statistics: null,
        viewMode: 'agent',
        filters: {
          correlation_id: 'test-correlation-id',
          time_range: { preset: 'last1hour' },
          artifactTypes: ['Pizza', 'Order'],
          producers: ['pizza_master', 'waiter'],
          tags: ['urgent'],
          visibility: ['public'],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 0,
        truncated: false,
      };

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue([]);
      vi.mocked(overlayWebSocketState).mockReturnValue([]);

      await useGraphStore.getState().generateAgentViewGraph();

      expect(fetchGraphSnapshot).toHaveBeenCalledWith({
        viewMode: 'agent',
        filters: {
          correlation_id: 'test-correlation-id',
          time_range: { preset: 'last1hour' },
          artifactTypes: ['Pizza', 'Order'],
          producers: ['pizza_master', 'waiter'],
          tags: ['urgent'],
          visibility: ['public'],
        },
        options: { include_statistics: true },
      });
    });

    it('should update filter facets from backend statistics', async () => {
      const mockUpdateFacets = vi.fn();
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: null,
        timeRange: { preset: 'last10min' },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
        updateFacets: mockUpdateFacets,
      } as any);

      const mockSnapshot: GraphSnapshot = {
        nodes: [],
        edges: [],
        statistics: {
          producedByAgent: {},
          consumedByAgent: {},
          artifactSummary: {
            total: 100,
            by_type: { Pizza: 50, Order: 50 },
            by_producer: { pizza_master: 75, waiter: 25 },
            by_visibility: { public: 100 },
            tag_counts: { urgent: 10 },
            earliest_created_at: '2025-10-11T00:00:00Z',
            latest_created_at: '2025-10-11T01:00:00Z',
          },
        },
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 100,
        truncated: false,
      };

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue([]);
      vi.mocked(overlayWebSocketState).mockReturnValue([]);

      await useGraphStore.getState().generateAgentViewGraph();

      // Verify facets are transformed from artifactSummary
      expect(mockUpdateFacets).toHaveBeenCalledWith({
        artifactTypes: ['Pizza', 'Order'],
        producers: ['pizza_master', 'waiter'],
        tags: ['urgent'],
        visibilities: ['public'],
      });
    });

    it('should handle API errors gracefully', async () => {
      vi.mocked(fetchGraphSnapshot).mockRejectedValue(new Error('API error'));

      await expect(useGraphStore.getState().generateAgentViewGraph()).rejects.toThrow('API error');
    });
  });

  describe('generateBlackboardViewGraph()', () => {
    it('should fetch blackboard view graph from backend', async () => {
      const mockSnapshot: GraphSnapshot = {
        nodes: [
          { id: 'msg1', type: 'message', data: { artifact_type: 'Pizza' }, position: { x: 0, y: 0 }, hidden: false },
        ],
        edges: [
          { id: 'edge1', source: 'msg1', target: 'msg2', type: 'transformation', data: {}, hidden: false },
        ],
        statistics: null,
        viewMode: 'blackboard',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 1,
        truncated: false,
      };

      const mockMergedNodes: Node[] = [
        { id: 'msg1', type: 'message', data: { artifact_type: 'Pizza' }, position: { x: 100, y: 100 } } as Node,
      ];

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue(mockMergedNodes);
      vi.mocked(overlayWebSocketState).mockReturnValue(mockMergedNodes);

      await useGraphStore.getState().generateBlackboardViewGraph();

      // Verify backend API call with blackboard mode
      expect(fetchGraphSnapshot).toHaveBeenCalledWith({
        viewMode: 'blackboard',
        filters: expect.any(Object),
        options: { include_statistics: true },
      });

      // Verify state updated
      const state = useGraphStore.getState();
      expect(state.nodes).toHaveLength(1);
      expect(state.edges).toHaveLength(1);
      expect(state.viewMode).toBe('blackboard');
    });
  });

  describe('updateAgentStatus() - Real-time WebSocket updates', () => {
    it('should update agent status immediately (FAST path)', () => {
      // Setup initial state with agent node
      useGraphStore.setState({
        nodes: [
          { id: 'agent1', type: 'agent', data: { name: 'pizza_master', status: 'idle' }, position: { x: 0, y: 0 } } as Node,
        ],
      });

      // Update status
      useGraphStore.getState().updateAgentStatus('agent1', 'running');

      // Verify immediate update
      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'agent1');
      expect(node?.data.status).toBe('running');

      // Verify status stored in agentStatus map
      expect(state.agentStatus.get('agent1')).toBe('running');
    });

    it('should only update matching agent node', () => {
      useGraphStore.setState({
        nodes: [
          { id: 'agent1', type: 'agent', data: { status: 'idle' }, position: { x: 0, y: 0 } } as Node,
          { id: 'agent2', type: 'agent', data: { status: 'idle' }, position: { x: 100, y: 0 } } as Node,
        ],
      });

      useGraphStore.getState().updateAgentStatus('agent1', 'running');

      const state = useGraphStore.getState();
      expect(state.nodes.find((n) => n.id === 'agent1')?.data.status).toBe('running');
      expect(state.nodes.find((n) => n.id === 'agent2')?.data.status).toBe('idle');
    });
  });

  describe('updateStreamingTokens() - Real-time token display', () => {
    it('should update streaming tokens and keep last 6 only', () => {
      useGraphStore.setState({
        nodes: [
          { id: 'agent1', type: 'agent', data: { streamingTokens: [] }, position: { x: 0, y: 0 } } as Node,
        ],
      });

      // Send 8 tokens
      const tokens = ['token1', 'token2', 'token3', 'token4', 'token5', 'token6', 'token7', 'token8'];
      useGraphStore.getState().updateStreamingTokens('agent1', tokens);

      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'agent1');

      // Verify only last 6 tokens kept
      expect(node?.data.streamingTokens).toEqual(['token3', 'token4', 'token5', 'token6', 'token7', 'token8']);
      expect(node?.data.streamingTokens).toHaveLength(6);
    });

    it('should handle tokens less than 6', () => {
      useGraphStore.setState({
        nodes: [
          { id: 'agent1', type: 'agent', data: { streamingTokens: [] }, position: { x: 0, y: 0 } } as Node,
        ],
      });

      const tokens = ['token1', 'token2', 'token3'];
      useGraphStore.getState().updateStreamingTokens('agent1', tokens);

      const state = useGraphStore.getState();
      const node = state.nodes.find((n) => n.id === 'agent1');
      expect(node?.data.streamingTokens).toEqual(['token1', 'token2', 'token3']);
    });

    it('should store tokens in streamingTokens map', () => {
      useGraphStore.setState({
        nodes: [
          { id: 'agent1', type: 'agent', data: { streamingTokens: [] }, position: { x: 0, y: 0 } } as Node,
        ],
      });

      const tokens = ['token1', 'token2'];
      useGraphStore.getState().updateStreamingTokens('agent1', tokens);

      const state = useGraphStore.getState();
      expect(state.streamingTokens.get('agent1')).toEqual(['token1', 'token2']);
    });
  });

  describe('Position persistence integration', () => {
    it('should merge saved positions with backend nodes', async () => {
      const mockBackendNodes: GraphNode[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1' }, position: { x: 0, y: 0 }, hidden: false },
      ];

      // Mock saved positions (200, 300) should be used by mergeNodePositions
      const mockMergedNodes: Node[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1' }, position: { x: 200, y: 300 } } as Node,
      ];

      const mockSnapshot: GraphSnapshot = {
        nodes: mockBackendNodes,
        edges: [],
        statistics: null,
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 0,
        truncated: false,
      };

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue(mockMergedNodes);
      vi.mocked(overlayWebSocketState).mockReturnValue(mockMergedNodes);

      await useGraphStore.getState().generateAgentViewGraph();

      // Verify mergeNodePositions was called with correct arguments
      expect(mergeNodePositions).toHaveBeenCalledWith(
        mockBackendNodes,
        expect.any(Map), // savedPositions from IndexedDB
        [] // currentNodes (empty on first load)
      );

      // Verify merged positions applied
      const state = useGraphStore.getState();
      expect(state.nodes[0]!.position).toEqual({ x: 200, y: 300 });
    });

    it('should overlay WebSocket state on merged nodes', async () => {
      const mockBackendNodes: GraphNode[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1', status: 'idle' }, position: { x: 0, y: 0 }, hidden: false },
      ];

      const mockMergedNodes: Node[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1', status: 'idle' }, position: { x: 100, y: 100 } } as Node,
      ];

      const mockOverlayedNodes: Node[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1', status: 'running', streamingTokens: ['token1'] }, position: { x: 100, y: 100 } } as Node,
      ];

      const mockSnapshot: GraphSnapshot = {
        nodes: mockBackendNodes,
        edges: [],
        statistics: null,
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 0,
        truncated: false,
      };

      // Setup WebSocket state
      useGraphStore.setState({
        agentStatus: new Map([['agent1', 'running']]),
        streamingTokens: new Map([['agent1', ['token1']]]),
      });

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue(mockMergedNodes);
      vi.mocked(overlayWebSocketState).mockReturnValue(mockOverlayedNodes);

      await useGraphStore.getState().generateAgentViewGraph();

      // Verify overlayWebSocketState called with WebSocket state
      expect(overlayWebSocketState).toHaveBeenCalledWith(
        mockMergedNodes,
        expect.any(Map), // agentStatus
        expect.any(Map), // streamingTokens
        expect.any(Map) // agentLogicOperations
      );
    });
  });

  describe('Statistics from backend snapshot', () => {
    it('should store statistics from backend', async () => {
      const mockStatistics = {
        producedByAgent: {
          pizza_master: { total: 50, byType: { Pizza: 50 } },
        },
        consumedByAgent: {
          waiter: { total: 50, byType: { Pizza: 50 } },
        },
        artifactSummary: {
          total: 100,
          by_type: { Pizza: 100 },
          by_producer: { pizza_master: 100 },
          by_visibility: { public: 100 },
          tag_counts: {},
          earliest_created_at: '2025-10-11T00:00:00Z',
          latest_created_at: '2025-10-11T01:00:00Z',
        },
      };

      const mockSnapshot: GraphSnapshot = {
        nodes: [],
        edges: [],
        statistics: mockStatistics,
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
        generatedAt: '2025-10-11T00:00:00Z',
        totalArtifacts: 100,
        truncated: false,
      };

      vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue([]);
      vi.mocked(overlayWebSocketState).mockReturnValue([]);

      await useGraphStore.getState().generateAgentViewGraph();

      const state = useGraphStore.getState();
      expect(state.statistics).toEqual(mockStatistics);
    });
  });

  describe('UI state management', () => {
    it('should add events to event log', () => {
      const event = {
        id: 'msg1',
        type: 'Pizza',
        payload: {},
        producedBy: 'pizza_master',
        correlationId: 'corr-1',
        timestamp: Date.now(),
      };

      useGraphStore.getState().addEvent(event as any);

      const state = useGraphStore.getState();
      expect(state.events).toHaveLength(1);
      expect(state.events[0]).toEqual(event);
    });

    it('should limit events to 100 entries', () => {
      // Add 150 events
      for (let i = 0; i < 150; i++) {
        useGraphStore.getState().addEvent({
          id: `msg${i}`,
          type: 'Pizza',
          payload: {},
          producedBy: 'pizza_master',
          correlationId: 'corr-1',
          timestamp: Date.now() + i,
        } as any);
      }

      const state = useGraphStore.getState();
      expect(state.events).toHaveLength(100);
      // Most recent should be first
      expect(state.events[0]!.id).toBe('msg149');
    });

    it('should update view mode', () => {
      useGraphStore.getState().setViewMode('blackboard');
      expect(useGraphStore.getState().viewMode).toBe('blackboard');

      useGraphStore.getState().setViewMode('agent');
      expect(useGraphStore.getState().viewMode).toBe('agent');
    });
  });
});
