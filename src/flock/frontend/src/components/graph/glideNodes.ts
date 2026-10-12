import type { XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { animatePositions } from './animatePositions';

export interface Glide {
  /** Stops where the nodes are */
  stop: () => void;
  /** Puts the nodes where they are going at once (but a node someone dragged) */
  finish: () => void;
}

// The board has one glide at a time
let running: Glide | null = null;

/**
 * Glides the board's nodes to `targets` (a new layout, an unfold making room,
 * a fold putting them back), frame by frame like animatePositions. One glide
 * at a time: a new one stops the one going on and takes over from where the
 * nodes are. While it runs the store's `moving` names its nodes, so a snapshot
 * leaves them on their way (#650); a node someone drags is left out for the
 * rest of it.
 */
export function glideNodes(targets: Map<string, XYPosition>): Glide {
  running?.stop();
  const { nodes, setMoving } = useGraphStore.getState();
  const from = new Map(nodes.map((node) => [node.id, node.position]));
  const dragged = new Set<string>();
  const place = (positions: Map<string, XYPosition>) => {
    const state = useGraphStore.getState();
    for (const node of state.nodes) if (node.dragging) dragged.add(node.id);
    state.setNodePositions(dragged.size ? new Map([...positions].filter(([id]) => !dragged.has(id))) : positions);
  };
  let over = false;
  let halt = () => {};
  const end = () => {
    if (over) return;
    over = true;
    halt();
    if (running === glide) {
      running = null;
      useGraphStore.getState().setMoving(new Set());
    }
  };
  const glide: Glide = {
    stop: end,
    finish: () => {
      if (over) return;
      halt();
      place(targets);
      end();
    },
  };
  running = glide;
  setMoving(new Set(targets.keys()));
  // With reduced motion this is there at once and has ended already
  halt = animatePositions(from, targets, place, undefined, end);
  return glide;
}
