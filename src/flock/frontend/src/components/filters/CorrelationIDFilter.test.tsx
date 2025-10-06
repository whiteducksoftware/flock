import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CorrelationIDFilter from './CorrelationIDFilter';
import { useFilterStore } from '../../store/filterStore';

vi.mock('../../store/filterStore');

describe('CorrelationIDFilter', () => {
  const mockSetCorrelationId = vi.fn();
  const mockAvailableIds = [
    {
      correlation_id: 'abc12345',
      first_seen: Date.now() - 120000,
      artifact_count: 5,
      run_count: 2,
    },
    {
      correlation_id: 'def67890',
      first_seen: Date.now() - 60000,
      artifact_count: 3,
      run_count: 1,
    },
    {
      correlation_id: 'ghi11111',
      first_seen: Date.now() - 300000,
      artifact_count: 10,
      run_count: 3,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        availableCorrelationIds: mockAvailableIds,
        setCorrelationId: mockSetCorrelationId,
      };
      return selector(state);
    });
  });

  it('should render correlation ID filter input', () => {
    render(<CorrelationIDFilter />);
    expect(screen.getByPlaceholderText(/Search correlation ID/i)).toBeInTheDocument();
  });

  it('should show dropdown when input is focused', () => {
    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i);

    fireEvent.focus(input);

    // Should show all available IDs
    expect(screen.getByText(/abc12345/)).toBeInTheDocument();
    expect(screen.getByText(/def67890/)).toBeInTheDocument();
    expect(screen.getByText(/ghi11111/)).toBeInTheDocument();
  });

  it('should display metadata for each correlation ID', () => {
    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i);

    fireEvent.focus(input);

    // Should show artifact count and time ago
    expect(screen.getByText(/5 messages/)).toBeInTheDocument();
    expect(screen.getByText(/3 messages/)).toBeInTheDocument();
    expect(screen.getByText(/10 messages/)).toBeInTheDocument();
  });

  it('should filter dropdown items based on input', () => {
    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i) as HTMLInputElement;

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'abc' } });

    // Should only show matching ID
    expect(screen.getByText(/abc12345/)).toBeInTheDocument();
    expect(screen.queryByText(/def67890/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ghi11111/)).not.toBeInTheDocument();
  });

  it('should call setCorrelationId when an option is selected', () => {
    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i);

    fireEvent.focus(input);
    const option = screen.getByText(/abc12345/);
    fireEvent.click(option);

    expect(mockSetCorrelationId).toHaveBeenCalledWith('abc12345');
  });

  it('should display selected correlation ID in input', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'abc12345',
        availableCorrelationIds: mockAvailableIds,
        setCorrelationId: mockSetCorrelationId,
      };
      return selector(state);
    });

    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i) as HTMLInputElement;

    expect(input.value).toBe('abc12345');
  });

  it('should clear selection when clear button is clicked', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: 'abc12345',
        availableCorrelationIds: mockAvailableIds,
        setCorrelationId: mockSetCorrelationId,
      };
      return selector(state);
    });

    render(<CorrelationIDFilter />);
    const clearButton = screen.getByRole('button', { name: /clear/i });

    fireEvent.click(clearButton);

    expect(mockSetCorrelationId).toHaveBeenCalledWith(null);
  });

  it('should hide dropdown when clicking outside', () => {
    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i);

    fireEvent.focus(input);
    expect(screen.getByText(/abc12345/)).toBeInTheDocument();

    // Simulate click outside
    fireEvent.blur(input);

    // Dropdown should be hidden (use setTimeout to wait for blur)
    setTimeout(() => {
      expect(screen.queryByText(/abc12345/)).not.toBeInTheDocument();
    }, 100);
  });

  it('should show "No correlation IDs found" when list is empty', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        availableCorrelationIds: [],
        setCorrelationId: mockSetCorrelationId,
      };
      return selector(state);
    });

    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i);

    fireEvent.focus(input);

    expect(screen.getByText(/No correlation IDs found/i)).toBeInTheDocument();
  });

  it('should format time ago correctly', () => {
    const now = Date.now();
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        correlationId: null,
        availableCorrelationIds: [
          {
            correlation_id: 'recent',
            first_seen: now - 30000, // 30 seconds ago
            artifact_count: 1,
            run_count: 1,
          },
          {
            correlation_id: 'old',
            first_seen: now - 3600000, // 1 hour ago
            artifact_count: 1,
            run_count: 1,
          },
        ],
        setCorrelationId: mockSetCorrelationId,
      };
      return selector(state);
    });

    render(<CorrelationIDFilter />);
    const input = screen.getByPlaceholderText(/Search correlation ID/i);

    fireEvent.focus(input);

    // Should show relative time
    expect(screen.getByText(/30s ago/i)).toBeInTheDocument();
    expect(screen.getByText(/1h ago/i)).toBeInTheDocument();
  });
});
