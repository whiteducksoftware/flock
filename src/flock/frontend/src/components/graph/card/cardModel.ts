/**
 * What an agent card shows, derived from the node data of the graph snapshot
 * (docs/internal/design-system/README.md, Card anatomy and States).
 */

import type { ScheduleSpecDisplay } from '../../../types/graph';
import { shortTypeName } from '../../../utils/typeName';
import type { SinkInfo } from '../../sinks/deliveries';

/** The node data the card reads (the backend sends more). */
export interface AgentData {
  name?: string;
  status?: string;
  subscriptions?: string[];
  subscriptionGroups?: string[][];
  outputTypes?: string[];
  receivedByType?: Record<string, number>;
  sentByType?: Record<string, number>;
  recvCount?: number;
  typeLabels?: Record<string, string>;
  logicOperations?: LogicOperation[];
  scheduleSpec?: ScheduleSpecDisplay;
  timerState?: {
    iteration: number;
    last_fire_time: string | null;
    next_fire_time: string | null;
    is_completed?: boolean;
    is_stopped?: boolean;
  };
  decision?: { questions?: { name: string }[] };
  engineTag?: string | null;
  /** A sink's target and deliveries */
  sink?: SinkInfo;
  isOpenClawAgent?: boolean;
  streamingTokens?: string[];
  /** When the snapshot arrived, on the monotonic clock (`performance.now()`) */
  snapshotAt?: number;
  lastError?: { type?: string | null; message?: string | null; at?: string | null; correlationId?: string | null } | null;
}

export interface LogicOperation {
  subscription_index: number;
  subscription_types: string[];
  join?: { window_type?: string; window_value?: number; window_unit?: string; required_types?: string[] };
  batch?: { strategy?: string; size?: number; timeout_seconds?: number };
  waiting_state?: {
    is_waiting: boolean;
    // Countdowns as the server counted them when it took the snapshot
    correlation_groups?: {
      correlation_key: string;
      created_at?: string | null;
      elapsed_seconds?: number;
      /** null for a window counted in artifacts */
      expires_in_seconds?: number | null;
      collected_types: Record<string, number>;
      required_types: Record<string, number>;
      is_complete: boolean;
      is_expired: boolean;
    }[];
    batch_state?: {
      created_at?: string;
      items_collected: number;
      items_target: number | null;
      timeout_seconds?: number;
      /** null or missing for a batch without a timeout */
      timeout_remaining_seconds?: number | null;
    };
  };
}

export type CardTag =
  | { kind: 'decision'; text: string; more: number }
  | { kind: 'schedule'; text: string }
  | { kind: 'engine'; text: string };

export interface PortRow {
  dir: 'in' | 'and' | 'join' | 'out';
  type: string;
  label: string;
  /** A choice handle (`◆ Route.billing`) */
  decision: boolean;
  count: number;
  /** How many of this type the subscription needs */
  times: number;
}

const DURATION = /^P(?:T)?(\d+)([SMHD])$/;

/** `every 30s`, `daily 17:00`, `once` or the cron expression. */
export function scheduleText(spec: ScheduleSpecDisplay): string {
  if (spec.type === 'interval' && spec.interval) {
    const match = spec.interval.match(DURATION);
    if (match) return `every ${match[1]}${match[2]!.toLowerCase()}`;
    return `every ${spec.interval}`;
  }
  if (spec.type === 'time' && spec.time) return `daily ${spec.time.slice(0, 5)}`;
  if (spec.type === 'datetime') return 'once';
  return spec.cron ?? '';
}

/** The card's tag: a decider's question, else the schedule, else the engine. */
export function tagOf(data: AgentData): CardTag | null {
  const questions = data.decision?.questions ?? [];
  if (questions.length > 0) {
    return { kind: 'decision', text: `◆ ${questions[0]!.name}`, more: questions.length - 1 };
  }
  if (data.scheduleSpec) return { kind: 'schedule', text: scheduleText(data.scheduleSpec) };
  if (data.engineTag) return { kind: 'engine', text: data.engineTag };
  if (data.isOpenClawAgent) return { kind: 'engine', text: 'OpenClaw' };
  return null;
}

const row = (
  dir: PortRow['dir'],
  type: string,
  labels: Record<string, string>,
  counts: Record<string, number>,
  times = 1,
): PortRow => {
  const labelled = labels[type];
  const decision = labelled?.startsWith('◆') ?? false;
  return {
    dir,
    type,
    label: decision ? labelled!.replace(/^◆\s*/, '') : (labelled ?? shortTypeName(type)),
    decision,
    count: counts[type] ?? 0,
    times,
  };
};

/**
 * The port rows: per subscription its first type is IN and the others AND
 * (JOIN when the subscription joins by a key; decision handles about the same
 * subject correlate like a join but read as AND); types received outside a
 * subscription are IN too; outputs are OUT. A decider's Decision output is
 * left out, its summary stands for it. Subscriptions that would show the same
 * row show it once: the server labels and counts by type, so
 * `.consumes(Route.billing).consumes(Route.shipping)` is one row for both.
 */
export function portRows(data: AgentData): PortRow[] {
  const labels = data.typeLabels ?? {};
  const received = data.receivedByType ?? {};
  const sent = data.sentByType ?? {};
  const groups = data.subscriptionGroups ?? (data.subscriptions ?? []).map((type) => [type]);
  const joins = new Set((data.logicOperations ?? []).filter((op) => op.join).map((op) => op.subscription_index));

  const rows: PortRow[] = [];
  const shown = new Set<string>();
  groups.forEach((group, index) => {
    const times = new Map<string, number>();
    group.forEach((type) => times.set(type, (times.get(type) ?? 0) + 1));
    const handles = group.every((type) => labels[type]?.startsWith('◆'));
    const joined = joins.has(index) && !handles;
    [...times.entries()].forEach(([type, count], position) => {
      const dir = position === 0 ? 'in' : joined ? 'join' : 'and';
      if (!rows.some((other) => other.dir === dir && other.type === type && other.times === count)) {
        rows.push(row(dir, type, labels, received, count));
      }
      shown.add(type);
    });
  });
  Object.keys(received)
    .filter((type) => !shown.has(type))
    .forEach((type) => rows.push(row('in', type, labels, received)));

  const outputs = [...new Set([...(data.outputTypes ?? []), ...Object.keys(sent)])].filter(
    (type) => !(data.decision && type.startsWith('Decision[')),
  );
  outputs.forEach((type) => rows.push(row('out', type, labels, sent)));
  return rows;
}

/** At most this many port rows on a card, `+N more` rows included. */
export const MAX_PORT_ROWS = 8;

/** The rows of one direction a card leaves out, shown as one `+N more` row. */
export interface FoldedPorts {
  dir: 'in' | 'out';
  rows: PortRow[];
  count: number;
}

/**
 * The port rows a card shows, in order: all of them up to MAX_PORT_ROWS, else the first rows of each
 * direction (inputs: IN, AND and JOIN; outputs: OUT) within an even share of the rows, a side's unused
 * share going to the other, and per direction with more rows than its share one `+N more` entry after
 * its shown rows.
 */
export function foldPorts(rows: PortRow[]): (PortRow | FoldedPorts)[] {
  if (rows.length <= MAX_PORT_ROWS) return rows;
  const inputs = rows.filter((r) => r.dir !== 'out');
  const outputs = rows.filter((r) => r.dir === 'out');
  const half = MAX_PORT_ROWS / 2;
  const outShare = Math.min(outputs.length, Math.max(half, MAX_PORT_ROWS - inputs.length));
  const inShare = Math.min(inputs.length, MAX_PORT_ROWS - outShare);
  const entries: (PortRow | FoldedPorts)[] = [];
  for (const [dir, side, share] of [['in', inputs, inShare], ['out', outputs, outShare]] as const) {
    if (side.length <= share) {
      entries.push(...side);
      continue;
    }
    const rest = side.slice(share - 1);
    entries.push(...side.slice(0, share - 1), { dir, rows: rest, count: rest.reduce((sum, r) => sum + r.count, 0) });
  }
  return entries;
}

/** A `+N more` entry of foldPorts, as opposed to a port row. */
export const isFolded = (entry: PortRow | FoldedPorts): entry is FoldedPorts => 'rows' in entry;

/** `16 h 34 m`, `3 m 10 s`, `45 s` */
export function formatSpan(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s >= 3600) return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} m`;
  if (s >= 60) return `${Math.floor(s / 60)} m ${s % 60} s`;
  return `${s} s`;
}

/** `23 h ago`, `2 m ago`, `4 s ago` */
export function formatAgo(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s >= 86400) return `${Math.floor(s / 86400)} d ago`;
  if (s >= 3600) return `${Math.floor(s / 3600)} h ago`;
  if (s >= 60) return `${Math.floor(s / 60)} m ago`;
  return `${s} s ago`;
}

/** A countdown: `0:24`, `1:05`, `1:02:05` */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const pad = (n: number) => String(n).padStart(2, '0');
  if (s >= 3600) return `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
  return `${Math.floor(s / 60)}:${pad(s % 60)}`;
}

/** `('T-0001',)` -> `T-0001`; long keys (ids) keep their first 8 characters. */
function keyText(key: string): string {
  const plain = key.replace(/^\(|,?\)$/g, '').replace(/['"]/g, '').trim();
  return plain.length > 12 ? plain.slice(0, 8) : plain;
}

const sum = (counts: Record<string, number>) => Object.values(counts).reduce((total, n) => total + n, 0);

export interface JoinWait {
  key: string;
  collected: number;
  required: number;
  /** Until the join window closes; null for a count window */
  secondsLeft: number | null;
  /** Other keys waiting too */
  more: number;
}

/**
 * The oldest open join group of all the agent's joins, if any. `age` is the
 * time in seconds since the snapshot arrived: the countdown goes on from the
 * server's, so the browser's clock never has to agree with the server's.
 */
export function joinWait(operations: LogicOperation[], age: number): JoinWait | null {
  const groups = operations.flatMap((operation) =>
    operation.waiting_state?.is_waiting
      ? (operation.waiting_state.correlation_groups ?? []).filter((group) => !group.is_complete && !group.is_expired)
      : [],
  );
  if (groups.length === 0) return null;
  const oldest = groups.reduce((a, b) => ((b.elapsed_seconds ?? 0) > (a.elapsed_seconds ?? 0) ? b : a));
  const expiresIn = oldest.expires_in_seconds;
  return {
    key: keyText(oldest.correlation_key),
    collected: sum(oldest.collected_types),
    required: sum(oldest.required_types),
    secondsLeft: expiresIn === null || expiresIn === undefined ? null : expiresIn - age,
    more: groups.length - 1,
  };
}

export interface BatchWait {
  collected: number;
  target: number | null;
  /** Until the batch flushes on its timeout; null without one */
  secondsLeft: number | null;
}

/** The agent's batch being collected, if any; `age` as for `joinWait`. */
export function batchWait(operations: LogicOperation[], age: number): BatchWait | null {
  for (const operation of operations) {
    const batch = operation.waiting_state?.batch_state;
    if (!operation.waiting_state?.is_waiting || !batch) continue;
    const remaining = batch.timeout_remaining_seconds;
    return {
      collected: batch.items_collected,
      target: batch.items_target,
      secondsLeft: remaining === null || remaining === undefined ? null : remaining - age,
    };
  }
  return null;
}
