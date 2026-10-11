import 'fake-indexeddb/auto';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSettingsStore } from '../../store/settingsStore';
import { useUIStore } from '../../store/uiStore';
import { useWSStore } from '../../store/wsStore';
import AppHeader from './AppHeader';

describe('AppHeader', () => {
  beforeEach(() => {
    useSettingsStore.getState().resetToDefaults();
    useUIStore.setState({ mode: 'agent' });
    useWSStore.setState({ status: 'connected', reconnectAttempts: 0, nextRetryAt: null });
  });

  it('switches between Flow and Blackboard', () => {
    render(<AppHeader onShowShortcuts={() => {}} />);
    const views = screen.getByRole('navigation', { name: 'Views' });
    expect(screen.getByRole('button', { name: 'Flow' }).getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: 'Blackboard' }));

    expect(useUIStore.getState().mode).toBe('blackboard');
    expect(views.querySelector('[aria-pressed="true"]')?.textContent).toBe('Blackboard');
  });

  it('opens and closes the publish panel and the settings', () => {
    render(<AppHeader onShowShortcuts={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

    expect(useSettingsStore.getState().ui).toMatchObject({ showControls: true, showSettings: true });
    expect(screen.getByRole('button', { name: 'Publish' }).getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
    expect(useSettingsStore.getState().ui.showControls).toBe(false);
  });

  it('opens the keyboard shortcuts', () => {
    const onShowShortcuts = vi.fn();
    render(<AppHeader onShowShortcuts={onShowShortcuts} />);

    fireEvent.click(screen.getByRole('button', { name: 'Keyboard shortcuts' }));

    expect(onShowShortcuts).toHaveBeenCalledOnce();
  });

  it('holds the wordmark, the scope, the search and the live status', () => {
    render(<AppHeader onShowShortcuts={() => {}} />);

    expect(screen.getByText('flock')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Last 10 min|All time|Last/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Filter' })).toBeTruthy();
    // The search arrives with the command palette (⌘K)
    expect((screen.getByRole('button', { name: /Search agents, types, runs/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('status').textContent).toContain('Live');
  });
});
