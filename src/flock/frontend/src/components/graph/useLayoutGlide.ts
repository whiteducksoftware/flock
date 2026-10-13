import { useCallback, useEffect, useRef } from 'react';
import type { XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { type Glide, glideNodes } from './glideNodes';

/**
 * Moves the board's nodes to a new layout (auto-arrange, a layout chosen, new
 * spacing): they glide there like the nodes that make room for an unfolded
 * one, instead of jumping (#650). A layout where the nodes are moves nothing,
 * and an unfold finishes the glide first, so making room starts from the
 * layout. The glide itself is glideNodes: one at a time, drags and snapshots
 * respected.
 */
export function useLayoutGlide(): (targets: Map<string, XYPosition>) => void {
  const glide = useRef<Glide | null>(null);
  const unfoldedNodeId = useUIStore((state) => state.unfoldedNodeId);

  useEffect(() => {
    if (unfoldedNodeId !== null) glide.current?.finish();
  }, [unfoldedNodeId]);
  useEffect(() => () => glide.current?.stop(), []);

  return useCallback((targets: Map<string, XYPosition>) => {
    const at = new Map(useGraphStore.getState().nodes.map((node) => [node.id, node.position]));
    const moves = [...targets].some(([id, to]) => {
      const from = at.get(id);
      return !from || Math.abs(from.x - to.x) >= 0.5 || Math.abs(from.y - to.y) >= 0.5;
    });
    if (!moves) {
      glide.current?.stop();
      glide.current = null;
      return;
    }
    glide.current = glideNodes(targets);
  }, []);
}
