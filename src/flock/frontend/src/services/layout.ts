import dagre from 'dagre';
import { Node, Edge } from '@xyflow/react';

/**
 * Phase 4: Graph Visualization & Dual Views - Layout Service
 *
 * Provides Dagre-based hierarchical layout algorithm for automatic node positioning.
 * Supports both vertical (TB) and horizontal (LR) layouts with configurable spacing.
 *
 * REQUIREMENT: Must complete <200ms for 10 nodes
 * SPECIFICATION: docs/specs/003-real-time-dashboard/PLAN.md Phase 4
 */

export interface LayoutOptions {
  direction?: 'TB' | 'LR' | 'BT' | 'RL';
  nodeSpacing?: number;
  rankSpacing?: number;
  center?: { x: number; y: number };  // Optional center point for layout
}

export interface LayoutResult {
  nodes: Node[];
  edges: Edge[];
  width: number;
  height: number;
}

// Default node dimensions
const DEFAULT_NODE_WIDTH = 200;
const DEFAULT_NODE_HEIGHT = 80;
const MESSAGE_NODE_WIDTH = 150;
const MESSAGE_NODE_HEIGHT = 60;

/**
 * Get node dimensions based on node type
 */
function getNodeDimensions(node: Node): { width: number; height: number } {
  if (node.type === 'message') {
    return { width: MESSAGE_NODE_WIDTH, height: MESSAGE_NODE_HEIGHT };
  }
  return { width: DEFAULT_NODE_WIDTH, height: DEFAULT_NODE_HEIGHT };
}

/**
 * Apply hierarchical layout using Dagre algorithm
 *
 * @param nodes - Array of nodes to layout
 * @param edges - Array of edges defining connections
 * @param options - Layout configuration options
 * @returns Layout result with positioned nodes and graph dimensions
 */
export function applyHierarchicalLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): LayoutResult {
  const {
    direction = 'TB',
    center,
  } = options;

  // Handle empty graph
  if (nodes.length === 0) {
    return { nodes: [], edges, width: 0, height: 0 };
  }

  // Calculate dynamic spacing based on actual node sizes
  // This ensures 100px minimum clearance regardless of node dimensions
  let maxWidth = 0;
  let maxHeight = 0;

  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    maxWidth = Math.max(maxWidth, width);
    maxHeight = Math.max(maxHeight, height);
  });

  // Spacing = half of max node size + 100px minimum clearance
  const nodeSpacing = options.nodeSpacing ?? (maxWidth / 2 + 100);
  const rankSpacing = options.rankSpacing ?? (maxHeight / 2 + 100);

  // Create a new directed graph
  const graph = new dagre.graphlib.Graph();

  // Set graph layout options
  graph.setGraph({
    rankdir: direction,
    nodesep: nodeSpacing,
    ranksep: rankSpacing,
    marginx: 20,
    marginy: 20,
  });

  // Default edge configuration
  graph.setDefaultEdgeLabel(() => ({}));

  // Add nodes to the graph with their dimensions
  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    graph.setNode(node.id, { width, height });
  });

  // Add edges to the graph
  edges.forEach((edge) => {
    graph.setEdge(edge.source, edge.target);
  });

  // Run the layout algorithm
  dagre.layout(graph);

  // Get graph dimensions first to calculate offset
  const graphConfig = graph.graph();
  const graphWidth = (graphConfig.width || 0) + 40; // Add margin
  const graphHeight = (graphConfig.height || 0) + 40; // Add margin

  // Calculate offset to center the layout around viewport center (or 0,0 if no center provided)
  const offsetX = center ? center.x - graphWidth / 2 : 0;
  const offsetY = center ? center.y - graphHeight / 2 : 0;

  // Extract positioned nodes
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = graph.node(node.id);

    // Dagre positions nodes at their center, we need top-left corner
    const { width, height } = getNodeDimensions(node);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2 + offsetX,
        y: nodeWithPosition.y - height / 2 + offsetY,
      },
    };
  });

  return {
    nodes: layoutedNodes,
    edges,
    width: graphWidth,
    height: graphHeight,
  };
}

/**
 * Legacy function name for backwards compatibility
 * Delegates to applyHierarchicalLayout
 */
export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB',
  nodeSpacing?: number,
  rankSpacing?: number,
  center?: { x: number; y: number }
): Node[] {
  const result = applyHierarchicalLayout(nodes, edges, {
    direction,
    nodeSpacing,
    rankSpacing,
    center
  });
  return result.nodes;
}
