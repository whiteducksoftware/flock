/**
 * Where the nodes go while one of them is unfolded on the board
 * (docs/internal/design-system/README.md, Nodes: four levels).
 */

import type { Edge, Node, XYPosition } from '@xyflow/react';
import { applyHierarchicalLayout } from '../../services/layout';
import type { AutoLayoutMode } from '../../store/uiStore';

/** An unfolded node's size on the board. */
export const UNFOLDED_SIZE = { width: 560, height: 470 };

export interface UnfoldOptions {
  /** The board's layout; hierarchical layouts rerun, the others only make room */
  mode: AutoLayoutMode;
  /** Rendered sizes of the nodes, as the layouts take them */
  dimensions: Record<string, { width: number; height: number }>;
  nodeSpacing?: number;
  rankSpacing?: number;
}

/**
 * Every node's position while `nodeId` is unfolded. A hierarchical layout
 * reruns with the unfolded size; circular, grid and random arrangements keep
 * their shape and get room inserted (see `insertRoom`). Either way the
 * unfolded node keeps its top-left corner, so it opens where it was clicked.
 */
export function unfoldedPositions(
  nodes: Node[],
  edges: Edge[],
  nodeId: string,
  options: UnfoldOptions,
): Map<string, XYPosition> {
  const dimensionsByNodeId = { ...options.dimensions, [nodeId]: UNFOLDED_SIZE };
  const hierarchical = options.mode === 'hierarchical-horizontal' || options.mode === 'hierarchical-vertical';
  const direction = options.mode === 'hierarchical-vertical' ? 'TB' : 'LR';

  if (!hierarchical) return insertRoom(nodes, nodeId, options.dimensions[nodeId]);

  const placed = applyHierarchicalLayout(nodes, edges, {
    direction,
    dimensionsByNodeId,
    nodeSpacing: options.nodeSpacing,
    rankSpacing: options.rankSpacing,
  }).nodes;

  const before = nodes.find((node) => node.id === nodeId)?.position;
  const after = placed.find((node) => node.id === nodeId)?.position;
  const dx = before && after ? before.x - after.x : 0;
  const dy = before && after ? before.y - after.y : 0;
  return new Map(placed.map((node) => [node.id, { x: node.position.x + dx, y: node.position.y + dy }]));
}

/**
 * Room for the unfolded node without a new arrangement: what lies right of
 * the card moves right by the width it gains, what lies below moves down by
 * the height. Nodes keep their order on both axes, so no two that were apart
 * overlap afterwards.
 */
function insertRoom(nodes: Node[], nodeId: string, card = { width: 260, height: 120 }): Map<string, XYPosition> {
  const anchor = nodes.find((node) => node.id === nodeId)?.position ?? { x: 0, y: 0 };
  const wider = Math.max(0, UNFOLDED_SIZE.width - card.width);
  const taller = Math.max(0, UNFOLDED_SIZE.height - card.height);
  return new Map(
    nodes.map((node) => {
      const { x, y } = node.position;
      if (node.id === nodeId) return [node.id, { x, y }];
      return [
        node.id,
        { x: x >= anchor.x + card.width ? x + wider : x, y: y >= anchor.y + card.height ? y + taller : y },
      ];
    }),
  );
}
