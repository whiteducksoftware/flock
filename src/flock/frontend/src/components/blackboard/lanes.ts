/**
 * The Blackboard view's run lanes: one lane per run (correlation), its
 * artifacts left to right by what they came from
 * (docs/internal/design-system/README.md, Blackboard view; mockup
 * Blackboard.dc.html).
 */

import type { Edge, Node } from '@xyflow/react';
import type { DecisionInfo } from '../graph/DecisionDisplay';
import { duration } from '../graph/unfold/format';

/** A running run of an agent: its correlation and what it consumed. */
export interface RunningRun {
  agent: string;
  correlationId: string | null;
  artifacts: string[];
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
  kind: 'running' | 'review' | 'done';
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
}

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

const dataOf = (node: Node) => node.data as ArtifactData;

/** The first text of a payload, the run's title in its lane header. */
export function titleOf(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;
  const text = Object.values(payload as Record<string, unknown>).find((value) => typeof value === 'string' && value.trim());
  return typeof text === 'string' ? text : null;
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
  const span = Math.max(...done.map((card) => card.timestamp)) - Math.min(...done.map((card) => card.timestamp));
  return { kind: 'done', text: `done in ${duration(span)} · ${done.length} artifact${done.length === 1 ? '' : 's'}` };
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
    // Streaming artifacts are not on the record yet: after what their run consumed
    const runDepth = (agent: string, last: number) => {
      const consumed = runs.find((run) => run.agent === agent)?.artifacts.filter((artifact) => byId.has(artifact)) ?? [];
      return consumed.length > 0 ? 1 + Math.max(...consumed.map((artifact) => depths.get(artifact) ?? 0)) : last + 1;
    };
    const recorded = members.filter((node) => !dataOf(node).isStreaming);
    const last = Math.max(0, ...recorded.map((node) => depths.get(node.id) ?? 0));

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
        depth: streaming ? runDepth(data.producedBy ?? '', last) : (depths.get(node.id) ?? 0),
      };
    });
    for (const run of runs) {
      if (placed.some(({ card }) => card.state === 'streaming' && card.producedBy === run.agent)) continue;
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
        depth: runDepth(run.agent, last),
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
    const first = [...recorded].sort((a, b) => (dataOf(a).timestamp ?? 0) - (dataOf(b).timestamp ?? 0))[0] ?? members[0]!;
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
