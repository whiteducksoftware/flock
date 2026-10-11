/**
 * Keyboard for a tablist (WAI-ARIA tabs): Left and Right move to the previous
 * and next tab, wrapping around; Home and End to the first and last.
 */
export function nextTab<T>(tabs: readonly T[], current: T, key: string): T | null {
  const index = tabs.indexOf(current);
  if (key === 'ArrowRight') return tabs[(index + 1) % tabs.length] ?? null;
  if (key === 'ArrowLeft') return tabs[(index - 1 + tabs.length) % tabs.length] ?? null;
  if (key === 'Home') return tabs[0] ?? null;
  if (key === 'End') return tabs[tabs.length - 1] ?? null;
  return null;
}
