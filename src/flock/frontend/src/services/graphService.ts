import { GraphRequest, GraphSnapshot, GraphNode } from '../types/graph';
import { Node } from '@xyflow/react';

/**
 * Fetch graph snapshot from backend
 */
export async function fetchGraphSnapshot(
  request: GraphRequest
): Promise<GraphSnapshot> {
  const response = await fetch('/api/dashboard/graph', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Graph API error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Merge backend node positions with saved/current positions
 * Priority: saved > current > backend > random
 */
export function mergeNodePositions(
  backendNodes: GraphNode[],
  savedPositions: Map<string, { x: number; y: number }>,
  currentNodes: Node[]
): Node[] {
  const currentPositions = new Map(
    currentNodes.map(n => [n.id, n.position])
  );

  return backendNodes.map(node => {
    const position =
      savedPositions.get(node.id) ||
      currentPositions.get(node.id) ||
      (node.position.x !== 0 || node.position.y !== 0 ? node.position : null) ||
      randomPosition();

    return { ...node, position };
  });
}

function randomPosition() {
  return {
    x: 400 + Math.random() * 200,
    y: 300 + Math.random() * 200,
  };
}

/**
 * Overlay real-time WebSocket state on backend nodes
 */
export function overlayWebSocketState(
  nodes: Node[],
  agentStatus: Map<string, string>,
  streamingTokens: Map<string, string[]>,
  agentLogicOperations?: Map<string, any[]>
): Node[] {
  return nodes.map(node => {
    if (node.type === 'agent') {
      return {
        ...node,
        data: {
          ...node.data,
          status: agentStatus.get(node.id) || node.data.status,
          streamingTokens: streamingTokens.get(node.id) || [],
          logicOperations: agentLogicOperations?.get(node.id) || node.data.logicOperations || [],
        },
      };
    }
    return node;
  });
}
