import { useEffect } from 'react';
import DashboardLayout from './components/layout/DashboardLayout';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { measureRenderTime } from './utils/performance';
import { initializeWebSocket } from './services/websocket';
import { registerModules } from './components/modules/registerModules';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { fetchArtifactSummary, fetchArtifacts } from './services/api';
import { useGraphStore } from './store/graphStore';
import { useUIStore } from './store/uiStore';
import { useFilterStore } from './store/filterStore';
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

        // UI Optimization Migration (Phase 2/4 - Spec 002): Backend-driven architecture
        // Fetch artifact summary to populate filter facets
        //    Note: Node positions are now loaded automatically in generateAgentViewGraph/generateBlackboardViewGraph
        const summary = await fetchArtifactSummary();
        filterStore.setSummary(summary);
        filterStore.updateAvailableFacets({
          artifactTypes: Object.keys(summary.by_type),
          producers: Object.keys(summary.by_producer),
          tags: Object.keys(summary.tag_counts),
          visibilities: Object.keys(summary.by_visibility),
        });

        // Fetch correlation IDs for filter dropdown
        const artifactResponse = await fetchArtifacts({ limit: 200, embedMeta: true });
        if (artifactResponse.items.length > 0) {
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

        // Generate initial graph view from backend snapshot
        //    (GraphCanvas useEffect will handle initial render based on mode)
        //    No need to manually trigger here - happens in GraphCanvas mount
      } catch (error) {
        console.error('[App] Failed to load historical artifacts:', error);
      }
    };

    // UI Optimization Migration (Phase 2/4 - Spec 002): Simplified initial graph load
    // Backend snapshot includes all agents + artifacts + edges in a single call
    const loadInitialGraph = async () => {
      try {
        console.log('[App] Loading initial graph from backend snapshot...');
        const graphStore = useGraphStore.getState();
        const uiStore = useUIStore.getState();

        // Fetch complete graph snapshot from backend (includes agents + artifacts + edges)
        if (uiStore.mode === 'agent') {
          await graphStore.generateAgentViewGraph();
        } else {
          await graphStore.generateBlackboardViewGraph();
        }

        console.log('[App] Initial graph loaded from backend');
      } catch (error) {
        console.error('[App] Failed to load initial graph:', error);
        // Graceful degradation: graph will populate as WebSocket events arrive
      }
    };

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8344/ws';
    const wsClient = initializeWebSocket(wsUrl);
    let cancelled = false;

    const bootstrap = async () => {
      await loadHistoricalData();
      await loadInitialGraph();

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
