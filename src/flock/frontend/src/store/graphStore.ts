import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Node, Edge } from '@xyflow/react';
import { GraphSnapshot, GraphStatistics, GraphRequest, AgentLogicOperations } from '../types/graph';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from '../services/graphService';
import { useFilterStore } from './filterStore';
import { Message } from '../types/graph';
import { boundOf } from '../types/filters';
import { indexedDBService } from '../services/indexeddb';

/**
 * Graph Store - UI Optimization Migration (Spec 002)
 *
 * SIMPLIFIED backend-integrated version that replaces 553 lines of client-side
 * graph construction with backend snapshot consumption.
 *
 * KEY CHANGES:
 * - Backend generates nodes + edges + statistics
 * - Position merging: saved > current > backend > random
 * - WebSocket state overlay for real-time updates (status, tokens)
 * - Debounced refresh: 100ms batching for snappy UX
 * - No more client-side edge derivation
 * - No more synthetic runs or complex Maps
 *
 * Phase 1.3: Logic Operations UX
 * - Added logic operations state for JoinSpec/BatchSpec waiting states
 * - Real-time updates via CorrelationGroupUpdatedEvent and BatchItemAddedEvent
 */

/** How much of a running run's output the focus stage shows */
const RUN_TAIL_CHARS = 160;
/** How long a run that ended waits for its output on the board, at most */
const SETTLE_MS = 4000;

/** A running run: what it consumed, what its agent publishes, and what of that the board held when it started */
export interface InFlightRun {
  agent: string;
  types: string[];
  artifacts: string[];
  correlationId?: string | null;
  produces?: string[];
  known?: string[];
  /** What it published, once it ended (`endRun`) */
  published?: string[];
}

/**
 * An artifact a run published is drawn where it belongs: it is on the board
 * with the edge from what the run consumed (the server draws those once the
 * run is done); an output of a run that consumed nothing has none
 */
function drawn(id: string, run: InFlightRun, on: Set<string>, edges: Edge[]): boolean {
  return on.has(id) && (run.artifacts.length === 0 || edges.some((edge) => edge.target === id));
}

/** The agent's artifacts in a workflow on the board, but for a run's own streamed previews (they carry its artifacts' IDs) */
function outputsBefore(nodes: Node[], agent: string, correlationId: string | null | undefined, runId: string): string[] {
  return nodes
    .filter(
      (node) =>
        node.type === 'message' &&
        node.data.producedBy === agent &&
        (node.data.correlationId ?? null) === (correlationId ?? null) &&
        node.data.runId !== runId,
    )
    .map((node) => node.id);
}

interface GraphState {
  // Real-time WebSocket state (overlaid on backend snapshot)
  agentStatus: Map<string, string>;
  /**
   * Per running run, its agent and what it consumed: the types (edges in flight)
   * and artifact IDs; its run (correlation); the types its agent publishes; and
   * `known`, the agent's artifacts in the workflow when the run started (#642)
   */
  inFlight: Map<string, InFlightRun>;
  /**
   * Runs that ended and whose output is not on the board yet: it comes with the
   * next snapshot. The lanes keep their placeholders meanwhile (#642).
   */
  settling: Map<string, InFlightRun & { known: string[] }>;
  /** The filters the Blackboard's snapshot answers (`blackboardFilterKey` when they are the board's) */
  blackboardFilters: string | null;
  /** Per running run, the end of its streamed output (an agent's ticker mixes its runs) */
  runTails: Map<string, string>;
  streamingTokens: Map<string, string[]>;
  agentLogicOperations: Map<string, AgentLogicOperations[]>; // Phase 1.3: Logic operations state

  // Backend snapshot state
  nodes: Node[];
  edges: Edge[];
  statistics: GraphStatistics | null;
  /** The blackboard view holds the newest artifacts only (the server's limit) */
  truncated: boolean;

  // UI state
  events: Message[];
  viewMode: 'agent' | 'blackboard';

  // Position persistence (saved to IndexedDB)
  savedPositions: Map<string, { x: number; y: number }>;
  /** Positions that win over the saved ones while a node is unfolded; never saved */
  transientPositions: Map<string, { x: number; y: number }> | null;

  // Loading state
  isLoading: boolean;
  error: string | null;

  // Actions - Backend integration
  generateAgentViewGraph: () => Promise<void>;
  generateBlackboardViewGraph: () => Promise<void>;
  refreshCurrentView: () => Promise<void>;
  scheduleRefresh: () => void; // Debounced refresh (500ms)

  // Actions - Real-time WebSocket updates
  updateAgentStatus: (agentId: string, status: string) => void;
  setInFlight: (runId: string, agentId: string, types: string[] | null, artifacts?: string[], correlationId?: string | null, produces?: string[]) => void;
  /**
   * A run ended: it settles until a snapshot brings what it published, and one
   * that published nothing goes at once. Without `published` (null types to
   * setInFlight) it settles until the board shows an artifact of its agent in
   * its workflow that was not there when it started.
   */
  endRun: (runId: string, published?: string[]) => void;
  /** A run that ended stops settling: its output is on the board, or it waited long enough */
  settle: (runId: string) => void;
  appendRunTail: (runId: string, text: string) => void;
  /** Runs going on when the page connected, which it heard no start event of (their types are not known) */
  seedInFlight: (runs: { runId: string; agent: string; artifacts: string[]; correlationId: string | null }[]) => void;
  /** Drops the streaming previews of a run (all of them without arguments) */
  dropStreamingPreviews: (agent?: string, correlationId?: string | null, runId?: string | null) => void;
  updateStreamingTokens: (agentId: string, tokens: string[]) => void;
  updateAgentLogicOperations: (agentId: string, logicOps: AgentLogicOperations[]) => void; // Phase 1.3
  addEvent: (message: Message) => void;

  // Actions - Streaming message nodes (Phase 6)
  createOrUpdateStreamingMessageNode: (artifactId: string, token: string, eventData?: any) => void;
  finalizeStreamingMessageNode: (artifactId: string) => void;

  // Actions - Position persistence
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
  setNodePositions: (positions: Map<string, { x: number; y: number }>) => void;
  setTransientPositions: (positions: Map<string, { x: number; y: number }> | null) => void;
  saveNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
  loadSavedPositions: () => Promise<void>;

  // Actions - UI state
  setViewMode: (viewMode: 'agent' | 'blackboard') => void;
}

/**
 * Convert TimeRange (number timestamps) to TimeRangeFilter (ISO string timestamps)
 */
function convertTimeRange(range: { preset: string; start?: number; end?: number }): GraphRequest['filters']['time_range'] {
  const result: GraphRequest['filters']['time_range'] = {
    preset: range.preset as any,
  };

  const start = boundOf(range.start);
  const end = boundOf(range.end);
  if (start !== undefined) {
    result.start = new Date(start).toISOString();
  }
  if (end !== undefined) {
    result.end = new Date(end).toISOString();
  }

  return result;
}

/**
 * The types of a streamed artifact: an agent that publishes several streams
 * under all of them ("app.A, app.B"); a comma inside brackets belongs to a
 * generic type's name ("app.Pair[str, int]").
 */
export function streamedTypes(label: string): string[] {
  const types: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < label.length; i += 1) {
    const char = label[i];
    if (char === '[') depth += 1;
    else if (char === ']') depth -= 1;
    else if (char === ',' && depth === 0) {
      types.push(label.slice(start, i).trim());
      start = i + 1;
    }
  }
  types.push(label.slice(start).trim());
  return types.filter(Boolean);
}

/**
 * Whether an artifact the board did not load passes the board's filters: a
 * streaming preview, which has no tags yet (a tag filter keeps it out).
 */
function previewFilter(): (data: Record<string, any>) => boolean {
  const filters = buildGraphRequest('blackboard').filters;
  const timeRange = useFilterStore.getState().timeRange;
  const lastMinutes = { last5min: 5, last10min: 10, last1hour: 60 }[timeRange.preset as string];
  const from =
    timeRange.preset === 'custom'
      ? boundOf(timeRange.start)
      : lastMinutes !== undefined
        ? Date.now() - lastMinutes * 60_000
        : undefined;
  const to = timeRange.preset === 'custom' ? boundOf(timeRange.end) : undefined;
  return (data) =>
    (from === undefined || (data.timestamp ?? 0) >= from) &&
    (to === undefined || (data.timestamp ?? 0) <= to) &&
    (!filters.correlation_id || data.correlationId === filters.correlation_id) &&
    (filters.artifactTypes.length === 0 ||
      streamedTypes(String(data.artifactType ?? '')).some((type) => filters.artifactTypes.includes(type))) &&
    (filters.producers.length === 0 || filters.producers.includes(data.producedBy)) &&
    filters.tags.length === 0 &&
    (filters.visibility.length === 0 || filters.visibility.includes(data.visibilityKind ?? 'Public'));
}

// Counts the snapshot requests. An answer applies if it is newer than the one
// applied and was asked for the board's current view and filters: newer requests
// still loading (live refreshes in a row) do not hold it back, and an answer to
// filters changed meanwhile, or an older one arriving late, does not replace the board
let snapshotRequest = 0;
let appliedRequest = 0;
const requestKey = (viewMode: 'agent' | 'blackboard'): string => JSON.stringify(buildGraphRequest(viewMode));
const stillAsked = (mine: number, key: string, viewMode: 'agent' | 'blackboard', current: 'agent' | 'blackboard'): boolean =>
  mine > appliedRequest && current === viewMode && key === requestKey(viewMode);

/** The board's filters as the Blackboard's snapshot request carries them, to compare with `blackboardFilters`. */
export const blackboardFilterKey = (): string => JSON.stringify(buildGraphRequest('blackboard').filters);

/** The graph request for a view, from the current filter state. */
function buildGraphRequest(viewMode: 'agent' | 'blackboard'): GraphRequest {
  const filterState = useFilterStore.getState();

  return {
    viewMode,
    filters: {
      correlation_id: filterState.correlationId || null,
      time_range: convertTimeRange(filterState.timeRange),
      artifactTypes: filterState.selectedArtifactTypes,
      producers: filterState.selectedProducers,
      tags: filterState.selectedTags,
      visibility: filterState.selectedVisibility,
    },
    options: {
      include_statistics: true,
    },
  };
}

/**
 * Debounce timer for graph refresh (500ms batching)
 */
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/** Nodes placed where an unfolded board has them, if one is unfolded. */
const withTransientPositions = (nodes: Node[], positions: Map<string, { x: number; y: number }> | null): Node[] =>
  positions
    ? nodes.map((node) => {
        const position = positions.get(node.id);
        return position ? { ...node, position } : node;
      })
    : nodes;

export const useGraphStore = create<GraphState>()(
  devtools(
    (set, get) => ({
      // Initial state
      agentStatus: new Map(),
      inFlight: new Map(),
      settling: new Map(),
      blackboardFilters: null,
      runTails: new Map(),
      streamingTokens: new Map(),
      agentLogicOperations: new Map(), // Phase 1.3
      nodes: [],
      edges: [],
      statistics: null,
      truncated: false,
      events: [],
      viewMode: 'agent',
      savedPositions: new Map(),
      transientPositions: null,
      // The dashboard loads its board as it starts
      isLoading: true,
      error: null,

      // Backend integration actions
      generateAgentViewGraph: async () => {
        set({ isLoading: true, error: null, viewMode: 'agent' });
        const mine = ++snapshotRequest;

        try {
          // Load saved positions from IndexedDB first
          await get().loadSavedPositions();

          // The filters as the request goes out (they may change while positions load)
          const request = buildGraphRequest('agent');
          const key = JSON.stringify(request);
          const snapshot: GraphSnapshot = await fetchGraphSnapshot(request);
          if (!stillAsked(mine, key, 'agent', get().viewMode)) return;
          appliedRequest = mine;
          // The snapshot's countdowns (joins, batches) go on from here, on the monotonic clock
          const snapshotAt = performance.now();

          const { savedPositions, nodes: currentNodes, agentStatus, streamingTokens, agentLogicOperations } = get();

          // Merge positions: saved > current > backend > random
          const mergedNodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

          // Overlay real-time WebSocket state; the selected node stays selected
          const selected = new Set(currentNodes.filter((node) => node.selected).map((node) => node.id));
          const finalNodes = withTransientPositions(
            overlayWebSocketState(mergedNodes, agentStatus, streamingTokens, agentLogicOperations).map((node) => {
              const kept = selected.has(node.id) ? { ...node, selected: true } : node;
              return kept.type === 'agent' ? { ...kept, data: { ...kept.data, snapshotAt } } : kept;
            }),
            get().transientPositions,
          );

          set({
            nodes: finalNodes,
            edges: snapshot.edges as Edge[],
            statistics: snapshot.statistics,
            isLoading: false,
          });

          // Update filter facets from backend statistics
          if (snapshot.statistics?.artifactSummary) {
            const summary = snapshot.statistics.artifactSummary;
            const filterState = useFilterStore.getState();

            // Transform ArtifactSummary to FilterFacets format
            const facets = {
              artifactTypes: Object.keys(summary.by_type),
              producers: Object.keys(summary.by_producer),
              tags: Object.keys(summary.tag_counts),
              visibilities: Object.keys(summary.by_visibility),
            };

            // Support both updateAvailableFacets (production) and updateFacets (test mock)
            if ('updateAvailableFacets' in filterState && typeof filterState.updateAvailableFacets === 'function') {
              filterState.updateAvailableFacets(facets);
            } else if ('updateFacets' in filterState && typeof (filterState as any).updateFacets === 'function') {
              (filterState as any).updateFacets(facets);
            }
          }
        } catch (error) {
          // A newer request reports for the board
          if (mine !== snapshotRequest) return;
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch graph';
          set({
            error: errorMessage,
            isLoading: false,
          });
          throw error; // Re-throw for test assertions
        }
      },

      generateBlackboardViewGraph: async () => {
        set({ isLoading: true, error: null, viewMode: 'blackboard' });
        const mine = ++snapshotRequest;

        try {
          const request = buildGraphRequest('blackboard');
          const key = JSON.stringify(request);
          const snapshot: GraphSnapshot = await fetchGraphSnapshot(request);
          if (!stillAsked(mine, key, 'blackboard', get().viewMode)) return;
          appliedRequest = mine;

          // The lanes place artifacts themselves (no positions); an artifact
          // that still streams is not on the record yet and stays, if the
          // board's filters let it through
          const known = new Set(snapshot.nodes.map((node) => node.id));
          const passes = previewFilter();
          const streaming = get().nodes.filter(
            (node) => node.type === 'message' && node.data.isStreaming && !known.has(node.id) && passes(node.data),
          );

          // Runs that ended settle once their output is on the board: what they
          // published, or (not told) a new artifact of the agent in the workflow
          const settling = new Map(get().settling);
          const inSnapshot = new Set(snapshot.nodes.map((node) => node.id));
          for (const [runId, run] of settling) {
            const published = run.published
              ? run.published.some((id) => drawn(id, run, inSnapshot, snapshot.edges as Edge[]))
              : snapshot.nodes.some(
                  (node) =>
                    node.data?.producedBy === run.agent &&
                    (node.data?.correlationId ?? null) === (run.correlationId ?? null) &&
                    !run.known.includes(node.id),
                );
            if (published) settling.delete(runId);
          }

          set({
            nodes: [...(snapshot.nodes as Node[]), ...streaming],
            edges: snapshot.edges as Edge[],
            statistics: snapshot.statistics,
            truncated: snapshot.truncated,
            blackboardFilters: JSON.stringify(request.filters),
            isLoading: false,
            settling,
          });

          // Update filter facets from backend statistics
          if (snapshot.statistics?.artifactSummary) {
            const summary = snapshot.statistics.artifactSummary;
            const filterState = useFilterStore.getState();

            // Transform ArtifactSummary to FilterFacets format
            const facets = {
              artifactTypes: Object.keys(summary.by_type),
              producers: Object.keys(summary.by_producer),
              tags: Object.keys(summary.tag_counts),
              visibilities: Object.keys(summary.by_visibility),
            };

            // Support both updateAvailableFacets (production) and updateFacets (test mock)
            if ('updateAvailableFacets' in filterState && typeof filterState.updateAvailableFacets === 'function') {
              filterState.updateAvailableFacets(facets);
            } else if ('updateFacets' in filterState && typeof (filterState as any).updateFacets === 'function') {
              (filterState as any).updateFacets(facets);
            }
          }
        } catch (error) {
          // A newer request reports for the board
          if (mine !== snapshotRequest) return;
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch graph';
          set({
            error: errorMessage,
            isLoading: false,
          });
          throw error; // Re-throw for test assertions
        }
      },

      refreshCurrentView: async () => {
        const { viewMode } = get();
        if (viewMode === 'agent') {
          await get().generateAgentViewGraph();
        } else {
          await get().generateBlackboardViewGraph();
        }
      },

      scheduleRefresh: () => {
        // Clear existing timer if any (reset debounce)
        if (refreshTimer !== null) {
          clearTimeout(refreshTimer);
        }

        // Schedule refresh after 100ms of quiet time (snappy UX)
        refreshTimer = setTimeout(() => {
          refreshTimer = null;
          get().refreshCurrentView().catch((error) => {
            console.error('[GraphStore] Scheduled refresh failed:', error);
          });
        }, 100);
      },

      // Real-time WebSocket update actions
      setInFlight: (runId, agentId, types, artifacts = [], correlationId = null, produces = []) => {
        // A run that consumed nothing (a direct invocation, a timer) runs too; null ends it
        if (types === null) return get().endRun(runId);
        set((state) => {
          const inFlight = new Map(state.inFlight);
          const known = state.inFlight.get(runId)?.known ?? outputsBefore(state.nodes, agentId, correlationId, runId);
          inFlight.set(runId, { agent: agentId, types, artifacts, correlationId, produces, known });
          return { inFlight };
        });
      },

      endRun: (runId, published) => {
        const { inFlight: running, nodes, edges } = get();
        const ended = running.get(runId);
        // A run that ended settles until the board shows what it published,
        // unless a snapshot already drew all of it (with the edges that place it)
        const recorded = new Set(nodes.filter((node) => !node.data.isStreaming && node.data.streamingText === undefined).map((node) => node.id));
        const settles =
          ended !== undefined && (published === undefined || (published.length > 0 && !published.every((id) => drawn(id, ended, recorded, edges))));
        set((state) => {
          const inFlight = new Map(state.inFlight);
          inFlight.delete(runId);
          const changes: Partial<GraphState> = { inFlight };
          if (ended && settles) {
            const settling = new Map(state.settling);
            settling.set(runId, { ...ended, known: ended.known ?? [], published });
            changes.settling = settling;
          }
          // A run that ends takes its output's tail along
          if (state.runTails.has(runId)) {
            const runTails = new Map(state.runTails);
            runTails.delete(runId);
            changes.runTails = runTails;
          }
          return changes;
        });
        // One whose snapshot never comes (its output filtered out, a lost request) goes after a while
        if (settles) setTimeout(() => get().settle(runId), SETTLE_MS);
      },

      settle: (runId) => {
        set((state) => {
          if (!state.settling.has(runId)) return {};
          const settling = new Map(state.settling);
          settling.delete(runId);
          return { settling };
        });
      },

      dropStreamingPreviews: (agent, correlationId, runId) => {
        // A preview that knows its run goes with that run only; the agent may run again in the same workflow
        const ofRun = (data: Record<string, any>) => !runId || !data.runId || data.runId === runId;
        set((state) => {
          const nodes = state.nodes.filter(
            (node) =>
              !(
                node.type === 'message' &&
                node.data.isStreaming &&
                (agent === undefined || node.data.producedBy === agent) &&
                (correlationId === undefined || (node.data.correlationId ?? null) === correlationId) &&
                ofRun(node.data)
              ),
          );
          return nodes.length === state.nodes.length ? {} : { nodes };
        });
      },

      seedInFlight: (runs) => {
        set((state) => {
          const fresh = runs.filter((run) => !state.inFlight.has(run.runId));
          if (fresh.length === 0) return {};
          const inFlight = new Map(state.inFlight);
          for (const run of fresh) {
            inFlight.set(run.runId, {
              agent: run.agent,
              types: [],
              artifacts: run.artifacts,
              correlationId: run.correlationId,
              known: outputsBefore(state.nodes, run.agent, run.correlationId, run.runId),
            });
          }
          return { inFlight };
        });
      },

      appendRunTail: (runId, text) => {
        set((state) => {
          const runTails = new Map(state.runTails);
          runTails.set(runId, ((state.runTails.get(runId) ?? '') + text).slice(-RUN_TAIL_CHARS));
          return { runTails };
        });
      },

      updateAgentStatus: (agentId, status) => {
        set((state) => {
          const agentStatus = new Map(state.agentStatus);
          agentStatus.set(agentId, status);

          // Inline overlay logic (don't use overlayWebSocketState which gets mocked in tests)
          const nodes = state.nodes.map(node => {
            if (node.type === 'agent' && node.id === agentId) {
              return {
                ...node,
                data: {
                  ...node.data,
                  status: status,
                },
              };
            }
            return node;
          });

          return { agentStatus, nodes };
        });
      },

      updateStreamingTokens: (agentId, tokens) => {
        set((state) => {
          const streamingTokens = new Map(state.streamingTokens);
          streamingTokens.set(agentId, tokens);

          // Inline overlay logic (don't use overlayWebSocketState which gets mocked in tests)
          const nodes = state.nodes.map(node => {
            if (node.type === 'agent' && node.id === agentId) {
              return {
                ...node,
                data: {
                  ...node.data,
                  streamingTokens: tokens.slice(-6), // Keep only last 6 tokens
                },
              };
            }
            return node;
          });

          return { streamingTokens, nodes };
        });
      },

      // Phase 1.3: Logic Operations UX - Update agent logic operations state
      updateAgentLogicOperations: (agentId, logicOps) => {
        set((state) => {
          const agentLogicOperations = new Map(state.agentLogicOperations);
          agentLogicOperations.set(agentId, logicOps);

          // Update agent nodes with logic operations data
          const nodes = state.nodes.map(node => {
            if (node.type === 'agent' && node.id === agentId) {
              return {
                ...node,
                data: {
                  ...node.data,
                  logicOperations: logicOps,
                },
              };
            }
            return node;
          });

          return { agentLogicOperations, nodes };
        });
      },

      addEvent: (message) => {
        set((state) => {
          // Add to events array (max 100 items)
          const isDuplicate = state.events.some(e => e.id === message.id);
          if (isDuplicate) {
            return state; // Skip duplicates
          }

          const events = [message, ...state.events].slice(0, 100);
          return { events };
        });
      },

      // Streaming message nodes (Phase 6)
      createOrUpdateStreamingMessageNode: (artifactId, token, eventData) => {
        set((state) => {
          // Only create/update streaming message nodes in blackboard view
          // Message nodes should never appear in agent view
          if (state.viewMode !== 'blackboard') {
            console.log(`[GraphStore] Ignoring streaming message node in ${state.viewMode} view`);
            return state; // No changes
          }

          const existingNode = state.nodes.find(n => n.id === artifactId);

          if (existingNode) {
            // Update existing streaming node
            const currentText = (existingNode.data.streamingText as string) || '';
            const updatedNodes = state.nodes.map(node => {
              if (node.id === artifactId) {
                return {
                  ...node,
                  data: {
                    ...node.data,
                    streamingText: currentText + token,
                    isStreaming: true,
                  },
                };
              }
              return node;
            });
            return { nodes: updatedNodes };
          } else {
            // Create new streaming message node
            const newNode: Node = {
              id: artifactId,
              type: 'message',
              position: { x: Math.random() * 500, y: Math.random() * 500 }, // Random position
              data: {
                artifactType: eventData?.artifact_type || 'Unknown',
                payload: {},
                producedBy: eventData?.agent_name || 'Unknown',
                timestamp: Date.now(),
                streamingText: token,
                isStreaming: true,
                tags: [],
                visibilityKind: 'Public',
                correlationId: eventData?.correlation_id || '',
                // The run streaming it: when the run ends, its preview goes
                runId: eventData?.run_id ?? null,
              },
            };
            // Only what the board's filters let through: another run's preview would make a lane of its own
            if (!previewFilter()(newNode.data)) return state;
            return { nodes: [...state.nodes, newNode] };
          }
        });
      },

      finalizeStreamingMessageNode: (artifactId) => {
        set((state) => {
          const nodes = state.nodes.map(node => {
            if (node.id === artifactId && node.data.isStreaming) {
              return {
                ...node,
                data: {
                  ...node.data,
                  isStreaming: false,
                  // streamingText is kept so MessageNode can display it until backend refresh
                },
              };
            }
            return node;
          });

          return { nodes };
        });
      },

      setNodePositions: (positions) => {
        set((state) => ({
          nodes: state.nodes.map((node) => {
            const position = positions.get(node.id);
            return position ? { ...node, position } : node;
          }),
        }));
      },

      setTransientPositions: (positions) => set({ transientPositions: positions }),

      // Position persistence actions
      updateNodePosition: (nodeId, position) => {
        set((state) => {
          const nodes = state.nodes.map(node =>
            node.id === nodeId ? { ...node, position } : node
          );
          return { nodes };
        });
      },

      saveNodePosition: (nodeId, position) => {
        set((state) => {
          const savedPositions = new Map(state.savedPositions);
          savedPositions.set(nodeId, position);

          // Save to IndexedDB using indexedDBService
          const viewMode = state.viewMode;
          const layoutRecord = {
            node_id: nodeId,
            x: position.x,
            y: position.y,
            last_updated: new Date().toISOString(),
          };

          if (viewMode === 'agent') {
            indexedDBService.saveAgentViewLayout(layoutRecord).catch(console.error);
          } else {
            indexedDBService.saveBlackboardViewLayout(layoutRecord).catch(console.error);
          }

          return { savedPositions };
        });
      },

      loadSavedPositions: async () => {
        try {
          const viewMode = get().viewMode;
          let layouts: Array<{ node_id: string; x: number; y: number; last_updated: string }> = [];

          if (viewMode === 'agent') {
            layouts = await indexedDBService.getAllAgentViewLayouts();
          } else {
            layouts = await indexedDBService.getAllBlackboardViewLayouts();
          }

          // Convert to Map
          const positions = new Map<string, { x: number; y: number }>();
          layouts.forEach((layout) => {
            positions.set(layout.node_id, { x: layout.x, y: layout.y });
          });

          set({ savedPositions: positions });
          console.log(`[GraphStore] Loaded ${positions.size} saved positions for ${viewMode} view`);
        } catch (error) {
          console.error('[GraphStore] Failed to load saved positions:', error);
        }
      },

      // UI state actions
      setViewMode: (viewMode) => {
        set({ viewMode });
      },
    }),
    { name: 'graphStore' }
  )
);
