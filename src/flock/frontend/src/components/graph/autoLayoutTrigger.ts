import type { Edge, Node } from '@xyflow/react';

export const AUTO_LAYOUT_DEBOUNCE_MS = 500;

/** How far a card's size may drift from the size the last layout used before the board lays itself out again */
export const RESIZE_THRESHOLD_PX = 8;
/** A card that grew lays the board out at once (not after the debounce): the board moves as the card opens (#655) */
export const RESIZE_LAYOUT_DELAY_MS = 30;

type Size = { width: number; height: number };

/**
 * Whether a card is RESIZE_THRESHOLD_PX or more off the size the last layout
 * used: with Auto-arrange on, a card that grows (the guesser's thumbnails)
 * lays the board out again, centred, so it grows up and down instead of out
 * of the view (#655). A card the last layout did not place is new: that is
 * the topology trigger's.
 */
export function cardsResized(laidOut: Record<string, Size> | null, cards: Map<string, Size>, threshold = RESIZE_THRESHOLD_PX): boolean {
  if (!laidOut) return false;
  for (const [id, size] of cards) {
    const was = laidOut[id];
    if (was && (Math.abs(size.width - was.width) >= threshold || Math.abs(size.height - was.height) >= threshold)) return true;
  }
  return false;
}

export type TimeoutRef = { current: ReturnType<typeof setTimeout> | null };

export function getNodeIdSet(nodes: Array<Pick<Node, 'id'>>): Set<string> {
  return new Set(nodes.map((node) => node.id));
}

export function getEdgeIdSet(edges: Array<Pick<Edge, 'id'>>): Set<string> {
  return new Set(edges.map((edge) => edge.id));
}

function hasNewIdAdditions(
  previousIds: Set<string> | null,
  currentIds: Set<string>
): boolean {
  if (!previousIds) {
    return false;
  }

  return Array.from(currentIds).some((id) => !previousIds.has(id));
}

export function hasNewNodeAdditions(
  previousNodeIds: Set<string> | null,
  currentNodeIds: Set<string>
): boolean {
  return hasNewIdAdditions(previousNodeIds, currentNodeIds);
}

export function hasNewEdgeAdditions(
  previousEdgeIds: Set<string> | null,
  currentEdgeIds: Set<string>
): boolean {
  return hasNewIdAdditions(previousEdgeIds, currentEdgeIds);
}

export function clearDebouncedAutoLayout(timerRef: TimeoutRef): void {
  if (timerRef.current) {
    clearTimeout(timerRef.current);
    timerRef.current = null;
  }
}

export function scheduleDebouncedAutoLayout(
  timerRef: TimeoutRef,
  callback: () => void,
  delayMs: number = AUTO_LAYOUT_DEBOUNCE_MS
): void {
  clearDebouncedAutoLayout(timerRef);

  timerRef.current = setTimeout(() => {
    timerRef.current = null;
    callback();
  }, delayMs);
}
