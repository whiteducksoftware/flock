export type ViewMode = 'agent' | 'blackboard';

export interface ServerGraphNode {
  id: string;
  type: string;
  data: Record<string, unknown>;
  position?: { x: number; y: number };
  hidden?: boolean;
}

export interface ServerGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
  data?: Record<string, unknown>;
  hidden?: boolean;
}

export interface ServerGraphSnapshot {
  generatedAt: string;
  viewMode: ViewMode;
  nodes: ServerGraphNode[];
  edges: ServerGraphEdge[];
  totalArtifacts: number;
  truncated: boolean;
  statistics?: Record<string, unknown>;
}

export interface GraphFiltersPayload {
  correlationId?: string | null;
  artifactTypes?: string[];
  producers?: string[];
  tags?: string[];
  visibility?: string[];
}

export interface GraphRequestPayload {
  viewMode: ViewMode;
  filters?: GraphFiltersPayload;
}
