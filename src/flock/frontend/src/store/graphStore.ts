import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Node, Edge } from '@xyflow/react';
import { GraphSnapshot, GraphStatistics, GraphRequest } from '../types/graph';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from '../services/graphService';
import { useFilterStore } from './filterStore';
import { Message } from '../types/graph';

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
 * - No more client-side edge derivation
 * - No more synthetic runs or complex Maps
 */

interface GraphState {
  // Real-time WebSocket state (overlaid on backend snapshot)
  agentStatus: Map<string, string>;
  streamingTokens: Map<string, string[]>;

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
  addEvent: (message: Message) => void;

  // Actions - Position persistence
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
  saveNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
  loadSavedPositions: () => Promise<void>;

  // Actions - UI state
  setViewMode: (viewMode: 'agent' | 'blackboard') => void;
}

/**
 * IndexedDB helpers for position persistence
 */
const DB_NAME = 'flock-dashboard';
const DB_VERSION = 1;
const STORE_NAME = 'node-positions';

async function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
  });
}

async function savePositionToDB(nodeId: string, position: { x: number; y: number }): Promise<void> {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  const store = tx.objectStore(STORE_NAME);
  store.put(position, nodeId);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function loadPositionsFromDB(): Promise<Map<string, { x: number; y: number }>> {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const store = tx.objectStore(STORE_NAME);
  const request = store.getAllKeys();

  return new Promise((resolve, reject) => {
    request.onsuccess = () => {
      const keys = request.result as string[];
      const positions = new Map<string, { x: number; y: number }>();

      let pending = keys.length;
      if (pending === 0) {
        resolve(positions);
        return;
      }

      keys.forEach((key) => {
        const getRequest = store.get(key);
        getRequest.onsuccess = () => {
          positions.set(key, getRequest.result);
          pending--;
          if (pending === 0) {
            resolve(positions);
          }
        };
        getRequest.onerror = () => reject(getRequest.error);
      });
    };
    request.onerror = () => reject(request.error);
  });
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
          const request = buildGraphRequest('agent');
          const snapshot: GraphSnapshot = await fetchGraphSnapshot(request);

          const { savedPositions, nodes: currentNodes, agentStatus, streamingTokens } = get();

          // Merge positions: saved > current > backend > random
          const mergedNodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

          // Overlay real-time WebSocket state
          const finalNodes = overlayWebSocketState(mergedNodes, agentStatus, streamingTokens);

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
          const request = buildGraphRequest('blackboard');
          const snapshot: GraphSnapshot = await fetchGraphSnapshot(request);

          const { savedPositions, nodes: currentNodes, agentStatus, streamingTokens } = get();

          // Merge positions: saved > current > backend > random
          const mergedNodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

          // Overlay real-time WebSocket state (primarily for message streaming)
          const finalNodes = overlayWebSocketState(mergedNodes, agentStatus, streamingTokens);

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

        // Schedule refresh after 500ms of quiet time
        refreshTimer = setTimeout(() => {
          refreshTimer = null;
          get().refreshCurrentView().catch((error) => {
            console.error('[GraphStore] Scheduled refresh failed:', error);
          });
        }, 500);
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

          // Save to IndexedDB
          savePositionToDB(nodeId, position).catch(console.error);

          return { savedPositions };
        });
      },

      loadSavedPositions: async () => {
        try {
          const positions = await loadPositionsFromDB();
          set({ savedPositions: positions });
        } catch (error) {
          console.error('Failed to load saved positions:', error);
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
