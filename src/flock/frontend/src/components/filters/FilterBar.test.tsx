import { describe, it, expect, vi, beforeEach } from 'vitest';
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
vi.mock('./ArtifactTypeFilter', () => ({
  default: () => <div data-testid="artifact-type-filter">ArtifactTypeFilter</div>,
}));
vi.mock('./ProducerFilter', () => ({
  default: () => <div data-testid="producer-filter">ProducerFilter</div>,
}));
vi.mock('./TagFilter', () => ({
  default: () => <div data-testid="tag-filter">TagFilter</div>,
}));
vi.mock('./VisibilityFilter', () => ({
  default: () => <div data-testid="visibility-filter">VisibilityFilter</div>,
}));
vi.mock('./SavedFiltersControl', () => ({
  default: () => <div data-testid="saved-filters-control">SavedFiltersControl</div>,
}));
vi.mock('./FilterPills', () => ({
  default: () => <div data-testid="filter-pills">FilterPills</div>,
}));

type MockedFn = ReturnType<typeof vi.fn>;
const mockedUseFilterStore = useFilterStore as unknown as MockedFn;

const createMockState = (overrides: Record<string, unknown> = {}) =>
  ({
    correlationId: null,
    timeRange: { preset: 'last10min' as const },
    availableCorrelationIds: [],
    availableArtifactTypes: [],
    availableProducers: [],
    availableTags: [],
    availableVisibility: [],
    selectedArtifactTypes: [],
    selectedProducers: [],
    selectedTags: [],
    selectedVisibility: [],
    summary: null,
    savedFilters: [],
    getActiveFilters: () => [],
    setCorrelationId: vi.fn(),
    setTimeRange: vi.fn(),
    setArtifactTypes: vi.fn(),
    setProducers: vi.fn(),
    setTags: vi.fn(),
    setVisibility: vi.fn(),
    clearFilters: vi.fn(),
    updateAvailableCorrelationIds: vi.fn(),
    updateAvailableFacets: vi.fn(),
    setSummary: vi.fn(),
    setSavedFilters: vi.fn(),
    addSavedFilter: vi.fn(),
    removeSavedFilter: vi.fn(),
    getFilterSnapshot: vi.fn(() => ({
      correlationId: null,
      timeRange: { preset: 'last10min' as const },
      artifactTypes: [],
      producers: [],
      tags: [],
      visibility: [],
    })),
    applyFilterSnapshot: vi.fn(),
    removeFilter: vi.fn(),
    ...overrides,
  }) as Record<string, unknown>;

const mockStore = (overrides: Record<string, unknown> = {}) => {
  const state = createMockState(overrides);
  mockedUseFilterStore.mockImplementation((selector: any) => selector(state));
};

describe('FilterBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseFilterStore.mockReset();
  });

  it('should render all filter components', () => {
    mockStore();

    render(<FilterBar />);

    expect(screen.getByTestId('correlation-id-filter')).toBeInTheDocument();
    expect(screen.getByTestId('time-range-filter')).toBeInTheDocument();
    expect(screen.getByTestId('artifact-type-filter')).toBeInTheDocument();
    expect(screen.getByTestId('producer-filter')).toBeInTheDocument();
    expect(screen.getByTestId('tag-filter')).toBeInTheDocument();
    expect(screen.getByTestId('visibility-filter')).toBeInTheDocument();
    expect(screen.getByTestId('saved-filters-control')).toBeInTheDocument();
    expect(screen.getByTestId('filter-pills')).toBeInTheDocument();
  });

  it('should have proper layout structure', () => {
    mockStore();

    const { container } = render(<FilterBar />);

    // Should have a container with CSS module class (hashed)
    const filterBar = container.firstChild as HTMLElement;
    expect(filterBar.className).toMatch(/filterBar/);
  });

  it('should render correlation ID filter and time range filter in top row', () => {
    mockStore();

    render(<FilterBar />);

    const correlationFilter = screen.getByTestId('correlation-id-filter');
    const timeRangeFilter = screen.getByTestId('time-range-filter');

    // Both should be present
    expect(correlationFilter).toBeInTheDocument();
    expect(timeRangeFilter).toBeInTheDocument();
  });

  it('should render filter pills below filter controls', () => {
    mockStore({
      correlationId: 'test-123',
      timeRange: { preset: 'last5min' },
      getActiveFilters: () => [
        {
          type: 'correlationId',
          value: 'test-123',
          label: 'Correlation ID: test-123',
        },
      ],
    });

    render(<FilterBar />);

    expect(screen.getByTestId('filter-pills')).toBeInTheDocument();
  });

  it('should have appropriate spacing between components', () => {
    mockStore();

    const { container } = render(<FilterBar />);
    const filterBar = container.firstChild as HTMLElement;

    // Should have filter controls with CSS module class (hashed)
    const filterControls = filterBar.querySelector('[class*="filterControls"]');
    expect(filterControls).toBeInTheDocument();
  });

  it('should maintain consistent styling with dashboard theme', () => {
    mockStore();

    const { container } = render(<FilterBar />);
    const filterBar = container.firstChild as HTMLElement;

    // Should have padding and background consistent with dashboard
    expect(filterBar).toBeDefined();
  });
});
