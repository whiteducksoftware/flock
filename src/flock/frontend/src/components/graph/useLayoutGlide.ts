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
 * first, so making room starts from the layout.
 */
export function useLayoutGlide(): (targets: Map<string, XYPosition>) => void {
  const stop = useRef<() => void>(() => {});
  // The layout a glide is on its way to, until it is there
  const goal = useRef<Map<string, XYPosition> | null>(null);
  const unfoldedNodeId = useUIStore((state) => state.unfoldedNodeId);

  useEffect(() => {
    if (unfoldedNodeId === null || goal.current === null) return;
    stop.current();
    useGraphStore.getState().setNodePositions(goal.current);
    goal.current = null;
  }, [unfoldedNodeId]);
  useEffect(() => () => stop.current(), []);

  return useCallback((targets: Map<string, XYPosition>) => {
    stop.current();
    goal.current = null;
    const { nodes, setNodePositions } = useGraphStore.getState();
    const from = new Map(nodes.map((node) => [node.id, node.position]));
    const moves = [...targets].some(([id, to]) => {
      const at = from.get(id);
      return !at || Math.abs(at.x - to.x) >= 0.5 || Math.abs(at.y - to.y) >= 0.5;
    });
    if (!moves) return;
    goal.current = targets;
    stop.current = animatePositions(from, targets, setNodePositions, undefined, () => {
      goal.current = null;
    });
  }, []);
}
