/**
 * The Blackboard view's run lanes: one lane per run (correlation), its
 * artifacts left to right by what they came from
 * (docs/internal/design-system/README.md, Blackboard view; mockup
 * Blackboard.dc.html).
 */

import type { Edge, Node } from '@xyflow/react';
import type { DecisionInfo } from '../graph/DecisionDisplay';
import { duration } from '../graph/unfold/format';
import { DELIVERY_FAILED } from '../sinks/deliveries';

/** A running run of an agent: its correlation and what it consumed. */
export interface RunningRun {
  /** Its run ID; a stream knows the run that makes it */
  runId?: string;
  agent: string;
  correlationId: string | null;
  artifacts: string[];
  /** The types it consumed, and those its agent publishes: who makes what a run waits for */
  types?: string[];
  produces?: string[];
}

export interface LaneCard {
  id: string;
  /** The full type name; a pending card's comes from what its agent published before, if anything */
  type: string | null;
  producedBy: string;
  timestamp: number;
  /** The artifact node's data (payload, decision, images, ...) */
  data: Record<string, unknown>;
  /** Pending: its agent works on it and has shown nothing yet */
  state: 'done' | 'streaming' | 'pending';
}

export interface LaneColumn {
  cards: LaneCard[];
  /** Everything in it came from unsure decisions: its arrow is dashed */
  unsureIn: boolean;
  /** Something in it is being made: its arrow is amber */
  activeIn: boolean;
}

export interface LaneStatus {
  /** Failed: done, and a sink could not deliver one of its artifacts */
  kind: 'running' | 'review' | 'done' | 'failed';
  text: string;
}

export interface Lane {
  /** The correlation ID ('' for artifacts without one) */
  id: string;
  title: string | null;
  startedAt: number;
  status: LaneStatus;
  /** An unsure decision no one reviewed yet */
  needsReview: boolean;
  /** Its artifacts, not the pending cards */
  count: number;
  columns: LaneColumn[];
}

interface ArtifactData {
  artifactType?: string;
  producedBy?: string;
  timestamp?: number;
  correlationId?: string | null;
  payload?: unknown;
  decision?: DecisionInfo;
  isStreaming?: boolean;
  streamingText?: string;
  runId?: string | null;
}

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

const dataOf = (node: Node) => node.data as ArtifactData;

/** Fields that name what an artifact is about, in the order they are taken. */
const TITLE_FIELDS = ['title', 'subject', 'name', 'question', 'summary'];

/** The run's title in its lane header: a field that names it, else the payload's first text. */
export function titleOf(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;
  const fields = payload as Record<string, unknown>;
  const text = (value: unknown): value is string => typeof value === 'string' && value.trim() !== '';
  const named = TITLE_FIELDS.map((field) => fields[field]).find(text);
  return named ?? Object.values(fields).find(text) ?? null;
}

/** An unsure decision a person still has to review (a checklist's unsure items are its results, not a route). */
export const awaitsReview = (decision: DecisionInfo | undefined): boolean =>
  !!decision && decision.choice === 'UNSURE' && decision.kind !== 'checklist' && !decision.review && !decision.reviewOf;

const isUnsure = (decision: DecisionInfo | undefined) => decision?.choice === 'UNSURE';

/** Column depth of every artifact: one after the deepest artifact it came from. */
function depthsOf(nodes: Node[], edges: Edge[]): Map<string, number> {
  const inputs = new Map<string, string[]>();
  for (const edge of edges) inputs.set(edge.target, [...(inputs.get(edge.target) ?? []), edge.source]);
  const known = new Set(nodes.map((node) => node.id));
  const depths = new Map<string, number>();
  const depthOf = (id: string, seen: Set<string>): number => {
    const cached = depths.get(id);
    if (cached !== undefined) return cached;
    if (seen.has(id)) return 0; // a cycle cannot happen, but must not hang
    seen.add(id);
    const from = (inputs.get(id) ?? []).filter((source) => known.has(source));
    const depth = from.length === 0 ? 0 : 1 + Math.max(...from.map((source) => depthOf(source, seen)));
    depths.set(id, depth);
    return depth;
  };
  for (const node of nodes) depthOf(node.id, new Set());
  return depths;
}

function statusOf(cards: LaneCard[], runs: RunningRun[], deciders: Set<string>, answeredBy: string[], needsReview: boolean): LaneStatus {
  const agents = [...new Set(runs.map((run) => run.agent))];
  if (agents.length === 1) {
    const agent = agents[0]!;
    const verb = deciders.has(agent)
      ? 'is deciding'
      : cards.some((card) => card.state === 'streaming' && card.producedBy === agent)
        ? 'is writing'
        : 'is running';
    return { kind: 'running', text: `${agent} ${verb}` };
  }
  if (agents.length > 1) return { kind: 'running', text: `${agents[0]} and ${agents.length - 1} more are working` };
  if (needsReview) {
    return { kind: 'review', text: answeredBy.length > 0 ? `needs review · answered by ${answeredBy.join(', ')}` : 'needs review' };
  }
  const done = cards.filter((card) => card.state === 'done');
  // A stream whose run ended before anything was published has no time to tell
  if (done.length === 0) return { kind: 'done', text: 'done · 0 artifacts' };
  const span = Math.max(...done.map((card) => card.timestamp)) - Math.min(...done.map((card) => card.timestamp));
  const text = `done in ${duration(span)} · ${done.length} artifact${done.length === 1 ? '' : 's'}`;
  const undelivered = done.filter((card) => card.type === DELIVERY_FAILED).length;
  if (undelivered > 0) {
    return { kind: 'failed', text: `${text} · ${undelivered} deliver${undelivered === 1 ? 'y' : 'ies'} failed` };
  }
  return { kind: 'done', text };
}

/**
 * The lanes of the board's artifacts (message nodes and their transformation
 * edges), newest run first. Running runs add their agent's pending card,
 * unless the agent already streams its artifact.
 */
export function lanesOf(nodes: Node[], edges: Edge[], running: RunningRun[]): Lane[] {
  const artifacts = nodes.filter((node) => node.type === 'message');
  const byId = new Map(artifacts.map((node) => [node.id, node]));
  const depths = depthsOf(artifacts, edges);
  const inputs = new Map<string, string[]>();
  for (const edge of edges) inputs.set(edge.target, [...(inputs.get(edge.target) ?? []), edge.source]);

  // What each agent published last, for its pending cards; who decides
  const lastType = new Map<string, { type: string; at: number }>();
  const deciders = new Set<string>();
  for (const node of artifacts) {
    const { producedBy = '', artifactType = '', timestamp = 0, isStreaming } = dataOf(node);
    if (isStreaming) continue;
    if (DECISION.test(artifactType)) deciders.add(producedBy);
    if ((lastType.get(producedBy)?.at ?? -1) < timestamp) lastType.set(producedBy, { type: artifactType, at: timestamp });
  }

  const groups = new Map<string, Node[]>();
  for (const node of artifacts) {
    const key = dataOf(node).correlationId ?? '';
    groups.set(key, [...(groups.get(key) ?? []), node]);
  }

  const lanes = [...groups.entries()].map(([id, members]): Lane => {
    const runs = running.filter((run) => (run.correlationId ?? '') === id);
    // Not on the record yet: still streaming, or published by a run the server
    // draws edges for only once it is done (or streamed, before its snapshot)
    const unrecorded = (node: Node) => {
      const data = dataOf(node);
      if (data.isStreaming) return true;
      if ((inputs.get(node.id) ?? []).some((source) => byId.has(source))) return false;
      return data.streamingText !== undefined || runs.some((run) => run.agent === data.producedBy);
    };
    const recorded = members.filter((node) => !dataOf(node).isStreaming);
    const last = Math.max(0, ...members.filter((node) => !unrecorded(node)).map((node) => depths.get(node.id) ?? 0));
    const runOf = (agent: string, runId?: string | null) =>
      (runId && runs.find((each) => each.runId === runId)) || runs.find((each) => each.agent === agent);
    // Runs that show nothing yet get a placeholder; one that ended stays until its
    // output is on the board (the snapshot after it)
    const showsOutput = (agent: string) => members.some((node) => dataOf(node).producedBy === agent && unrecorded(node));

    // Where an artifact shows: its edges' depth once on the record, else where
    // its stream is drawn; a run's output goes after the deepest of its inputs
    // (its own run's, when the agent runs twice in the workflow)
    const shownDepth = (id: string): number | null => {
      const node = byId.get(id);
      if (!node) return null;
      return unrecorded(node) ? streamDepth(dataOf(node).producedBy ?? '', dataOf(node).runId) : (depths.get(id) ?? 0);
    };
    const runDepth = (agent: string, runId?: string | null) => {
      const inputsShown = (runOf(agent, runId)?.artifacts ?? []).map(shownDepth).filter((depth): depth is number => depth !== null);
      return inputsShown.length > 0 ? 1 + Math.max(...inputsShown) : last + 1;
    };
    // A run that consumed something not on the board yet (a stream, or a
    // placeholder) goes after the placeholders of the runs that will publish it:
    // those that publish a type it waits for, placed the same way themselves
    // (a chain of them). It keeps its column when the snapshot brings the input (#642)
    const waits = (agent: string, runId?: string | null) => runOf(agent, runId)?.artifacts.some((artifact) => !byId.has(artifact)) ?? false;
    const afterMakers = (agent: string, runId: string | null | undefined, depth: number) => {
      const run = runOf(agent, runId);
      if (!run || !waits(agent, runId)) return depth;
      const shown = new Set(run.artifacts.filter((artifact) => byId.has(artifact)).map((artifact) => dataOf(byId.get(artifact)!).artifactType));
      const missing = (run.types ?? []).filter((type) => !shown.has(type));
      const makers = runs.filter(
        (each) => each.agent !== agent && !showsOutput(each.agent) && (each.produces ?? []).some((type) => missing.includes(type)),
      );
      const before = makers.map((run) => streamDepth(run.agent, run.runId));
      return before.length > 0 ? Math.max(depth, 1 + Math.max(...before)) : depth;
    };
    const streams = new Map<string, number>();
    const busy = new Set<string>();
    const streamDepth = (agent: string, runId?: string | null): number => {
      const key = `${agent}|${runId ?? ''}`;
      const known = streams.get(key);
      if (known !== undefined) return known;
      if (busy.has(key)) return last + 1; // runs cannot feed each other, but must not hang
      busy.add(key);
      const depth = afterMakers(agent, runId, runDepth(agent, runId));
      busy.delete(key);
      streams.set(key, depth);
      return depth;
    };

    const placed: { card: LaneCard; depth: number }[] = members.map((node) => {
      const data = dataOf(node);
      const streaming = !!data.isStreaming;
      return {
        card: {
          id: node.id,
          type: data.artifactType ?? null,
          producedBy: data.producedBy ?? '',
          timestamp: data.timestamp ?? 0,
          data: node.data as Record<string, unknown>,
          state: streaming ? 'streaming' : 'done',
        },
        depth: unrecorded(node) ? streamDepth(data.producedBy ?? '', data.runId) : (depths.get(node.id) ?? 0),
      };
    });
    for (const run of runs) {
      // A run that shows what it makes (streaming, or published but not on the record yet) needs no placeholder
      if (members.some((node) => dataOf(node).producedBy === run.agent && unrecorded(node))) continue;
      if (placed.some(({ card }) => card.id === `pending:${run.agent}`)) continue;
      placed.push({
        card: {
          id: `pending:${run.agent}`,
          type: lastType.get(run.agent)?.type ?? null,
          producedBy: run.agent,
          timestamp: Number.MAX_SAFE_INTEGER,
          data: {},
          state: 'pending',
        },
        depth: afterMakers(run.agent, run.runId, runDepth(run.agent, run.runId)),
      });
    }

    // Depths with nothing in this lane (inputs from another run) close up
    const levels = [...new Set(placed.map(({ depth }) => depth))].sort((a, b) => a - b);
    const columns: LaneColumn[] = levels.map((level) => {
      const cards = placed
        .filter(({ depth }) => depth === level)
        .map(({ card }) => card)
        .sort((a, b) => a.timestamp - b.timestamp);
      const unsureIn =
        level > 0 &&
        cards.every((card) => {
          const from = inputs.get(card.id) ?? [];
          return from.length > 0 && from.every((source) => isUnsure(byId.get(source) && dataOf(byId.get(source)!).decision));
        });
      return { cards, unsureIn, activeIn: level > 0 && cards.some((card) => card.state !== 'done') };
    });

    const cards = columns.flatMap((column) => column.cards);
    const unsure = recorded.filter((node) => awaitsReview(dataOf(node).decision));
    const answeredBy = [
      ...new Set(
        edges
          .filter((edge) => unsure.some((node) => node.id === edge.source))
          .map((edge) => byId.get(edge.target))
          .filter((node): node is Node => !!node)
          .map((node) => dataOf(node).producedBy ?? ''),
      ),
    ];
    // What the run started with: an artifact none of whose inputs are in this run,
    // the earliest of them. A wall clock can step back (a VM's time sync), so a
    // decision may carry an earlier time than what it decided about. An agent still
    // running on this run's artifacts has no edges yet: what it published meanwhile
    // is not a start, unless it led to what one of its runs consumes (a feedback loop)
    const inRun = new Set(members.map((node) => node.id));
    const ledTo = (agent: string): Set<string> => {
      const found = new Set<string>();
      const visit = (id: string) => {
        if (found.has(id) || !inRun.has(id)) return;
        found.add(id);
        for (const source of inputs.get(id) ?? []) visit(source);
      };
      for (const run of runs) if (run.agent === agent) for (const id of run.artifacts) visit(id);
      return found;
    };
    const awaitingEdges = (node: Node) => {
      const agent = dataOf(node).producedBy;
      const active = runs.some((run) => run.agent === agent && run.artifacts.some((id) => inRun.has(id)));
      return active && !ledTo(agent ?? '').has(node.id);
    };
    const startedWith = recorded.filter(
      (node) => !(inputs.get(node.id) ?? []).some((source) => inRun.has(source)) && !awaitingEdges(node),
    );
    const first =
      [...(startedWith.length > 0 ? startedWith : recorded)].sort(
        (a, b) => (dataOf(a).timestamp ?? 0) - (dataOf(b).timestamp ?? 0),
      )[0] ?? members[0]!;
    return {
      id,
      title: titleOf(dataOf(first).payload),
      startedAt: dataOf(first).timestamp ?? 0,
      status: statusOf(cards, runs, deciders, answeredBy, unsure.length > 0),
      needsReview: unsure.length > 0,
      count: members.length,
      columns,
    };
  });

  return lanes.sort((a, b) => b.startedAt - a.startedAt);
}
