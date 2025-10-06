import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Node, Edge } from '@xyflow/react';
import { Agent, Message, AgentNodeData, MessageNodeData } from '../types/graph';
import { deriveAgentViewEdges, deriveBlackboardViewEdges, Artifact, Run, DashboardState } from '../utils/transforms';
import { useFilterStore } from './filterStore';

interface GraphState {
  // Core data
  agents: Map<string, Agent>;
  messages: Map<string, Message>;
  events: Message[];
  runs: Map<string, Run>;

  // Phase 11 Bug Fix: Track actual consumption (artifact_id -> consumer_ids[])
  // Updated by agent_activated events to reflect filtering and actual consumption
  consumptions: Map<string, string[]>;

  // Message node positions (message_id -> {x, y})
  // Messages don't have position in their data model, so we track it separately
  messagePositions: Map<string, { x: number; y: number }>;

  // Graph representation
  nodes: Node[];
  edges: Edge[];

  // Actions
  addAgent: (agent: Agent) => void;
  updateAgent: (id: string, updates: Partial<Agent>) => void;
  removeAgent: (id: string) => void;

  addMessage: (message: Message) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  addRun: (run: Run) => void;

  // Phase 11 Bug Fix: Track actual consumption from agent_activated events
  recordConsumption: (artifactIds: string[], consumerId: string) => void;

  // Transform streaming message to final message (changes ID)
  finalizeStreamingMessage: (oldId: string, newMessage: Message) => void;

  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void;

  // Mode-specific graph generation
  generateAgentViewGraph: () => void;
  generateBlackboardViewGraph: () => void;

  // Filter application
  applyFilters: () => void;

  // Bulk updates
  batchUpdate: (update: { agents?: Agent[]; messages?: Message[]; runs?: Run[] }) => void;
}

// Helper function to convert Message to Artifact
function messageToArtifact(message: Message, consumptions: Map<string, string[]>): Artifact {
  // BUG FIX: Use ACTUAL consumption data from consumptions Map, not inferred from subscriptions!
  // This ensures edges reflect what actually happened, not what "should" happen based on current subscriptions.
  const actualConsumers = consumptions.get(message.id) || [];

  return {
    artifact_id: message.id,
    artifact_type: message.type,
    produced_by: message.producedBy,
    consumed_by: actualConsumers,  // Use actual consumption data
    published_at: new Date(message.timestamp).toISOString(),
    payload: message.payload,
    correlation_id: message.correlationId,
  };
}

// Helper function to convert store state to DashboardState
function toDashboardState(
  messages: Map<string, Message>,
  runs: Map<string, Run>,
  consumptions: Map<string, string[]>
): DashboardState {
  const artifacts = new Map<string, Artifact>();

  messages.forEach((message) => {
    artifacts.set(message.id, messageToArtifact(message, consumptions));
  });

  return {
    artifacts,
    runs,
    consumptions, // Phase 11: Pass actual consumption data for filtered count calculation
  };
}

export const useGraphStore = create<GraphState>()(
  devtools(
    (set, get) => ({
      agents: new Map(),
      messages: new Map(),
      events: [],
      runs: new Map(),
      consumptions: new Map(), // Phase 11: Track actual artifact consumption
      messagePositions: new Map(), // Track message node positions
      nodes: [],
      edges: [],

      addAgent: (agent) =>
        set((state) => {
          const agents = new Map(state.agents);
          agents.set(agent.id, agent);
          return { agents };
        }),

      updateAgent: (id, updates) =>
        set((state) => {
          const agents = new Map(state.agents);
          const agent = agents.get(id);
          if (agent) {
            agents.set(id, { ...agent, ...updates });
          }
          return { agents };
        }),

      removeAgent: (id) =>
        set((state) => {
          const agents = new Map(state.agents);
          agents.delete(id);
          return { agents };
        }),

      addMessage: (message) =>
        set((state) => {
          const messages = new Map(state.messages);
          messages.set(message.id, message);

          // Only add to events if this is a NEW message (not already in the array)
          // This prevents streaming token updates from flooding the Event Log
          const isDuplicate = state.events.some(e => e.id === message.id);
          const events = isDuplicate
            ? state.events  // Skip if already in events array
            : [message, ...state.events].slice(0, 100);  // Add new message

          return { messages, events };
        }),

      updateMessage: (id, updates) =>
        set((state) => {
          const messages = new Map(state.messages);
          const message = messages.get(id);
          if (message) {
            messages.set(id, { ...message, ...updates });
          }
          // Note: updateMessage does NOT touch the events array
          // This allows streaming updates without flooding the Event Log
          return { messages };
        }),

      addRun: (run) =>
        set((state) => {
          const runs = new Map(state.runs);
          runs.set(run.run_id, run);
          return { runs };
        }),

      // Phase 11 Bug Fix: Record actual consumption from agent_activated events
      recordConsumption: (artifactIds, consumerId) =>
        set((state) => {
          const consumptions = new Map(state.consumptions);
          artifactIds.forEach((artifactId) => {
            const existing = consumptions.get(artifactId) || [];
            if (!existing.includes(consumerId)) {
              consumptions.set(artifactId, [...existing, consumerId]);
            }
          });
          return { consumptions };
        }),

      finalizeStreamingMessage: (oldId, newMessage) =>
        set((state) => {
          // Remove old streaming message, add final message with new ID
          const messages = new Map(state.messages);
          messages.delete(oldId);
          messages.set(newMessage.id, newMessage);

          // Transfer position from old ID to new ID
          const messagePositions = new Map(state.messagePositions);
          const oldPos = messagePositions.get(oldId);
          if (oldPos) {
            messagePositions.delete(oldId);
            messagePositions.set(newMessage.id, oldPos);
          }

          // Update events array: replace streaming ID with final message ID
          const events = state.events.map(e =>
            e.id === oldId ? newMessage : e
          );

          return { messages, messagePositions, events };
        }),

      updateNodePosition: (nodeId, position) =>
        set((state) => {
          const agents = new Map(state.agents);
          const agent = agents.get(nodeId);
          if (agent) {
            // Update agent position
            agents.set(nodeId, { ...agent, position });
            return { agents };
          } else {
            // Must be a message node - update message position
            const messagePositions = new Map(state.messagePositions);
            messagePositions.set(nodeId, position);
            return { messagePositions };
          }
        }),

      generateAgentViewGraph: () => {
        const { agents, messages, runs, consumptions, nodes: currentNodes } = get();

        // Create a map of current node positions to preserve them during regeneration
        const currentPositions = new Map<string, { x: number; y: number }>();
        currentNodes.forEach(node => {
          currentPositions.set(node.id, node.position);
        });

        const nodes: Node<AgentNodeData>[] = [];

        // Create nodes from agents
        agents.forEach((agent) => {
          // Preserve position priority: saved position > current React Flow position > default
          const position = agent.position
            || currentPositions.get(agent.id)
            || { x: 400 + Math.random() * 200, y: 300 + Math.random() * 200 };

          nodes.push({
            id: agent.id,
            type: 'agent',
            position,
            data: {
              name: agent.name,
              status: agent.status,
              subscriptions: agent.subscriptions,
              outputTypes: agent.outputTypes,
              sentCount: agent.sentCount,
              recvCount: agent.recvCount,
              receivedByType: agent.receivedByType,
              sentByType: agent.sentByType,
              streamingTokens: agent.streamingTokens,
            },
          });
        });

        // Derive edges using transform algorithm
        const dashboardState = toDashboardState(messages, runs, consumptions);
        const edges = deriveAgentViewEdges(dashboardState);

        set({ nodes, edges });
      },

      generateBlackboardViewGraph: () => {
        const { messages, runs, consumptions, messagePositions, nodes: currentNodes } = get();

        // Create a map of current node positions to preserve them during regeneration
        const currentPositions = new Map<string, { x: number; y: number }>();
        currentNodes.forEach(node => {
          currentPositions.set(node.id, node.position);
        });

        const nodes: Node<MessageNodeData>[] = [];

        // Create nodes from messages
        messages.forEach((message) => {
          const payloadStr = JSON.stringify(message.payload);

          // BUG FIX: Use ACTUAL consumption data from consumptions Map, not inferred from subscriptions!
          const consumedBy = consumptions.get(message.id) || [];

          // Preserve position priority: saved position > current React Flow position > default
          const position = messagePositions.get(message.id)
            || currentPositions.get(message.id)
            || { x: 400 + Math.random() * 200, y: 300 + Math.random() * 200 };

          nodes.push({
            id: message.id,
            type: 'message',
            position,
            data: {
              artifactType: message.type,
              payloadPreview: payloadStr.slice(0, 100),
              payload: message.payload, // Full payload for display
              producedBy: message.producedBy,
              consumedBy,  // Use actual consumption data
              timestamp: message.timestamp,
              isStreaming: message.isStreaming || false,
              streamingText: message.streamingText || '',
            },
          });
        });

        // Derive edges using transform algorithm
        const dashboardState = toDashboardState(messages, runs, consumptions);
        const edges = deriveBlackboardViewEdges(dashboardState);

        set({ nodes, edges });
      },

      batchUpdate: (update) =>
        set((state) => {
          const newState: Partial<GraphState> = {};

          if (update.agents) {
            const agents = new Map(state.agents);
            update.agents.forEach((a) => agents.set(a.id, a));
            newState.agents = agents;
          }

          if (update.messages) {
            const messages = new Map(state.messages);
            update.messages.forEach((m) => messages.set(m.id, m));
            newState.messages = messages;
            newState.events = [...update.messages, ...state.events].slice(0, 100);
          }

          if (update.runs) {
            const runs = new Map(state.runs);
            update.runs.forEach((r) => runs.set(r.run_id, r));
            newState.runs = runs;
          }

          return newState;
        }),

      applyFilters: () => {
        const { nodes, edges, messages } = get();
        const { correlationId, timeRange } = useFilterStore.getState();

        // Helper to calculate time range boundaries
        const getTimeRangeBoundaries = (): { start: number; end: number } => {
          const now = Date.now();
          if (timeRange.preset === 'last5min') {
            return { start: now - 5 * 60 * 1000, end: now };
          } else if (timeRange.preset === 'last10min') {
            return { start: now - 10 * 60 * 1000, end: now };
          } else if (timeRange.preset === 'last1hour') {
            return { start: now - 60 * 60 * 1000, end: now };
          } else if (timeRange.preset === 'custom' && timeRange.start && timeRange.end) {
            return { start: timeRange.start, end: timeRange.end };
          }
          return { start: now - 10 * 60 * 1000, end: now };
        };

        const { start: timeStart, end: timeEnd } = getTimeRangeBoundaries();

        // Filter messages based on correlation ID and time range
        const visibleMessageIds = new Set<string>();
        messages.forEach((message) => {
          let visible = true;

          // Apply correlation ID filter (selective)
          if (correlationId && message.correlationId !== correlationId) {
            visible = false;
          }

          // Apply time range filter (in-memory)
          if (visible && (message.timestamp < timeStart || message.timestamp > timeEnd)) {
            visible = false;
          }

          if (visible) {
            visibleMessageIds.add(message.id);
          }
        });

        // Update nodes visibility
        const updatedNodes = nodes.map((node) => {
          if (node.type === 'message') {
            // For message nodes, check if message is visible
            return {
              ...node,
              hidden: !visibleMessageIds.has(node.id),
            };
          } else if (node.type === 'agent') {
            // For agent nodes, show if any visible messages involve this agent
            let hasVisibleMessages = false;
            messages.forEach((message) => {
              if (visibleMessageIds.has(message.id)) {
                if (message.producedBy === node.id) {
                  hasVisibleMessages = true;
                }
              }
            });
            return {
              ...node,
              hidden: !hasVisibleMessages,
            };
          }
          return node;
        });

        // Update edges visibility
        const updatedEdges = edges.map((edge) => {
          // Hide edge if either source or target node is hidden
          const sourceNode = updatedNodes.find((n) => n.id === edge.source);
          const targetNode = updatedNodes.find((n) => n.id === edge.target);
          const hidden = sourceNode?.hidden || targetNode?.hidden || false;

          return {
            ...edge,
            hidden,
          };
        });

        set({ nodes: updatedNodes, edges: updatedEdges });
      },
    }),
    { name: 'graphStore' }
  )
);
