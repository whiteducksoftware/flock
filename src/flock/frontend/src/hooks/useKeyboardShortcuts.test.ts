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
    useUIStore.setState({ unfoldedNodeId: null, focusedNodeId: null, dockOpen: false, unfoldedArtifactId: null });
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

  it('leaves Space to elements that act as buttons', () => {
    const row = document.createElement('div');
    row.setAttribute('role', 'button');
    row.tabIndex = 0;
    document.body.appendChild(row);
    row.focus();

    press(' ');

    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
  });

  it('leaves focus mode with Esc before folding, and keeps Space from the board behind it', () => {
    useUIStore.getState().unfold('intake');
    useUIStore.getState().focus('triage');

    press(' ');
    press('D', { ctrlKey: true, shiftKey: true });
    expect(useUIStore.getState().unfoldedNodeId).toBe('intake');

    press('Escape');
    expect(useUIStore.getState().focusedNodeId).toBeNull();
    expect(useUIStore.getState().unfoldedNodeId).toBe('intake');
  });

  it('collapses the timeline dock with Esc after focus mode, before folding', () => {
    useUIStore.getState().unfold('intake');
    useUIStore.getState().openDock('traces');

    press('Escape');
    expect(useUIStore.getState().dockOpen).toBe(false);
    expect(useUIStore.getState().unfoldedNodeId).toBe('intake');
  });

  it('leaves Esc to a dialog that handled it', () => {
    useUIStore.getState().unfold('intake');
    // As the image and help dialogs do: on window, in the capture phase
    const dialog = (event: KeyboardEvent) => event.key === 'Escape' && event.preventDefault();
    window.addEventListener('keydown', dialog, true);

    press('Escape');

    window.removeEventListener('keydown', dialog, true);
    expect(useUIStore.getState().unfoldedNodeId).toBe('intake');
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

  it('folds what the view shows: the artifact card on the Blackboard, the agent on the Flow', () => {
    useUIStore.setState({ mode: 'blackboard', unfoldedNodeId: 'intake', unfoldedArtifactId: 'artifact-1' });

    press('Escape');
    expect(useUIStore.getState()).toMatchObject({ unfoldedArtifactId: null, unfoldedNodeId: 'intake' });

    useUIStore.setState({ mode: 'agent', unfoldedArtifactId: 'artifact-2' });
    press('Escape');
    expect(useUIStore.getState()).toMatchObject({ unfoldedArtifactId: 'artifact-2', unfoldedNodeId: null });
    useUIStore.setState({ mode: 'agent', unfoldedArtifactId: null });
  });
});
