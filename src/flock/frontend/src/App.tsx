import { useEffect } from 'react';
import DashboardLayout from './components/layout/DashboardLayout';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { measureRenderTime } from './utils/performance';
import { initializeWebSocket } from './services/websocket';
import { registerModules } from './components/modules/registerModules';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { fetchRegisteredAgents, fetchArtifactSummary, fetchArtifacts } from './services/api';
import { useGraphStore } from './store/graphStore';
import { useUIStore } from './store/uiStore';
import { useFilterStore } from './store/filterStore';
import { mapArtifactToMessage } from './utils/artifacts';
import { indexedDBService } from './services/indexeddb';

// Register modules once at module load time
registerModules();

const App: React.FC = () => {
  // Enable global keyboard shortcuts
  useKeyboardShortcuts();

  useEffect(() => {
    const startMark = 'app-initial-render-start';
    performance.mark(startMark);

    // Measure after first render
    requestAnimationFrame(() => {
      const duration = measureRenderTime('App (initial)', startMark, 'app-initial-render-end');
      if (duration < 200) {
        console.log('[Performance] ✓ Initial render under 200ms target');
      } else {
        console.warn('[Performance] ✗ Initial render exceeded 200ms target');
      }
    });

    const loadHistoricalData = async () => {
      try {
        await indexedDBService.initialize();

        const filterStore = useFilterStore.getState();
        const graphStore = useGraphStore.getState();
        const uiStore = useUIStore.getState();

        const summary = await fetchArtifactSummary();
        filterStore.setSummary(summary);
        filterStore.updateAvailableFacets({
          artifactTypes: Object.keys(summary.by_type),
          producers: Object.keys(summary.by_producer),
          tags: Object.keys(summary.tag_counts),
          visibilities: Object.keys(summary.by_visibility),
        });

        const artifactResponse = await fetchArtifacts({ limit: 200, embedMeta: true });
        const messages = artifactResponse.items.map(mapArtifactToMessage);
        if (messages.length > 0) {
          graphStore.batchUpdate({ messages });
          if (uiStore.mode === 'blackboard') {
            graphStore.generateBlackboardViewGraph();
          } else {
            graphStore.generateAgentViewGraph();
          }
          graphStore.applyFilters();

          const correlationMetadata = new Map<string, { correlation_id: string; first_seen: number; artifact_count: number; run_count: number }>();
          artifactResponse.items.forEach((item) => {
            if (!item.correlation_id) return;
            const timestamp = new Date(item.created_at).getTime();
            const existing = correlationMetadata.get(item.correlation_id);
            if (existing) {
              existing.artifact_count += 1;
              existing.first_seen = Math.min(existing.first_seen, timestamp);
            } else {
              correlationMetadata.set(item.correlation_id, {
                correlation_id: item.correlation_id,
                first_seen: timestamp,
                artifact_count: 1,
                run_count: 0,
              });
            }
          });
          if (correlationMetadata.size > 0) {
            filterStore.updateAvailableCorrelationIds(Array.from(correlationMetadata.values()));
          }
        }
      } catch (error) {
        console.error('[App] Failed to load historical artifacts:', error);
      }
    };

    // Load registered agents from orchestrator
    // This pre-populates the graph with all agent nodes before any events occur
    const loadInitialAgents = async () => {
      try {
        console.log('[App] Fetching registered agents...');
        const agents = await fetchRegisteredAgents();
        console.log(`[App] Loaded ${agents.length} registered agents`);

        const graphStore = useGraphStore.getState();
        const uiStore = useUIStore.getState();

        // Add all agents to the store
        agents.forEach(agent => graphStore.addAgent(agent));

        // Generate initial graph layout based on current view mode
        if (uiStore.mode === 'agent') {
          graphStore.generateAgentViewGraph();
        } else {
          graphStore.generateBlackboardViewGraph();
        }
      } catch (error) {
        console.error('[App] Failed to load registered agents:', error);
        // Graceful degradation: agents will appear when they activate via WebSocket
      }
    };

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
    const wsClient = initializeWebSocket(wsUrl);
    let cancelled = false;

    const bootstrap = async () => {
      await loadHistoricalData();
      await loadInitialAgents();

      if (!cancelled) {
        wsClient.connect();
      }
    };

    bootstrap().catch((error) => {
      console.error('[App] Bootstrap failed:', error);
    });

    // Cleanup on unmount
    return () => {
      cancelled = true;
      wsClient.disconnect();
    };
  }, []);

  return (
    <ErrorBoundary>
      <DashboardLayout />
    </ErrorBoundary>
  );
};

export default App;
