import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TimeRangeFilter from './TimeRangeFilter';
import { useFilterStore } from '../../store/filterStore';

vi.mock('../../store/filterStore');

describe('TimeRangeFilter', () => {
  const mockSetTimeRange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        timeRange: { preset: 'last10min' },
        setTimeRange: mockSetTimeRange,
      };
      return selector(state);
    });
  });

  it('should render time range filter with presets', () => {
    render(<TimeRangeFilter />);
    expect(screen.getByText(/Last 5 min/i)).toBeInTheDocument();
    expect(screen.getByText(/Last 10 min/i)).toBeInTheDocument();
    expect(screen.getByText(/Last hour/i)).toBeInTheDocument();
    expect(screen.getByText(/Custom/i)).toBeInTheDocument();
  });

  it('should highlight selected preset', () => {
    render(<TimeRangeFilter />);
    const last10MinButton = screen.getByText(/Last 10 min/i);

    // Should have active class for selected preset (hashed by CSS modules)
    expect(last10MinButton.className).toMatch(/active/);
  });

  it('should call setTimeRange when preset is selected', () => {
    render(<TimeRangeFilter />);
    const last5MinButton = screen.getByText(/Last 5 min/i);

    fireEvent.click(last5MinButton);

    expect(mockSetTimeRange).toHaveBeenCalledWith({ preset: 'last5min' });
  });

  it('should show custom date inputs when Custom is selected', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        timeRange: { preset: 'custom', start: Date.now() - 3600000, end: Date.now() },
        setTimeRange: mockSetTimeRange,
      };
      return selector(state);
    });

    render(<TimeRangeFilter />);

    expect(screen.getByLabelText(/Start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/End/i)).toBeInTheDocument();
  });

  it('should not show custom date inputs when preset is not custom', () => {
    render(<TimeRangeFilter />);

    expect(screen.queryByLabelText(/Start/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/End/i)).not.toBeInTheDocument();
  });

  it('should call setTimeRange with custom range when dates are changed', () => {
    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        timeRange: { preset: 'custom', start: Date.now() - 3600000, end: Date.now() },
        setTimeRange: mockSetTimeRange,
      };
      return selector(state);
    });

    render(<TimeRangeFilter />);

    const startInput = screen.getByLabelText(/Start/i) as HTMLInputElement;

    // Create datetime-local format
    const startDate = new Date(Date.now() - 7200000);
    const startValue = startDate.toISOString().slice(0, 16);

    fireEvent.change(startInput, { target: { value: startValue } });

    expect(mockSetTimeRange).toHaveBeenCalledWith({
      preset: 'custom',
      start: expect.any(Number),
      end: expect.any(Number),
    });
  });

  it('should display current custom range values in inputs', () => {
    const now = Date.now();
    const start = now - 3600000;
    const end = now;

    vi.mocked(useFilterStore).mockImplementation((selector: any) => {
      const state = {
        timeRange: { preset: 'custom', start, end },
        setTimeRange: mockSetTimeRange,
      };
      return selector(state);
    });

    render(<TimeRangeFilter />);

    const startInput = screen.getByLabelText(/Start/i) as HTMLInputElement;
    const endInput = screen.getByLabelText(/End/i) as HTMLInputElement;

    // Should have values set
    expect(startInput.value).toBeTruthy();
    expect(endInput.value).toBeTruthy();
  });

  it('should switch to custom preset when clicking Custom button', () => {
    render(<TimeRangeFilter />);
    const customButton = screen.getByText(/Custom/i);

    fireEvent.click(customButton);

    expect(mockSetTimeRange).toHaveBeenCalledWith({
      preset: 'custom',
      start: expect.any(Number),
      end: expect.any(Number),
    });
  });

  it('should apply consistent styling to all preset buttons', () => {
    render(<TimeRangeFilter />);
    const buttons = [
      screen.getByText(/Last 5 min/i),
      screen.getByText(/Last 10 min/i),
      screen.getByText(/Last hour/i),
      screen.getByText(/Custom/i),
    ];

    buttons.forEach((button) => {
      // All buttons should have the presetButton class (hashed by CSS modules)
      expect(button.className).toMatch(/presetButton/);
    });
  });

  it('should handle last1hour preset correctly', () => {
    render(<TimeRangeFilter />);
    const lastHourButton = screen.getByText(/Last hour/i);

    fireEvent.click(lastHourButton);

    expect(mockSetTimeRange).toHaveBeenCalledWith({ preset: 'last1hour' });
  });
});
