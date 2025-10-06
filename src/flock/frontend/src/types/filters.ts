export type TimeRangePreset = 'last5min' | 'last10min' | 'last1hour' | 'custom';

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
