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
  /** Lays the board out, when a layout came due while a node was unfolded (see `layoutDue`) */
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
      // A snapshot keeps the gliding nodes on their way (#650)
      useGraphStore.getState().setMoving(new Set(targets.keys()));
      stop.current = animatePositions(current, targets, setNodePositions, undefined, () =>
        useGraphStore.getState().setMoving(new Set()),
      );
    };

    if (unfoldedNodeId === null) {
      const restore = before.current;
      before.current = null;
      setTransientPositions(null);
      if (!restore) {
        // Nothing to put back (the node left the board): a layout due goes with that board
        if (latest.current.layoutDue) latest.current.layoutDue.current = false;
        return;
      }
      // A layout that came due runs now; otherwise every node goes back, and one that came meanwhile stays
      const due = latest.current.layoutDue;
      if (!due?.current) {
        moveTo(new Map([...restore].filter(([id]) => current.has(id))));
        return;
      }
      due.current = false;
      latest.current.relayout();
      return;
    }

    if (!current.has(unfoldedNodeId)) return;
    before.current ??= current;
    const base = before.current;
    const { mode, nodeSpacing, rankSpacing, collectDimensions } = latest.current;
    const dimensions = collectDimensions();
    // Its element is unfolded by now; making room starts from the card (a default one if it never was a card)
    const card = cardSizes.get(unfoldedNodeId);
    if (card) dimensions[unfoldedNodeId] = card;
    else delete dimensions[unfoldedNodeId];

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
        if (latest.current.layoutDue) latest.current.layoutDue.current = false;
        if (state.transientPositions) state.setTransientPositions(null);
        useUIStore.getState().fold();
      }),
    [],
  );

  useEffect(() => () => stop.current(), []);
}
