/**
 * The Flow canvas's commands for code outside it (the ⌘K palette): the
 * canvas registers them while it is mounted. A command for a canvas that is
 * not mounted yet (the Blackboard view switches to the Flow first) waits for
 * the next one, and runs once its board settled. The newest request wins:
 * one that still waits is dropped when another comes.
 */

import { useGraphStore } from '../../store/graphStore';
import type { AutoLayoutMode } from '../../store/uiStore';
import { AUTO_LAYOUT_DEBOUNCE_MS } from './autoLayoutTrigger';

export interface CanvasCommands {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  layout: (mode: AutoLayoutMode) => void;
  /** Selects an agent and centers the board on it */
  show: (nodeId: string) => void;
}

/** How long a board that just got its agents takes to lay them out */
export const SETTLE_MS = AUTO_LAYOUT_DEBOUNCE_MS + 100;

let current: CanvasCommands | null = null;
let waiting: ((canvas: CanvasCommands) => void) | null = null;
let waitingTimer: ReturnType<typeof setTimeout> | null = null;
// Counts the requests: a delayed one runs only while it is the newest
let generation = 0;

/** A new request: whatever an older one still waits for is dropped. */
function newRequest(): void {
  generation += 1;
  waiting = null;
  if (waitingTimer) {
    clearTimeout(waitingTimer);
    waitingTimer = null;
  }
}

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
      waitingTimer = null;
      if (current) pendingRun(current);
    }, settleMs);
    waitingTimer = timer;
  }
  return () => {
    // Unmounted before it ran (React's strict mode mounts twice): the next canvas runs it
    if (timer && waitingTimer === timer) {
      clearTimeout(timer);
      waitingTimer = null;
      waiting ??= pendingRun;
    }
    if (current === canvas) current = null;
  };
}

/** Runs a command on the canvas now, or on the next one that mounts. */
export function withCanvas(run: (canvas: CanvasCommands) => void): void {
  newRequest();
  if (current) run(current);
  else waiting = run;
}

/**
 * Runs `run` once the board has the agent: at once, or `settleMs` after it
 * arrives (a board that just mounted loads its agents and lays them out
 * first), unless a newer request came meanwhile. Gives up after `giveUpMs`.
 */
export function whenOnBoard(nodeId: string, run: () => void, settleMs: number, giveUpMs = 5000): void {
  const mine = generation;
  const onBoard = () => useGraphStore.getState().nodes.some((node) => node.id === nodeId && node.type === 'agent');
  if (onBoard()) {
    run();
    return;
  }
  const unsubscribe = useGraphStore.subscribe(() => {
    if (mine !== generation) {
      unsubscribe();
      clearTimeout(giveUp);
      return;
    }
    if (!onBoard()) return;
    unsubscribe();
    clearTimeout(giveUp);
    setTimeout(() => mine === generation && run(), settleMs);
  });
  const giveUp = setTimeout(unsubscribe, giveUpMs);
}

/** A request about an agent (unfold it, focus it): runs once it is on the Flow's board, as the newest request. */
export function withAgent(nodeId: string, run: () => void): void {
  newRequest();
  whenOnBoard(nodeId, run, SETTLE_MS);
}
