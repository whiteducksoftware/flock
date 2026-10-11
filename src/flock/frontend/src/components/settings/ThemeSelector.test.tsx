import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { applyBuiltInTheme } from '../../services/themeApplicator';
import { useSettingsStore } from '../../store/settingsStore';
import ThemeSelector from './ThemeSelector';

vi.mock('../../services/themeService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/themeService')>()),
  fetchThemeList: vi.fn(async () => ['dracula', 'nord']),
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
    expect(useSettingsStore.getState().appearance.theme).toBe('paper');
  });

  it('finds a built-in theme by name without claiming nothing matched', async () => {
    render(<ThemeSelector />);
    await waitFor(() => expect(screen.getByText('Built-in Themes')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Search Themes'), { target: { value: 'graphite' } });

    expect(screen.getByRole('button', { name: 'Graphite' })).toBeTruthy();
    expect(screen.queryByText(/No themes found/)).toBeNull();
  });

  it('shows a theme stored by the old dashboard as Graphite', async () => {
    useSettingsStore.getState().setTheme('default');

    render(<ThemeSelector />);

    await waitFor(() => expect(screen.getAllByText('Graphite').length).toBeGreaterThan(0));
    expect(screen.queryByText('Default (Flock)')).toBeNull();
  });
});
