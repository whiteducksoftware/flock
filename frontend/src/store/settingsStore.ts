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
    agentIdleColor: string;
    agentActiveColor: string;
    agentErrorColor: string;
    nodeShadow: 'none' | 'small' | 'medium' | 'large';
    showStatusPulse: boolean;
    compactNodeView: boolean;
    theme: string;
  };

  advanced: {
    layoutDirection: 'TB' | 'LR';
    nodeSpacing: number;
    rankSpacing: number;
    debugMode: boolean;
    performanceMode: boolean;
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
  setAgentIdleColor: (color: string) => void;
  setAgentActiveColor: (color: string) => void;
  setAgentErrorColor: (color: string) => void;
  setNodeShadow: (shadow: SettingsState['appearance']['nodeShadow']) => void;
  setShowStatusPulse: (show: boolean) => void;
  setCompactNodeView: (compact: boolean) => void;

  // Advanced Actions
  setLayoutDirection: (direction: SettingsState['advanced']['layoutDirection']) => void;
  setNodeSpacing: (spacing: number) => void;
  setRankSpacing: (spacing: number) => void;
  setDebugMode: (enabled: boolean) => void;
  setPerformanceMode: (enabled: boolean) => void;

  // Utility Actions
  resetToDefaults: () => void;
}

const DEFAULT_SETTINGS: Omit<SettingsState, keyof ReturnType<typeof createActions>> = {
  version: '1.0.0',

  ui: {
    showFilters: false, // Hidden by default
    showControls: true, // Shown by default
    showSettings: false, // Hidden by default
  },

  graph: {
    edgeType: 'bezier',
    edgeStrokeWidth: 3,
    edgeAnimation: true,
    showEdgeLabels: true,
  },

  appearance: {
    agentIdleColor: '#60a5fa', // Blue
    agentActiveColor: '#10b981', // Green
    agentErrorColor: '#ef4444', // Red
    nodeShadow: 'medium',
    showStatusPulse: true,
    compactNodeView: false,
    theme: 'default',
  },

  advanced: {
    layoutDirection: 'LR',
    nodeSpacing: 75,       // Horizontal spacing between nodes
    rankSpacing: 150,      // Vertical spacing between ranks
    debugMode: false,
    performanceMode: false,
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

  setAgentIdleColor: (color: string) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, agentIdleColor: color } })),

  setAgentActiveColor: (color: string) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, agentActiveColor: color } })),

  setAgentErrorColor: (color: string) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, agentErrorColor: color } })),

  setNodeShadow: (shadow: SettingsState['appearance']['nodeShadow']) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, nodeShadow: shadow } })),

  setShowStatusPulse: (show: boolean) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, showStatusPulse: show } })),

  setCompactNodeView: (compact: boolean) =>
    set((state: SettingsState) => ({ appearance: { ...state.appearance, compactNodeView: compact } })),

  // Advanced Actions
  setLayoutDirection: (direction: SettingsState['advanced']['layoutDirection']) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, layoutDirection: direction } })),

  setNodeSpacing: (spacing: number) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, nodeSpacing: spacing } })),

  setRankSpacing: (spacing: number) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, rankSpacing: spacing } })),

  setDebugMode: (enabled: boolean) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, debugMode: enabled } })),

  setPerformanceMode: (enabled: boolean) =>
    set((state: SettingsState) => ({ advanced: { ...state.advanced, performanceMode: enabled } })),

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
    }
  )
);
