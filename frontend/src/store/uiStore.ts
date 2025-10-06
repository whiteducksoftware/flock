import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export type VisualizationMode = 'agent' | 'blackboard';

interface DetailWindow {
  nodeId: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  activeTab: 'liveOutput' | 'messageHistory' | 'runStatus';
}

interface UIState {
  // Visualization mode
  mode: VisualizationMode;
  setMode: (mode: VisualizationMode) => void;

  // Node selection
  selectedNodeIds: Set<string>;
  selectNode: (nodeId: string) => void;
  deselectNode: (nodeId: string) => void;
  clearSelection: () => void;

  // Detail windows
  detailWindows: Map<string, DetailWindow>;
  openDetailWindow: (nodeId: string) => void;
  closeDetailWindow: (nodeId: string) => void;
  updateDetailWindow: (nodeId: string, updates: Partial<DetailWindow>) => void;

  // Layout preferences
  layoutDirection: 'TB' | 'LR';
  setLayoutDirection: (direction: 'TB' | 'LR') => void;
  autoLayoutEnabled: boolean;
  setAutoLayoutEnabled: (enabled: boolean) => void;

  // Preferences
  defaultTab: 'liveOutput' | 'messageHistory' | 'runStatus';
  setDefaultTab: (tab: 'liveOutput' | 'messageHistory' | 'runStatus') => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        mode: 'agent',
        setMode: (mode) => set({ mode }),

        selectedNodeIds: new Set(),
        selectNode: (nodeId) =>
          set((state) => ({
            selectedNodeIds: new Set(state.selectedNodeIds).add(nodeId),
          })),
        deselectNode: (nodeId) =>
          set((state) => {
            const ids = new Set(state.selectedNodeIds);
            ids.delete(nodeId);
            return { selectedNodeIds: ids };
          }),
        clearSelection: () => set({ selectedNodeIds: new Set() }),

        detailWindows: new Map(),
        openDetailWindow: (nodeId) =>
          set((state) => {
            const windows = new Map(state.detailWindows);
            if (!windows.has(nodeId)) {
              windows.set(nodeId, {
                nodeId,
                position: { x: 100 + windows.size * 20, y: 100 + windows.size * 20 },
                size: { width: 600, height: 400 },
                activeTab: state.defaultTab,
              });
            }
            return { detailWindows: windows };
          }),
        closeDetailWindow: (nodeId) =>
          set((state) => {
            const windows = new Map(state.detailWindows);
            windows.delete(nodeId);
            return { detailWindows: windows };
          }),
        updateDetailWindow: (nodeId, updates) =>
          set((state) => {
            const windows = new Map(state.detailWindows);
            const existing = windows.get(nodeId);
            if (existing) {
              windows.set(nodeId, { ...existing, ...updates });
            }
            return { detailWindows: windows };
          }),

        layoutDirection: 'TB',
        setLayoutDirection: (direction) => set({ layoutDirection: direction }),
        autoLayoutEnabled: true,
        setAutoLayoutEnabled: (enabled) => set({ autoLayoutEnabled: enabled }),

        defaultTab: 'liveOutput',
        setDefaultTab: (tab) => set({ defaultTab: tab }),
      }),
      {
        name: 'ui-storage',
        partialize: (state) => ({
          defaultTab: state.defaultTab,
          layoutDirection: state.layoutDirection,
          autoLayoutEnabled: state.autoLayoutEnabled,
        }),
      }
    ),
    { name: 'uiStore' }
  )
);
