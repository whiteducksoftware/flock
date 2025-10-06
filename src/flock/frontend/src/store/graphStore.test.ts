import { describe, it, expect, beforeEach } from 'vitest';
import { useGraphStore } from './graphStore';
import { Agent, Message } from '../types/graph';

describe('graphStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useGraphStore.setState({
      agents: new Map(),
      messages: new Map(),
      events: [],
      nodes: [],
      edges: [],
    });
  });

  it('should add an agent', () => {
    const agent: Agent = {
      id: 'test-agent',
      name: 'test-agent',
      status: 'idle',
      subscriptions: ['Movie'],
      lastActive: Date.now(),
      sentCount: 0,
      recvCount: 0,
    };

    useGraphStore.getState().addAgent(agent);

    const agents = useGraphStore.getState().agents;
    expect(agents.size).toBe(1);
    expect(agents.get('test-agent')).toEqual(agent);
  });

  it('should update an agent', () => {
    const agent: Agent = {
      id: 'test-agent',
      name: 'test-agent',
      status: 'idle',
      subscriptions: [],
      lastActive: Date.now(),
      sentCount: 0,
      recvCount: 0,
    };

    useGraphStore.getState().addAgent(agent);
    useGraphStore.getState().updateAgent('test-agent', { status: 'running', sentCount: 5 });

    const updatedAgent = useGraphStore.getState().agents.get('test-agent');
    expect(updatedAgent?.status).toBe('running');
    expect(updatedAgent?.sentCount).toBe(5);
  });

  it('should add a message', () => {
    const message: Message = {
      id: 'msg-1',
      type: 'Movie',
      payload: { title: 'Test Movie' },
      timestamp: Date.now(),
      correlationId: 'corr-1',
      producedBy: 'movie',
    };

    useGraphStore.getState().addMessage(message);

    const messages = useGraphStore.getState().messages;
    const events = useGraphStore.getState().events;
    expect(messages.size).toBe(1);
    expect(messages.get('msg-1')).toEqual(message);
    expect(events.length).toBe(1);
    expect(events[0]).toEqual(message);
  });

  it('should limit events to 100', () => {
    for (let i = 0; i < 120; i++) {
      const message: Message = {
        id: `msg-${i}`,
        type: 'Movie',
        payload: { index: i },
        timestamp: Date.now(),
        correlationId: 'corr-1',
        producedBy: 'movie',
      };
      useGraphStore.getState().addMessage(message);
    }

    const events = useGraphStore.getState().events;
    expect(events.length).toBe(100);
  });

  it('should batch update agents and messages', () => {
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
      {
        id: 'agent-2',
        name: 'agent-2',
        status: 'running',
        subscriptions: [],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      },
    ];

    const messages: Message[] = [
      {
        id: 'msg-1',
        type: 'Movie',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-1',
        producedBy: 'agent-1',
      },
    ];

    useGraphStore.getState().batchUpdate({ agents, messages });

    expect(useGraphStore.getState().agents.size).toBe(2);
    expect(useGraphStore.getState().messages.size).toBe(1);
    expect(useGraphStore.getState().events.length).toBe(1);
  });

  it('should generate agent view graph', () => {
    const agents: Agent[] = [
      {
        id: 'movie',
        name: 'movie',
        status: 'idle',
        subscriptions: [],
        lastActive: Date.now(),
        sentCount: 2,
        recvCount: 0,
        position: { x: 0, y: 0 },
      },
      {
        id: 'tagline',
        name: 'tagline',
        status: 'idle',
        subscriptions: ['Movie'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 2,
        position: { x: 200, y: 0 },
      },
    ];

    const messages: Message[] = [
      {
        id: 'msg-1',
        type: 'Movie',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-1',
        producedBy: 'movie',
      },
      {
        id: 'msg-2',
        type: 'Movie',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-1',
        producedBy: 'movie',
      },
    ];

    useGraphStore.getState().batchUpdate({ agents, messages });
    // Phase 11 fix: Record consumption to populate consumed_by field
    useGraphStore.getState().recordConsumption(['msg-1', 'msg-2'], 'tagline');
    useGraphStore.getState().generateAgentViewGraph();

    const nodes = useGraphStore.getState().nodes;
    const edges = useGraphStore.getState().edges;

    expect(nodes.length).toBe(2);
    expect(nodes[0]?.type).toBe('agent');
    expect(edges.length).toBeGreaterThan(0);
  });
});
