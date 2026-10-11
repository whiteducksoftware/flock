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

  it('shows a theme stored by the old dashboard as Graphite', async () => {
    useSettingsStore.getState().setTheme('default');

    render(<ThemeSelector />);

    await waitFor(() => expect(screen.getAllByText('Graphite').length).toBeGreaterThan(0));
    expect(screen.queryByText('Default (Flock)')).toBeNull();
  });
});
