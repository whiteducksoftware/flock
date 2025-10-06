import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { TimeRange, CorrelationIdMetadata } from '../types/filters';

export interface ActiveFilter {
  type: 'correlationId' | 'timeRange';
  value: string | TimeRange;
  label: string;
}

interface FilterState {
  // Active filters
  correlationId: string | null;
  timeRange: TimeRange;

  // Autocomplete data
  availableCorrelationIds: CorrelationIdMetadata[];

  // Actions
  setCorrelationId: (id: string | null) => void;
  setTimeRange: (range: TimeRange) => void;
  clearFilters: () => void;

  // Update available IDs
  updateAvailableCorrelationIds: (metadata: CorrelationIdMetadata[]) => void;

  // Get active filters
  getActiveFilters: () => ActiveFilter[];

  // Remove specific filter
  removeFilter: (type: 'correlationId' | 'timeRange') => void;
}

const formatTimeRange = (range: TimeRange): string => {
  if (range.preset === 'last5min') return 'Last 5 min';
  if (range.preset === 'last10min') return 'Last 10 min';
  if (range.preset === 'last1hour') return 'Last hour';
  if (range.preset === 'custom' && range.start && range.end) {
    const startDate = new Date(range.start).toLocaleString();
    const endDate = new Date(range.end).toLocaleString();
    return `${startDate} - ${endDate}`;
  }
  return 'Unknown';
};

export const useFilterStore = create<FilterState>()(
  devtools(
    (set, get) => ({
      correlationId: null,
      timeRange: { preset: 'last10min' },
      availableCorrelationIds: [],

      setCorrelationId: (id) => set({ correlationId: id }),
      setTimeRange: (range) => set({ timeRange: range }),
      clearFilters: () =>
        set({
          correlationId: null,
          timeRange: { preset: 'last10min' },
        }),

      updateAvailableCorrelationIds: (metadata) => {
        // Sort by most recent first
        const sorted = [...metadata].sort((a, b) => b.first_seen - a.first_seen);
        set({
          availableCorrelationIds: sorted.slice(0, 50),
        });
      },

      getActiveFilters: () => {
        const state = get();
        const filters: ActiveFilter[] = [];

        if (state.correlationId) {
          filters.push({
            type: 'correlationId',
            value: state.correlationId,
            label: `Correlation ID: ${state.correlationId}`,
          });
        }

        // Only add time range if it's not the default
        if (state.timeRange.preset !== 'last10min') {
          filters.push({
            type: 'timeRange',
            value: state.timeRange,
            label: `Time: ${formatTimeRange(state.timeRange)}`,
          });
        }

        return filters;
      },

      removeFilter: (type) => {
        if (type === 'correlationId') {
          set({ correlationId: null });
        } else if (type === 'timeRange') {
          set({ timeRange: { preset: 'last10min' } });
        }
      },
    }),
    { name: 'filterStore' }
  )
);
