import { useEffect } from 'react';
import DashboardLayout from './components/layout/DashboardLayout';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { measureRenderTime } from './utils/performance';
import { initializeWebSocket } from './services/websocket';
import { registerModules } from './components/modules/registerModules';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { fetchRegisteredAgents } from './services/api';
import { useGraphStore } from './store/graphStore';
import { useUIStore } from './store/uiStore';

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

    // Initialize WebSocket connection
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
    const wsClient = initializeWebSocket(wsUrl);
    wsClient.connect();

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

    loadInitialAgents();

    // Cleanup on unmount
    return () => {
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
