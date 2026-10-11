import 'fake-indexeddb/auto';
import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { useSettingsStore } from './store/settingsStore';
import { useUIStore } from './store/uiStore';

// The board itself is not under test here
vi.mock('./components/graph/GraphCanvas', () => ({ default: () => <div data-testid="graph" /> }));
vi.mock('./services/websocket', () => {
  const client = { connect: vi.fn(), disconnect: vi.fn(), reconnectManually: vi.fn() };
  return { initializeWebSocket: () => client, getWebSocketClient: () => client };
});
vi.mock('./services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./services/api')>()),
  fetchArtifactSummary: vi.fn(async () => ({
    total: 0,
    by_type: {},
    by_producer: {},
    by_visibility: {},
    tag_counts: {},
    earliest_created_at: null,
    latest_created_at: null,
  })),
  fetchArtifacts: vi.fn(async () => ({ items: [], pagination: { total: 0, limit: 200, offset: 0 } })),
}));

const press = (key: string, shiftKey = false) =>
  act(() => {
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key, ctrlKey: key !== 'Escape', shiftKey, bubbles: true }),
    );
  });

describe('App keyboard shortcuts', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, json: async () => ({ artifact_types: [], nodes: [], edges: [] }) })),
    );
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
    useSettingsStore.getState().resetToDefaults();
    useSettingsStore.setState((state) => ({
      ui: { ...state.ui, showControls: false, showSettings: false, showFilters: false },
    }));
    useUIStore.setState({ mode: 'agent' });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const renderApp = async () => {
    render(<App />);
    await waitFor(() => expect(document.querySelector('header')).not.toBeNull());
  };

  it('opens the publish panel with Ctrl+Shift+P', async () => {
    await renderApp();

    press('P', true);

    expect(useSettingsStore.getState().ui.showControls).toBe(true);
  });

  it('switches between the views with Ctrl+M', async () => {
    await renderApp();

    press('m');

    expect(useUIStore.getState().mode).toBe('blackboard');
  });

  it('closes one panel per Esc', async () => {
    await renderApp();
    act(() => {
      useSettingsStore.getState().setShowSettings(true);
      useSettingsStore.getState().setShowControls(true);
    });

    press('Escape');

    // Settings close first; the publish panel stays for the next Esc
    expect(useSettingsStore.getState().ui).toMatchObject({ showSettings: false, showControls: true });
  });
});
