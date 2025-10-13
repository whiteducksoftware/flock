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

// Phase 1.3: Logic Operations UX - Real-time WebSocket Events
export interface CorrelationGroupUpdatedEvent {
  timestamp: string;
  agent_name: string;
  subscription_index: number;
  correlation_key: string;
  collected_types: Record<string, number>;
  required_types: Record<string, number>;
  waiting_for: string[];
  elapsed_seconds: number;
  expires_in_seconds: number | null;
  expires_in_artifacts: number | null;
  artifact_id: string;
  artifact_type: string;
  is_complete: boolean;
}

export interface BatchItemAddedEvent {
  timestamp: string;
  agent_name: string;
  subscription_index: number;
  items_collected: number;
  items_target: number | null;
  items_remaining: number | null;
  elapsed_seconds: number;
  timeout_seconds: number | null;
  timeout_remaining_seconds: number | null;
  will_flush: 'on_size' | 'on_timeout' | 'unknown';
  artifact_id: string;
  artifact_type: string;
}

// Agent logic operations state (from /api/agents endpoint + WebSocket updates)
export interface AgentLogicOperations {
  subscription_index: number;
  subscription_types: string[];
  join?: JoinSpecConfig;
  batch?: BatchSpecConfig;
  waiting_state?: LogicOperationsWaitingState;
}

export interface JoinSpecConfig {
  correlation_strategy: 'by_key';
  window_type: 'time' | 'count';
  window_value: number;
  window_unit: 'seconds' | 'artifacts';
  required_types: string[];
  type_counts: Record<string, number>;
}

export interface BatchSpecConfig {
  strategy: 'size' | 'timeout' | 'hybrid';
  size?: number;
  timeout_seconds?: number;
}

export interface LogicOperationsWaitingState {
  is_waiting: boolean;
  correlation_groups?: CorrelationGroupState[];
  batch_state?: BatchState;
}

export interface CorrelationGroupState {
  correlation_key: string;
  created_at: string;
  elapsed_seconds: number;
  expires_in_seconds: number | null;
  expires_in_artifacts: number | null;
  collected_types: Record<string, number>;
  required_types: Record<string, number>;
  waiting_for: string[];
  is_complete: boolean;
  is_expired: boolean;
}

export interface BatchState {
  created_at: string;
  elapsed_seconds: number;
  items_collected: number;
  items_target: number | null;
  items_remaining: number | null;
  timeout_seconds?: number;
  timeout_remaining_seconds?: number;
  will_flush: 'on_size' | 'on_timeout' | 'unknown';
}
