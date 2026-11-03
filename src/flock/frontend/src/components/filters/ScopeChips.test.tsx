import 'fake-indexeddb/auto';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFilterStore } from '../../store/filterStore';
import { useGraphStore } from '../../store/graphStore';
import { useSettingsStore } from '../../store/settingsStore';
import ScopeChips from './ScopeChips';

describe('ScopeChips', () => {
  beforeEach(() => {
    // Changing a filter refreshes the board; that is not under test here
    vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    useSettingsStore.getState().resetToDefaults();
    useFilterStore.getState().clearFilters();
    useFilterStore.setState({ timeRange: { preset: 'last10min' } });
  });

  it('shows the time range and changes it from its chip', () => {
    render(<ScopeChips />);

    fireEvent.click(screen.getByRole('button', { name: /Last 10 min/ }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Time range' })).getByText('Last hour'));

    expect(useFilterStore.getState().timeRange).toEqual({ preset: 'last1hour' });
    expect(screen.queryByRole('dialog', { name: 'Time range' })).toBeNull();
    expect(screen.getByRole('button', { name: /Last hour/ })).toBeTruthy();
  });

  it('keeps the time range open to enter a custom range', () => {
    render(<ScopeChips />);

    fireEvent.click(screen.getByRole('button', { name: /Last 10 min/ }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Time range' })).getByText('Custom'));

    expect(screen.getByLabelText(/Start/)).toBeTruthy();
  });

  it('closes the time range when a shortcut opens the filters', () => {
    render(<ScopeChips />);
    fireEvent.click(screen.getByRole('button', { name: /Last 10 min/ }));

    act(() => useSettingsStore.getState().setShowFilters(true)); // Ctrl+Shift+F

    expect(screen.queryByRole('dialog', { name: 'Time range' })).toBeNull();
    expect(screen.getByRole('dialog', { name: 'Filters' })).toBeTruthy();
  });

  it('shows one chip per active filter, with short type names', () => {
    useFilterStore.setState({
      correlationId: '4f2a9c81-e0b3-4c55-9d0e-1a2b3c4d5e6f',
      selectedArtifactTypes: ['__main__.SupportTicket'],
      selectedProducers: ['triage'],
      selectedTags: ['urgent'],
      selectedVisibility: ['Public'],
    });

    render(<ScopeChips />);

    const chips = screen.getAllByRole('listitem').map((chip) => chip.textContent);
    expect(chips).toEqual([
      expect.stringContaining('Correlation4f2a9c81'),
      expect.stringContaining('TypeSupportTicket'),
      expect.stringContaining('Producertriage'),
      expect.stringContaining('Tagurgent'),
      expect.stringContaining('VisibilityPublic'),
    ]);
    // The full values stay one hover away
    expect(screen.getByTitle('Type: __main__.SupportTicket')).toBeTruthy();
  });

  it('removes a filter from its chip', () => {
    useFilterStore.setState({ selectedArtifactTypes: ['__main__.SupportTicket', '__main__.Reply'] });
    render(<ScopeChips />);

    fireEvent.click(screen.getByRole('button', { name: 'Remove Type __main__.SupportTicket' }));

    expect(useFilterStore.getState().selectedArtifactTypes).toEqual(['__main__.Reply']);
  });

  it('opens every facet and the presets from + Filter', () => {
    render(<ScopeChips />);

    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));

    expect(useSettingsStore.getState().ui.showFilters).toBe(true);
    const panel = screen.getByRole('dialog', { name: 'Filters' });
    for (const section of ['Presets', 'Correlation', 'Artifact types', 'Producers', 'Tags', 'Visibility']) {
      expect(within(panel).getByRole('heading', { name: section })).toBeTruthy();
    }
  });

  it('closes the filters when the user clicks elsewhere', () => {
    useSettingsStore.getState().setShowFilters(true);
    render(
      <div>
        <ScopeChips />
        <p>board</p>
      </div>,
    );

    fireEvent.mouseDown(screen.getByText('board'));

    expect(useSettingsStore.getState().ui.showFilters).toBe(false);
  });
});
