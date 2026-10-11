import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export type VisualizationMode = 'agent' | 'blackboard';
export type AutoLayoutMode =
  | 'hierarchical-horizontal'
  | 'hierarchical-vertical'
  | 'circular'
  | 'grid'
  | 'random';

interface DetailWindow {
  nodeId: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
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

  // The node unfolded on the board, one at a time (not saved)
  unfoldedNodeId: string | null;
  unfold: (nodeId: string) => void;
  fold: () => void;
  toggleUnfold: (nodeId: string) => void;

  // The node in focus: a full stage over the dimmed board (not saved)
  focusedNodeId: string | null;
  focus: (nodeId: string) => void;
  unfocus: () => void;

  // Artifact detail windows of the Blackboard view, until its cards unfold (#565); not saved
  detailWindows: Map<string, DetailWindow>;
  openDetailWindow: (nodeId: string) => void;
  closeDetailWindow: (nodeId: string) => void;
  updateDetailWindow: (nodeId: string, updates: Partial<DetailWindow>) => void;

  // Layout preferences
  layoutDirection: 'TB' | 'LR';
  setLayoutDirection: (direction: 'TB' | 'LR') => void;
  autoLayoutEnabled: boolean;
  setAutoLayoutEnabled: (enabled: boolean) => void;
  autoLayoutMode: AutoLayoutMode;
  setAutoLayoutMode: (mode: AutoLayoutMode) => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist<UIState>(
      (set) => ({
        mode: 'agent',
        setMode: (mode: VisualizationMode) => set({ mode }),

        selectedNodeIds: new Set(),
        selectNode: (nodeId: string) =>
          set((state) => ({
            selectedNodeIds: new Set(state.selectedNodeIds).add(nodeId),
          })),
        deselectNode: (nodeId: string) =>
          set((state) => {
            const ids = new Set(state.selectedNodeIds);
            ids.delete(nodeId);
            return { selectedNodeIds: ids };
          }),
        clearSelection: () => set({ selectedNodeIds: new Set() }),

        unfoldedNodeId: null,
        unfold: (nodeId: string) => set({ unfoldedNodeId: nodeId }),
        fold: () => set({ unfoldedNodeId: null }),
        toggleUnfold: (nodeId: string) =>
          set((state) => ({ unfoldedNodeId: state.unfoldedNodeId === nodeId ? null : nodeId })),

        focusedNodeId: null,
        focus: (nodeId: string) => set({ focusedNodeId: nodeId }),
        unfocus: () => set({ focusedNodeId: null }),

        detailWindows: new Map(),
        openDetailWindow: (nodeId: string) =>
          set((state) => {
            const windows = new Map(state.detailWindows);
            if (!windows.has(nodeId)) {
              windows.set(nodeId, {
                nodeId,
                position: { x: 100 + windows.size * 20, y: 100 + windows.size * 20 },
                size: { width: 600, height: 400 },
              });
            }
            return { detailWindows: windows };
          }),
        closeDetailWindow: (nodeId: string) =>
          set((state) => {
            const windows = new Map(state.detailWindows);
            windows.delete(nodeId);
            return { detailWindows: windows };
          }),
        updateDetailWindow: (nodeId: string, updates: Partial<DetailWindow>) =>
          set((state) => {
            const windows = new Map(state.detailWindows);
            const existing = windows.get(nodeId);
            if (existing) {
              windows.set(nodeId, { ...existing, ...updates });
            }
            return { detailWindows: windows };
          }),

        layoutDirection: 'TB',
        setLayoutDirection: (direction: 'TB' | 'LR') => set({ layoutDirection: direction }),
        autoLayoutEnabled: true,
        setAutoLayoutEnabled: (enabled: boolean) => set({ autoLayoutEnabled: enabled }),
        autoLayoutMode: 'hierarchical-horizontal',
        setAutoLayoutMode: (mode: AutoLayoutMode) => set({ autoLayoutMode: mode }),

      }),
      {
        name: 'ui-storage',
        partialize: (state) => ({
          mode: state.mode,
          layoutDirection: state.layoutDirection,
          autoLayoutEnabled: state.autoLayoutEnabled,
          autoLayoutMode: state.autoLayoutMode,
        }) as any,
        merge: (persistedState: any, currentState: any) => {
          // Older dashboards saved their detail windows and their default tab; agents unfold now
          const { detailWindows: _windows, defaultTab: _tab, ...saved } = persistedState ?? {};
          return {
            ...currentState,
            ...saved,
          };
        },
      }
    ),
    { name: 'uiStore' }
  )
);
