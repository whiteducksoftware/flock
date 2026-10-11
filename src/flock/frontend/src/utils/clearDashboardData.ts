import { useFilterStore } from '../store/filterStore';
import { useGraphStore } from '../store/graphStore';
import { useModuleStore } from '../store/moduleStore';
import { useUIStore } from '../store/uiStore';

/**
 * Forget everything the dashboard keeps in this browser (graph, filters,
 * windows, saved layouts and presets) and reload. The blackboard itself is
 * untouched.
 */
export function clearDashboardData(): void {
  useGraphStore.setState({
    events: [],
    nodes: [],
    edges: [],
    statistics: null,
    agentStatus: new Map(),
    streamingTokens: new Map(),
  });
  useUIStore.setState({ mode: 'agent' });
  useFilterStore.getState().clearFilters();
  useModuleStore.getState().instances.clear();

  indexedDB.databases().then((databases) => {
    databases.forEach((database) => {
      if (database.name) indexedDB.deleteDatabase(database.name);
    });
  });
  localStorage.clear();
  window.location.reload();
}
