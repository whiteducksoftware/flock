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
  dimensionsByNodeId?: Record<string, { width: number; height: number }>;
  minClearance?: number;
  deOverlapPasses?: number;
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
const DEFAULT_MIN_CLEARANCE = 24;
const DEFAULT_DEOVERLAP_PASSES = 8;
const EPSILON = 0.01;

interface NodeDimensions {
  width: number;
  height: number;
}

/**
 * Get default dimensions based on node type.
 */
function getDefaultNodeDimensions(node: Node): NodeDimensions {
  if (node.type === 'message') {
    return { width: MESSAGE_NODE_WIDTH, height: MESSAGE_NODE_HEIGHT };
  }
  return { width: DEFAULT_NODE_WIDTH, height: DEFAULT_NODE_HEIGHT };
}

function parseNumericSize(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return undefined;
}

function resolveDimension(
  value: number | undefined,
  fallback: number
): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
    ? value
    : fallback;
}

/**
 * Get node dimensions with precedence:
 * 1) dimensionsByNodeId override
 * 2) measured/runtime node dimensions
 * 3) type defaults
 */
function getNodeDimensions(
  node: Node,
  options: LayoutOptions = {}
): NodeDimensions {
  const defaults = getDefaultNodeDimensions(node);

  const fromMap = options.dimensionsByNodeId?.[node.id];
  if (fromMap) {
    return {
      width: resolveDimension(fromMap.width, defaults.width),
      height: resolveDimension(fromMap.height, defaults.height),
    };
  }

  const measured = (node as Node & { measured?: { width?: number; height?: number } }).measured;
  const style = (node.style ?? {}) as Record<string, unknown>;

  const width =
    parseNumericSize(measured?.width) ??
    parseNumericSize(node.width) ??
    parseNumericSize(style.width) ??
    defaults.width;

  const height =
    parseNumericSize(measured?.height) ??
    parseNumericSize(node.height) ??
    parseNumericSize(style.height) ??
    defaults.height;

  return {
    width: resolveDimension(width, defaults.width),
    height: resolveDimension(height, defaults.height),
  };
}

function getNodeCenter(
  position: { x: number; y: number },
  dimensions: NodeDimensions
): { x: number; y: number } {
  return {
    x: position.x + dimensions.width / 2,
    y: position.y + dimensions.height / 2,
  };
}

function chooseSeparationAxis(
  overlapX: number,
  overlapY: number,
  direction: LayoutOptions['direction']
): 'x' | 'y' {
  const preferCrossRank = direction === 'TB' || direction === 'BT' ? 'x' : 'y';
  const otherAxis = preferCrossRank === 'x' ? 'y' : 'x';
  const preferValue = preferCrossRank === 'x' ? overlapX : overlapY;
  const otherValue = otherAxis === 'x' ? overlapX : overlapY;

  // Strongly prefer cross-rank moves, but allow escape via the other axis
  // if cross-rank displacement would be disproportionately large.
  if (preferValue <= otherValue * 1.4) {
    return preferCrossRank;
  }

  return otherAxis;
}

function resolveNodeOverlaps(
  nodes: Node[],
  options: LayoutOptions = {}
): Node[] {
  if (nodes.length < 2) {
    return nodes;
  }

  const direction = options.direction ?? 'TB';
  const minClearance = options.minClearance ?? DEFAULT_MIN_CLEARANCE;
  const maxPasses = options.deOverlapPasses ?? DEFAULT_DEOVERLAP_PASSES;

  const dimensions = new Map<string, NodeDimensions>();
  nodes.forEach((node) => {
    dimensions.set(node.id, getNodeDimensions(node, options));
  });

  const working = nodes.map((node) => ({
    ...node,
    position: { x: node.position.x, y: node.position.y },
  }));

  const originalCentroid = working.reduce(
    (acc, node) => {
      const dims = dimensions.get(node.id)!;
      const center = getNodeCenter(node.position, dims);
      acc.x += center.x;
      acc.y += center.y;
      return acc;
    },
    { x: 0, y: 0 }
  );
  originalCentroid.x /= working.length;
  originalCentroid.y /= working.length;

  for (let pass = 0; pass < maxPasses; pass++) {
    let collisionCount = 0;
    const displacement = new Map<string, { x: number; y: number; count: number }>();

    for (let i = 0; i < working.length; i++) {
      for (let j = i + 1; j < working.length; j++) {
        const nodeA = working[i];
        const nodeB = working[j];
        if (!nodeA || !nodeB) {
          continue;
        }

        const dimsA = dimensions.get(nodeA.id);
        const dimsB = dimensions.get(nodeB.id);
        if (!dimsA || !dimsB) {
          continue;
        }

        const centerA = getNodeCenter(nodeA.position, dimsA);
        const centerB = getNodeCenter(nodeB.position, dimsB);

        const dx = centerB.x - centerA.x;
        const dy = centerB.y - centerA.y;

        const requiredX = (dimsA.width + dimsB.width) / 2 + minClearance;
        const requiredY = (dimsA.height + dimsB.height) / 2 + minClearance;

        const overlapX = requiredX - Math.abs(dx);
        const overlapY = requiredY - Math.abs(dy);

        if (overlapX <= EPSILON || overlapY <= EPSILON) {
          continue;
        }

        collisionCount += 1;

        const axis = chooseSeparationAxis(overlapX, overlapY, direction);
        const moveAmount = (axis === 'x' ? overlapX : overlapY) / 2 + 0.5;

        const axisDelta = axis === 'x' ? dx : dy;
        const deterministicDirection =
          Math.abs(axisDelta) > EPSILON
            ? (axisDelta < 0 ? -1 : 1)
            : (nodeA.id < nodeB.id ? -1 : 1);

        const moveA = axis === 'x'
          ? { x: -deterministicDirection * moveAmount, y: 0 }
          : { x: 0, y: -deterministicDirection * moveAmount };
        const moveB = axis === 'x'
          ? { x: deterministicDirection * moveAmount, y: 0 }
          : { x: 0, y: deterministicDirection * moveAmount };

        const currentA = displacement.get(nodeA.id) ?? { x: 0, y: 0, count: 0 };
        const currentB = displacement.get(nodeB.id) ?? { x: 0, y: 0, count: 0 };

        displacement.set(nodeA.id, {
          x: currentA.x + moveA.x,
          y: currentA.y + moveA.y,
          count: currentA.count + 1,
        });
        displacement.set(nodeB.id, {
          x: currentB.x + moveB.x,
          y: currentB.y + moveB.y,
          count: currentB.count + 1,
        });
      }
    }

    if (collisionCount === 0) {
      break;
    }

    working.forEach((node) => {
      const delta = displacement.get(node.id);
      if (!delta || delta.count === 0) {
        return;
      }

      node.position = {
        x: node.position.x + delta.x / delta.count,
        y: node.position.y + delta.y / delta.count,
      };
    });

    // Keep the layout centered around the original centroid to avoid drift.
    const currentCentroid = working.reduce(
      (acc, node) => {
        const dims = dimensions.get(node.id)!;
        const center = getNodeCenter(node.position, dims);
        acc.x += center.x;
        acc.y += center.y;
        return acc;
      },
      { x: 0, y: 0 }
    );
    currentCentroid.x /= working.length;
    currentCentroid.y /= working.length;

    const shiftX = originalCentroid.x - currentCentroid.x;
    const shiftY = originalCentroid.y - currentCentroid.y;

    if (Math.abs(shiftX) > EPSILON || Math.abs(shiftY) > EPSILON) {
      working.forEach((node) => {
        node.position = {
          x: node.position.x + shiftX,
          y: node.position.y + shiftY,
        };
      });
    }
  }

  return working;
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

  // Calculate spacing and graph bounds from resolved node dimensions.
  let maxWidth = 0;
  let maxHeight = 0;

  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node, options);
    maxWidth = Math.max(maxWidth, width);
    maxHeight = Math.max(maxHeight, height);
  });

  // Keep sensible defaults if settings are not provided.
  const nodeSpacing = options.nodeSpacing ?? (maxWidth / 2 + 200);
  const rankSpacing = options.rankSpacing ?? (maxHeight / 2 + 200);

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
    const { width, height } = getNodeDimensions(node, options);
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
    const { width, height } = getNodeDimensions(node, options);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2 + offsetX,
        y: nodeWithPosition.y - height / 2 + offsetY,
      },
    };
  });

  const deOverlappedNodes = resolveNodeOverlaps(layoutedNodes, {
    ...options,
    direction,
  });

  return {
    nodes: deOverlappedNodes,
    edges,
    width: graphWidth,
    height: graphHeight,
  };
}

/**
 * Apply circular layout - nodes arranged in a circle
 */
export function applyCircularLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): LayoutResult {
  const { center } = options;

  if (nodes.length === 0) {
    return { nodes: [], edges, width: 0, height: 0 };
  }

  // Calculate radius based on number of nodes and their sizes
  let maxWidth = 0;
  let maxHeight = 0;
  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    maxWidth = Math.max(maxWidth, width);
    maxHeight = Math.max(maxHeight, height);
  });

  const minSpacing = 200; // 200px minimum clearance
  const nodeSize = Math.max(maxWidth, maxHeight);
  const circumference = nodes.length * (nodeSize + minSpacing);
  const radius = circumference / (2 * Math.PI);

  const centerX = center?.x ?? 0;
  const centerY = center?.y ?? 0;

  const layoutedNodes = nodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / nodes.length;
    const { width, height } = getNodeDimensions(node);

    return {
      ...node,
      position: {
        x: centerX + radius * Math.cos(angle) - width / 2,
        y: centerY + radius * Math.sin(angle) - height / 2,
      },
    };
  });

  const graphWidth = radius * 2 + maxWidth;
  const graphHeight = radius * 2 + maxHeight;

  return {
    nodes: layoutedNodes,
    edges,
    width: graphWidth,
    height: graphHeight,
  };
}

/**
 * Apply grid layout - nodes arranged in a grid
 */
export function applyGridLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): LayoutResult {
  const { center } = options;

  if (nodes.length === 0) {
    return { nodes: [], edges, width: 0, height: 0 };
  }

  // Calculate grid dimensions
  const cols = Math.ceil(Math.sqrt(nodes.length));
  const rows = Math.ceil(nodes.length / cols);

  let maxWidth = 0;
  let maxHeight = 0;
  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    maxWidth = Math.max(maxWidth, width);
    maxHeight = Math.max(maxHeight, height);
  });

  const minSpacing = 200;
  const cellWidth = maxWidth + minSpacing;
  const cellHeight = maxHeight + minSpacing;

  const graphWidth = cols * cellWidth;
  const graphHeight = rows * cellHeight;

  const startX = center ? center.x - graphWidth / 2 : 0;
  const startY = center ? center.y - graphHeight / 2 : 0;

  const layoutedNodes = nodes.map((node, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const { width, height } = getNodeDimensions(node);

    return {
      ...node,
      position: {
        x: startX + col * cellWidth + (cellWidth - width) / 2,
        y: startY + row * cellHeight + (cellHeight - height) / 2,
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
 * Apply random layout - nodes placed randomly with minimum spacing
 */
export function applyRandomLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): LayoutResult {
  const { center } = options;

  if (nodes.length === 0) {
    return { nodes: [], edges, width: 0, height: 0 };
  }

  let maxWidth = 0;
  let maxHeight = 0;
  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    maxWidth = Math.max(maxWidth, width);
    maxHeight = Math.max(maxHeight, height);
  });

  const minSpacing = 200;
  const spreadFactor = 1.5; // How much to spread nodes apart
  const areaSize = Math.sqrt(nodes.length) * (maxWidth + maxHeight + minSpacing) * spreadFactor;

  const centerX = center?.x ?? 0;
  const centerY = center?.y ?? 0;

  // Place nodes randomly, checking for collisions
  const layoutedNodes: Node[] = [];
  const maxAttempts = 100;

  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);
    let placed = false;
    let attempts = 0;

    while (!placed && attempts < maxAttempts) {
      const x = centerX + (Math.random() - 0.5) * areaSize - width / 2;
      const y = centerY + (Math.random() - 0.5) * areaSize - height / 2;

      // Check if this position collides with existing nodes
      const collides = layoutedNodes.some((existingNode) => {
        const exDims = getNodeDimensions(existingNode);
        const dx = Math.abs(x - existingNode.position.x);
        const dy = Math.abs(y - existingNode.position.y);
        return dx < (width + exDims.width) / 2 + minSpacing &&
               dy < (height + exDims.height) / 2 + minSpacing;
      });

      if (!collides) {
        layoutedNodes.push({
          ...node,
          position: { x, y },
        });
        placed = true;
      }
      attempts++;
    }

    // If we couldn't place it without collision, just place it anyway
    if (!placed) {
      layoutedNodes.push({
        ...node,
        position: {
          x: centerX + (Math.random() - 0.5) * areaSize - width / 2,
          y: centerY + (Math.random() - 0.5) * areaSize - height / 2,
        },
      });
    }
  });

  return {
    nodes: layoutedNodes,
    edges,
    width: areaSize,
    height: areaSize,
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
