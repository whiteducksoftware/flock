/**
 * Neighbors make room while a node is unfolded, and go back when it folds
 * (docs/internal/design-system/README.md, Nodes: four levels).
 */

import { useEffect, useRef } from 'react';
import type { XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore, type AutoLayoutMode } from '../../store/uiStore';
import { animatePositions } from './animatePositions';
import { cardSizes } from './cardSizes';
import { UNFOLDED_SIZE, unfoldedPositions } from './unfoldLayout';

interface UnfoldLayoutOptions {
  /** The board's layout */
  mode: AutoLayoutMode;
  nodeSpacing?: number;
  rankSpacing?: number;
  /** The rendered size of every node on the board */
  collectDimensions: () => Record<string, { width: number; height: number }>;
  /** Lays the board out anew, for nodes that came or went while one was unfolded */
  relayout: () => void;
  /** Moves the board so this box (flow coordinates) is in view */
  reveal?: (box: { x: number; y: number; width: number; height: number }) => void;
  /** Set while a node is unfolded when a layout came due (new nodes or edges, a layout chosen); folding runs it */
  layoutDue?: { current: boolean };
}

export function useUnfoldLayout(options: UnfoldLayoutOptions): void {
  const unfoldedNodeId = useUIStore((state) => state.unfoldedNodeId);
  // Where the nodes were before the first unfold; folding puts them back
  const before = useRef<Map<string, XYPosition> | null>(null);
  const stop = useRef<() => void>(() => {});
  const latest = useRef(options);
  latest.current = options;

  useEffect(() => {
    const { nodes, edges, setNodePositions, setTransientPositions } = useGraphStore.getState();
    stop.current();
    const current = new Map(nodes.map((node) => [node.id, node.position]));
    const moveTo = (targets: Map<string, XYPosition>) => {
      stop.current = animatePositions(current, targets, setNodePositions);
    };

    if (unfoldedNodeId === null) {
      const restore = before.current;
      before.current = null;
      setTransientPositions(null);
      if (!restore) return;
      const same = nodes.length === restore.size && nodes.every((node) => restore.has(node.id));
      const due = latest.current.layoutDue;
      if (same && !due?.current) {
        moveTo(restore);
        return;
      }
      if (due) due.current = false;
      latest.current.relayout();
      return;
    }

    if (!current.has(unfoldedNodeId)) return;
    before.current ??= current;
    const base = before.current;
    const { mode, nodeSpacing, rankSpacing, collectDimensions } = latest.current;
    const dimensions = collectDimensions();
    // Its element is unfolded by now; making room starts from the card
    const card = cardSizes.get(unfoldedNodeId);
    if (card) dimensions[unfoldedNodeId] = card;

    const targets = unfoldedPositions(
      nodes.map((node) => ({ ...node, position: base.get(node.id) ?? node.position })),
      edges,
      unfoldedNodeId,
      { mode, dimensions, nodeSpacing, rankSpacing },
    );
    setTransientPositions(targets);
    moveTo(targets);
    const at = targets.get(unfoldedNodeId);
    if (at) latest.current.reveal?.({ ...at, ...UNFOLDED_SIZE });
  }, [unfoldedNodeId]);

  // The unfolded node left the board (the other view, filters): fold, move nothing
  useEffect(
    () =>
      useGraphStore.subscribe((state) => {
        const id = useUIStore.getState().unfoldedNodeId;
        if (id === null || state.nodes.some((node) => node.id === id)) return;
        stop.current();
        before.current = null;
        if (state.transientPositions) state.setTransientPositions(null);
        useUIStore.getState().fold();
      }),
    [],
  );

  useEffect(() => () => stop.current(), []);
}
