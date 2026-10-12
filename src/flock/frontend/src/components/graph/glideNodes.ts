import type { XYPosition } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { animatePositions } from './animatePositions';

export interface Glide {
  /** Stops where the nodes are */
  stop: () => void;
  /** Puts the nodes where they are going at once (but a node someone dragged) */
  finish: () => void;
}

// The board has one glide at a time; `claim` leaves a node to the person moving it
let running: (Glide & { claim: (id: string) => void }) | null = null;
// What waits for the nodes to keep still (a fit, centring on a node)
const waiting: (() => void)[] = [];

/**
 * Runs `run` once the board's nodes keep still: at once, or the frame after
 * the glide going on ended (React Flow has their final positions by then), so
 * a fit or a centring uses where the nodes end, not where they are on their
 * way (#650). A glide that takes over meanwhile is waited for too. Returns a
 * function that drops it, if it still waits.
 */
/**
 * A node was moved by hand (dragged, the arrow keys): the glide going on
 * leaves it where it is, also when React Flow's `dragging` flag missed it.
 */
export function movedByHand(id: string): void {
  running?.claim(id);
}

export function afterGlide(run: () => void): () => void {
  if (!running) {
    run();
    return () => {};
  }
  waiting.push(run);
  return () => {
    const at = waiting.indexOf(run);
    if (at >= 0) waiting.splice(at, 1);
  };
}

function settled(): void {
  if (waiting.length === 0) return;
  requestAnimationFrame(() => {
    if (running) return; // another glide took over: its end runs them
    for (const run of waiting.splice(0)) run();
  });
}

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
      settled();
    }
  };
  const glide = {
    claim: (id: string) => dragged.add(id),
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
