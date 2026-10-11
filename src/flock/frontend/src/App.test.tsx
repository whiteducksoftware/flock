import 'fake-indexeddb/auto';
import { act, render, waitFor } from '@testing-library/react';
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

  it('opens the filters on the correlation search with Ctrl+F', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());

    press('f');

    expect(useSettingsStore.getState().ui.showFilters).toBe(true);
    await waitFor(() =>
      expect((document.activeElement as HTMLInputElement | null)?.placeholder).toMatch(/correlation/i),
    );
  });

  it('opens the filters with Ctrl+F even when another correlation field is open', async () => {
    render(
      <>
        {/* The trace viewer has a correlation ID field too */}
        <input placeholder="Filter by correlation ID" />
        <App />
      </>,
    );
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());

    press('f');

    expect(useSettingsStore.getState().ui.showFilters).toBe(true);
    await waitFor(() =>
      expect(document.activeElement?.closest('[role="dialog"][aria-label="Filters"]')).not.toBeNull(),
    );
  });

  it('switches between Flow and Blackboard with Ctrl+M', async () => {
    render(<App />);
    // The bootstrap connects last; nothing of it may outlive the test
    await waitFor(() => expect(client.connect).toHaveBeenCalled());

    press('m');

    expect(useUIStore.getState().mode).toBe('blackboard');
  });
});
