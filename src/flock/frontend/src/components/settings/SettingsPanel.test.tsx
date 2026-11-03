import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyTheme } from '../../services/themeApplicator';
import { useSettingsStore } from '../../store/settingsStore';
import SettingsPanel from './SettingsPanel';

const dracula = {
  name: 'dracula',
  colors: {
    primary: { background: '#282a36', foreground: '#f8f8f2' },
    normal: { black: '#000000', red: '#ff5555', green: '#50fa7b', yellow: '#f1fa8c', blue: '#bd93f9', magenta: '#ff79c6', cyan: '#8be9fd', white: '#bbbbbb' },
    bright: { black: '#555555', red: '#ff5555', green: '#50fa7b', yellow: '#f1fa8c', blue: '#bd93f9', magenta: '#ff79c6', cyan: '#8be9fd', white: '#ffffff' },
    selection: { background: '#44475a', text: '#ffffff' },
    cursor: { cursor: '#ffffff', text: '#000000' },
  },
};

describe('SettingsPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resets a terminal theme to Graphite with all settings', () => {
    applyTheme(dracula);
    useSettingsStore.getState().setTheme('dracula');
    vi.stubGlobal('confirm', () => true);
    render(<SettingsPanel />);

    fireEvent.click(screen.getByRole('button', { name: 'Reset to defaults' }));

    expect(useSettingsStore.getState().appearance.theme).toBe('graphite');
    expect(document.documentElement.dataset.theme).toBe('graphite');
    expect(document.documentElement.style.getPropertyValue('--bg')).toBe('');
  });

  it('is a sheet with the tabs Graph, Appearance and Advanced, by click and arrow keys', () => {
    useSettingsStore.getState().setShowSettings(true);
    render(<SettingsPanel />);

    const sheet = screen.getByRole('dialog', { name: 'Settings' });
    const tabs = within(sheet).getAllByRole('tab');
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Graph', 'Appearance', 'Advanced']);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'Graph' })).toBeInTheDocument();

    fireEvent.keyDown(tabs[0]!, { key: 'ArrowRight' });
    expect(screen.getByRole('tab', { name: 'Appearance' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Appearance' })).toHaveFocus();
    expect(screen.getByRole('tabpanel', { name: 'Appearance' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Advanced' }));
    const advanced = screen.getByRole('tabpanel', { name: 'Advanced' });
    expect(within(advanced).getByLabelText(/Node spacing/)).toBeInTheDocument();
    expect(within(advanced).getByLabelText(/Rank spacing/)).toBeInTheDocument();
    expect(within(advanced).getByRole('button', { name: 'Clear all dashboard data' })).toBeInTheDocument();
    // Gone: they had no effect (debug and performance mode were read nowhere; every layout names its direction)
    expect(within(advanced).queryByText(/Debug mode|Performance mode|Layout direction/)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Close settings' }));
    expect(useSettingsStore.getState().ui.showSettings).toBe(false);
  });

  it('says what edge labels show', () => {
    render(<SettingsPanel />);

    expect(screen.getByText("Each edge's type and how many artifacts went along it")).toBeInTheDocument();
    expect(screen.queryByText(/correlation IDs/)).toBeNull();
  });
});
