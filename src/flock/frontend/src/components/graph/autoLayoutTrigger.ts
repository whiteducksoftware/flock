import type { Node } from '@xyflow/react';

export const AUTO_LAYOUT_DEBOUNCE_MS = 500;

export type TimeoutRef = { current: ReturnType<typeof setTimeout> | null };

export function getNodeIdSet(nodes: Array<Pick<Node, 'id'>>): Set<string> {
  return new Set(nodes.map((node) => node.id));
}

export function hasNewNodeAdditions(
  previousNodeIds: Set<string> | null,
  currentNodeIds: Set<string>
): boolean {
  if (!previousNodeIds) {
    return false;
  }

  return Array.from(currentNodeIds).some((nodeId) => !previousNodeIds.has(nodeId));
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
