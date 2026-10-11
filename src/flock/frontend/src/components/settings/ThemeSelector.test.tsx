import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { applyBuiltInTheme } from '../../services/themeApplicator';
import { useSettingsStore } from '../../store/settingsStore';
import ThemeSelector from './ThemeSelector';

const loading: { finish: (theme: unknown) => void } = { finish: () => {} };

vi.mock('../../services/themeService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/themeService')>()),
  fetchThemeList: vi.fn(async () => ['dracula', 'nord']),
  // Loads until the test finishes it
  fetchTheme: vi.fn(() => new Promise((resolve) => (loading.finish = resolve))),
}));

describe('ThemeSelector', () => {
  beforeEach(() => {
    applyBuiltInTheme('graphite');
    useSettingsStore.getState().setTheme('graphite');
  });

  it('offers Graphite and Paper first and applies them without a fetch', async () => {
    render(<ThemeSelector />);
    await waitFor(() => expect(screen.getByText('Built-in Themes')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Paper' }));

    expect(document.documentElement.dataset.theme).toBe('paper');
    await waitFor(() => expect(useSettingsStore.getState().appearance.theme).toBe('paper'));
  });

  it('finds a built-in theme by name without claiming nothing matched', async () => {
    render(<ThemeSelector />);
    await waitFor(() => expect(screen.getByText('Built-in Themes')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Search Themes'), { target: { value: 'graphite' } });

    expect(screen.getByRole('button', { name: 'Graphite' })).toBeTruthy();
    expect(screen.queryByText(/No themes found/)).toBeNull();
  });

  it('keeps a newer choice when an older theme finishes loading', async () => {
    render(<ThemeSelector />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'dracula' })).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'dracula' })); // loading
    fireEvent.click(screen.getByRole('button', { name: 'Paper' }));
    loading.finish({
      name: 'dracula',
      colors: {
        primary: { background: '#282a36', foreground: '#f8f8f2' },
        normal: { black: '#000000', red: '#ff5555', green: '#50fa7b', yellow: '#f1fa8c', blue: '#bd93f9', magenta: '#ff79c6', cyan: '#8be9fd', white: '#bbbbbb' },
        bright: { black: '#555555', red: '#ff5555', green: '#50fa7b', yellow: '#f1fa8c', blue: '#bd93f9', magenta: '#ff79c6', cyan: '#8be9fd', white: '#ffffff' },
        selection: { background: '#44475a', text: '#ffffff' },
        cursor: { cursor: '#ffffff', text: '#000000' },
      },
    });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(document.documentElement.dataset.theme).toBe('paper');
    expect(useSettingsStore.getState().appearance.theme).toBe('paper');
  });

  it('does not apply a built-in theme on hover', async () => {
    render(<ThemeSelector />);
    await waitFor(() => expect(screen.getByText('Built-in Themes')).toBeTruthy());

    fireEvent.mouseEnter(screen.getByRole('button', { name: 'Paper' }));

    expect(document.documentElement.dataset.theme).toBe('graphite');
  });

  it('shows a theme stored by the old dashboard as Graphite', async () => {
    useSettingsStore.getState().setTheme('default');

    render(<ThemeSelector />);

    await waitFor(() => expect(screen.getAllByText('Graphite').length).toBeGreaterThan(0));
    expect(screen.queryByText('Default (Flock)')).toBeNull();
  });
});
