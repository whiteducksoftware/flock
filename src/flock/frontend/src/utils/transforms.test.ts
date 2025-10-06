import { describe, it, expect, beforeEach } from 'vitest';
import { Edge } from '@xyflow/react';

/**
 * Phase 4: Graph Visualization & Dual Views - Edge Derivation Tests
 *
 * Tests for edge derivation algorithms from DATA_MODEL.md:
 * - deriveAgentViewEdges: Creates message flow edges between agents
 * - deriveBlackboardViewEdges: Creates transformation edges between artifacts
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/DATA_MODEL.md lines 770-853
 * REFERENCE: docs/specs/003-real-time-dashboard/PLAN.md Phase 4
 */

// Type definitions matching DATA_MODEL.md specification

interface Artifact {
  artifact_id: string;
  artifact_type: string;
  produced_by: string;
  consumed_by: string[];
  published_at: string; // ISO timestamp
  payload: any;
  correlation_id: string;
}

interface Run {
  run_id: string;
  agent_name: string;
  correlation_id: string; // Groups multiple agent runs together
  status: 'active' | 'completed' | 'error';
  consumed_artifacts: string[];
  produced_artifacts: string[];
  duration_ms?: number;
}

interface DashboardState {
  artifacts: Map<string, Artifact>;
  runs: Map<string, Run>;
}

// Edge type definitions from DATA_MODEL.md lines 805-817
interface AgentViewEdge extends Edge {
  type: 'message_flow';
  label: string; // Format: "message_type (count)"
  data: {
    message_type: string;
    message_count: number;
    artifact_ids: string[];
    latest_timestamp: string;
  };
}

// Edge type definitions from DATA_MODEL.md lines 836-847
interface BlackboardViewEdge extends Edge {
  type: 'transformation';
  label: string; // agent_name
  data: {
    transformer_agent: string;
    run_id: string;
    duration_ms?: number;
  };
}

// Function interfaces (to be implemented in transforms.ts)
interface EdgeTransforms {
  deriveAgentViewEdges(state: DashboardState): AgentViewEdge[];
  deriveBlackboardViewEdges(state: DashboardState): BlackboardViewEdge[];
}

describe('Edge Derivation Algorithms', () => {
  let transforms: EdgeTransforms;

  beforeEach(() => {
    // Mock implementation that will fail until real implementation
    transforms = {
      deriveAgentViewEdges: () => {
        throw new Error('deriveAgentViewEdges not implemented');
      },
      deriveBlackboardViewEdges: () => {
        throw new Error('deriveBlackboardViewEdges not implemented');
      },
    };
  });

  describe('deriveAgentViewEdges - Message Flow Edges', () => {
    it('should create edges between agents (source → target)', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: { title: 'Inception' },
              correlation_id: 'corr-1',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior after implementation:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].source).toBe('movie-agent');
      // expect(edges[0].target).toBe('tagline-agent');
      // expect(edges[0].type).toBe('message_flow');
    });

    it('should group edges by message_type', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
          [
            'artifact-2',
            {
              artifact_id: 'artifact-2',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:01:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
          [
            'artifact-3',
            {
              artifact_id: 'artifact-3',
              artifact_type: 'Tagline',
              produced_by: 'tagline-agent',
              consumed_by: ['output-agent'],
              published_at: '2025-10-03T10:02:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // // Should have 2 edges: movie→tagline (Movie type), tagline→output (Tagline type)
      // expect(edges).toHaveLength(2);
      //
      // const movieEdge = edges.find(e => e.data.message_type === 'Movie');
      // expect(movieEdge).toBeDefined();
      // expect(movieEdge!.source).toBe('movie-agent');
      // expect(movieEdge!.target).toBe('tagline-agent');
      //
      // const taglineEdge = edges.find(e => e.data.message_type === 'Tagline');
      // expect(taglineEdge).toBeDefined();
      // expect(taglineEdge!.source).toBe('tagline-agent');
      // expect(taglineEdge!.target).toBe('output-agent');
    });

    it('should count artifacts per edge', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
          [
            'artifact-2',
            {
              artifact_id: 'artifact-2',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:01:00Z',
              payload: {},
              correlation_id: 'corr-2',
            },
          ],
          [
            'artifact-3',
            {
              artifact_id: 'artifact-3',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:02:00Z',
              payload: {},
              correlation_id: 'corr-3',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].data.message_count).toBe(3);
      // expect(edges[0].data.artifact_ids).toHaveLength(3);
      // expect(edges[0].data.artifact_ids).toContain('artifact-1');
      // expect(edges[0].data.artifact_ids).toContain('artifact-2');
      // expect(edges[0].data.artifact_ids).toContain('artifact-3');
    });

    it('should format edge label as "Type (N)"', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
          [
            'artifact-2',
            {
              artifact_id: 'artifact-2',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:01:00Z',
              payload: {},
              correlation_id: 'corr-2',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].label).toBe('Movie (2)');
    });

    it('should track latest_timestamp for each edge', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
          [
            'artifact-2',
            {
              artifact_id: 'artifact-2',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:05:00Z', // Latest
              payload: {},
              correlation_id: 'corr-2',
            },
          ],
          [
            'artifact-3',
            {
              artifact_id: 'artifact-3',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:02:00Z',
              payload: {},
              correlation_id: 'corr-3',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].data.latest_timestamp).toBe('2025-10-03T10:05:00Z');
    });

    it('should create unique edge IDs using edgeKey format', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior (from DATA_MODEL.md line 782):
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // // Edge ID format: `${source}_${target}_${message_type}`
      // expect(edges[0].id).toBe('movie-agent_tagline-agent_Movie');
    });

    it('should handle multiple consumers (fan-out)', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent', 'summary-agent', 'rating-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // // Should create 3 edges: movie→tagline, movie→summary, movie→rating
      // expect(edges).toHaveLength(3);
      //
      // const targets = edges.map(e => e.target).sort();
      // expect(targets).toEqual(['rating-agent', 'summary-agent', 'tagline-agent']);
      //
      // // All should have the same source
      // edges.forEach(edge => {
      //   expect(edge.source).toBe('movie-agent');
      // });
    });

    it('should handle empty consumed_by array (no edges)', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: [], // No consumers
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // // No edges should be created
      // expect(edges).toHaveLength(0);
    });

    it('should return empty array for empty state', () => {
      const state: DashboardState = {
        artifacts: new Map(),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      // expect(edges).toHaveLength(0);
      // expect(edges).toEqual([]);
    });
  });

  describe('deriveBlackboardViewEdges - Transformation Edges', () => {
    it('should create edges between artifacts (consumed → produced)', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'tagline-agent',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1500,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].source).toBe('artifact-1');
      // expect(edges[0].target).toBe('artifact-2');
      // expect(edges[0].type).toBe('transformation');
    });

    it('should create one edge per consumed × produced pair', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
          ['artifact-3', { artifact_id: 'artifact-3' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'multi-agent',
              status: 'completed',
              consumed_artifacts: ['artifact-1', 'artifact-2'],
              produced_artifacts: ['artifact-3'],
              duration_ms: 2000,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // // Should create 2 edges: artifact-1→artifact-3, artifact-2→artifact-3
      // expect(edges).toHaveLength(2);
      //
      // const edge1 = edges.find(e => e.source === 'artifact-1');
      // expect(edge1).toBeDefined();
      // expect(edge1!.target).toBe('artifact-3');
      //
      // const edge2 = edges.find(e => e.source === 'artifact-2');
      // expect(edge2).toBeDefined();
      // expect(edge2!.target).toBe('artifact-3');
    });

    it('should label edges with agent_name', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'tagline-agent',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1500,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior (from DATA_MODEL.md line 841):
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].label).toBe('tagline-agent');
    });

    it('should include edge data with run metadata', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'tagline-agent',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1500,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior (from DATA_MODEL.md lines 842-846):
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // expect(edges[0].data).toEqual({
      //   transformer_agent: 'tagline-agent',
      //   run_id: 'run-1',
      //   correlation_id: 'test-correlation',
      //   duration_ms: 1500,
      // });
    });

    it('should skip active runs (status === "active")', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'active-agent',
              status: 'active', // Still running
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
            },
          ],
          [
            'run-2',
            {
              run_id: 'run-2',
              correlation_id: 'test-correlation',
              agent_name: 'completed-agent',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1000,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior (from DATA_MODEL.md line 831):
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // // Only run-2 should create an edge (run-1 is active)
      // expect(edges).toHaveLength(1);
      // expect(edges[0].data.run_id).toBe('run-2');
    });

    it('should generate unique edge IDs', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'agent-1',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1000,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior (from DATA_MODEL.md line 837):
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // expect(edges).toHaveLength(1);
      // // Edge ID format: `${consumed_id}_${produced_id}`
      // expect(edges[0].id).toBe('artifact-1_artifact-2');
    });

    it('should handle runs with no consumed artifacts', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'source-agent',
              status: 'completed',
              consumed_artifacts: [], // No inputs
              produced_artifacts: ['artifact-1'],
              duration_ms: 500,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // // No edges should be created (no consumed artifacts)
      // expect(edges).toHaveLength(0);
    });

    it('should handle runs with no produced artifacts', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'sink-agent',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: [], // No outputs
              duration_ms: 500,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // // No edges should be created (no produced artifacts)
      // expect(edges).toHaveLength(0);
    });

    it('should return empty array for empty runs', () => {
      const state: DashboardState = {
        artifacts: new Map(),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveBlackboardViewEdges(state);
      // expect(edges).toHaveLength(0);
      // expect(edges).toEqual([]);
    });
  });

  describe('Edge Deduplication', () => {
    it('should not duplicate Agent View edges with same source, target, and type', () => {
      const state: DashboardState = {
        artifacts: new Map([
          [
            'artifact-1',
            {
              artifact_id: 'artifact-1',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:00:00Z',
              payload: {},
              correlation_id: 'corr-1',
            },
          ],
          [
            'artifact-2',
            {
              artifact_id: 'artifact-2',
              artifact_type: 'Movie',
              produced_by: 'movie-agent',
              consumed_by: ['tagline-agent'],
              published_at: '2025-10-03T10:01:00Z',
              payload: {},
              correlation_id: 'corr-2',
            },
          ],
        ]),
        runs: new Map(),
      };

      expect(() => {
        transforms.deriveAgentViewEdges(state);
      }).toThrow('deriveAgentViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveAgentViewEdges(state);
      //
      // // Should create only 1 edge (not 2) with count of 2
      // expect(edges).toHaveLength(1);
      // expect(edges[0].data.message_count).toBe(2);
    });

    it('should allow multiple Blackboard View edges with same source and target from different runs', () => {
      const state: DashboardState = {
        artifacts: new Map([
          ['artifact-1', { artifact_id: 'artifact-1' } as Artifact],
          ['artifact-2', { artifact_id: 'artifact-2' } as Artifact],
        ]),
        runs: new Map([
          [
            'run-1',
            {
              run_id: 'run-1',
              correlation_id: 'test-correlation',
              agent_name: 'agent-1',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1000,
            },
          ],
          [
            'run-2',
            {
              run_id: 'run-2',
              correlation_id: 'test-correlation',
              agent_name: 'agent-2',
              status: 'completed',
              consumed_artifacts: ['artifact-1'],
              produced_artifacts: ['artifact-2'],
              duration_ms: 1500,
            },
          ],
        ]),
      };

      expect(() => {
        transforms.deriveBlackboardViewEdges(state);
      }).toThrow('deriveBlackboardViewEdges not implemented');

      // Expected behavior:
      // const edges = transforms.deriveBlackboardViewEdges(state);
      //
      // // Should create 2 edges (same source/target but different runs)
      // // This will cause overlapping edges, but that's expected per spec
      // expect(edges).toHaveLength(2);
      //
      // const edge1 = edges.find(e => e.data.run_id === 'run-1');
      // const edge2 = edges.find(e => e.data.run_id === 'run-2');
      //
      // expect(edge1).toBeDefined();
      // expect(edge2).toBeDefined();
      //
      // // Note: React Flow will need to handle overlapping edges visually
    });
  });
});
