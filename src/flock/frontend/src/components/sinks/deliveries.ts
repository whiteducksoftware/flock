/**
 * Sink receipts and a sink's deliveries (docs/guides/sinks.md): a sink
 * publishes `Delivered` or `DeliveryFailed` for every delivery, and its node
 * counts them.
 */

export const DELIVERED = 'flock.sinks.models.Delivered';
export const DELIVERY_FAILED = 'flock.sinks.models.DeliveryFailed';

/** A sink's node data: its target and its receipts on the board. */
export interface SinkInfo {
  method: string;
  target: string;
  delivered: number;
  failed: number;
  last: {
    ok: boolean;
    status: number | null;
    latencyMs: number | null;
    error: string | null;
    at: string;
    correlationId: string | null;
  } | null;
}

export interface Receipt {
  ok: boolean;
  method: string;
  target: string;
  status: number | null;
  attempts: number;
  latencyMs: number | null;
  error: string | null;
}

/** A receipt, or null for any other artifact. */
export function receiptOf(type: string | null, payload: unknown): Receipt | null {
  if ((type !== DELIVERED && type !== DELIVERY_FAILED) || !payload || typeof payload !== 'object') return null;
  const fields = payload as Record<string, unknown>;
  const number = (value: unknown) => (typeof value === 'number' ? value : null);
  return {
    ok: type === DELIVERED,
    method: String(fields.method ?? ''),
    target: String(fields.target ?? ''),
    status: number(fields.status),
    attempts: number(fields.attempts) ?? 0,
    latencyMs: number(fields.latency_ms),
    error: typeof fields.error === 'string' ? fields.error : null,
  };
}

/** What went where and how it ended: `POST myapp:/billing · 200 · 41 ms`, `… · HTTP 503 · 4 attempts`. */
export function receiptText(receipt: Receipt): string {
  return `${receipt.method} ${receipt.target} · ${outcomeText(receipt)}`;
}

/** How a delivery ended: `200 · 41 ms`, `HTTP 503 · 4 attempts`, or the error without an answer. */
export function outcomeText(receipt: Receipt): string {
  if (receipt.ok) {
    return [receipt.status, receipt.latencyMs !== null && `${Math.round(receipt.latencyMs)} ms`].filter(Boolean).join(' · ');
  }
  const outcome = receipt.status !== null ? `HTTP ${receipt.status}` : (receipt.error ?? 'failed');
  return [outcome, receipt.attempts > 1 && `${receipt.attempts} attempts`].filter(Boolean).join(' · ');
}

/** The last delivery in a word: `200 · 41 ms`, `HTTP 503`. */
export function lastText(last: NonNullable<SinkInfo['last']>): string {
  if (!last.ok) return last.status !== null ? `HTTP ${last.status}` : 'failed';
  return [last.status, last.latencyMs !== null && `${Math.round(last.latencyMs)} ms`].filter(Boolean).join(' · ');
}
