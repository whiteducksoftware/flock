import { useCallback, useEffect, useRef } from 'react';
import type { XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { animatePositions } from './animatePositions';

/**
 * Moves the board's nodes to a new layout (auto-arrange, a layout chosen, new
 * spacing): they glide there like the nodes that make room for an unfolded
 * one, instead of jumping (#650). A layout where the nodes are moves nothing,
 * a new one takes over from where they are, and an unfold finishes the glide
 * first, so making room starts from the layout. A node dragged meanwhile
 * stays where it is dropped, and a snapshot keeps gliding nodes on their way
 * (the store's `moving`).
 */
export function useLayoutGlide(): (targets: Map<string, XYPosition>) => void {
  const stop = useRef<() => void>(() => {});
  // The layout a glide is on its way to, until it is there
  const goal = useRef<Map<string, XYPosition> | null>(null);
  const unfoldedNodeId = useUIStore((state) => state.unfoldedNodeId);

  useEffect(() => {
    if (unfoldedNodeId === null || goal.current === null) return;
    stop.current();
    const { setNodePositions, setMoving } = useGraphStore.getState();
    setNodePositions(goal.current);
    setMoving(new Set());
    goal.current = null;
  }, [unfoldedNodeId]);
  useEffect(
    () => () => {
      stop.current();
      if (goal.current) useGraphStore.getState().setMoving(new Set());
    },
    [],
  );

  return useCallback((targets: Map<string, XYPosition>) => {
    stop.current();
    const { nodes, setMoving } = useGraphStore.getState();
    const from = new Map(nodes.map((node) => [node.id, node.position]));
    const moves = [...targets].some(([id, to]) => {
      const at = from.get(id);
      return !at || Math.abs(at.x - to.x) >= 0.5 || Math.abs(at.y - to.y) >= 0.5;
    });
    if (!moves) {
      if (goal.current) setMoving(new Set());
      goal.current = null;
      return;
    }
    goal.current = targets;
    setMoving(new Set(targets.keys()));
    // A node someone drags is theirs for the rest of the glide
    const dragged = new Set<string>();
    const apply = (positions: Map<string, XYPosition>) => {
      const state = useGraphStore.getState();
      for (const node of state.nodes) if (node.dragging) dragged.add(node.id);
      state.setNodePositions(dragged.size ? new Map([...positions].filter(([id]) => !dragged.has(id))) : positions);
    };
    stop.current = animatePositions(from, targets, apply, undefined, () => {
      goal.current = null;
      useGraphStore.getState().setMoving(new Set());
    });
  }, []);
}
