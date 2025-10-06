/**
 * REST API client for orchestrator control operations.
 *
 * Provides methods to publish artifacts and invoke agents via HTTP endpoints.
 * Handles error responses and provides typed return values.
 *
 * Base URL defaults to /api for same-origin requests.
 */

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

/**
 * Fetch registered agents and transform to graph store format
 * Returns agents with 'idle' status ready for initial display
 */
export async function fetchRegisteredAgents(): Promise<import('../types/graph').Agent[]> {
  const agents = await fetchAgents();
  return agents.map(agent => ({
    id: agent.name,
    name: agent.name,
    status: 'idle' as const,
    subscriptions: agent.subscriptions || [],
    outputTypes: agent.output_types || [],
    lastActive: Date.now(),
    sentCount: 0,
    recvCount: 0,
    receivedByType: {},
    sentByType: {},
  }));
}

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
