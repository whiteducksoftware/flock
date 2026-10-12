import 'fake-indexeddb/auto';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { useSettingsStore } from './store/settingsStore';
import { useUIStore } from './store/uiStore';

// The board itself is not under test here
vi.mock('./components/graph/GraphCanvas', () => ({ default: () => <div data-testid="graph" /> }));
const client = vi.hoisted(() => ({ connect: vi.fn(), disconnect: vi.fn(), reconnectManually: vi.fn() }));
vi.mock('./services/websocket', () => ({
  initializeWebSocket: () => client,
  getWebSocketClient: () => client,
  retryConnectionNow: () => client.reconnectManually(),
}));
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
    window.dispatchEvent(new KeyboardEvent('keydown', { key, ctrlKey: true, shiftKey, bubbles: true }));
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
    useUIStore.setState({ mode: 'agent' });
    client.connect.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('opens the publish panel with Ctrl+Shift+P', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());

    press('P', true);

    expect(useSettingsStore.getState().ui.showControls).toBe(true);
  });

  it('opens and closes the palette with Ctrl+K, and leaves Ctrl+F to the browser', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());

    press('k');
    expect(useUIStore.getState().paletteOpen).toBe(true);
    expect(await screen.findByRole('combobox')).toBe(document.activeElement);

    // From inside the palette (a modal dialog) Ctrl+K closes it
    act(() => {
      document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
    });
    expect(useUIStore.getState().paletteOpen).toBe(false);

    const find = new KeyboardEvent('keydown', { key: 'f', ctrlKey: true, bubbles: true, cancelable: true });
    act(() => {
      window.dispatchEvent(find);
    });
    expect(find.defaultPrevented).toBe(false);
    expect(useSettingsStore.getState().ui.showFilters).toBe(false);
  });

  it('does not open the palette over the keyboard shortcuts', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());
    press('/');
    await screen.findByRole('dialog', { name: 'Keyboard shortcuts' });

    press('k');

    expect(useUIStore.getState().paletteOpen).toBe(false);
  });

  it('does not open the palette over the publish composer', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());
    act(() => useSettingsStore.getState().setShowControls(true));
    await screen.findByPlaceholderText('Find a type');

    press('k');

    expect(useUIStore.getState().paletteOpen).toBe(false);
  });

  it('closes one panel per Esc', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());
    act(() => {
      useSettingsStore.getState().setShowSettings(true);
      useSettingsStore.getState().setShowControls(true);
    });

    press('Escape');

    // Settings close first; the publish panel stays for the next Esc
    expect(useSettingsStore.getState().ui).toMatchObject({ showSettings: false, showControls: true });
  });

  it('keeps the board\'s shortcuts away from an open publish composer, all but Esc', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());
    act(() => useSettingsStore.getState().setShowControls(true));
    const search = await screen.findByPlaceholderText('Find a type');

    // Ctrl+F, Ctrl+, and Ctrl+M from inside the modal: nothing behind it opens or changes
    for (const key of ['f', ',', 'm']) {
      act(() => {
        search.dispatchEvent(new KeyboardEvent('keydown', { key, ctrlKey: true, bubbles: true }));
      });
    }
    expect(useSettingsStore.getState().ui).toMatchObject({ showFilters: false, showSettings: false });
    expect(useUIStore.getState().mode).toBe('agent');
    expect(document.activeElement).toBe(search);

    press('Escape');
    expect(useSettingsStore.getState().ui.showControls).toBe(false);
  });

  it('switches between Flow and Blackboard with Ctrl+M', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());

    press('m');

    expect(useUIStore.getState().mode).toBe('blackboard');
  });
});
