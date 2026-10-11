import { indexedDBService } from '../services/indexeddb';
import { useFilterStore } from '../store/filterStore';
import { useGraphStore } from '../store/graphStore';
import { useModuleStore } from '../store/moduleStore';
import { useSettingsStore } from '../store/settingsStore';
import { useUIStore } from '../store/uiStore';

/**
 * Forget what the dashboard keeps in this browser (graph, filters, windows,
 * saved layouts and presets, settings), then reload. Other apps on the same
 * origin keep their data, and the blackboard itself is untouched. While
 * another dashboard tab holds the database open, `onBlocked` is told and the
 * reload waits for that tab to close.
 */
export async function clearDashboardData(
  reload: () => void = () => window.location.reload(),
  onBlocked?: () => void,
): Promise<void> {
  useGraphStore.setState({
    events: [],
    nodes: [],
    edges: [],
    statistics: null,
    agentStatus: new Map(),
    streamingTokens: new Map(),
  });
  useModuleStore.getState().instances.clear();

  await indexedDBService.deleteDatabase(onBlocked);
  for (const store of [useFilterStore, useSettingsStore, useUIStore, useModuleStore]) {
    store.persist.clearStorage();
  }
  // Only now: a reload any earlier could drop the deletion
  reload();
}
