/**
 * Settings Store
 *
 * Manages all user preferences and customization settings.
 * Persisted to localStorage for cross-session persistence.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface SettingsState {
  version: string; // For future migrations

  ui: {
    showFilters: boolean;
    showControls: boolean;
    showSettings: boolean;
  };

  graph: {
    edgeType: 'smoothstep' | 'bezier' | 'straight' | 'simplebezier';
    edgeStrokeWidth: number;
    edgeAnimation: boolean;
    showEdgeLabels: boolean;
  };

  appearance: {
    theme: string;
  };

  advanced: {
    nodeSpacing: number;
    rankSpacing: number;
  };

  // UI Actions
  setShowFilters: (show: boolean) => void;
  setShowControls: (show: boolean) => void;
  setShowSettings: (show: boolean) => void;

  // Graph Actions
  setEdgeType: (edgeType: SettingsState['graph']['edgeType']) => void;
  setEdgeStrokeWidth: (width: number) => void;
  setEdgeAnimation: (enabled: boolean) => void;
  setShowEdgeLabels: (show: boolean) => void;

  // Appearance Actions
  setTheme: (theme: string) => void;

  // Advanced Actions
  setNodeSpacing: (spacing: number) => void;
  setRankSpacing: (spacing: number) => void;

  // Utility Actions
  resetToDefaults: () => void;
}

const DEFAULT_SETTINGS: Omit<SettingsState, keyof ReturnType<typeof createActions>> = {
  version: '1.0.0',

  // Which panels are open; not saved, so the dashboard opens on the board
  ui: {
    showFilters: false,
    showControls: false,
    showSettings: false,
  },

  graph: {
    edgeType: 'bezier',
    edgeStrokeWidth: 1.5,
    edgeAnimation: true,
    showEdgeLabels: true,
  },

  appearance: {
    theme: 'graphite',
  },

  advanced: {
    nodeSpacing: 75,       // Horizontal spacing between nodes
    rankSpacing: 150,      // Vertical spacing between ranks
  },
};

const createActions = (set: any) => ({
  // UI Actions
  setShowFilters: (show: boolean) =>
    set((state: SettingsState) => ({ ui: { ...state.ui, showFilters: show } })),

  setShowControls: (show: boolean) =>
    set((state: SettingsState) => ({ ui: { ...state.ui, showControls: show } })),

  setShowSettings: (show: boolean) =>
    set((state: SettingsState) => ({ ui: { ...state.ui, showSettings: show } })),

  // Graph Actions
  setEdgeType: (edgeType: SettingsState['graph']['edgeType']) =>
    set((state: SettingsState) => ({ graph: { ...state.graph, edgeType } })),

  setEdgeStrokeWidth: (width: number) =>
    set((state: SettingsState) => ({ graph: { ...state.graph, edgeStrokeWidth: width } })),

  setEdgeAnimation: (enabled: boolean) =>
    set((state: SettingsState) => ({ graph: { ...state.graph, edgeAnimation: enabled } })),

  setShowEdgeLabels: (show: boolean) =>
    set((state: SettingsState) => ({ graph: { ...state.graph, showEdgeLabels: show } })),

  // Appearance Actions
  setTheme: (theme: string) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, theme } })),

  // Advanced Actions
  setNodeSpacing: (spacing: number) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, nodeSpacing: spacing } })),

  setRankSpacing: (spacing: number) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, rankSpacing: spacing } })),


  // Utility Actions
  resetToDefaults: () => set(DEFAULT_SETTINGS),
});

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      ...DEFAULT_SETTINGS,
      ...createActions(set),
    }),
    {
      name: 'flock-flow-settings',
      version: 1,
      partialize: ({ ui: _ui, ...saved }) => saved,
      // Sessions before this one saved the open panels too, and settings that are gone
      // (layout direction, debug and performance mode); a saved section may lack newer keys
      merge: (persisted, current) => {
        const saved = (persisted ?? {}) as Partial<SettingsState>;
        return {
          ...current,
          graph: { ...current.graph, ...saved.graph },
          appearance: { ...current.appearance, ...saved.appearance },
          advanced: {
            nodeSpacing: saved.advanced?.nodeSpacing ?? current.advanced.nodeSpacing,
            rankSpacing: saved.advanced?.rankSpacing ?? current.advanced.rankSpacing,
          },
        };
      },
    }
  )
);
