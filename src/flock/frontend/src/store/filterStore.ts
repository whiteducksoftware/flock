import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import {
  TimeRange,
  CorrelationIdMetadata,
  FilterFacets,
  ArtifactSummary,
  SavedFilterMeta,
  FilterSnapshot,
} from '../types/filters';
import { useGraphStore } from './graphStore';

export type ActiveFilterType =
  | 'correlationId'
  | 'timeRange'
  | 'artifactTypes'
  | 'producers'
  | 'tags'
  | 'visibility';

export interface ActiveFilter {
  type: ActiveFilterType;
  value: string | TimeRange;
  label: string;
}

interface FilterState {
  correlationId: string | null;
  timeRange: TimeRange;
  selectedArtifactTypes: string[];
  selectedProducers: string[];
  selectedTags: string[];
  selectedVisibility: string[];
  availableCorrelationIds: CorrelationIdMetadata[];
  availableArtifactTypes: string[];
  availableProducers: string[];
  availableTags: string[];
  availableVisibility: string[];
  summary: ArtifactSummary | null;
  savedFilters: SavedFilterMeta[];

  setCorrelationId: (id: string | null) => void;
  setTimeRange: (range: TimeRange) => void;
  setArtifactTypes: (types: string[]) => void;
  setProducers: (producers: string[]) => void;
  setTags: (tags: string[]) => void;
  setVisibility: (visibility: string[]) => void;
  clearFilters: () => void;
  applyFilters: () => Promise<void>;

  updateAvailableCorrelationIds: (metadata: CorrelationIdMetadata[]) => void;
  updateAvailableFacets: (facets: FilterFacets) => void;
  setSummary: (summary: ArtifactSummary | null) => void;

  setSavedFilters: (filters: SavedFilterMeta[]) => void;
  addSavedFilter: (filter: SavedFilterMeta) => void;
  removeSavedFilter: (filterId: string) => void;

  getActiveFilters: () => ActiveFilter[];
  removeFilter: (filter: ActiveFilter) => void;
  getFilterSnapshot: () => FilterSnapshot;
  applyFilterSnapshot: (snapshot: FilterSnapshot) => void;
}

const defaultTimeRange: TimeRange = { preset: 'last10min' };

export const formatTimeRange = (range: TimeRange): string => {
  if (range.preset === 'last5min') return 'Last 5 min';
  if (range.preset === 'last10min') return 'Last 10 min';
  if (range.preset === 'last1hour') return 'Last hour';
  if (range.preset === 'all') return 'All time';
  if (range.preset === 'custom' && range.start && range.end) {
    const startDate = new Date(range.start).toLocaleString();
    const endDate = new Date(range.end).toLocaleString();
    return `${startDate} - ${endDate}`;
  }
  if (range.preset === 'custom') {
    return 'Custom range';
  }
  return 'Last 10 min';
};

const uniqueSorted = (items: string[]) => Array.from(new Set(items)).sort((a, b) => a.localeCompare(b));

export const useFilterStore = create<FilterState>()(
  devtools(
    persist(
      (set, get) => ({
        correlationId: null,
        timeRange: defaultTimeRange,
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

      setCorrelationId: (id) => set({ correlationId: id }),
      setTimeRange: (range) => set({ timeRange: range }),
      setArtifactTypes: (types) => set({ selectedArtifactTypes: uniqueSorted(types) }),
      setProducers: (producers) => set({ selectedProducers: uniqueSorted(producers) }),
      setTags: (tags) => set({ selectedTags: uniqueSorted(tags) }),
      setVisibility: (visibility) => set({ selectedVisibility: uniqueSorted(visibility) }),
      clearFilters: () =>
        set({
          correlationId: null,
          timeRange: defaultTimeRange,
          selectedArtifactTypes: [],
          selectedProducers: [],
          selectedTags: [],
          selectedVisibility: [],
        }),

      applyFilters: async () => {
        // UI Optimization Migration (Phase 4 - Spec 002): Backend-driven filtering
        // Trigger backend snapshot refresh with current filter state
        // The graphStore will read current filter state via buildGraphRequest()
        await useGraphStore.getState().refreshCurrentView();
      },

      updateAvailableCorrelationIds: (metadata) => {
        const sorted = [...metadata].sort((a, b) => b.first_seen - a.first_seen);
        set({
          availableCorrelationIds: sorted.slice(0, 50),
        });
      },

      updateAvailableFacets: (facets) =>
        set({
          availableArtifactTypes: uniqueSorted(facets.artifactTypes),
          availableProducers: uniqueSorted(facets.producers),
          availableTags: uniqueSorted(facets.tags),
          availableVisibility: uniqueSorted(facets.visibilities),
        }),

      setSummary: (summary) => set({ summary }),

      setSavedFilters: (filters) => set({ savedFilters: filters }),
      addSavedFilter: (filter) =>
        set((state) => ({
          savedFilters: [...state.savedFilters.filter((f) => f.filter_id !== filter.filter_id), filter],
        })),
      removeSavedFilter: (filterId) =>
        set((state) => ({
          savedFilters: state.savedFilters.filter((f) => f.filter_id !== filterId),
        })),

      getFilterSnapshot: () => {
        const state = get();
        return {
          correlationId: state.correlationId,
          timeRange: state.timeRange,
          artifactTypes: [...state.selectedArtifactTypes],
          producers: [...state.selectedProducers],
          tags: [...state.selectedTags],
          visibility: [...state.selectedVisibility],
        };
      },

      applyFilterSnapshot: (snapshot) =>
        set({
          correlationId: snapshot.correlationId,
          timeRange: snapshot.timeRange,
          selectedArtifactTypes: uniqueSorted(snapshot.artifactTypes),
          selectedProducers: uniqueSorted(snapshot.producers),
          selectedTags: uniqueSorted(snapshot.tags),
          selectedVisibility: uniqueSorted(snapshot.visibility),
        }),

      getActiveFilters: () => {
        console.debug('[filterStore] computing active filters', { correlationId: get().correlationId, timeRange: get().timeRange });
        const state = get();
        const filters: ActiveFilter[] = [];

        if (state.correlationId) {
          filters.push({
            type: 'correlationId',
            value: state.correlationId,
            label: `Correlation ID: ${state.correlationId}`,
          });
        }

        filters.push({
          type: 'timeRange',
          value: state.timeRange,
          label: `Time: ${formatTimeRange(state.timeRange)}`,
        });

        state.selectedArtifactTypes.forEach((type) => {
          filters.push({
            type: 'artifactTypes',
            value: type,
            label: `Type: ${type}`,
          });
        });

        state.selectedProducers.forEach((producer) => {
          filters.push({
            type: 'producers',
            value: producer,
            label: `Producer: ${producer}`,
          });
        });

        state.selectedTags.forEach((tag) => {
          filters.push({
            type: 'tags',
            value: tag,
            label: `Tag: ${tag}`,
          });
        });

        state.selectedVisibility.forEach((kind) => {
          filters.push({
            type: 'visibility',
            value: kind,
            label: `Visibility: ${kind}`,
          });
        });

        return filters;
      },

      removeFilter: (filter) => {
        if (filter.type === 'correlationId') {
          set({ correlationId: null });
          return;
        }
        if (filter.type === 'timeRange') {
          set({ timeRange: defaultTimeRange });
          return;
        }
        if (typeof filter.value !== 'string') {
          return;
        }
        set((state) => {
          if (filter.type === 'artifactTypes') {
            return { selectedArtifactTypes: state.selectedArtifactTypes.filter((item) => item !== filter.value) };
          }
          if (filter.type === 'producers') {
            return { selectedProducers: state.selectedProducers.filter((item) => item !== filter.value) };
          }
          if (filter.type === 'tags') {
            return { selectedTags: state.selectedTags.filter((item) => item !== filter.value) };
          }
          if (filter.type === 'visibility') {
            return { selectedVisibility: state.selectedVisibility.filter((item) => item !== filter.value) };
          }
          return {};
        });
      },
      }),
      {
        name: 'flock-filter-state',
        partialize: (state) => ({
          correlationId: state.correlationId,
          timeRange: state.timeRange,
          selectedArtifactTypes: state.selectedArtifactTypes,
          selectedProducers: state.selectedProducers,
          selectedTags: state.selectedTags,
          selectedVisibility: state.selectedVisibility,
        }),
      }
    ),
    { name: 'filterStore' }
  )
);
