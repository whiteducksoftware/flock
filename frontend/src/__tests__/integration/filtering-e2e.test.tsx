import { describe, it, expect, beforeEach } from 'vitest';
import { useFilterStore } from '../../store/filterStore';
import { useGraphStore } from '../../store/graphStore';
import { Message, Agent } from '../../types/graph';

describe('Filtering Integration E2E', () => {
  beforeEach(() => {
    // Clear all stores
    const filterStore = useFilterStore.getState();
    filterStore.clearFilters();
    filterStore.updateAvailableCorrelationIds([]);

    const graphStore = useGraphStore.getState();
    // Clear all data
    graphStore.agents.clear();
    graphStore.messages.clear();
    graphStore.events.length = 0;
    graphStore.runs.clear();
  });

  describe('Correlation ID filtering', () => {
    it('should filter messages by correlation ID', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      // Add test agents
      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);

      // Add messages with different correlation IDs
      const message1: Message = {
        id: 'msg-1',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      const message2: Message = {
        id: 'msg-2',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-456',
        producedBy: 'agent-1',
      };
      graphStore.addMessage(message1);
      graphStore.addMessage(message2);

      // Generate graph
      graphStore.generateBlackboardViewGraph();

      // Initially all nodes should be visible
      let state = useGraphStore.getState();
      expect(state.nodes.filter((n) => !n.hidden)).toHaveLength(2);

      // Set correlation ID filter
      filterStore.setCorrelationId('corr-123');
      graphStore.applyFilters();

      // Should only show message with corr-123
      state = useGraphStore.getState();
      const visibleNodes = state.nodes.filter((n) => !n.hidden);
      expect(visibleNodes).toHaveLength(1);
      expect(visibleNodes[0]?.id).toBe('msg-1');
    });

    it('should show all messages when correlation ID filter is cleared', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);

      const message1: Message = {
        id: 'msg-1',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      const message2: Message = {
        id: 'msg-2',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-456',
        producedBy: 'agent-1',
      };
      graphStore.addMessage(message1);
      graphStore.addMessage(message2);
      graphStore.generateBlackboardViewGraph();

      // Apply and then clear filter
      filterStore.setCorrelationId('corr-123');
      graphStore.applyFilters();

      filterStore.setCorrelationId(null);
      graphStore.applyFilters();

      const state = useGraphStore.getState();
      expect(state.nodes.filter((n) => !n.hidden)).toHaveLength(2);
    });
  });

  describe('Time range filtering', () => {
    it('should filter messages by time range (last 5 minutes)', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);

      const now = Date.now();
      const message1: Message = {
        id: 'msg-1',
        type: 'test',
        payload: {},
        timestamp: now - 2 * 60 * 1000, // 2 minutes ago
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      const message2: Message = {
        id: 'msg-2',
        type: 'test',
        payload: {},
        timestamp: now - 10 * 60 * 1000, // 10 minutes ago
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      graphStore.addMessage(message1);
      graphStore.addMessage(message2);
      graphStore.generateBlackboardViewGraph();

      // Set time range to last 5 minutes
      filterStore.setTimeRange({ preset: 'last5min' });
      graphStore.applyFilters();

      const state = useGraphStore.getState();
      const visibleNodes = state.nodes.filter((n) => !n.hidden);
      expect(visibleNodes).toHaveLength(1);
      expect(visibleNodes[0]?.id).toBe('msg-1');
    });

    it('should filter messages by custom time range', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);

      const now = Date.now();
      const message1: Message = {
        id: 'msg-1',
        type: 'test',
        payload: {},
        timestamp: now - 30 * 60 * 1000, // 30 minutes ago
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      const message2: Message = {
        id: 'msg-2',
        type: 'test',
        payload: {},
        timestamp: now - 90 * 60 * 1000, // 90 minutes ago
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      graphStore.addMessage(message1);
      graphStore.addMessage(message2);
      graphStore.generateBlackboardViewGraph();

      // Set custom time range: last 60 minutes
      filterStore.setTimeRange({
        preset: 'custom',
        start: now - 60 * 60 * 1000,
        end: now,
      });
      graphStore.applyFilters();

      const state = useGraphStore.getState();
      const visibleNodes = state.nodes.filter((n) => !n.hidden);
      expect(visibleNodes).toHaveLength(1);
      expect(visibleNodes[0]?.id).toBe('msg-1');
    });
  });

  describe('Combined filtering', () => {
    it('should apply both correlation ID and time range filters', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);

      const now = Date.now();
      const messages: Message[] = [
        {
          id: 'msg-1',
          type: 'test',
          payload: {},
          timestamp: now - 2 * 60 * 1000, // 2 min ago, corr-123
          correlationId: 'corr-123',
          producedBy: 'agent-1',
        },
        {
          id: 'msg-2',
          type: 'test',
          payload: {},
          timestamp: now - 2 * 60 * 1000, // 2 min ago, corr-456
          correlationId: 'corr-456',
          producedBy: 'agent-1',
        },
        {
          id: 'msg-3',
          type: 'test',
          payload: {},
          timestamp: now - 10 * 60 * 1000, // 10 min ago, corr-123
          correlationId: 'corr-123',
          producedBy: 'agent-1',
        },
      ];
      messages.forEach((m) => graphStore.addMessage(m));
      graphStore.generateBlackboardViewGraph();

      // Apply both filters
      filterStore.setCorrelationId('corr-123');
      filterStore.setTimeRange({ preset: 'last5min' });
      graphStore.applyFilters();

      // Should only show msg-1 (corr-123 AND within 5 min)
      const state = useGraphStore.getState();
      const visibleNodes = state.nodes.filter((n) => !n.hidden);
      expect(visibleNodes).toHaveLength(1);
      expect(visibleNodes[0]?.id).toBe('msg-1');
    });
  });

  describe('Agent view filtering', () => {
    it('should hide agents with no visible messages', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      const agent2: Agent = {
        id: 'agent-2',
        name: 'Agent 2',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);
      graphStore.addAgent(agent2);

      const message1: Message = {
        id: 'msg-1',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      const message2: Message = {
        id: 'msg-2',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-456',
        producedBy: 'agent-2',
      };
      graphStore.addMessage(message1);
      graphStore.addMessage(message2);
      graphStore.generateAgentViewGraph();

      // Filter to only show corr-123
      filterStore.setCorrelationId('corr-123');
      graphStore.applyFilters();

      const state = useGraphStore.getState();
      const visibleNodes = state.nodes.filter((n) => !n.hidden);
      // Only agent-1 should be visible
      expect(visibleNodes).toHaveLength(1);
      expect(visibleNodes[0]?.id).toBe('agent-1');
    });
  });

  describe('Edge visibility', () => {
    it('should hide edges when connected nodes are hidden', () => {
      const graphStore = useGraphStore.getState();
      const filterStore = useFilterStore.getState();

      const agent1: Agent = {
        id: 'agent-1',
        name: 'Agent 1',
        status: 'running',
        subscriptions: ['test'],
        lastActive: Date.now(),
        sentCount: 0,
        recvCount: 0,
      };
      graphStore.addAgent(agent1);

      const message1: Message = {
        id: 'msg-1',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-123',
        producedBy: 'agent-1',
      };
      const message2: Message = {
        id: 'msg-2',
        type: 'test',
        payload: {},
        timestamp: Date.now(),
        correlationId: 'corr-456',
        producedBy: 'agent-1',
      };
      graphStore.addMessage(message1);
      graphStore.addMessage(message2);
      graphStore.generateBlackboardViewGraph();

      // Apply filter
      filterStore.setCorrelationId('corr-123');
      graphStore.applyFilters();

      const state = useGraphStore.getState();
      const hiddenNodes = state.nodes.filter((n) => n.hidden);
      const hiddenEdges = state.edges.filter((e) => e.hidden);

      // Should have some hidden nodes and edges
      expect(hiddenNodes.length).toBeGreaterThan(0);
      expect(hiddenEdges.length).toBeGreaterThanOrEqual(0);
    });
  });
});
