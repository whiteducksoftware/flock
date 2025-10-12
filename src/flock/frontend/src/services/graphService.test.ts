import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from './graphService';
import { GraphRequest, GraphSnapshot } from '../types/graph';
import { Node } from '@xyflow/react';

/**
 * Graph Service Tests - UI Optimization Migration (Spec 002)
 *
 * Tests the NEW graph service layer that replaces client-side graph construction
 * with backend snapshot consumption.
 *
 * SPECIFICATION: docs/internal/ui-optimization/03-migration-implementation-guide.md
 * FOCUS: Backend integration, position merging, WebSocket state overlay, error handling
 */

describe('graphService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchGraphSnapshot', () => {
    it('should fetch agent view graph from backend with correct request format', async () => {
      const mockSnapshot: GraphSnapshot = {
        nodes: [
          { id: 'agent1', type: 'agent', data: { name: 'agent1' }, position: { x: 0, y: 0 }, hidden: false },
        ],
        edges: [
          { id: 'edge1', source: 'agent1', target: 'agent2', type: 'message_flow', hidden: false, data: {} },
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

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockSnapshot,
      }) as any;

      const request: GraphRequest = {
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: ['Pizza'],
          producers: ['pizza_master'],
          tags: [],
          visibility: [],
        },
        options: { include_statistics: true },
      };

      const result = await fetchGraphSnapshot(request);

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/dashboard/graph', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      expect(result).toEqual(mockSnapshot);
      expect(result.nodes).toHaveLength(1);
      expect(result.edges).toHaveLength(1);
    });

    it('should throw error when API call fails', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const request: GraphRequest = {
        viewMode: 'agent',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last10min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
      };

      await expect(fetchGraphSnapshot(request)).rejects.toThrow('Graph API error: Internal Server Error');
    });

    it('should handle network errors gracefully', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      const request: GraphRequest = {
        viewMode: 'blackboard',
        filters: {
          correlation_id: null,
          time_range: { preset: 'last5min' },
          artifactTypes: [],
          producers: [],
          tags: [],
          visibility: [],
        },
      };

      await expect(fetchGraphSnapshot(request)).rejects.toThrow('Network error');
    });
  });

  describe('mergeNodePositions - Priority Logic', () => {
    it('should prioritize saved positions over all others', () => {
      const backendNodes = [
        { id: 'agent1', type: 'agent' as const, data: { name: 'agent1' }, position: { x: 100, y: 100 }, hidden: false },
      ];

      const savedPositions = new Map([['agent1', { x: 500, y: 500 }]]);

      const currentNodes: Node[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1' }, position: { x: 300, y: 300 } },
      ];

      const result = mergeNodePositions(backendNodes, savedPositions, currentNodes);

      // Saved position (500, 500) wins
      expect(result[0]?.position).toEqual({ x: 500, y: 500 });
    });

    it('should prioritize current positions when no saved position exists', () => {
      const backendNodes = [
        { id: 'agent1', type: 'agent' as const, data: { name: 'agent1' }, position: { x: 100, y: 100 }, hidden: false },
      ];

      const savedPositions = new Map(); // No saved position

      const currentNodes: Node[] = [
        { id: 'agent1', type: 'agent', data: { name: 'agent1' }, position: { x: 300, y: 300 } },
      ];

      const result = mergeNodePositions(backendNodes, savedPositions, currentNodes);

      // Current position (300, 300) wins
      expect(result[0]!.position).toEqual({ x: 300, y: 300 });
    });

    it('should use backend position when saved and current are unavailable', () => {
      const backendNodes = [
        { id: 'agent1', type: 'agent' as const, data: { name: 'agent1' }, position: { x: 100, y: 100 }, hidden: false },
      ];

      const savedPositions = new Map(); // No saved position
      const currentNodes: Node[] = []; // No current position

      const result = mergeNodePositions(backendNodes, savedPositions, currentNodes);

      // Backend position (100, 100) wins
      expect(result[0]!.position).toEqual({ x: 100, y: 100 });
    });

    it('should generate random position when backend has zero coordinates', () => {
      const backendNodes = [
        { id: 'agent1', type: 'agent' as const, data: { name: 'agent1' }, position: { x: 0, y: 0 }, hidden: false },
      ];

      const savedPositions = new Map(); // No saved position
      const currentNodes: Node[] = []; // No current position

      const result = mergeNodePositions(backendNodes, savedPositions, currentNodes);

      // Random position should be generated (not 0, 0)
      expect(result[0]!.position.x).toBeGreaterThan(0);
      expect(result[0]!.position.y).toBeGreaterThan(0);
      // Random position range: x in [400, 600], y in [300, 500]
      expect(result[0]!.position.x).toBeGreaterThanOrEqual(400);
      expect(result[0]!.position.x).toBeLessThanOrEqual(600);
      expect(result[0]!.position.y).toBeGreaterThanOrEqual(300);
      expect(result[0]!.position.y).toBeLessThanOrEqual(500);
    });

    it('should handle multiple nodes with mixed position sources', () => {
      const backendNodes = [
        { id: 'agent1', type: 'agent' as const, data: { name: 'agent1' }, position: { x: 100, y: 100 }, hidden: false },
        { id: 'agent2', type: 'agent' as const, data: { name: 'agent2' }, position: { x: 200, y: 200 }, hidden: false },
        { id: 'agent3', type: 'agent' as const, data: { name: 'agent3' }, position: { x: 0, y: 0 }, hidden: false },
      ];

      const savedPositions = new Map([['agent1', { x: 500, y: 500 }]]); // Only agent1

      const currentNodes: Node[] = [
        { id: 'agent2', type: 'agent', data: { name: 'agent2' }, position: { x: 300, y: 300 } },
      ];

      const result = mergeNodePositions(backendNodes, savedPositions, currentNodes);

      // agent1: saved position wins
      expect(result[0]!.position).toEqual({ x: 500, y: 500 });
      // agent2: current position wins
      expect(result[1]!.position).toEqual({ x: 300, y: 300 });
      // agent3: random position (backend is 0,0)
      expect(result[2]!.position.x).toBeGreaterThan(0);
      expect(result[2]!.position.y).toBeGreaterThan(0);
    });
  });

  describe('overlayWebSocketState', () => {
    it('should overlay agent status from WebSocket state', () => {
      const nodes: Node[] = [
        {
          id: 'agent1',
          type: 'agent',
          data: { name: 'agent1', status: 'idle' },
          position: { x: 100, y: 100 },
        },
      ];

      const agentStatus = new Map([['agent1', 'running']]);
      const streamingTokens = new Map<string, string[]>();

      const result = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      expect(result[0]!.data.status).toBe('running');
    });

    it('should overlay streaming tokens from WebSocket state', () => {
      const nodes: Node[] = [
        {
          id: 'agent1',
          type: 'agent',
          data: { name: 'agent1', status: 'idle' },
          position: { x: 100, y: 100 },
        },
      ];

      const agentStatus = new Map<string, string>();
      const streamingTokens = new Map([['agent1', ['token1', 'token2', 'token3']]]);

      const result = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      expect(result[0]!.data.streamingTokens).toEqual(['token1', 'token2', 'token3']);
    });

    it('should use backend status when WebSocket state is unavailable', () => {
      const nodes: Node[] = [
        {
          id: 'agent1',
          type: 'agent',
          data: { name: 'agent1', status: 'idle' },
          position: { x: 100, y: 100 },
        },
      ];

      const agentStatus = new Map<string, string>(); // Empty
      const streamingTokens = new Map<string, string[]>(); // Empty

      const result = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      // Backend status is preserved
      expect(result[0]!.data.status).toBe('idle');
      // Empty array for tokens
      expect(result[0]!.data.streamingTokens).toEqual([]);
    });

    it('should not modify non-agent nodes', () => {
      const nodes: Node[] = [
        {
          id: 'message1',
          type: 'message',
          data: { type: 'Pizza', payload: {} },
          position: { x: 100, y: 100 },
        },
      ];

      const agentStatus = new Map([['message1', 'running']]);
      const streamingTokens = new Map([['message1', ['token1']]]);

      const result = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      // Message node should not be modified
      expect(result[0]!.data).toEqual({ type: 'Pizza', payload: {} });
      expect(result[0]!.data.status).toBeUndefined();
      expect(result[0]!.data.streamingTokens).toBeUndefined();
    });

    it('should handle multiple agent nodes with mixed WebSocket state', () => {
      const nodes: Node[] = [
        {
          id: 'agent1',
          type: 'agent',
          data: { name: 'agent1', status: 'idle' },
          position: { x: 100, y: 100 },
        },
        {
          id: 'agent2',
          type: 'agent',
          data: { name: 'agent2', status: 'idle' },
          position: { x: 200, y: 200 },
        },
        {
          id: 'message1',
          type: 'message',
          data: { type: 'Pizza' },
          position: { x: 300, y: 300 },
        },
      ];

      const agentStatus = new Map([['agent1', 'running']]); // Only agent1
      const streamingTokens = new Map([['agent2', ['token1', 'token2']]]); // Only agent2

      const result = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      // agent1: status updated, no tokens
      expect(result[0]!.data.status).toBe('running');
      expect(result[0]!.data.streamingTokens).toEqual([]);
      // agent2: status from backend, tokens updated
      expect(result[1]!.data.status).toBe('idle');
      expect(result[1]!.data.streamingTokens).toEqual(['token1', 'token2']);
      // message1: unchanged
      expect(result[2]!.data).toEqual({ type: 'Pizza' });
    });
  });
});
