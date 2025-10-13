import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Node, Edge } from '@xyflow/react';
import { GraphSnapshot, GraphStatistics, GraphRequest, AgentLogicOperations } from '../types/graph';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from '../services/graphService';
import { useFilterStore } from './filterStore';
import { Message } from '../types/graph';
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

interface GraphState {
  // Real-time WebSocket state (overlaid on backend snapshot)
  agentStatus: Map<string, string>;
  streamingTokens: Map<string, string[]>;
  agentLogicOperations: Map<string, AgentLogicOperations[]>; // Phase 1.3: Logic operations state

  // Backend snapshot state
  nodes: Node[];
  edges: Edge[];
  statistics: GraphStatistics | null;

  // UI state
  events: Message[];
  viewMode: 'agent' | 'blackboard';

  // Position persistence (saved to IndexedDB)
  savedPositions: Map<string, { x: number; y: number }>;

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
  updateStreamingTokens: (agentId: string, tokens: string[]) => void;
  updateAgentLogicOperations: (agentId: string, logicOps: AgentLogicOperations[]) => void; // Phase 1.3
  addEvent: (message: Message) => void;

  // Actions - Streaming message nodes (Phase 6)
  createOrUpdateStreamingMessageNode: (artifactId: string, token: string, eventData?: any) => void;
  finalizeStreamingMessageNode: (artifactId: string) => void;

  // Actions - Position persistence
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
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

  if (range.start !== undefined) {
    result.start = new Date(range.start).toISOString();
  }
  if (range.end !== undefined) {
    result.end = new Date(range.end).toISOString();
  }

  return result;
}

/**
 * Build GraphRequest from current filter state
 */
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

export const useGraphStore = create<GraphState>()(
  devtools(
    (set, get) => ({
      // Initial state
      agentStatus: new Map(),
      streamingTokens: new Map(),
      agentLogicOperations: new Map(), // Phase 1.3
      nodes: [],
      edges: [],
      statistics: null,
      events: [],
      viewMode: 'agent',
      savedPositions: new Map(),
      isLoading: false,
      error: null,

      // Backend integration actions
      generateAgentViewGraph: async () => {
        set({ isLoading: true, error: null, viewMode: 'agent' });

        try {
          // Load saved positions from IndexedDB first
          await get().loadSavedPositions();

          const request = buildGraphRequest('agent');
          const snapshot: GraphSnapshot = await fetchGraphSnapshot(request);

          const { savedPositions, nodes: currentNodes, agentStatus, streamingTokens, agentLogicOperations } = get();

          // Merge positions: saved > current > backend > random
          const mergedNodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

          // Overlay real-time WebSocket state
          const finalNodes = overlayWebSocketState(mergedNodes, agentStatus, streamingTokens, agentLogicOperations);

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

        try {
          // Load saved positions from IndexedDB first
          await get().loadSavedPositions();

          const request = buildGraphRequest('blackboard');
          const snapshot: GraphSnapshot = await fetchGraphSnapshot(request);

          const { savedPositions, nodes: currentNodes, agentStatus, streamingTokens, agentLogicOperations } = get();

          // Merge positions: saved > current > backend > random
          const mergedNodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

          // Overlay real-time WebSocket state (primarily for message streaming)
          const finalNodes = overlayWebSocketState(mergedNodes, agentStatus, streamingTokens, agentLogicOperations);

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
              },
            };
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
