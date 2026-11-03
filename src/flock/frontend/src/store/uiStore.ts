import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export type VisualizationMode = 'agent' | 'blackboard';
export type DockTab = 'traces' | 'history' | 'metrics' | 'settings';

export type AutoLayoutMode =
  | 'hierarchical-horizontal'
  | 'hierarchical-vertical'
  | 'circular'
  | 'grid'
  | 'random';

export type BlackboardView = 'lanes' | 'graph';

/** A short message at the bottom of the board, with an optional action. */
export interface ToastMessage {
  message: string;
  /** The tooltip of the message, e.g. a full run ID */
  title?: string;
  /** A second, fainter line */
  detail?: string;
  action?: { label: string; onClick: () => void };
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

  // The timeline dock, expanded on a tab (not saved); the trace search it opens with
  dockOpen: boolean;
  dockTab: DockTab;
  traceSearch: string;
  openDock: (tab: DockTab, traceSearch?: string) => void;
  setTraceSearch: (traceSearch: string) => void;
  closeDock: () => void;

  // The node in focus: a full stage over the dimmed board (not saved)
  focusedNodeId: string | null;
  focus: (nodeId: string) => void;
  unfocus: () => void;

  // The Blackboard view: lanes or the table (saved), the artifact card unfolded in place
  // and whether only runs that need a review show (not saved)
  blackboardView: BlackboardView;
  setBlackboardView: (view: BlackboardView) => void;
  // The Blackboard graph's layout and whether new artifacts lay it out (saved)
  graphLayout: AutoLayoutMode;
  setGraphLayout: (mode: AutoLayoutMode) => void;
  graphAutoArrange: boolean;
  setGraphAutoArrange: (on: boolean) => void;
  unfoldedArtifactId: string | null;
  unfoldArtifact: (artifactId: string) => void;
  foldArtifact: () => void;
  needsReviewOnly: boolean;
  setNeedsReviewOnly: (on: boolean) => void;

  // The ⌘K palette (not saved)
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;

  // The type the publish composer opens on, once (not saved)
  publishType: string | null;
  setPublishType: (type: string | null) => void;

  // The toast, one at a time; it closes itself (not saved)
  toast: ToastMessage | null;
  showToast: (toast: ToastMessage) => void;
  dismissToast: () => void;

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

        dockOpen: false,
        dockTab: 'traces',
        traceSearch: '',
        // The expanded dock and the focus stage each need the board's room: one closes the other
        openDock: (tab: DockTab, traceSearch?: string) =>
          set((state) => ({ dockOpen: true, dockTab: tab, traceSearch: traceSearch ?? state.traceSearch, focusedNodeId: null })),
        closeDock: () => set({ dockOpen: false }),
        setTraceSearch: (traceSearch: string) => set({ traceSearch }),

        focusedNodeId: null,
        focus: (nodeId: string) => set({ focusedNodeId: nodeId, dockOpen: false }),
        unfocus: () => set({ focusedNodeId: null }),

        blackboardView: 'lanes',
        setBlackboardView: (view: BlackboardView) => set({ blackboardView: view }),
        // Runs as narrow trees side by side; left to right they are wide, one or two a row
        graphLayout: 'hierarchical-vertical',
        setGraphLayout: (mode: AutoLayoutMode) => set({ graphLayout: mode }),
        // A busy board would move all the time: cards stay where they are unless asked
        graphAutoArrange: false,
        setGraphAutoArrange: (on: boolean) => set({ graphAutoArrange: on }),
        // One card at a time, as one agent unfolds at a time
        unfoldedArtifactId: null,
        unfoldArtifact: (artifactId: string) => set({ unfoldedArtifactId: artifactId }),
        foldArtifact: () => set({ unfoldedArtifactId: null }),
        needsReviewOnly: false,
        setNeedsReviewOnly: (on: boolean) => set({ needsReviewOnly: on }),

        paletteOpen: false,
        openPalette: () => set({ paletteOpen: true }),
        closePalette: () => set({ paletteOpen: false }),

        publishType: null,
        setPublishType: (publishType: string | null) => set({ publishType }),

        toast: null,
        showToast: (toast: ToastMessage) => set({ toast }),
        dismissToast: () => set({ toast: null }),

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
          blackboardView: state.blackboardView,
          graphLayout: state.graphLayout,
          graphAutoArrange: state.graphAutoArrange,
          layoutDirection: state.layoutDirection,
          autoLayoutEnabled: state.autoLayoutEnabled,
          autoLayoutMode: state.autoLayoutMode,
        }) as any,
        merge: (persistedState: any, currentState: any) => {
          // Older dashboards saved their detail windows and their default tab; agents and artifacts unfold now
          const { detailWindows: _windows, defaultTab: _tab, ...saved } = persistedState ?? {};
          // The Blackboard's table is gone (it was the timeline dock's History)
          if (saved.blackboardView === 'table') saved.blackboardView = 'lanes';
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
