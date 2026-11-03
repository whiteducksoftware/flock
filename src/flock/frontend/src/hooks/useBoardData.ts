/**
 * Loads the board's snapshot for the view (the Flow's agents, the
 * Blackboard's artifacts) when the view changes and whenever a filter
 * changes, whichever view shows it.
 */

import { useEffect } from 'react';
import { useFilterStore } from '../store/filterStore';
import { useGraphStore } from '../store/graphStore';
import { useUIStore } from '../store/uiStore';

export function useBoardData(): void {
  const mode = useUIStore((state) => state.mode);
  const applyFilters = useFilterStore((state) => state.applyFilters);
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const selectedArtifactTypes = useFilterStore((state) => state.selectedArtifactTypes);
  const selectedProducers = useFilterStore((state) => state.selectedProducers);
  const selectedTags = useFilterStore((state) => state.selectedTags);
  const selectedVisibility = useFilterStore((state) => state.selectedVisibility);

  useEffect(() => {
    const { generateAgentViewGraph, generateBlackboardViewGraph } = useGraphStore.getState();
    // A failed load is the store's error, which the board shows
    (mode === 'agent' ? generateAgentViewGraph() : generateBlackboardViewGraph()).catch(() => {});
  }, [mode]);

  useEffect(() => {
    applyFilters().catch(() => {});
  }, [
    applyFilters,
    correlationId,
    timeRange.preset,
    timeRange.start,
    timeRange.end,
    selectedArtifactTypes.join('|'),
    selectedProducers.join('|'),
    selectedTags.join('|'),
    selectedVisibility.join('|'),
  ]);
}
