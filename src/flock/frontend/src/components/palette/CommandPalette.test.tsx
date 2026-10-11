import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useFilterStore } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import { useUIStore } from '../../store/uiStore';
import CommandPalette from './CommandPalette';

vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  fetchAgents: vi.fn(async () => [
    { name: 'triage', description: '', status: 'idle', subscriptions: ['app.SupportTicket'], output_types: [] },
    { name: 'billing_team', description: '', status: 'running', subscriptions: [], output_types: [] },
  ]),
  fetchArtifactTypes: vi.fn(async () => [
    { name: 'app.SupportTicket', schema: { type: 'object', properties: { title: { type: 'string' } } } },
  ]),
}));

const input = () => screen.getByRole('combobox');
const active = () => document.getElementById(input().getAttribute('aria-activedescendant') ?? '');
const key = (k: string, init: KeyboardEventInit = {}) => fireEvent.keyDown(input(), { key: k, ...init });

describe('CommandPalette', () => {
  beforeEach(() => {
    useUIStore.setState({
      paletteOpen: true,
      mode: 'agent',
      publishType: null,
      unfoldedNodeId: null,
      focusedNodeId: null,
      dockOpen: false,
    });
    useSettingsStore.getState().resetToDefaults();
    useFilterStore.setState({
      correlationId: null,
      availableCorrelationIds: [
        { correlation_id: '4e7b1c2d-0000-4000-8000-000000000000', first_seen: Date.now() - 5_000, artifact_count: 5, run_count: 3 },
      ],
    });
  });

  afterEach(() => {
    useUIStore.setState({ paletteOpen: false });
  });

  it('opens on its search, as a combobox over grouped results', async () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);

    expect(document.activeElement).toBe(input());
    expect(input().getAttribute('aria-expanded')).toBe('true');
    const list = screen.getByRole('listbox');
    expect(input().getAttribute('aria-controls')).toBe(list.id);
    await waitFor(() => expect(within(list).getByRole('group', { name: 'Agents' })).toBeTruthy());
    expect(within(list).getByRole('group', { name: 'Types' }).textContent).toContain('SupportTicket');
    expect(within(list).getByRole('group', { name: 'Runs' }).textContent).toContain('4e7b1c2d');
    expect(within(list).getByRole('group', { name: 'Commands' }).textContent).toContain('Switch to Blackboard');
    // The first result is active
    expect(active()?.textContent).toContain('triage');
  });

  it('narrows to a query, moves with the arrows and runs a command with Enter', async () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);
    await screen.findByRole('group', { name: 'Agents' });

    fireEvent.change(input(), { target: { value: 'switch' } });
    expect(active()?.textContent).toContain('Switch to Blackboard');
    key('ArrowDown');
    key('ArrowUp');
    key('Enter');

    expect(useUIStore.getState().mode).toBe('blackboard');
    expect(useUIStore.getState().paletteOpen).toBe(false);
  });

  it("runs a result's second and third action with Shift+Enter and Ctrl+Enter", async () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);
    await screen.findByRole('group', { name: 'Types' });

    fireEvent.change(input(), { target: { value: 'supportticket' } });
    key('Enter', { shiftKey: true });

    expect(useUIStore.getState().publishType).toBe('app.SupportTicket');
    expect(useSettingsStore.getState().ui.showControls).toBe(true);
    expect(useUIStore.getState().paletteOpen).toBe(false);
  });

  it("offers the active result's actions as buttons", async () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);
    await screen.findByRole('group', { name: 'Agents' });

    fireEvent.change(input(), { target: { value: 'triage' } });
    const actions = screen.getByRole('group', { name: 'Actions' });
    expect(within(actions).getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Show↵',
      `Unfold⇧↵`,
      expect.stringMatching(/^Focus(⌘|Ctrl\+)↵$/),
    ]);
    fireEvent.click(within(actions).getByRole('button', { name: /Unfold/ }));

    expect(useUIStore.getState().unfoldedNodeId).toBe('triage');
    expect(useUIStore.getState().paletteOpen).toBe(false);
  });

  it('filters by a run found by the start of its ID', async () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);

    fireEvent.change(input(), { target: { value: '4e7b' } });
    fireEvent.click(screen.getByRole('option', { name: /4e7b1c2d/ }));

    expect(useFilterStore.getState().correlationId).toBe('4e7b1c2d-0000-4000-8000-000000000000');
  });

  it('says when nothing matches', () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);

    fireEvent.change(input(), { target: { value: 'zzzzqqq' } });

    expect(screen.getByText('Nothing matches “zzzzqqq”.')).toBeTruthy();
    expect(input().getAttribute('aria-expanded')).toBe('false');
    expect(input().hasAttribute('aria-activedescendant')).toBe(false);
  });

  it("closes with Esc, which the board's Esc does not see", () => {
    render(<CommandPalette onShowShortcuts={() => {}} />);

    const notPrevented = key('Escape');

    expect(notPrevented).toBe(false);
    expect(useUIStore.getState().paletteOpen).toBe(false);
  });

  it('closes on the scrim and gives the focus back', () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(<CommandPalette onShowShortcuts={() => {}} />);

    fireEvent.click(screen.getByTestId('palette-scrim'));
    expect(useUIStore.getState().paletteOpen).toBe(false);
    unmount();

    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});
