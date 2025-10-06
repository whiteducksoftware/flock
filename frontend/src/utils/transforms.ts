import { Edge } from '@xyflow/react';

/**
 * Phase 4: Graph Visualization & Dual Views - Edge Derivation Algorithms
 *
 * Implements edge derivation logic as specified in DATA_MODEL.md:
 * - deriveAgentViewEdges: Creates message flow edges between agents (producer → consumer)
 * - deriveBlackboardViewEdges: Creates transformation edges between artifacts (consumed → produced)
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/DATA_MODEL.md lines 770-853
 * REFERENCE: docs/specs/003-real-time-dashboard/PLAN.md Phase 4
 */

// Type definitions matching DATA_MODEL.md specification
export interface Artifact {
  artifact_id: string;
  artifact_type: string;
  produced_by: string;
  consumed_by: string[];
  published_at: string; // ISO timestamp
  payload: any;
  correlation_id: string;
}

export interface Run {
  run_id: string;
  agent_name: string;
  correlation_id: string; // Groups multiple agent runs together
  status: 'active' | 'completed' | 'error';
  consumed_artifacts: string[];
  produced_artifacts: string[];
  duration_ms?: number;
  started_at?: string;
  completed_at?: string;
  metrics?: {
    tokensUsed?: number;
    costUsd?: number;
    artifactsProduced?: number;
  };
  error_message?: string;
}

export interface DashboardState {
  artifacts: Map<string, Artifact>;
  runs: Map<string, Run>;
  consumptions: Map<string, string[]>; // Phase 11: Track actual consumption (artifact_id -> consumer_ids[])
}

// Edge type definitions from DATA_MODEL.md
// Note: Using camelCase for TypeScript/JavaScript convention
export interface AgentViewEdge extends Edge {
  type: 'message_flow';
  label: string; // Format: "messageType (count)"
  data: {
    messageType: string;
    messageCount: number;
    artifactIds: string[];
    latestTimestamp: string;
    labelOffset?: number; // Phase 11: Vertical offset in pixels to prevent label overlap
  };
}

export interface BlackboardViewEdge extends Edge {
  type: 'transformation';
  label: string; // agentName
  data: {
    transformerAgent: string;
    runId: string;
    durationMs?: number;
    labelOffset?: number; // Phase 11: Vertical offset in pixels to prevent label overlap
  };
}

/**
 * Derive Agent View edges from dashboard state
 *
 * Algorithm (DATA_MODEL.md lines 770-821):
 * 1. Group messages by (producer, consumer, message_type)
 * 2. Create one edge per unique triple
 * 3. Count artifacts in each group
 * 4. Track latest timestamp
 * 5. Add label offset for multiple edges between same nodes (Phase 11 bug fix)
 *
 * Edge format:
 * - ID: `${producer}_${consumer}_${message_type}`
 * - Type: 'message_flow'
 * - Label: "Type (N)" where N is the count
 * - Data: { message_type, message_count, artifact_ids[], latest_timestamp, labelOffset }
 *
 * @param state - Dashboard state with artifacts and runs
 * @returns Array of message flow edges
 */
export function deriveAgentViewEdges(state: DashboardState): AgentViewEdge[] {
  const edgeMap = new Map<
    string,
    {
      source: string;
      target: string;
      message_type: string;
      artifact_ids: string[];
      latest_timestamp: string;
    }
  >();

  // Iterate through all artifacts
  state.artifacts.forEach((artifact) => {
    const producer = artifact.produced_by;
    const messageType = artifact.artifact_type;

    // For each consumer, create or update edge
    artifact.consumed_by.forEach((consumer) => {
      const edgeKey = `${producer}_${consumer}_${messageType}`;

      const existing = edgeMap.get(edgeKey);

      if (existing) {
        // Update existing edge
        existing.artifact_ids.push(artifact.artifact_id);

        // Update latest timestamp if this artifact is newer
        if (artifact.published_at > existing.latest_timestamp) {
          existing.latest_timestamp = artifact.published_at;
        }
      } else {
        // Create new edge entry
        edgeMap.set(edgeKey, {
          source: producer,
          target: consumer,
          message_type: messageType,
          artifact_ids: [artifact.artifact_id],
          latest_timestamp: artifact.published_at,
        });
      }
    });
  });

  // Phase 11 Bug Fix: Calculate label offsets for edges between same node pairs
  // Group edges by node pair to detect multiple edges
  // Use canonical pair key (sorted) so A→B and B→A are treated as same pair
  const nodePairEdges = new Map<string, string[]>();
  edgeMap.forEach((data, edgeKey) => {
    const nodes = [data.source, data.target].sort();
    const pairKey = `${nodes[0]}_${nodes[1]}`;
    const existing = nodePairEdges.get(pairKey) || [];
    existing.push(edgeKey);
    nodePairEdges.set(pairKey, existing);
  });

  // Convert map to edges with label offsets
  const edges: AgentViewEdge[] = [];

  edgeMap.forEach((data, edgeKey) => {
    const nodes = [data.source, data.target].sort();
    const pairKey = `${nodes[0]}_${nodes[1]}`;
    const edgesInPair = nodePairEdges.get(pairKey) || [];
    const edgeIndex = edgesInPair.indexOf(edgeKey);
    const totalEdgesInPair = edgesInPair.length;

    // Calculate label offset (spread labels vertically if multiple edges)
    // Offset range: -20 to +20 pixels for up to 3 edges, more if needed
    let labelOffset = 0;
    if (totalEdgesInPair > 1) {
      const offsetRange = Math.min(40, totalEdgesInPair * 15);
      const step = offsetRange / (totalEdgesInPair - 1);
      labelOffset = edgeIndex * step - offsetRange / 2;
    }

    // Phase 11 Bug Fix: Calculate filtered count from actual consumption data
    // Count how many artifacts were actually consumed by the target agent
    const totalCount = data.artifact_ids.length;
    const consumedCount = data.artifact_ids.filter((artifactId) => {
      const consumers = state.consumptions.get(artifactId) || [];
      return consumers.includes(data.target);
    }).length;

    // Format label: "Type (total, filtered: consumed)" if filtering occurred
    let label = `${data.message_type} (${totalCount})`;
    if (consumedCount < totalCount && consumedCount > 0) {
      label = `${data.message_type} (${totalCount}, filtered: ${consumedCount})`;
    }

    edges.push({
      id: edgeKey,
      source: data.source,
      target: data.target,
      type: 'message_flow',
      label,
      markerEnd: {
        type: 'arrowclosed',
        width: 20,
        height: 20,
      },
      data: {
        messageType: data.message_type,
        messageCount: data.artifact_ids.length,
        artifactIds: data.artifact_ids,
        latestTimestamp: data.latest_timestamp,
        labelOffset, // Phase 11: Added for label positioning
      },
    });
  });

  return edges;
}

/**
 * Derive Blackboard View edges from dashboard state
 *
 * Algorithm (DATA_MODEL.md lines 824-853):
 * 1. For each completed run (status !== 'active')
 * 2. Create edges from consumed artifacts to produced artifacts
 * 3. Label with agent name
 * 4. Include run metadata (run_id, duration_ms)
 * 5. Add label offset for multiple edges between same artifacts (Phase 11 bug fix)
 *
 * Edge format:
 * - ID: `${consumed_id}_${produced_id}_${run_id}` (Phase 11: Added run_id for uniqueness)
 * - Type: 'transformation'
 * - Label: agent_name
 * - Data: { transformer_agent, run_id, duration_ms, labelOffset }
 *
 * @param state - Dashboard state with artifacts and runs
 * @returns Array of transformation edges
 */
export function deriveBlackboardViewEdges(
  state: DashboardState
): BlackboardViewEdge[] {
  const tempEdges: Array<{
    id: string;
    source: string;
    target: string;
    label: string;
    data: {
      transformerAgent: string;
      runId: string;
      durationMs?: number;
    };
  }> = [];

  // Iterate through all runs
  state.runs.forEach((run) => {
    // Skip active runs (only process completed or error runs)
    if (run.status === 'active') {
      return;
    }

    // Skip runs with no consumed or produced artifacts
    if (
      run.consumed_artifacts.length === 0 ||
      run.produced_artifacts.length === 0
    ) {
      return;
    }

    // Create edges for each consumed × produced pair
    run.consumed_artifacts.forEach((consumedId) => {
      run.produced_artifacts.forEach((producedId) => {
        // Phase 11: Include run_id in edge ID to make it unique per transformation
        const edgeId = `${consumedId}_${producedId}_${run.run_id}`;

        tempEdges.push({
          id: edgeId,
          source: consumedId,
          target: producedId,
          label: run.agent_name,
          data: {
            transformerAgent: run.agent_name,
            runId: run.run_id,
            durationMs: run.duration_ms,
          },
        });
      });
    });
  });

  // Phase 11 Bug Fix: Calculate label offsets for edges between same artifact pairs
  // Group edges by artifact pair to detect multiple transformations
  // Use canonical pair key (sorted) so A→B and B→A are treated as same pair
  const artifactPairEdges = new Map<string, string[]>();
  tempEdges.forEach((edge) => {
    const nodes = [edge.source, edge.target].sort();
    const pairKey = `${nodes[0]}_${nodes[1]}`;
    const existing = artifactPairEdges.get(pairKey) || [];
    existing.push(edge.id);
    artifactPairEdges.set(pairKey, existing);
  });

  // Convert to final edges with label offsets
  const edges: BlackboardViewEdge[] = tempEdges.map((edge) => {
    const nodes = [edge.source, edge.target].sort();
    const pairKey = `${nodes[0]}_${nodes[1]}`;
    const edgesInPair = artifactPairEdges.get(pairKey) || [];
    const edgeIndex = edgesInPair.indexOf(edge.id);
    const totalEdgesInPair = edgesInPair.length;

    // Calculate label offset (spread labels vertically if multiple transformations)
    let labelOffset = 0;
    if (totalEdgesInPair > 1) {
      const offsetRange = Math.min(40, totalEdgesInPair * 15);
      const step = offsetRange / (totalEdgesInPair - 1);
      labelOffset = edgeIndex * step - offsetRange / 2;
    }

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'transformation',
      label: edge.label,
      markerEnd: {
        type: 'arrowclosed',
        width: 20,
        height: 20,
      },
      data: {
        ...edge.data,
        labelOffset, // Phase 11: Added for label positioning
      },
    };
  });

  return edges;
}
