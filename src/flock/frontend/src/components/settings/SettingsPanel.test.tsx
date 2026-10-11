import { fireEvent, render, screen } from '@testing-library/react';
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

    fireEvent.click(screen.getByRole('button', { name: 'Reset to Defaults' }));

    expect(useSettingsStore.getState().appearance.theme).toBe('graphite');
    expect(document.documentElement.dataset.theme).toBe('graphite');
    expect(document.documentElement.style.getPropertyValue('--bg')).toBe('');
  });
});
