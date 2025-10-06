import { describe, it, expect, beforeEach } from 'vitest';
import { useFilterStore } from './filterStore';

describe('filterStore', () => {
  beforeEach(() => {
    const store = useFilterStore.getState();
    store.clearFilters();
    store.updateAvailableCorrelationIds([]);
  });

  describe('Initial State', () => {
    it('should have no correlation ID selected', () => {
      const state = useFilterStore.getState();
      expect(state.correlationId).toBeNull();
    });

    it('should have default time range of last 10 minutes', () => {
      const state = useFilterStore.getState();
      expect(state.timeRange).toEqual({ preset: 'last10min' });
    });

    it('should have empty available correlation IDs', () => {
      const state = useFilterStore.getState();
      expect(state.availableCorrelationIds).toEqual([]);
    });
  });

  describe('setCorrelationId', () => {
    it('should set correlation ID', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-correlation-id');

      expect(useFilterStore.getState().correlationId).toBe('test-correlation-id');
    });

    it('should clear correlation ID when set to null', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-id');
      store.setCorrelationId(null);

      expect(useFilterStore.getState().correlationId).toBeNull();
    });
  });

  describe('setTimeRange', () => {
    it('should set time range preset', () => {
      const store = useFilterStore.getState();
      store.setTimeRange({ preset: 'last5min' });

      expect(useFilterStore.getState().timeRange).toEqual({ preset: 'last5min' });
    });

    it('should set custom time range', () => {
      const store = useFilterStore.getState();
      const customRange = {
        preset: 'custom' as const,
        start: Date.now() - 3600000,
        end: Date.now(),
      };
      store.setTimeRange(customRange);

      expect(useFilterStore.getState().timeRange).toEqual(customRange);
    });
  });

  describe('clearFilters', () => {
    it('should reset all filters to defaults', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-id');
      store.setTimeRange({ preset: 'last1hour' });

      store.clearFilters();

      const state = useFilterStore.getState();
      expect(state.correlationId).toBeNull();
      expect(state.timeRange).toEqual({ preset: 'last10min' });
    });
  });

  describe('updateAvailableCorrelationIds', () => {
    it('should update available correlation IDs with metadata', () => {
      const store = useFilterStore.getState();
      const now = Date.now();
      const metadata = [
        {
          correlation_id: 'abc123',
          first_seen: now - 120000,
          artifact_count: 5,
          run_count: 2,
        },
        {
          correlation_id: 'def456',
          first_seen: now - 60000,
          artifact_count: 3,
          run_count: 1,
        },
      ];

      store.updateAvailableCorrelationIds(metadata);

      const state = useFilterStore.getState();
      // Should be sorted by most recent first
      expect(state.availableCorrelationIds).toHaveLength(2);
      expect(state.availableCorrelationIds[0]?.correlation_id).toBe('def456');
      expect(state.availableCorrelationIds[1]?.correlation_id).toBe('abc123');
    });

    it('should limit to 50 correlation IDs', () => {
      const store = useFilterStore.getState();
      const metadata = Array.from({ length: 100 }, (_, i) => ({
        correlation_id: `id-${i}`,
        first_seen: Date.now() - i * 1000,
        artifact_count: i,
        run_count: 1,
      }));

      store.updateAvailableCorrelationIds(metadata);

      const state = useFilterStore.getState();
      expect(state.availableCorrelationIds).toHaveLength(50);
    });

    it('should sort by most recent first', () => {
      const store = useFilterStore.getState();
      const now = Date.now();
      const metadata = [
        {
          correlation_id: 'oldest',
          first_seen: now - 300000,
          artifact_count: 1,
          run_count: 1,
        },
        {
          correlation_id: 'newest',
          first_seen: now - 10000,
          artifact_count: 2,
          run_count: 1,
        },
        {
          correlation_id: 'middle',
          first_seen: now - 120000,
          artifact_count: 3,
          run_count: 1,
        },
      ];

      store.updateAvailableCorrelationIds(metadata);

      const state = useFilterStore.getState();
      expect(state.availableCorrelationIds[0]?.correlation_id).toBe('newest');
      expect(state.availableCorrelationIds[1]?.correlation_id).toBe('middle');
      expect(state.availableCorrelationIds[2]?.correlation_id).toBe('oldest');
    });
  });

  describe('getActiveFilters', () => {
    it('should return empty array when no filters active', () => {
      const store = useFilterStore.getState();
      const activeFilters = store.getActiveFilters();
      expect(activeFilters).toEqual([]);
    });

    it('should return correlation ID filter when set', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-123');

      const activeFilters = store.getActiveFilters();
      expect(activeFilters).toHaveLength(1);
      expect(activeFilters[0]).toEqual({
        type: 'correlationId',
        value: 'test-123',
        label: 'Correlation ID: test-123',
      });
    });

    it('should return time range filter when not default', () => {
      const store = useFilterStore.getState();
      store.setTimeRange({ preset: 'last5min' });

      const activeFilters = store.getActiveFilters();
      expect(activeFilters).toHaveLength(1);
      expect(activeFilters[0]).toEqual({
        type: 'timeRange',
        value: { preset: 'last5min' },
        label: 'Time: Last 5 min',
      });
    });

    it('should return custom time range filter with formatted dates', () => {
      const store = useFilterStore.getState();
      const start = Date.now() - 3600000;
      const end = Date.now();
      store.setTimeRange({ preset: 'custom', start, end });

      const activeFilters = store.getActiveFilters();
      expect(activeFilters).toHaveLength(1);
      expect(activeFilters[0]?.type).toBe('timeRange');
      expect(activeFilters[0]?.label).toMatch(/^Time: /);
    });

    it('should return both filters when both are active', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-123');
      store.setTimeRange({ preset: 'last1hour' });

      const activeFilters = store.getActiveFilters();
      expect(activeFilters).toHaveLength(2);
    });
  });

  describe('removeFilter', () => {
    it('should remove correlation ID filter', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-123');

      store.removeFilter('correlationId');

      expect(useFilterStore.getState().correlationId).toBeNull();
    });

    it('should reset time range filter to default', () => {
      const store = useFilterStore.getState();
      store.setTimeRange({ preset: 'last1hour' });

      store.removeFilter('timeRange');

      expect(useFilterStore.getState().timeRange).toEqual({ preset: 'last10min' });
    });

    it('should not affect other filters', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('test-123');
      store.setTimeRange({ preset: 'last1hour' });

      store.removeFilter('correlationId');

      const state = useFilterStore.getState();
      expect(state.correlationId).toBeNull();
      expect(state.timeRange).toEqual({ preset: 'last1hour' });
    });
  });
});
