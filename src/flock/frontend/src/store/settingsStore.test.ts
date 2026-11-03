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

  it('loads settings an earlier dashboard saved, without the ones that are gone', async () => {
    localStorage.setItem(
      'flock-flow-settings',
      JSON.stringify({
        state: {
          // An older graph section without the labels switch, and the removed advanced settings
          graph: { edgeType: 'straight', edgeStrokeWidth: 2, edgeAnimation: false },
          advanced: { layoutDirection: 'TB', nodeSpacing: 90, rankSpacing: 200, debugMode: true, performanceMode: true },
          appearance: { theme: 'paper' },
        },
        version: 1,
      }),
    );

    await useSettingsStore.persist.rehydrate();

    const state = useSettingsStore.getState();
    expect(state.graph).toEqual({ edgeType: 'straight', edgeStrokeWidth: 2, edgeAnimation: false, showEdgeLabels: true });
    expect(state.advanced).toEqual({ nodeSpacing: 90, rankSpacing: 200 });
    expect(state.appearance.theme).toBe('paper');
  });
});
