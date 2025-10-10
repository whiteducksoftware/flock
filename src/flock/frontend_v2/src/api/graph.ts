import type { GraphRequestPayload, ServerGraphSnapshot, ViewMode } from './types';

const DEFAULT_REQUEST: GraphRequestPayload = {
  viewMode: 'agent',
};

export async function fetchGraphSnapshot(
  viewMode: ViewMode,
  payload: Partial<GraphRequestPayload> = {}
): Promise<ServerGraphSnapshot> {
  const body: GraphRequestPayload = {
    ...DEFAULT_REQUEST,
    ...payload,
    viewMode,
  };

  const response = await fetch('/api/dashboard/graph', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const message = await response.text().catch(() => response.statusText);
    throw new Error(`Failed to load dashboard snapshot: ${response.status} ${message}`);
  }

  return response.json() as Promise<ServerGraphSnapshot>;
}
