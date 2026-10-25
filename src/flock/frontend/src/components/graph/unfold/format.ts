/** Formats of the unfolded node's tabs. */

/** `13:24:41` in the viewer's time zone; empty for no time. */
export const clockTime = (at: string | number | null | undefined): string =>
  at === null || at === undefined || at === '' ? '' : new Date(at).toLocaleTimeString([], { hour12: false });

/** `61 ms`, `1.2 s`, `2.5 m` */
export function duration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${(ms / 60_000).toFixed(1)} m`;
}

/** `$0`, `<$0.0001`, `$0.0012`, `$1.25` */
export function usd(cost: number): string {
  if (cost === 0) return '$0';
  if (cost < 0.0001) return '<$0.0001';
  return `$${cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2)}`;
}

/** `1,234` */
export const count = (n: number): string => n.toLocaleString('en-US');

/** The first characters of an id, enough to tell runs apart. */
export const shortId = (id: string | null | undefined, length = 6): string => (id ? id.replace(/-/g, '').slice(0, length) : '');
