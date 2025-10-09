import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FilterPills from './FilterPills';
import { useFilterStore } from '../../store/filterStore';

vi.mock('../../store/filterStore');

describe('FilterPills', () => {
  const mockRemoveFilter = vi.fn();

  const setupStore = (filters: { type: string; value: string | Record<string, unknown>; label: string }[]) => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        getActiveFilters: () => filters,
        removeFilter: mockRemoveFilter,
      };
      return selector(state);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should not render anything when no filters are active', () => {
    setupStore([]);

    const { container } = render(<FilterPills />);
    expect(container.firstChild).toBeNull();
  });

  it('should render filter pill for active correlation ID', () => {
    setupStore([
      {
        type: 'correlationId',
        value: 'test-123',
        label: 'Correlation ID: test-123',
      },
    ]);

    render(<FilterPills />);
    expect(screen.getByText('Correlation ID: test-123')).toBeInTheDocument();
  });

  it('should render filter pill for active time range', () => {
    setupStore([
      {
        type: 'timeRange',
        value: { preset: 'last5min' },
        label: 'Time: Last 5 min',
      },
    ]);

    render(<FilterPills />);
    expect(screen.getByText('Time: Last 5 min')).toBeInTheDocument();
  });

  it('should render multiple filter pills', () => {
    setupStore([
      { type: 'correlationId', value: 'test-123', label: 'Correlation ID: test-123' },
      { type: 'timeRange', value: { preset: 'last1hour' }, label: 'Time: Last hour' },
    ]);

    render(<FilterPills />);
    expect(screen.getByText('Correlation ID: test-123')).toBeInTheDocument();
    expect(screen.getByText('Time: Last hour')).toBeInTheDocument();
  });

  it('should render remove button for each pill', () => {
    setupStore([
      { type: 'correlationId', value: 'test-123', label: 'Correlation ID: test-123' },
    ]);

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });
    expect(removeButton).toBeInTheDocument();
  });

  it('should call removeFilter when remove button is clicked', () => {
    const filter = { type: 'correlationId', value: 'test-123', label: 'Correlation ID: test-123' };
    setupStore([filter]);

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });

    fireEvent.click(removeButton);

    expect(mockRemoveFilter).toHaveBeenCalledWith(filter);
  });

  it('should call removeFilter with correct type for time range', () => {
    const filter = {
      type: 'timeRange',
      value: { preset: 'last5min' },
      label: 'Time: Last 5 min',
    };
    setupStore([filter]);

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*time/i });

    fireEvent.click(removeButton);

    expect(mockRemoveFilter).toHaveBeenCalledWith(filter);
  });

  it('should display pills in a horizontal layout', () => {
    setupStore([
      { type: 'correlationId', value: 'test-123', label: 'Correlation ID: test-123' },
    ]);

    render(<FilterPills />);
    const container = screen.getByText('Correlation ID: test-123').closest('div')?.parentElement;

    // Should have container class (hashed by CSS modules)
    expect(container?.className).toMatch(/container/);
  });

  it('should render X icon in remove button', () => {
    setupStore([
      { type: 'correlationId', value: 'test-123', label: 'Correlation ID: test-123' },
    ]);

    render(<FilterPills />);
    const removeButton = screen.getByRole('button', { name: /remove.*correlation/i });

    expect(removeButton).toHaveTextContent('×');
  });

  it('should handle custom time range label', () => {
    setupStore([
      {
        type: 'timeRange',
        value: {
          preset: 'custom',
          start: new Date('2025-01-01T10:00:00').getTime(),
          end: new Date('2025-01-01T12:00:00').getTime(),
        },
        label: 'Time: 1/1/2025, 10:00:00 AM - 1/1/2025, 12:00:00 PM',
      },
    ]);

    render(<FilterPills />);
    expect(screen.getByText(/Time:/)).toBeInTheDocument();
  });
});
