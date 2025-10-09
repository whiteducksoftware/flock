import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import FilterPills from './FilterPills';
import { useFilterStore, formatTimeRange } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import type { TimeRange } from '../../types/filters';

vi.mock('../../store/filterStore', async () => {
  const actual = await vi.importActual<typeof import('../../store/filterStore')>('../../store/filterStore');
  return {
    ...actual,
    useFilterStore: vi.fn(),
  };
});

vi.mock('../../store/settingsStore', async () => {
  const actual = await vi.importActual<typeof import('../../store/settingsStore')>('../../store/settingsStore');
  return {
    ...actual,
    useSettingsStore: vi.fn(),
  };
});

describe('FilterPills', () => {
  const mockRemoveFilter = vi.fn();
  const mockSetShowFilters = vi.fn();

  type MockFilterState = {
    correlationId: string | null;
    timeRange: TimeRange;
    selectedArtifactTypes: string[];
    selectedProducers: string[];
    selectedTags: string[];
    selectedVisibility: string[];
    removeFilter: typeof mockRemoveFilter;
  };

  const setupStore = (override: Partial<MockFilterState> = {}) => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state: MockFilterState = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        selectedArtifactTypes: [],
        selectedProducers: [],
        selectedTags: [],
        selectedVisibility: [],
        removeFilter: mockRemoveFilter,
        ...override,
      };
      return selector(state);
    });

    vi.mocked(useSettingsStore).mockImplementation((selector: any) =>
      selector({
        ui: { showFilters: false },
        setShowFilters: mockSetShowFilters,
      })
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render the default time range filter when no other filters are active', () => {
    setupStore();

    render(<FilterPills />);
    expect(screen.getByRole('button', { name: /filter panel/i })).toBeInTheDocument();
    expect(screen.getByText('Time')).toBeInTheDocument();
    expect(screen.getByText('Last 10 min')).toBeInTheDocument();
  });

  it('should render filter pill for active correlation ID', () => {
    setupStore({ correlationId: 'test-123' });

    render(<FilterPills />);
    const pill = screen.getAllByRole('listitem').find((item) => within(item).queryByText('Correlation ID'));
    expect(pill).toBeDefined();
    if (!pill) {
      throw new Error('Correlation ID pill not found');
    }
    expect(within(pill).getByText('Correlation ID')).toBeInTheDocument();
    expect(within(pill).getByText('test-123')).toBeInTheDocument();
  });

  it('should render filter pill for active time range', () => {
    setupStore({ timeRange: { preset: 'last5min' } as TimeRange });

    render(<FilterPills />);
    const pill = screen.getByRole('listitem');
    expect(within(pill).getByText('Time')).toBeInTheDocument();
    expect(within(pill).getByText('Last 5 min')).toBeInTheDocument();
  });

  it('should toggle filters when toggle button is clicked', () => {
    setupStore();

    render(<FilterPills />);
    fireEvent.click(screen.getByRole('button', { name: /filter panel/i }));

    expect(mockSetShowFilters).toHaveBeenCalledWith(true);
  });

  it('should render multiple filter pills', () => {
    setupStore({
      correlationId: 'test-123',
      timeRange: { preset: 'last1hour' } as TimeRange,
      selectedArtifactTypes: ['__main__.Example'],
    });

    render(<FilterPills />);
    expect(screen.getByText('Correlation ID')).toBeInTheDocument();
    expect(screen.getByText('test-123')).toBeInTheDocument();
    expect(screen.getByText('Time')).toBeInTheDocument();
    expect(screen.getByText('Last hour')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
    expect(screen.getByText('__main__.Example')).toBeInTheDocument();
  });

  it('should render remove button for each pill', () => {
    setupStore({ correlationId: 'test-123' });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });
    expect(removeButton).toBeInTheDocument();
  });

  it('should call removeFilter when remove button is clicked', () => {
    setupStore({ correlationId: 'test-123' });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });

    fireEvent.click(removeButton);

    expect(mockRemoveFilter).toHaveBeenCalledWith({
      type: 'correlationId',
      value: 'test-123',
      label: 'Correlation ID: test-123',
    });
  });

  it('should call removeFilter with correct type for time range', () => {
    const timeRange = { preset: 'last5min' } as TimeRange;
    setupStore({ timeRange });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*time/i });

    fireEvent.click(removeButton);

    expect(mockRemoveFilter).toHaveBeenCalledWith({
      type: 'timeRange',
      value: timeRange,
      label: 'Time: Last 5 min',
    });
  });

  it('should display pills in a horizontal layout', () => {
    setupStore({ correlationId: 'test-123' });

    render(<FilterPills />);
    const container = screen.getByRole('list');
    expect(container?.className).toMatch(/container/);
  });

  it('should render X icon in remove button', () => {
    setupStore({ correlationId: 'test-123' });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });

    expect(within(removeButton).getByText('×')).toBeInTheDocument();
  });

  it('should handle custom time range label', () => {
    const customRange: TimeRange = {
      preset: 'custom',
      start: new Date('2025-01-01T10:00:00').getTime(),
      end: new Date('2025-01-01T12:00:00').getTime(),
    };
    setupStore({ timeRange: customRange });

    render(<FilterPills />);
    expect(screen.getByText('Time')).toBeInTheDocument();
    expect(screen.getByText(formatTimeRange(customRange))).toBeInTheDocument();
  });
});
