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
  const syntheticRuns = new Map(runs);

  const producedBuckets = new Map<string, Set<string>>();
  const consumedBuckets = new Map<string, Set<string>>();

  // Helper to build bucket keys based on agent + correlation
  const makeBucketKey = (agentId: string, correlationId: string) =>
    `${agentId}::${correlationId || 'uncorrelated'}`;

  // Track (agent, correlation) pairs that already have explicit run data
  const existingRunBuckets = new Set<string>();
  runs.forEach((run) => {
    existingRunBuckets.add(makeBucketKey(run.agent_name, run.correlation_id));
  });

  messages.forEach((message) => {
    artifacts.set(message.id, messageToArtifact(message, consumptions));

    if (message.producedBy) {
      const key = makeBucketKey(message.producedBy, message.correlationId);
      if (!producedBuckets.has(key)) {
        producedBuckets.set(key, new Set());
      }
      producedBuckets.get(key)!.add(message.id);
    }
  });

  consumptions.forEach((consumerIds, artifactId) => {
    const message = messages.get(artifactId);
    const correlationId = message?.correlationId ?? '';
    consumerIds.forEach((consumerId) => {
      const key = makeBucketKey(consumerId, correlationId);
      if (!consumedBuckets.has(key)) {
        consumedBuckets.set(key, new Set());
      }
      consumedBuckets.get(key)!.add(artifactId);
    });
  });

  let syntheticCounter = 0;
  consumedBuckets.forEach((consumedSet, key) => {
    if (consumedSet.size === 0) {
      return;
    }
    const producedSet = producedBuckets.get(key);
    if (!producedSet || producedSet.size === 0) {
      return;
    }

    if (existingRunBuckets.has(key)) {
      return;
    }

    const [agentIdRaw, correlationPartRaw] = key.split('::');
    const agentId = agentIdRaw || 'unknown-agent';
    const correlationPart = correlationPartRaw || 'uncorrelated';
    const runId = `historic_${agentId}_${correlationPart}_${syntheticCounter++}`;

    if (!syntheticRuns.has(runId)) {
      syntheticRuns.set(runId, {
        run_id: runId,
        agent_name: agentId,
        correlation_id: correlationPart === 'uncorrelated' ? '' : correlationPart,
        status: 'completed',
        consumed_artifacts: Array.from(consumedSet),
        produced_artifacts: Array.from(producedSet),
      });
    }
  });

  return {
    artifacts,
    runs: syntheticRuns,
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
        // Re-apply active filters so newly generated nodes respect current selections
        useGraphStore.getState().applyFilters();
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
              tags: message.tags || [],
              visibilityKind: message.visibilityKind || 'Unknown',
            },
          });
        });

        // Derive edges using transform algorithm
        const dashboardState = toDashboardState(messages, runs, consumptions);
        const edges = deriveBlackboardViewEdges(dashboardState);

        set({ nodes, edges });
        // Ensure filters are reapplied after regeneration
        useGraphStore.getState().applyFilters();
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
            const consumptions = new Map(state.consumptions);
            update.messages.forEach((m) => {
              messages.set(m.id, m);
              if (m.consumedBy && m.consumedBy.length > 0) {
                consumptions.set(m.id, Array.from(new Set(m.consumedBy)));
              }
            });
            newState.messages = messages;
            newState.events = [...update.messages, ...state.events].slice(0, 100);
            newState.consumptions = consumptions;
          }

          if (update.runs) {
            const runs = new Map(state.runs);
            update.runs.forEach((r) => runs.set(r.run_id, r));
            newState.runs = runs;
          }

          return newState;
        }),

      applyFilters: () => {
        const { nodes, edges, messages, consumptions } = get();
        const {
          correlationId,
          timeRange,
          selectedArtifactTypes,
          selectedProducers,
          selectedTags,
          selectedVisibility,
        } = useFilterStore.getState();

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
          return { start: Number.NEGATIVE_INFINITY, end: Number.POSITIVE_INFINITY };
        };

        const { start: timeStart, end: timeEnd } = getTimeRangeBoundaries();

        const visibleMessageIds = new Set<string>();
        const producedStats = new Map<string, { total: number; byType: Record<string, number> }>();
        const consumedStats = new Map<string, { total: number; byType: Record<string, number> }>();

        const incrementStat = (
          map: Map<string, { total: number; byType: Record<string, number> }>,
          key: string,
          type: string
        ) => {
          if (!map.has(key)) {
            map.set(key, { total: 0, byType: {} });
          }
          const entry = map.get(key)!;
          entry.total += 1;
          entry.byType[type] = (entry.byType[type] || 0) + 1;
        };

        messages.forEach((message) => {
          let visible = true;

          if (correlationId && message.correlationId !== correlationId) {
            visible = false;
          }

          if (visible && (message.timestamp < timeStart || message.timestamp > timeEnd)) {
            visible = false;
          }

          if (
            visible &&
            selectedArtifactTypes.length > 0 &&
            !selectedArtifactTypes.includes(message.type)
          ) {
            visible = false;
          }

          if (
            visible &&
            selectedProducers.length > 0 &&
            !selectedProducers.includes(message.producedBy)
          ) {
            visible = false;
          }

          if (
            visible &&
            selectedVisibility.length > 0 &&
            !selectedVisibility.includes(message.visibilityKind || 'Unknown')
          ) {
            visible = false;
          }

          if (visible && selectedTags.length > 0) {
            const messageTags = message.tags || [];
            const hasAllTags = selectedTags.every((tag) => messageTags.includes(tag));
            if (!hasAllTags) {
              visible = false;
            }
          }

          if (visible) {
            visibleMessageIds.add(message.id);
            incrementStat(producedStats, message.producedBy, message.type);

            const consumers = consumptions.get(message.id) || [];
            consumers.forEach((consumerId) => {
              incrementStat(consumedStats, consumerId, message.type);
            });
          }
        });

        const updatedNodes = nodes.map((node) => {
          if (node.type === 'message') {
            return {
              ...node,
              hidden: !visibleMessageIds.has(node.id),
            };
          }
          if (node.type === 'agent') {
            const produced = producedStats.get(node.id);
            const consumed = consumedStats.get(node.id);
            const currentData = node.data as AgentNodeData;
            return {
              ...node,
              hidden: false,
              data: {
                ...node.data,
                sentCount: produced?.total ?? currentData.sentCount ?? 0,
                recvCount: consumed?.total ?? currentData.recvCount ?? 0,
                sentByType: produced?.byType ?? currentData.sentByType ?? {},
                receivedByType: consumed?.byType ?? currentData.receivedByType ?? {},
              },
            };
          }
          return node;
        });

        const updatedEdges = edges.map((edge) => {
          let hidden = edge.hidden ?? false;
          const data: any = edge.data;
          if (data && Array.isArray(data.artifactIds) && data.artifactIds.length > 0) {
            hidden = data.artifactIds.every((artifactId: string) => !visibleMessageIds.has(artifactId));
          } else {
            const sourceNode = updatedNodes.find((n) => n.id === edge.source);
            const targetNode = updatedNodes.find((n) => n.id === edge.target);
            hidden = !!(sourceNode?.hidden || targetNode?.hidden);
          }
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
