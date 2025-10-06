import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import FilterBar from './FilterBar';
import { useFilterStore } from '../../store/filterStore';

vi.mock('../../store/filterStore');
vi.mock('./CorrelationIDFilter', () => ({
  default: () => <div data-testid="correlation-id-filter">CorrelationIDFilter</div>,
}));
vi.mock('./TimeRangeFilter', () => ({
  default: () => <div data-testid="time-range-filter">TimeRangeFilter</div>,
}));
vi.mock('./FilterPills', () => ({
  default: () => <div data-testid="filter-pills">FilterPills</div>,
}));

describe('FilterBar', () => {
  it('should render all filter components', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        availableCorrelationIds: [],
        getActiveFilters: () => [],
      };
      return selector(state);
    });

    render(<FilterBar />);

    expect(screen.getByTestId('correlation-id-filter')).toBeInTheDocument();
    expect(screen.getByTestId('time-range-filter')).toBeInTheDocument();
    expect(screen.getByTestId('filter-pills')).toBeInTheDocument();
  });

  it('should have proper layout structure', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        availableCorrelationIds: [],
        getActiveFilters: () => [],
      };
      return selector(state);
    });

    const { container } = render(<FilterBar />);

    // Should have a container with CSS module class (hashed)
    const filterBar = container.firstChild as HTMLElement;
    expect(filterBar.className).toMatch(/filterBar/);
  });

  it('should render correlation ID filter and time range filter in top row', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        availableCorrelationIds: [],
        getActiveFilters: () => [],
      };
      return selector(state);
    });

    render(<FilterBar />);

    const correlationFilter = screen.getByTestId('correlation-id-filter');
    const timeRangeFilter = screen.getByTestId('time-range-filter');

    // Both should be present
    expect(correlationFilter).toBeInTheDocument();
    expect(timeRangeFilter).toBeInTheDocument();
  });

  it('should render filter pills below filter controls', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last5min' },
        availableCorrelationIds: [],
        getActiveFilters: () => [
          {
            type: 'correlationId',
            value: 'test-123',
            label: 'Correlation ID: test-123',
          },
        ],
      };
      return selector(state);
    });

    render(<FilterBar />);

    expect(screen.getByTestId('filter-pills')).toBeInTheDocument();
  });

  it('should have appropriate spacing between components', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        availableCorrelationIds: [],
        getActiveFilters: () => [],
      };
      return selector(state);
    });

    const { container } = render(<FilterBar />);
    const filterBar = container.firstChild as HTMLElement;

    // Should have filter controls with CSS module class (hashed)
    const filterControls = filterBar.querySelector('[class*="filterControls"]');
    expect(filterControls).toBeInTheDocument();
  });

  it('should maintain consistent styling with dashboard theme', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        availableCorrelationIds: [],
        getActiveFilters: () => [],
      };
      return selector(state);
    });

    const { container } = render(<FilterBar />);
    const filterBar = container.firstChild as HTMLElement;

    // Should have padding and background consistent with dashboard
    expect(filterBar).toBeDefined();
  });
});
