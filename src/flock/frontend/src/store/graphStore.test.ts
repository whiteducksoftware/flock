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
import { blackboardFilterKey, useGraphStore } from './graphStore';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from '../services/graphService';
import { useFilterStore } from './filterStore';
import { GraphSnapshot, GraphNode } from '../types/graph';
import { Node } from '@xyflow/react';
import { indexedDBService } from '../services/indexeddb';

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
      transientPositions: null,
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

  describe('streaming previews on the Blackboard', () => {
    const stream = (artifactId: string, correlation: string, agent = 'writer', type = 'app.Reply') =>
      useGraphStore.getState().createOrUpdateStreamingMessageNode(artifactId, 'tok', {
        artifact_type: type,
        agent_name: agent,
        correlation_id: correlation,
        run_id: `run-${artifactId}`,
      } as any);

    beforeEach(() => {
      useGraphStore.setState({ viewMode: 'blackboard', nodes: [] });
    });

    it('show only what the board\'s filters let through', () => {
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: 'c-1',
        timeRange: { preset: 'last10min' },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
      } as any);

      stream('a-1', 'c-1');
      stream('a-2', 'c-2'); // another run: no lane for it

      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['a-1']);
    });

    it('match a type filter by any type of an agent that publishes several', () => {
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: null,
        timeRange: { preset: 'all' },
        selectedArtifactTypes: ['app.B'],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
      } as any);

      // `.publishes(A, B)` streams under the label "app.A, app.B"
      stream('a-1', 'c-1', 'writer', 'app.A, app.B');
      stream('a-2', 'c-1', 'writer', 'app.A, app.C');

      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['a-1']);
    });

    it('keep a generic type name whole: its commas are not between types', () => {
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: null,
        timeRange: { preset: 'all' },
        selectedArtifactTypes: ['app.Pair[str, int]'],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
      } as any);

      stream('a-1', 'c-1', 'writer', 'app.Pair[str, int]');
      stream('a-2', 'c-1', 'writer', 'app.Pair[str, int], app.Note');
      stream('a-3', 'c-1', 'writer', 'app.Pair[str, bool]');

      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['a-1', 'a-2']);
    });

    it('follow the type, producer and tag filters', () => {
      const filters = { correlationId: null, timeRange: { preset: 'all' }, selectedVisibility: [] };
      vi.mocked(useFilterStore.getState).mockReturnValue({
        ...filters,
        selectedArtifactTypes: ['app.Reply'],
        selectedProducers: ['writer'],
        selectedTags: [],
      } as any);
      stream('a-1', 'c-1');
      stream('a-2', 'c-1', 'other');
      stream('a-3', 'c-1', 'writer', 'app.Note');
      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['a-1']);

      // A preview has no tags yet: a tag filter keeps it out
      vi.mocked(useFilterStore.getState).mockReturnValue({
        ...filters,
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: ['urgent'],
      } as any);
      stream('a-4', 'c-1');
      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['a-1']);
    });
  });

  describe('runs that ended, until the board shows their output (#642)', () => {
    const message = (id: string, producedBy: string) => ({
      id,
      type: 'message',
      position: { x: 0, y: 0 },
      data: { producedBy, correlationId: 'c-1', artifactType: producedBy === 'triage' ? 'Decision[app.Route]' : 'app.Ticket', timestamp: 1 },
    });
    const ticket = message('t1', 'external');
    const decided = message('d1', 'triage');
    const end = () => {
      useGraphStore.getState().setInFlight('r1', 'triage', ['app.Ticket'], ['t1'], 'c-1');
      useGraphStore.getState().setInFlight('r1', 'triage', null);
    };

    beforeEach(() => {
      useGraphStore.setState({ viewMode: 'blackboard', nodes: [ticket as any], inFlight: new Map(), settling: new Map() });
    });
    afterEach(() => vi.useRealTimers());

    it('keeps a decider that ended until a snapshot brings its decision', async () => {
      end();
      expect(useGraphStore.getState().inFlight.has('r1')).toBe(false);
      expect(useGraphStore.getState().settling.get('r1')).toMatchObject({ agent: 'triage', artifacts: ['t1'], correlationId: 'c-1' });

      // A snapshot asked for before its decision was stored
      vi.mocked(fetchGraphSnapshot).mockResolvedValueOnce({ nodes: [ticket], edges: [], statistics: null } as unknown as GraphSnapshot);
      await useGraphStore.getState().generateBlackboardViewGraph();
      expect(useGraphStore.getState().settling.has('r1')).toBe(true);

      vi.mocked(fetchGraphSnapshot).mockResolvedValueOnce({ nodes: [ticket, decided], edges: [], statistics: null } as unknown as GraphSnapshot);
      await useGraphStore.getState().generateBlackboardViewGraph();
      expect(useGraphStore.getState().settling.size).toBe(0);
    });

    it('does not take an earlier output of the agent for the one it waits for', async () => {
      useGraphStore.setState({ nodes: [ticket as any, decided as any] });
      end();
      vi.mocked(fetchGraphSnapshot).mockResolvedValueOnce({ nodes: [ticket, decided], edges: [], statistics: null } as unknown as GraphSnapshot);
      await useGraphStore.getState().generateBlackboardViewGraph();
      expect(useGraphStore.getState().settling.has('r1')).toBe(true);
    });

    it('settles a streamed run whose output the board already holds as its preview', async () => {
      // The finished preview keeps the artifact's ID until the snapshot brings the artifact
      const preview = { ...decided, data: { ...decided.data, isStreaming: false, streamingText: 'tech', runId: 'r1' } };
      useGraphStore.setState({ nodes: [ticket as any, preview as any] });
      end();
      vi.mocked(fetchGraphSnapshot).mockResolvedValueOnce({ nodes: [ticket, decided], edges: [], statistics: null } as unknown as GraphSnapshot);
      await useGraphStore.getState().generateBlackboardViewGraph();
      expect(useGraphStore.getState().settling.has('r1')).toBe(false);
    });

    it('settles a run whose output a snapshot brought while it still ran', async () => {
      useGraphStore.getState().setInFlight('r1', 'triage', ['app.Ticket'], ['t1'], 'c-1');
      vi.mocked(fetchGraphSnapshot).mockResolvedValueOnce({ nodes: [ticket, decided], edges: [], statistics: null } as unknown as GraphSnapshot);
      await useGraphStore.getState().generateBlackboardViewGraph();
      useGraphStore.getState().setInFlight('r1', 'triage', null);

      vi.mocked(fetchGraphSnapshot).mockResolvedValueOnce({ nodes: [ticket, decided], edges: [], statistics: null } as unknown as GraphSnapshot);
      await useGraphStore.getState().generateBlackboardViewGraph();
      expect(useGraphStore.getState().settling.has('r1')).toBe(false);
    });

    it('lets a run that published nothing go after a few seconds', () => {
      vi.useFakeTimers();
      end();
      vi.advanceTimersByTime(3900);
      expect(useGraphStore.getState().settling.has('r1')).toBe(true);
      vi.advanceTimersByTime(200);
      expect(useGraphStore.getState().settling.has('r1')).toBe(false);
    });
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

    it('stamps agent nodes with when the snapshot arrived, for their countdowns', async () => {
      const agent = { id: 'agent1', type: 'agent', data: { name: 'batcher' }, position: { x: 0, y: 0 } } as Node;
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({ nodes: [], edges: [], statistics: null } as unknown as GraphSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue([agent]);
      vi.mocked(overlayWebSocketState).mockReturnValue([agent]);
      vi.spyOn(performance, 'now').mockReturnValue(1234.5);

      await useGraphStore.getState().generateAgentViewGraph();

      expect(useGraphStore.getState().nodes[0]?.data).toEqual({ name: 'batcher', snapshotAt: 1234.5 });
    });

    it('keeps an unfolded board\'s positions over the saved ones when the snapshot refreshes', async () => {
      const agent = { id: 'agent1', type: 'agent', data: {}, position: { x: 100, y: 100 } } as Node;
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({ nodes: [], edges: [], statistics: null } as unknown as GraphSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue([agent]);
      vi.mocked(overlayWebSocketState).mockReturnValue([agent]);
      useGraphStore.getState().setTransientPositions(new Map([['agent1', { x: 5, y: 6 }]]));

      await useGraphStore.getState().generateAgentViewGraph();
      expect(useGraphStore.getState().nodes[0]?.position).toEqual({ x: 5, y: 6 });

      useGraphStore.getState().setTransientPositions(null);
      await useGraphStore.getState().generateAgentViewGraph();
      expect(useGraphStore.getState().nodes[0]?.position).toEqual({ x: 100, y: 100 });
    });

    it('keeps the selected node selected when the snapshot refreshes', async () => {
      const agent = (id: string) => ({ id, type: 'agent', data: {}, position: { x: 0, y: 0 } }) as Node;
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({ nodes: [], edges: [], statistics: null } as unknown as GraphSnapshot);
      vi.mocked(mergeNodePositions).mockReturnValue([agent('a'), agent('b')]);
      vi.mocked(overlayWebSocketState).mockImplementation((nodes) => nodes);
      useGraphStore.setState({ nodes: [{ ...agent('a'), selected: true }, agent('b')] });

      await useGraphStore.getState().generateAgentViewGraph();

      expect(useGraphStore.getState().nodes.map((node) => Boolean(node.selected))).toEqual([true, false]);
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

  describe('overlapping snapshot requests', () => {
    const snapshot = (id: string) =>
      ({ nodes: [{ id, type: 'message', data: {}, position: { x: 0, y: 0 } }], edges: [], statistics: null, truncated: false }) as unknown as GraphSnapshot;

    it('apply an answer for the same filters while newer requests still load (live refreshes in a row)', async () => {
      const answers: ((value: GraphSnapshot) => void)[] = [];
      vi.mocked(fetchGraphSnapshot).mockImplementation(() => new Promise((resolve) => answers.push(resolve)));

      const first = useGraphStore.getState().generateBlackboardViewGraph();
      const second = useGraphStore.getState().generateBlackboardViewGraph();
      answers[0]!(snapshot('first'));
      await first;
      // Newer than nothing applied, and asked for the board's filters: it shows
      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['first']);

      answers[1]!(snapshot('second'));
      await second;
      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['second']);
      expect(useGraphStore.getState().isLoading).toBe(false);
    });

    it('compare an Agent View answer with the filters its request was built for, after the saved positions load', async () => {
      const filters = (correlationId: string | null) =>
        vi.mocked(useFilterStore.getState).mockReturnValue({
          correlationId,
          timeRange: { preset: 'last10min' },
          selectedArtifactTypes: [],
          selectedProducers: [],
          selectedTags: [],
          selectedVisibility: [],
          updateFacets: vi.fn(),
        } as any);
      vi.mocked(mergeNodePositions).mockImplementation((nodes) => nodes as Node[]);
      vi.mocked(overlayWebSocketState).mockImplementation((nodes) => nodes);
      let positionsLoaded: () => void = () => {};
      vi.spyOn(indexedDBService, 'getAllAgentViewLayouts').mockImplementationOnce(
        () => new Promise((resolve) => (positionsLoaded = () => resolve([]))),
      );
      let answer: (value: GraphSnapshot) => void = () => {};
      vi.mocked(fetchGraphSnapshot).mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));

      // Asked under no filter; a run is filtered before the request goes out, then the filter is lifted
      const asked = useGraphStore.getState().generateAgentViewGraph();
      filters('c-2');
      positionsLoaded();
      await vi.waitFor(() => expect(fetchGraphSnapshot).toHaveBeenCalledTimes(1));
      expect(vi.mocked(fetchGraphSnapshot).mock.calls[0]![0].filters.correlation_id).toBe('c-2');
      filters(null);
      answer(snapshot('for-c-2'));
      await asked;

      // The answer is for the run's filter, not for the board's
      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual([]);
    });

    it('apply only the newest: an older answer arriving last does not replace it', async () => {
      let answerOld: (value: GraphSnapshot) => void = () => {};
      vi.mocked(fetchGraphSnapshot)
        .mockImplementationOnce(() => new Promise((resolve) => (answerOld = resolve)))
        .mockResolvedValueOnce(snapshot('new'));

      const older = useGraphStore.getState().generateBlackboardViewGraph();
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: 'c-2',
        timeRange: { preset: 'last10min' },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
      } as any);
      await useGraphStore.getState().generateBlackboardViewGraph();
      answerOld(snapshot('old'));
      await older;

      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['new']);
      expect(useGraphStore.getState().isLoading).toBe(false);
      // The board knows which filters its snapshot answers
      expect(useGraphStore.getState().blackboardFilters).toBe(blackboardFilterKey());
      expect(useGraphStore.getState().blackboardFilters).toContain('c-2');
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

    it('keeps an artifact that still streams, and says when the view is cut off', async () => {
      const streaming = {
        id: 'live',
        type: 'message',
        position: { x: 0, y: 0 },
        data: { artifactType: 'TeamReply', timestamp: Date.now(), isStreaming: true, streamingText: 'Hi, ' },
      } as Node;
      useGraphStore.setState({ nodes: [streaming] });
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({
        nodes: [{ id: 'msg1', type: 'message', data: { artifactType: 'Pizza' }, position: { x: 0, y: 0 }, hidden: false }],
        edges: [],
        statistics: null,
        viewMode: 'blackboard',
        filters: { correlation_id: null, time_range: { preset: 'last10min' }, artifactTypes: [], producers: [], tags: [], visibility: [] },
        generatedAt: '2026-10-11T00:00:00Z',
        totalArtifacts: 900,
        truncated: true,
      });

      await useGraphStore.getState().generateBlackboardViewGraph();

      const state = useGraphStore.getState();
      expect(state.nodes.map((node) => node.id)).toEqual(['msg1', 'live']);
      expect(state.truncated).toBe(true);
    });

    it('keeps no preview older than the last minutes the board shows', async () => {
      useGraphStore.setState({
        nodes: [{ id: 'old', type: 'message', position: { x: 0, y: 0 }, data: { artifactType: 'TeamReply', timestamp: Date.now() - 6 * 60_000, isStreaming: true } } as Node],
      });
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: null,
        timeRange: { preset: 'last5min' },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
        updateFacets: vi.fn(),
      } as any);
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({
        nodes: [],
        edges: [],
        statistics: null,
        viewMode: 'blackboard',
        filters: { correlation_id: null, time_range: { preset: 'last5min' }, artifactTypes: [], producers: [], tags: [], visibility: [] },
        generatedAt: '2026-10-11T00:00:00Z',
        totalArtifacts: 0,
        truncated: false,
      });

      await useGraphStore.getState().generateBlackboardViewGraph();

      expect(useGraphStore.getState().nodes).toEqual([]);
    });

    it('keeps no live preview in a time range that ended', async () => {
      useGraphStore.setState({
        nodes: [{ id: 'live', type: 'message', position: { x: 0, y: 0 }, data: { artifactType: 'TeamReply', timestamp: Date.now(), isStreaming: true } } as Node],
      });
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: null,
        timeRange: { preset: 'custom', start: Date.now() - 7_200_000, end: Date.now() - 3_600_000 },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
        updateFacets: vi.fn(),
      } as any);
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({
        nodes: [],
        edges: [],
        statistics: null,
        viewMode: 'blackboard',
        filters: { correlation_id: null, time_range: { preset: 'custom' }, artifactTypes: [], producers: [], tags: [], visibility: [] },
        generatedAt: '2026-10-11T00:00:00Z',
        totalArtifacts: 0,
        truncated: false,
      });

      await useGraphStore.getState().generateBlackboardViewGraph();

      expect(useGraphStore.getState().nodes).toEqual([]);
    });

    it('keeps only the streaming artifacts the board\'s filters let through', async () => {
      const preview = (id: string, correlationId: string) =>
        ({ id, type: 'message', position: { x: 0, y: 0 }, data: { artifactType: 'TeamReply', producedBy: 'billing', correlationId, timestamp: Date.now(), isStreaming: true } }) as Node;
      useGraphStore.setState({ nodes: [preview('in-c2', 'c2'), preview('in-c1', 'c1')] });
      vi.mocked(useFilterStore.getState).mockReturnValue({
        correlationId: 'c2',
        timeRange: { preset: 'last10min' },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
        updateFacets: vi.fn(),
      } as any);
      vi.mocked(fetchGraphSnapshot).mockResolvedValue({
        nodes: [],
        edges: [],
        statistics: null,
        viewMode: 'blackboard',
        filters: { correlation_id: 'c2', time_range: { preset: 'last10min' }, artifactTypes: [], producers: [], tags: [], visibility: [] },
        generatedAt: '2026-10-11T00:00:00Z',
        totalArtifacts: 0,
        truncated: false,
      });

      await useGraphStore.getState().generateBlackboardViewGraph();

      expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['in-c2']);
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

  describe('setNodePositions()', () => {
    it('moves the given nodes and leaves the others', () => {
      useGraphStore.setState({
        nodes: [
          { id: 'a', position: { x: 0, y: 0 }, data: {} },
          { id: 'b', position: { x: 10, y: 10 }, data: {} },
        ] as Node[],
      });

      useGraphStore.getState().setNodePositions(new Map([['a', { x: 3, y: 4 }]]));

      expect(useGraphStore.getState().nodes.map((node) => node.position)).toEqual([
        { x: 3, y: 4 },
        { x: 10, y: 10 },
      ]);
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

    it('should persist saved node positions to IndexedDB in agent view', () => {
      useGraphStore.setState({ viewMode: 'agent' });
      const saveSpy = vi.spyOn(indexedDBService, 'saveAgentViewLayout').mockResolvedValue();

      useGraphStore.getState().saveNodePosition('agent1', { x: 420, y: 240 });

      expect(saveSpy).toHaveBeenCalledWith({
        node_id: 'agent1',
        x: 420,
        y: 240,
        last_updated: expect.any(String),
      });

      saveSpy.mockRestore();
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
