import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useFilterStore } from './filterStore';
import type { FilterFacets, FilterSnapshot } from '../types/filters';
import { useGraphStore } from './graphStore';

// Mock graphStore to test applyFilters integration
vi.mock('./graphStore', () => ({
  useGraphStore: {
    getState: vi.fn(() => ({
      refreshCurrentView: vi.fn(),
      viewMode: 'agent',
    })),
  },
}));

describe('filterStore', () => {
  beforeEach(() => {
    useFilterStore.setState({
      correlationId: null,
      timeRange: { preset: 'last10min' },
      selectedArtifactTypes: [],
      selectedProducers: [],
      selectedTags: [],
      selectedVisibility: [],
      availableCorrelationIds: [],
      availableArtifactTypes: [],
      availableProducers: [],
      availableTags: [],
      availableVisibility: [],
      summary: null,
      savedFilters: [],
    });
  });

  describe('initial state', () => {
    it('should have defaults set', () => {
      const state = useFilterStore.getState();
      expect(state.correlationId).toBeNull();
      expect(state.timeRange).toEqual({ preset: 'last10min' });
      expect(state.selectedArtifactTypes).toEqual([]);
      expect(state.availableCorrelationIds).toEqual([]);
    });
  });

  describe('mutators', () => {
    it('should update correlation id and time range', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('abc');
      store.setTimeRange({ preset: 'last5min' });
      expect(useFilterStore.getState().correlationId).toBe('abc');
      expect(useFilterStore.getState().timeRange).toEqual({ preset: 'last5min' });
    });

    it('should update multi-select filters', () => {
      const store = useFilterStore.getState();
      store.setArtifactTypes(['TypeB', 'TypeA']);
      store.setProducers(['b', 'a']);
      store.setTags(['beta']);
      store.setVisibility(['Private', 'Public']);

      const state = useFilterStore.getState();
      expect(state.selectedArtifactTypes).toEqual(['TypeA', 'TypeB']);
      expect(state.selectedProducers).toEqual(['a', 'b']);
      expect(state.selectedTags).toEqual(['beta']);
      expect(state.selectedVisibility).toEqual(['Private', 'Public']);
    });

    it('should clear filters to defaults', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('abc');
      store.setArtifactTypes(['TypeA']);
      store.setTags(['x']);
      store.clearFilters();

      const state = useFilterStore.getState();
      expect(state.correlationId).toBeNull();
      expect(state.selectedArtifactTypes).toEqual([]);
      expect(state.selectedTags).toEqual([]);
      expect(state.timeRange).toEqual({ preset: 'last10min' });
    });

    it('should update available correlation ids', () => {
      const now = Date.now();
      useFilterStore
        .getState()
        .updateAvailableCorrelationIds([
          { correlation_id: 'old', first_seen: now - 10_000, artifact_count: 1, run_count: 1 },
          { correlation_id: 'new', first_seen: now - 1_000, artifact_count: 2, run_count: 2 },
        ]);
      const state = useFilterStore.getState();
      expect(state.availableCorrelationIds.map((m) => m.correlation_id)).toEqual(['new', 'old']);
    });

    it('should update available facets', () => {
      const facets: FilterFacets = {
        artifactTypes: ['TypeB', 'TypeA'],
        producers: ['b', 'a'],
        tags: ['beta', 'alpha'],
        visibilities: ['Private', 'Public'],
      };
      useFilterStore.getState().updateAvailableFacets(facets);
      const state = useFilterStore.getState();
      expect(state.availableArtifactTypes).toEqual(['TypeA', 'TypeB']);
      expect(state.availableProducers).toEqual(['a', 'b']);
      expect(state.availableTags).toEqual(['alpha', 'beta']);
      expect(state.availableVisibility).toEqual(['Private', 'Public']);
    });
  });

  describe('active filters', () => {
    it('should return active filters across selections', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('abc');
      store.setTimeRange({ preset: 'last5min' });
      store.setArtifactTypes(['TypeA']);
      store.setProducers(['agent1']);
      store.setTags(['urgent']);
      store.setVisibility(['Public']);

      const active = store.getActiveFilters();
      expect(active).toHaveLength(6);
      expect(active.map((f) => f.type)).toContain('visibility');
    });

    it('should remove individual filters', () => {
      const store = useFilterStore.getState();
      store.setArtifactTypes(['TypeA', 'TypeB']);

      const [firstFilter] = store.getActiveFilters().filter((f) => f.type === 'artifactTypes');
      expect(firstFilter?.value).toBe('TypeA');

      useFilterStore.getState().removeFilter(firstFilter!);
      expect(useFilterStore.getState().selectedArtifactTypes).toEqual(['TypeB']);
    });
  });

  describe('snapshots', () => {
    it('should export and reapply filter snapshots', () => {
      const store = useFilterStore.getState();
      store.setCorrelationId('snapshot');
      store.setArtifactTypes(['TypeA']);

      const snapshot = store.getFilterSnapshot();
      useFilterStore.getState().clearFilters();
      useFilterStore.getState().applyFilterSnapshot(snapshot);

      const state = useFilterStore.getState();
      expect(state.correlationId).toBe('snapshot');
      expect(state.selectedArtifactTypes).toEqual(['TypeA']);
    });

    it('should manage saved filters list', () => {
      const snapshot: FilterSnapshot = {
        correlationId: null,
        timeRange: { preset: 'last10min' },
        artifactTypes: [],
        producers: [],
        tags: [],
        visibility: [],
      };
      useFilterStore.getState().addSavedFilter({
        filter_id: '1',
        name: 'Default',
        created_at: Date.now(),
        filters: snapshot,
      });

      expect(useFilterStore.getState().savedFilters).toHaveLength(1);
      useFilterStore.getState().removeSavedFilter('1');
      expect(useFilterStore.getState().savedFilters).toHaveLength(0);
    });
  });

  describe('applyFilters - backend integration (Phase 4)', () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it('should trigger backend snapshot refresh when applying filters', async () => {
      const mockRefresh = vi.fn().mockResolvedValue(undefined);
      vi.mocked(useGraphStore.getState).mockReturnValue({
        refreshCurrentView: mockRefresh,
        viewMode: 'agent',
      } as any);

      await useFilterStore.getState().applyFilters();

      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });

    it('should use current filter state when refreshing graph', async () => {
      const mockRefresh = vi.fn().mockResolvedValue(undefined);
      vi.mocked(useGraphStore.getState).mockReturnValue({
        refreshCurrentView: mockRefresh,
        viewMode: 'agent',
      } as any);

      // Set some filters
      useFilterStore.setState({
        correlationId: 'test-correlation-456',
        selectedArtifactTypes: ['Pizza', 'Burger'],
        selectedProducers: ['chef_agent'],
        selectedTags: ['urgent'],
      });

      await useFilterStore.getState().applyFilters();

      // Verify refresh was called (graphStore.refreshCurrentView will use current filter state)
      expect(mockRefresh).toHaveBeenCalledTimes(1);

      // The filters are passed via the filterStore state, which graphStore reads in buildGraphRequest
      const filterState = useFilterStore.getState();
      expect(filterState.correlationId).toBe('test-correlation-456');
      expect(filterState.selectedArtifactTypes).toContain('Pizza');
    });

    it('should handle errors from backend refresh gracefully', async () => {
      const mockRefresh = vi.fn().mockRejectedValue(new Error('Backend API error'));
      vi.mocked(useGraphStore.getState).mockReturnValue({
        refreshCurrentView: mockRefresh,
        viewMode: 'agent',
      } as any);

      // Should propagate error to caller
      await expect(useFilterStore.getState().applyFilters()).rejects.toThrow('Backend API error');
    });

    it('should work with both agent and blackboard view modes', async () => {
      const mockRefresh = vi.fn().mockResolvedValue(undefined);

      // Test agent view
      vi.mocked(useGraphStore.getState).mockReturnValue({
        refreshCurrentView: mockRefresh,
        viewMode: 'agent',
      } as any);

      await useFilterStore.getState().applyFilters();
      expect(mockRefresh).toHaveBeenCalledTimes(1);

      // Test blackboard view
      vi.mocked(useGraphStore.getState).mockReturnValue({
        refreshCurrentView: mockRefresh,
        viewMode: 'blackboard',
      } as any);

      await useFilterStore.getState().applyFilters();
      expect(mockRefresh).toHaveBeenCalledTimes(2);
    });
  });
});
