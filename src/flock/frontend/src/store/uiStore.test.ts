import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from './uiStore';

const memoryStorage = new Map<string, string>();

describe('uiStore', () => {
  beforeEach(() => {
    memoryStorage.clear();

    // Use deterministic in-memory storage for persist middleware in tests
    (useUIStore as any).persist.setOptions({
      storage: {
        getItem: (name: string) => memoryStorage.get(name) ?? null,
        setItem: (name: string, value: string) => {
          memoryStorage.set(name, value);
        },
        removeItem: (name: string) => {
          memoryStorage.delete(name);
        },
      },
    });

    // Reset store before each test
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      unfoldedArtifactId: null,
      blackboardView: 'lanes',
      needsReviewOnly: false,
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
      autoLayoutMode: 'hierarchical-horizontal',
      unfoldedNodeId: null,
      focusedNodeId: null,
    });
  });

  it('opens the timeline dock on a tab, with a trace search, and does not save it', () => {
    useUIStore.getState().openDock('traces', 'c-123');
    expect(useUIStore.getState()).toMatchObject({ dockOpen: true, dockTab: 'traces', traceSearch: 'c-123' });
    expect(JSON.stringify(memoryStorage.get('ui-storage') ?? '')).not.toContain('dockOpen');

    useUIStore.getState().openDock('history');
    expect(useUIStore.getState()).toMatchObject({ dockOpen: true, dockTab: 'history', traceSearch: 'c-123' });

    useUIStore.getState().closeDock();
    expect(useUIStore.getState().dockOpen).toBe(false);
  });

  it('keeps focus mode and the expanded dock apart, since each needs the board', () => {
    useUIStore.setState({ focusedNodeId: null, dockOpen: false, unfoldedNodeId: 'triage' });

    useUIStore.getState().focus('triage');
    useUIStore.getState().openDock('traces', 'c-1');
    expect(useUIStore.getState()).toMatchObject({ focusedNodeId: null, dockOpen: true, unfoldedNodeId: 'triage' });

    useUIStore.getState().focus('triage');
    expect(useUIStore.getState()).toMatchObject({ focusedNodeId: 'triage', dockOpen: false });

    useUIStore.setState({ focusedNodeId: null, unfoldedNodeId: null });
  });

  it('focuses one node at a time and does not save it', () => {
    useUIStore.getState().focus('billing_team');
    expect(useUIStore.getState().focusedNodeId).toBe('billing_team');

    useUIStore.getState().focus('triage');
    expect(useUIStore.getState().focusedNodeId).toBe('triage');
    expect(JSON.stringify(memoryStorage.get('ui-storage') ?? '')).not.toContain('triage');

    useUIStore.getState().unfocus();
    expect(useUIStore.getState().focusedNodeId).toBeNull();
  });

  it('unfolds one node at a time', () => {
    const { unfold, fold, toggleUnfold } = useUIStore.getState();

    unfold('triage');
    expect(useUIStore.getState().unfoldedNodeId).toBe('triage');

    unfold('billing_team');
    expect(useUIStore.getState().unfoldedNodeId).toBe('billing_team');

    fold();
    expect(useUIStore.getState().unfoldedNodeId).toBeNull();

    toggleUnfold('triage');
    expect(useUIStore.getState().unfoldedNodeId).toBe('triage');
    toggleUnfold('triage');
    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
  });

  it('saves the view and the Blackboard view\'s mode, not what is unfolded or filtered', () => {
    useUIStore.getState().unfold('triage');
    useUIStore.getState().unfoldArtifact('artifact-1');
    useUIStore.getState().setNeedsReviewOnly(true);
    useUIStore.getState().setMode('blackboard');
    useUIStore.getState().setBlackboardView('graph');
    useUIStore.getState().setGraphLayout('grid');
    useUIStore.getState().setGraphAutoArrange(false);

    const saved = JSON.stringify(memoryStorage.get('ui-storage'));
    expect(saved).toContain('blackboard');
    expect(saved).toContain('"blackboardView":"graph"');
    expect(saved).toContain('"graphLayout":"grid"');
    expect(saved).toContain('"graphAutoArrange":false');
    expect(saved).not.toContain('triage');
    expect(saved).not.toContain('artifact-1');
    expect(saved).not.toContain('needsReviewOnly');
  });

  it('shows the lanes where an older dashboard saved the table, which is gone', async () => {
    memoryStorage.set('ui-storage', { state: { blackboardView: 'table' }, version: 0 } as unknown as string);

    await (useUIStore as any).persist.rehydrate();

    expect(useUIStore.getState().blackboardView).toBe('lanes');
  });

  it('drops the windows an older dashboard saved', async () => {
    memoryStorage.set('ui-storage', {
      state: { mode: 'blackboard', detailWindows: [['triage', { nodeId: 'triage' }]] },
      version: 0,
    } as unknown as string);

    await (useUIStore as any).persist.rehydrate();

    expect(useUIStore.getState().mode).toBe('blackboard');
    expect('detailWindows' in useUIStore.getState()).toBe(false);
  });

  it('should set mode to blackboard', () => {
    useUIStore.getState().setMode('blackboard');
    expect(useUIStore.getState().mode).toBe('blackboard');
  });

  it('should select and deselect nodes', () => {
    useUIStore.getState().selectNode('node-1');
    useUIStore.getState().selectNode('node-2');

    let selectedIds = useUIStore.getState().selectedNodeIds;
    expect(selectedIds.size).toBe(2);
    expect(selectedIds.has('node-1')).toBe(true);
    expect(selectedIds.has('node-2')).toBe(true);

    useUIStore.getState().deselectNode('node-1');
    selectedIds = useUIStore.getState().selectedNodeIds;
    expect(selectedIds.size).toBe(1);
    expect(selectedIds.has('node-1')).toBe(false);
  });

  it('should clear selection', () => {
    useUIStore.getState().selectNode('node-1');
    useUIStore.getState().selectNode('node-2');
    useUIStore.getState().clearSelection();

    expect(useUIStore.getState().selectedNodeIds.size).toBe(0);
  });

  it('unfolds one artifact card at a time, and folds it', () => {
    useUIStore.getState().unfoldArtifact('artifact-1');
    useUIStore.getState().unfoldArtifact('artifact-2');
    expect(useUIStore.getState().unfoldedArtifactId).toBe('artifact-2');

    useUIStore.getState().foldArtifact();
    expect(useUIStore.getState().unfoldedArtifactId).toBeNull();
  });

  it('should default auto-layout preferences correctly', () => {
    const state = useUIStore.getState();
    expect(state.autoLayoutEnabled).toBe(true);
    expect(state.autoLayoutMode).toBe('hierarchical-horizontal');
  });

  it('should allow toggling auto-layout enabled state', () => {
    useUIStore.getState().setAutoLayoutEnabled(false);
    expect(useUIStore.getState().autoLayoutEnabled).toBe(false);

    useUIStore.getState().setAutoLayoutEnabled(true);
    expect(useUIStore.getState().autoLayoutEnabled).toBe(true);
  });

  it('should persist last selected auto-layout mode in store state', () => {
    useUIStore.getState().setAutoLayoutMode('circular');
    expect(useUIStore.getState().autoLayoutMode).toBe('circular');

    useUIStore.getState().setAutoLayoutMode('grid');
    expect(useUIStore.getState().autoLayoutMode).toBe('grid');
  });
});
