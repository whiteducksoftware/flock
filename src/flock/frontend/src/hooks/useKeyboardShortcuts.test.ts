import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import type { Node } from '@xyflow/react';
import { useGraphStore } from '../store/graphStore';
import { useSettingsStore } from '../store/settingsStore';
import { useUIStore } from '../store/uiStore';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';

const press = (key: string, init: KeyboardEventInit = {}) => {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init });
  window.dispatchEvent(event);
  return event;
};

const agent = (id: string, selected = false): Node => ({ id, type: 'agent', position: { x: 0, y: 0 }, data: {}, selected });

describe('useKeyboardShortcuts: unfolding', () => {
  beforeEach(() => {
    useGraphStore.setState({ nodes: [agent('intake'), agent('triage', true)] });
    useUIStore.setState({ unfoldedNodeId: null, detailWindows: new Map() });
    renderHook(() => useKeyboardShortcuts());
  });

  afterEach(() => {
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    useUIStore.setState({ unfoldedNodeId: null });
    useSettingsStore.getState().setShowSettings(false);
    document.body.innerHTML = '';
  });

  it('unfolds and folds the selected node with Space', () => {
    const event = press(' ');
    expect(useUIStore.getState().unfoldedNodeId).toBe('triage');
    // The page does not scroll
    expect(event.defaultPrevented).toBe(true);

    press(' ');
    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
  });

  it('unfolds and folds the selected node with Ctrl+Shift+D', () => {
    press('D', { ctrlKey: true, shiftKey: true });
    expect(useUIStore.getState().unfoldedNodeId).toBe('triage');

    press('D', { ctrlKey: true, shiftKey: true });
    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
  });

  it('leaves Space to buttons and fields that have the focus', () => {
    const button = document.createElement('button');
    document.body.appendChild(button);
    button.focus();

    press(' ');

    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
  });

  it('folds the unfolded node with Esc once the panels are closed', () => {
    useUIStore.getState().unfold('intake');
    useSettingsStore.getState().setShowSettings(true);

    press('Escape');
    expect(useSettingsStore.getState().ui.showSettings).toBe(false);
    expect(useUIStore.getState().unfoldedNodeId).toBe('intake');

    press('Escape');
    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
  });
});
