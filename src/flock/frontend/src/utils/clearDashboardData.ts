import { indexedDBService } from '../services/indexeddb';
import { useFilterStore } from '../store/filterStore';
import { useGraphStore } from '../store/graphStore';
import { useModuleStore } from '../store/moduleStore';
import { useUIStore } from '../store/uiStore';

/** Delete a database; a deletion another tab blocks finishes once it closes. */
const deleteDatabase = (name: string): Promise<void> =>
  new Promise((resolve) => {
    const request = indexedDB.deleteDatabase(name);
    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
    request.onblocked = () => resolve();
  });

/**
 * Forget everything the dashboard keeps in this browser (graph, filters,
 * windows, saved layouts and presets), then reload. The blackboard itself is
 * untouched.
 */
export async function clearDashboardData(
  reload: () => void = () => window.location.reload(),
): Promise<void> {
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

  // The dashboard's own connection would block the deletion
  indexedDBService.close();
  const databases = await indexedDB.databases();
  await Promise.all(databases.flatMap((database) => (database.name ? [deleteDatabase(database.name)] : [])));
  localStorage.clear();
  // Only now: a reload any earlier could drop the deletions
  reload();
}
