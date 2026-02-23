import type { Edge, Node } from '@xyflow/react';

export const AUTO_LAYOUT_DEBOUNCE_MS = 500;

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
