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
      detailWindows: new Map(),
      layoutDirection: 'TB',
      autoLayoutEnabled: true,
      autoLayoutMode: 'hierarchical-horizontal',
      unfoldedNodeId: null,
    });
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

  it('saves neither the unfolded node nor open windows', () => {
    useUIStore.getState().unfold('triage');
    useUIStore.getState().openDetailWindow('artifact-1');
    useUIStore.getState().setMode('blackboard');

    const saved = JSON.stringify(memoryStorage.get('ui-storage'));
    expect(saved).toContain('blackboard');
    expect(saved).not.toContain('triage');
    expect(saved).not.toContain('artifact-1');
  });

  it('drops the windows an older dashboard saved', async () => {
    memoryStorage.set('ui-storage', {
      state: { mode: 'blackboard', detailWindows: [['triage', { nodeId: 'triage' }]] },
      version: 0,
    } as unknown as string);

    await (useUIStore as any).persist.rehydrate();

    expect(useUIStore.getState().mode).toBe('blackboard');
    expect(useUIStore.getState().detailWindows).toBeInstanceOf(Map);
    expect(useUIStore.getState().detailWindows.size).toBe(0);
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

  it('should open and close detail windows', () => {
    useUIStore.getState().openDetailWindow('node-1');

    let windows = useUIStore.getState().detailWindows;
    expect(windows.size).toBe(1);
    expect(windows.get('node-1')?.nodeId).toBe('node-1');

    useUIStore.getState().closeDetailWindow('node-1');
    windows = useUIStore.getState().detailWindows;
    expect(windows.size).toBe(0);
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
