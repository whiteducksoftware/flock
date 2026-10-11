import { beforeEach, describe, expect, it } from 'vitest';
import { useSettingsStore } from './settingsStore';

describe('settingsStore', () => {
  beforeEach(() => {
    localStorage.clear();
    useSettingsStore.getState().resetToDefaults();
  });

  it('starts with every panel closed', () => {
    expect(useSettingsStore.getState().ui).toEqual({
      showFilters: false,
      showControls: false,
      showSettings: false,
    });
  });

  it('restores the settings but not which panels were open', async () => {
    // Saved by an earlier session that had the publish panel open
    localStorage.setItem(
      'flock-flow-settings',
      JSON.stringify({
        state: {
          ui: { showFilters: true, showControls: true, showSettings: true },
          graph: { edgeType: 'straight', edgeStrokeWidth: 2, edgeAnimation: false, showEdgeLabels: false },
        },
        version: 1,
      }),
    );

    await useSettingsStore.persist.rehydrate();

    expect(useSettingsStore.getState().graph.edgeType).toBe('straight');
    expect(useSettingsStore.getState().ui.showControls).toBe(false);
    expect(useSettingsStore.getState().ui.showSettings).toBe(false);
    expect(useSettingsStore.getState().ui.showFilters).toBe(false);
  });

  it('does not save which panels are open', () => {
    useSettingsStore.getState().setShowControls(true);

    const saved = JSON.parse(localStorage.getItem('flock-flow-settings') ?? '{}');
    expect(saved.state.ui).toBeUndefined();
  });
});
