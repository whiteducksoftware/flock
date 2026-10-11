/**
 * The Flow canvas's commands for code outside it (the ⌘K palette): the
 * canvas registers them while it is mounted. A command for a canvas that is
 * not mounted yet (the Blackboard view switches to the Flow first) waits for
 * the next one, and runs once its board settled.
 */

import { useGraphStore } from '../../store/graphStore';
import type { AutoLayoutMode } from '../../store/uiStore';

export interface CanvasCommands {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  layout: (mode: AutoLayoutMode) => void;
  /** Selects an agent and centers the board on it */
  show: (nodeId: string) => void;
}

let current: CanvasCommands | null = null;
let waiting: ((canvas: CanvasCommands) => void) | null = null;

/**
 * Registers the mounted canvas; returns its unregister. `settleMs`: how long a
 * waiting command waits, so a newly mounted board can lay itself out first.
 */
export function registerCanvas(canvas: CanvasCommands, settleMs = 0): () => void {
  current = canvas;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const pendingRun = waiting;
  if (pendingRun) {
    waiting = null;
    timer = setTimeout(() => {
      timer = null;
      if (current) pendingRun(current);
    }, settleMs);
  }
  return () => {
    // Unmounted before it ran (React's strict mode mounts twice): the next canvas runs it
    if (timer) {
      clearTimeout(timer);
      waiting ??= pendingRun;
    }
    if (current === canvas) current = null;
  };
}

/** Runs a command on the canvas now, or on the next one that mounts (the newest request wins). */
export function withCanvas(run: (canvas: CanvasCommands) => void): void {
  if (current) run(current);
  else waiting = run;
}

/**
 * Runs `run` once the board has the agent: at once, or `settleMs` after it
 * arrives (a board that just mounted loads its agents and lays them out
 * first). Gives up after `giveUpMs`.
 */
export function whenOnBoard(nodeId: string, run: () => void, settleMs: number, giveUpMs = 5000): void {
  const onBoard = () => useGraphStore.getState().nodes.some((node) => node.id === nodeId && node.type === 'agent');
  if (onBoard()) {
    run();
    return;
  }
  const unsubscribe = useGraphStore.subscribe(() => {
    if (!onBoard()) return;
    unsubscribe();
    clearTimeout(giveUp);
    setTimeout(run, settleMs);
  });
  const giveUp = setTimeout(unsubscribe, giveUpMs);
}
