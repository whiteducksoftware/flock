import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from './uiStore';

describe('uiStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useUIStore.setState({
      mode: 'agent',
      selectedNodeIds: new Set(),
      detailWindows: new Map(),
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
});
