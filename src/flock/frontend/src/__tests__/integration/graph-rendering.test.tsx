import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { Agent, Message } from '../../types/graph';

/**
 * Phase 4: Graph Visualization & Dual Views - Integration Tests
 *
 * Tests full graph rendering for both Agent View and Blackboard View modes.
 * Validates mode toggling performance and WebSocket event integration.
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/PLAN.md Phase 4
 * REQUIREMENTS:
 * - Agent View renders correctly (agents as nodes, message flow edges)
 * - Blackboard View renders correctly (artifacts as nodes, transformation edges)
 * - Mode toggle switches between views within 100ms
 * - Graph updates on new WebSocket events
 */

// Mock GraphCanvas component (to be implemented)
const MockGraphCanvas = () => {
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const mode = useUIStore((state) => state.mode);

  return (
    <div data-testid="graph-canvas">
      <div data-testid="mode-indicator">{mode}</div>
      <div data-testid="node-count">{nodes.length}</div>
      <div data-testid="edge-count">{edges.length}</div>
      {nodes.map((node) => (
        <div key={node.id} data-testid={`node-${node.id}`} data-type={node.type}>
          {node.type === 'agent' && <span>{(node.data as any).name}</span>}
          {node.type === 'message' && <span>{(node.data as any).artifactType}</span>}
        </div>
      ))}
      {edges.map((edge) => (
        <div key={edge.id} data-testid={`edge-${edge.id}`}>
          {edge.source} → {edge.target}
        </div>
      ))}
    </div>
  );
};

describe('Graph Rendering Integration', () => {
  beforeEach(() => {
    // Reset stores before each test
    useGraphStore.setState({
      agents: new Map(),
      messages: new Map(),
      events: [],
      nodes: [],
      edges: [],
      runs: new Map(), // Phase 11: Reset runs map
      consumptions: new Map(), // Phase 11: Reset consumptions map
    });

    useUIStore.setState({
      mode: 'agent',
    });
  });

  describe('Agent View Rendering', () => {
    it('should render agents as nodes in Agent View', async () => {
      const agents: Agent[] = [
        {
          id: 'movie-agent',
          name: 'movie-agent',
          status: 'idle',
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 2,
          recvCount: 0,
          position: { x: 100, y: 100 },
        },
        {
          id: 'tagline-agent',
          name: 'tagline-agent',
          status: 'running',
          subscriptions: ['Movie'],
          lastActive: Date.now(),
          sentCount: 1,
          recvCount: 2,
          position: { x: 300, y: 100 },
        },
        {
          id: 'summary-agent',
          name: 'summary-agent',
          status: 'idle',
          subscriptions: ['Movie'],
          lastActive: Date.now(),
          sentCount: 0,
          recvCount: 2,
          position: { x: 500, y: 100 },
        },
      ];

      useGraphStore.getState().batchUpdate({ agents });
      useGraphStore.getState().generateAgentViewGraph();

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('mode-indicator')).toHaveTextContent('agent');
        expect(screen.getByTestId('node-count')).toHaveTextContent('3');

        // Verify all agent nodes are rendered
        expect(screen.getByTestId('node-movie-agent')).toBeInTheDocument();
        expect(screen.getByTestId('node-tagline-agent')).toBeInTheDocument();
        expect(screen.getByTestId('node-summary-agent')).toBeInTheDocument();

        // Verify node types
        expect(screen.getByTestId('node-movie-agent')).toHaveAttribute('data-type', 'agent');
        expect(screen.getByTestId('node-tagline-agent')).toHaveAttribute('data-type', 'agent');
      });
    });

    it('should render message flow edges in Agent View', async () => {
      const agents: Agent[] = [
        {
          id: 'movie-agent',
          name: 'movie-agent',
          status: 'idle',
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 2,
          recvCount: 0,
        },
        {
          id: 'tagline-agent',
          name: 'tagline-agent',
          status: 'idle',
          subscriptions: ['Movie'],
          lastActive: Date.now(),
          sentCount: 0,
          recvCount: 2,
        },
      ];

      const messages: Message[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          payload: { title: 'Inception' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'movie-agent',
        },
        {
          id: 'msg-2',
          type: 'Movie',
          payload: { title: 'Interstellar' },
          timestamp: Date.now(),
          correlationId: 'corr-2',
          producedBy: 'movie-agent',
        },
      ];

      useGraphStore.getState().batchUpdate({ agents, messages });
      // Phase 11 fix: Record consumption to populate consumed_by field
      useGraphStore.getState().recordConsumption(['msg-1', 'msg-2'], 'tagline-agent');
      useGraphStore.getState().generateAgentViewGraph();

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('node-count')).toHaveTextContent('2');
        expect(screen.getByTestId('edge-count')).not.toHaveTextContent('0');

        // Verify edge exists between movie-agent and tagline-agent
        const edges = useGraphStore.getState().edges;
        const edge = edges.find(
          (e) => e.source === 'movie-agent' && e.target === 'tagline-agent'
        );
        expect(edge).toBeDefined();
        expect(edge?.label).toContain('Movie');
        expect(edge?.label).toContain('2'); // Count of messages
      });
    });

    it('should display correct message counts on edges', async () => {
      const agents: Agent[] = [
        {
          id: 'producer',
          name: 'producer',
          status: 'idle',
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 5,
          recvCount: 0,
        },
        {
          id: 'consumer',
          name: 'consumer',
          status: 'idle',
          subscriptions: ['DataType'],
          lastActive: Date.now(),
          sentCount: 0,
          recvCount: 5,
        },
      ];

      const messages: Message[] = Array.from({ length: 5 }, (_, i) => ({
        id: `msg-${i}`,
        type: 'DataType',
        payload: { index: i },
        timestamp: Date.now() + i,
        correlationId: `corr-${i}`,
        producedBy: 'producer',
      }));

      useGraphStore.getState().batchUpdate({ agents, messages });
      // Phase 11 fix: Record consumption to populate consumed_by field
      useGraphStore.getState().recordConsumption(['msg-0', 'msg-1', 'msg-2', 'msg-3', 'msg-4'], 'consumer');
      useGraphStore.getState().generateAgentViewGraph();

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        const edges = useGraphStore.getState().edges;
        expect(edges).toHaveLength(1);

        const edge = edges[0];
        expect(edge).toBeDefined();
        expect(edge?.label).toBe('DataType (5)');
        expect(edge?.data?.messageCount).toBe(5);
        expect(edge?.data?.artifactIds).toHaveLength(5);
      });
    });
  });

  describe('Blackboard View Rendering', () => {
    it('should render artifacts as nodes in Blackboard View', async () => {
      const messages: Message[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          payload: { title: 'Inception' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'movie-agent',
        },
        {
          id: 'msg-2',
          type: 'Tagline',
          payload: { text: 'Dream within a dream' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'tagline-agent',
        },
        {
          id: 'msg-3',
          type: 'Summary',
          payload: { text: 'A sci-fi thriller' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'summary-agent',
        },
      ];

      useGraphStore.getState().batchUpdate({ messages });
      useGraphStore.getState().generateBlackboardViewGraph();
      useUIStore.setState({ mode: 'blackboard' });

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('mode-indicator')).toHaveTextContent('blackboard');
        expect(screen.getByTestId('node-count')).toHaveTextContent('3');

        // Verify all message nodes are rendered
        expect(screen.getByTestId('node-msg-1')).toBeInTheDocument();
        expect(screen.getByTestId('node-msg-2')).toBeInTheDocument();
        expect(screen.getByTestId('node-msg-3')).toBeInTheDocument();

        // Verify node types
        expect(screen.getByTestId('node-msg-1')).toHaveAttribute('data-type', 'message');
      });
    });

    it('should render transformation edges in Blackboard View', async () => {
      // Note: This test will need actual transformation edge logic
      // For now, we test the basic structure

      const messages: Message[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          payload: { title: 'Inception' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'movie-agent',
        },
        {
          id: 'msg-2',
          type: 'Tagline',
          payload: { text: 'Dream within a dream' },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'tagline-agent',
        },
      ];

      useGraphStore.getState().batchUpdate({ messages });
      useGraphStore.getState().generateBlackboardViewGraph();
      useUIStore.setState({ mode: 'blackboard' });

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('mode-indicator')).toHaveTextContent('blackboard');
        expect(screen.getByTestId('node-count')).toHaveTextContent('2');

        // Currently generateBlackboardViewGraph doesn't create edges
        // This will be implemented with transforms.ts
        const edges = useGraphStore.getState().edges;
        expect(edges).toHaveLength(0); // Will change after implementation
      });
    });

    it('should display artifact types correctly', async () => {
      const messages: Message[] = [
        {
          id: 'msg-1',
          type: 'Movie',
          payload: { title: 'Inception', year: 2010 },
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'movie-agent',
        },
      ];

      useGraphStore.getState().batchUpdate({ messages });
      useGraphStore.getState().generateBlackboardViewGraph();
      useUIStore.setState({ mode: 'blackboard' });

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        const nodes = useGraphStore.getState().nodes;
        expect(nodes).toHaveLength(1);
        expect(nodes[0]).toBeDefined();
        expect((nodes[0]?.data as any).artifactType).toBe('Movie');
        expect(screen.getByText('Movie')).toBeInTheDocument();
      });
    });
  });

  describe('Mode Toggle Performance', () => {
    it('should switch between views within 100ms (REQUIREMENT)', async () => {
      // Setup both agent and message data
      const agents: Agent[] = [
        {
          id: 'agent-1',
          name: 'agent-1',
          status: 'idle',
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 1,
          recvCount: 0,
        },
      ];

      const messages: Message[] = [
        {
          id: 'msg-1',
          type: 'TestType',
          payload: {},
          timestamp: Date.now(),
          correlationId: 'corr-1',
          producedBy: 'agent-1',
        },
      ];

      useGraphStore.getState().batchUpdate({ agents, messages });

      // Measure Agent View generation
      const agentStartTime = performance.now();
      useGraphStore.getState().generateAgentViewGraph();
      const agentEndTime = performance.now();
      const agentDuration = agentEndTime - agentStartTime;

      expect(agentDuration).toBeLessThan(100); // REQUIREMENT

      // Measure Blackboard View generation
      const blackboardStartTime = performance.now();
      useGraphStore.getState().generateBlackboardViewGraph();
      const blackboardEndTime = performance.now();
      const blackboardDuration = blackboardEndTime - blackboardStartTime;

      expect(blackboardDuration).toBeLessThan(100); // REQUIREMENT

      // Verify both views generated correctly
      const agentNodes = useGraphStore.getState().nodes;
      expect(agentNodes.length).toBeGreaterThan(0);
    });

    it('should toggle mode quickly with UI store update', async () => {
      const startMode = useUIStore.getState().mode;
      expect(startMode).toBe('agent');

      const startTime = performance.now();
      useUIStore.getState().setMode('blackboard');
      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(10); // Mode toggle should be instant
      expect(useUIStore.getState().mode).toBe('blackboard');

      // Toggle back
      useUIStore.getState().setMode('agent');
      expect(useUIStore.getState().mode).toBe('agent');
    });

    it('should handle rapid mode toggling', async () => {
      const agents: Agent[] = [
        {
          id: 'agent-1',
          name: 'agent-1',
          status: 'idle',
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 0,
          recvCount: 0,
        },
      ];

      useGraphStore.getState().batchUpdate({ agents });

      // Rapidly toggle modes
      const iterations = 10;
      const startTime = performance.now();

      for (let i = 0; i < iterations; i++) {
        const newMode = i % 2 === 0 ? 'blackboard' : 'agent';
        useUIStore.getState().setMode(newMode);

        if (useUIStore.getState().mode === 'agent') {
          useGraphStore.getState().generateAgentViewGraph();
        } else {
          useGraphStore.getState().generateBlackboardViewGraph();
        }
      }

      const endTime = performance.now();
      const totalDuration = endTime - startTime;
      const avgDuration = totalDuration / iterations;

      expect(avgDuration).toBeLessThan(100); // Average should be under 100ms
    });
  });

  describe('Graph Updates on WebSocket Events', () => {
    it('should update graph when new agent is added', async () => {
      useGraphStore.getState().generateAgentViewGraph();

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      expect(screen.getByTestId('node-count')).toHaveTextContent('0');

      // Simulate WebSocket event adding an agent
      const newAgent: Agent = {
        id: 'new-agent',
        name: 'new-agent',
        status: 'running',
        subscriptions: ['TestType'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };

      useGraphStore.getState().addAgent(newAgent);
      useGraphStore.getState().generateAgentViewGraph();

      await waitFor(() => {
        expect(screen.getByTestId('node-count')).toHaveTextContent('1');
        expect(screen.getByTestId('node-new-agent')).toBeInTheDocument();
      });
    });

    it('should update graph when new message is published', async () => {
      const agents: Agent[] = [
        {
          id: 'producer',
          name: 'producer',
          status: 'idle',
          subscriptions: [],
          lastActive: Date.now(),
          sentCount: 0,
          recvCount: 0,
        },
        {
          id: 'consumer',
          name: 'consumer',
          status: 'idle',
          subscriptions: ['TestType'],
          lastActive: Date.now(),
          sentCount: 0,
          recvCount: 0,
        },
      ];

      useGraphStore.getState().batchUpdate({ agents });
      useGraphStore.getState().generateAgentViewGraph();

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      const initialEdgeCount = useGraphStore.getState().edges.length;

      // Simulate WebSocket event publishing a message
      const newMessage: Message = {
        id: 'new-msg',
        type: 'TestType',
        payload: { data: 'test' },
        timestamp: Date.now(),
        correlationId: 'corr-1',
        producedBy: 'producer',
      };

      useGraphStore.getState().addMessage(newMessage);
      // Phase 11 fix: Record consumption to create edge
      useGraphStore.getState().recordConsumption(['new-msg'], 'consumer');
      useGraphStore.getState().generateAgentViewGraph();

      await waitFor(() => {
        const newEdgeCount = useGraphStore.getState().edges.length;
        expect(newEdgeCount).toBeGreaterThan(initialEdgeCount);
      });
    });

    it('should handle incremental updates efficiently', async () => {
      const initialAgents: Agent[] = Array.from({ length: 5 }, (_, i) => ({
        id: `agent-${i}`,
        name: `agent-${i}`,
        status: 'idle' as const,
        subscriptions: [],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      }));

      useGraphStore.getState().batchUpdate({ agents: initialAgents });
      useGraphStore.getState().generateAgentViewGraph();

      // Measure incremental update performance
      const startTime = performance.now();

      const newAgent: Agent = {
        id: 'agent-new',
        name: 'agent-new',
        status: 'running',
        subscriptions: [],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };

      useGraphStore.getState().addAgent(newAgent);
      useGraphStore.getState().generateAgentViewGraph();

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Incremental update should be very fast (<50ms)
      expect(duration).toBeLessThan(50);

      const nodes = useGraphStore.getState().nodes;
      expect(nodes).toHaveLength(6);
    });
  });

  describe('Empty States', () => {
    it('should render empty Agent View gracefully', async () => {
      useGraphStore.getState().generateAgentViewGraph();

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('node-count')).toHaveTextContent('0');
        expect(screen.getByTestId('edge-count')).toHaveTextContent('0');
      });
    });

    it('should render empty Blackboard View gracefully', async () => {
      useGraphStore.getState().generateBlackboardViewGraph();
      useUIStore.setState({ mode: 'blackboard' });

      render(
        <ReactFlowProvider>
          <MockGraphCanvas />
        </ReactFlowProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('mode-indicator')).toHaveTextContent('blackboard');
        expect(screen.getByTestId('node-count')).toHaveTextContent('0');
        expect(screen.getByTestId('edge-count')).toHaveTextContent('0');
      });
    });
  });
});
