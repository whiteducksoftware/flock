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

// Default spacing (increased by 50% for better label visibility)
const DEFAULT_NODE_SPACING = 75;  // Was 50
const DEFAULT_RANK_SPACING = 150; // Was 100

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
    nodeSpacing = DEFAULT_NODE_SPACING,
    rankSpacing = DEFAULT_RANK_SPACING,
  } = options;

  // Handle empty graph
  if (nodes.length === 0) {
    return { nodes: [], edges, width: 0, height: 0 };
  }

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

  // Extract positioned nodes
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = graph.node(node.id);

    // Dagre positions nodes at their center, we need top-left corner
    const { width, height } = getNodeDimensions(node);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });

  // Get graph dimensions
  const graphConfig = graph.graph();
  const width = (graphConfig.width || 0) + 40; // Add margin
  const height = (graphConfig.height || 0) + 40; // Add margin

  return {
    nodes: layoutedNodes,
    edges,
    width,
    height,
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
  rankSpacing?: number
): Node[] {
  const result = applyHierarchicalLayout(nodes, edges, {
    direction,
    nodeSpacing,
    rankSpacing
  });
  return result.nodes;
}
