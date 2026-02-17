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
      defaultTab: 'liveOutput',
    });
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
