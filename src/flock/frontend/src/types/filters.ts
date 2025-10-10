export type TimeRangePreset = 'last5min' | 'last10min' | 'last1hour' | 'custom' | 'all';

export interface TimeRange {
  preset: TimeRangePreset;
  start?: number;
  end?: number;
}

export interface CorrelationIdMetadata {
  correlation_id: string;
  first_seen: number;
  artifact_count: number;
  run_count: number;
}

export interface FilterFacets {
  artifactTypes: string[];
  producers: string[];
  tags: string[];
  visibilities: string[];
}

export interface ArtifactSummary {
  total: number;
  by_type: Record<string, number>;
  by_producer: Record<string, number>;
  by_visibility: Record<string, number>;
  tag_counts: Record<string, number>;
  earliest_created_at: string | null;
  latest_created_at: string | null;
}

export interface FilterSnapshot {
  correlationId: string | null;
  timeRange: TimeRange;
  artifactTypes: string[];
  producers: string[];
  tags: string[];
  visibility: string[];
}

export interface SavedFilterMeta {
  filter_id: string;
  name: string;
  created_at: number;
  filters: FilterSnapshot;
}
