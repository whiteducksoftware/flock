// Legacy types (still used during migration for events, WebSocket handlers)
export interface Message {
  id: string;
  type: string;
  payload: any;
  timestamp: number;
  correlationId: string;
  producedBy: string;
  tags?: string[];
  visibilityKind?: string;
  partitionKey?: string | null;
  version?: number;
  isStreaming?: boolean;
  streamingText?: string;
  consumedBy?: string[];
}

// New backend API types (Phase 1 - Spec 002)
export interface GraphRequest {
  viewMode: 'agent' | 'blackboard';
  filters: GraphFilters;
  options?: GraphRequestOptions;
}

export interface GraphFilters {
  correlation_id?: string | null;
  time_range: TimeRangeFilter;
  artifactTypes: string[];
  producers: string[];
  tags: string[];
  visibility: string[];
}

export interface TimeRangeFilter {
  preset: 'last10min' | 'last5min' | 'last1hour' | 'all' | 'custom';
  start?: string | null;
  end?: string | null;
}

export interface GraphRequestOptions {
  include_statistics?: boolean;
  label_offset_strategy?: 'stack' | 'none';
  limit?: number;
}

export interface GraphSnapshot {
  generatedAt: string;
  viewMode: 'agent' | 'blackboard';
  filters: GraphFilters;
  nodes: GraphNode[];
  edges: GraphEdge[];
  statistics: GraphStatistics | null;
  totalArtifacts: number;
  truncated: boolean;
}

export interface GraphNode {
  id: string;
  type: 'agent' | 'message';
  data: Record<string, any>;
  position: { x: number; y: number };
  hidden: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'message_flow' | 'transformation';
  label?: string | null;
  data: Record<string, any>;
  markerEnd?: { type: string; width: number; height: number };
  hidden: boolean;
}

export interface GraphStatistics {
  producedByAgent: Record<string, GraphAgentMetrics>;
  consumedByAgent: Record<string, GraphAgentMetrics>;
  artifactSummary: ArtifactSummary;
}

export interface GraphAgentMetrics {
  total: number;
  byType: Record<string, number>;
}

export interface ArtifactSummary {
  total: number;
  by_type: Record<string, number>;
  by_producer: Record<string, number>;
  by_visibility: Record<string, number>;
  tag_counts: Record<string, number>;
  earliest_created_at: string;
  latest_created_at: string;
}
