import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FilterPills from './FilterPills';
import { useFilterStore } from '../../store/filterStore';

vi.mock('../../store/filterStore');

describe('FilterPills', () => {
  const mockRemoveFilter = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should not render anything when no filters are active', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last10min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    const { container } = render(<FilterPills />);
    expect(container.firstChild).toBeNull();
  });

  it('should render filter pill for active correlation ID', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last10min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    expect(screen.getByText('Correlation ID: test-123')).toBeInTheDocument();
  });

  it('should render filter pill for active time range', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last5min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    expect(screen.getByText('Time: Last 5 min')).toBeInTheDocument();
  });

  it('should render multiple filter pills', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last1hour' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    expect(screen.getByText('Correlation ID: test-123')).toBeInTheDocument();
    expect(screen.getByText('Time: Last hour')).toBeInTheDocument();
  });

  it('should render remove button for each pill', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last10min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });
    expect(removeButton).toBeInTheDocument();
  });

  it('should call removeFilter when remove button is clicked', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last10min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });

    fireEvent.click(removeButton);

    expect(mockRemoveFilter).toHaveBeenCalledWith('correlationId');
  });

  it('should call removeFilter with correct type for time range', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: { preset: 'last5min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*time/i });

    fireEvent.click(removeButton);

    expect(mockRemoveFilter).toHaveBeenCalledWith('timeRange');
  });

  it('should display pills in a horizontal layout', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last5min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    const container = screen.getByText('Correlation ID: test-123').closest('div')?.parentElement;

    // Should have container class (hashed by CSS modules)
    expect(container?.className).toMatch(/container/);
  });

  it('should render X icon in remove button', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'test-123',
        timeRange: { preset: 'last10min' as const },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });

    expect(removeButton).toHaveTextContent('×');
  });

  it('should handle custom time range label', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        timeRange: {
          preset: 'custom' as const,
          start: new Date('2025-01-01T10:00:00').getTime(),
          end: new Date('2025-01-01T12:00:00').getTime(),
        },
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });

    render(<FilterPills />);
    expect(screen.getByText(/Time:/)).toBeInTheDocument();
  });
});
