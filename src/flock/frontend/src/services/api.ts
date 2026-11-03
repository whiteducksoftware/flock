/**
 * REST API client for orchestrator control operations.
 *
 * Provides methods to publish artifacts and invoke agents via HTTP endpoints.
 * Handles error responses and provides typed return values.
 *
 * Base URL defaults to /api for same-origin requests.
 */

import type { ArtifactSummary } from '../types/filters';
import type { ImageSummary } from '../utils/imageFields';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export interface ArtifactType {
  name: string;
  schema: {
    type: string;
    properties: Record<string, any>;
  };
}

export interface Agent {
  name: string;
  description: string;
  status: string;
  subscriptions: string[];
  output_types: string[];
}

export interface PublishResponse {
  status: string;
  correlation_id: string;
  message: string;
}

export interface InvokeResponse {
  status: string;
  invocation_id: string;
  correlation_id?: string | null;
  agent: string;
  message: string;
}

export interface ArtifactTypesResponse {
  artifact_types: ArtifactType[];
}

export interface AgentsResponse {
  agents: Agent[];
}

export interface ArtifactListItem {
  id: string;
  type: string;
  payload: Record<string, any>;
  produced_by: string;
  created_at: string;
  correlation_id: string | null;
  partition_key: string | null;
  tags: string[];
  visibility: { kind: string; [key: string]: any };
  visibility_kind?: string;
  version?: number;
  consumptions?: ArtifactConsumption[];
  consumed_by?: string[];
  images?: ImageSummary[]; // with images=thumbnails: previews; the payload describes images
}

export interface ArtifactConsumption {
  artifact_id: string;
  consumer: string;
  run_id: string | null;
  correlation_id: string | null;
  consumed_at: string;
}

export interface ArtifactListResponse {
  items: ArtifactListItem[];
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
}

export interface ArtifactSummaryResponse {
  summary: ArtifactSummary;
}

export interface ArtifactQueryOptions {
  types?: string[];
  producers?: string[];
  correlationId?: string | null;
  tags?: string[];
  visibility?: string[];
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
  embedMeta?: boolean;
  images?: 'thumbnails'; // thumbnails instead of full image data
}

export interface ErrorResponse {
  error: string;
  message: string;
}

class ApiError extends Error {
  constructor(public status: number, public errorResponse: ErrorResponse) {
    super(errorResponse.message || errorResponse.error);
    this.name = 'ApiError';
  }
}

/**
 * Fetch artifact types from orchestrator
 */
export async function fetchArtifactTypes(): Promise<ArtifactType[]> {
  try {
    const response = await fetch(`${BASE_URL}/artifact-types`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: 'Unknown error',
        message: 'Failed to fetch artifact types',
      }));
      throw new ApiError(response.status, errorData);
    }

    const data: ArtifactTypesResponse = await response.json();
    return data.artifact_types;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Failed to connect to API server');
  }
}

/**
 * Fetch available agents from orchestrator
 */
export async function fetchAgents(): Promise<Agent[]> {
  try {
    const response = await fetch(`${BASE_URL}/agents`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: 'Unknown error',
        message: 'Failed to fetch agents',
      }));
      throw new ApiError(response.status, errorData);
    }

    const data: AgentsResponse = await response.json();
    return data.agents;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Failed to connect to API server');
  }
}

// UI Optimization Migration (Phase 4.1 - Spec 002): Removed fetchRegisteredAgents()
// OLD Phase 1 function that transformed API agents to graph store format
// Backend now provides agent data directly in GraphSnapshot

/**
 * Publish an artifact to the orchestrator
 * @param artifactType - The type of artifact to publish
 * @param content - The artifact content as a parsed JSON object
 * @returns Response with correlation ID
 */
export async function publishArtifact(
  artifactType: string,
  content: any
): Promise<PublishResponse> {
  try {
    const response = await fetch(`${BASE_URL}/control/publish`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        artifact_type: artifactType,
        content: content,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: 'Unknown error',
        message: 'Failed to publish artifact',
      }));
      throw new ApiError(response.status, errorData);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Failed to connect to API server');
  }
}

export interface ReviewResponse {
  artifact_id: string;
  choice: string;
  correlation_id: string;
}

/**
 * Confirm or override a decision as a person
 * @param decisionId - Id of the decision artifact
 * @param choice - The option chosen; without it, the decision's best guess is confirmed
 * @returns The reviewed decision's id and choice
 */
export async function reviewDecision(decisionId: string, choice?: string): Promise<ReviewResponse> {
  const response = await fetch(`${BASE_URL}/control/decisions/${encodeURIComponent(decisionId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(choice ? { choice } : {}),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(response.status, {
      error: 'Review failed',
      message: typeof errorData.detail === 'string' ? errorData.detail : 'Failed to review the decision',
    } as ErrorResponse);
  }
  return await response.json();
}

/**
 * Invoke an agent via the orchestrator
 * @param agentName - The name of the agent to invoke
 * @returns Response with invocation ID
 */
export async function invokeAgent(agentName: string): Promise<InvokeResponse> {
  try {
    const response = await fetch(`${BASE_URL}/control/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        agent: agentName,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: 'Unknown error',
        message: 'Failed to invoke agent',
      }));
      throw new ApiError(response.status, errorData);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Failed to connect to API server');
  }
}

const buildArtifactQuery = (options: ArtifactQueryOptions): string => {
  const params = new URLSearchParams();

  options.types?.forEach((value) => params.append('type', value));
  options.producers?.forEach((value) => params.append('produced_by', value));
  options.tags?.forEach((value) => params.append('tag', value));
  options.visibility?.forEach((value) => params.append('visibility', value));

  if (options.correlationId) {
    params.append('correlation_id', options.correlationId);
  }
  if (options.from) {
    params.append('from', options.from);
  }
  if (options.to) {
    params.append('to', options.to);
  }
  if (typeof options.limit === 'number') {
    params.append('limit', String(options.limit));
  }
  if (typeof options.offset === 'number') {
    params.append('offset', String(options.offset));
  }
  if (options.embedMeta) {
    params.append('embed_meta', 'true');
  }
  if (options.images) {
    params.append('images', options.images);
  }

  return params.toString();
};

/**
 * One artifact, visibility applied: with its full payload (including image
 * data) by default; with `images: 'thumbnails'` image data is a description,
 * and `embedMeta` adds its consumption history.
 */
export async function fetchArtifact(
  artifactId: string,
  options: { images?: 'full' | 'thumbnails'; embedMeta?: boolean } = {},
): Promise<ArtifactListItem> {
  const params = new URLSearchParams();
  if (options.images) params.append('images', options.images);
  if (options.embedMeta) params.append('embed_meta', 'true');
  const query = params.toString();
  const response = await fetch(`${BASE_URL}/v1/artifacts/${encodeURIComponent(artifactId)}${query ? `?${query}` : ''}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({
      error: 'Unknown error',
      message: 'Failed to fetch artifact',
    }));
    throw new ApiError(response.status, errorData);
  }
  return response.json();
}

export async function fetchArtifacts(options: ArtifactQueryOptions = {}): Promise<ArtifactListResponse> {
  const query = buildArtifactQuery(options);

  try {
    const response = await fetch(`${BASE_URL}/v1/artifacts${query ? `?${query}` : ''}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: 'Unknown error',
        message: 'Failed to fetch artifacts',
      }));
      throw new ApiError(response.status, errorData);
    }

    const data: ArtifactListResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Failed to connect to API server');
  }
}

export async function fetchArtifactSummary(options: ArtifactQueryOptions = {}): Promise<ArtifactSummary> {
  const query = buildArtifactQuery(options);

  try {
    const response = await fetch(`${BASE_URL}/v1/artifacts/summary${query ? `?${query}` : ''}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: 'Unknown error',
        message: 'Failed to fetch artifact summary',
      }));
      throw new ApiError(response.status, errorData);
    }

    const data: ArtifactSummaryResponse = await response.json();
    return data.summary;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Failed to connect to API server');
  }
}
