import { indexedDBService } from '../services/indexeddb';
import { useFilterStore } from '../store/filterStore';
import { useGraphStore } from '../store/graphStore';
import { useSettingsStore } from '../store/settingsStore';
import { useUIStore } from '../store/uiStore';

/**
 * Forget what the dashboard keeps in this browser (graph, filters, windows,
 * saved layouts and presets, settings), then reload. Other apps on the same
 * origin keep their data, and the blackboard itself is untouched. While
 * another dashboard tab holds the database open, `onBlocked` is told and the
 * reload waits for that tab to close. When the database cannot be deleted it
 * rejects, and nothing else is cleared.
 */
export async function clearDashboardData(
  reload: () => void = () => window.location.reload(),
  onBlocked?: () => void,
): Promise<void> {
  await indexedDBService.deleteDatabase(onBlocked);

  // Cleared only once the database is gone; a failure leaves the dashboard as it was
  useGraphStore.setState({
    events: [],
    nodes: [],
    edges: [],
    statistics: null,
    agentStatus: new Map(),
    streamingTokens: new Map(),
  });
  for (const store of [useFilterStore, useSettingsStore, useUIStore]) {
    store.persist.clearStorage();
  }
  // The module windows' saved state, from dashboards before the timeline dock
  localStorage.removeItem('flock-module-state');
  // Only now: a reload any earlier could drop the deletion
  reload();
}
