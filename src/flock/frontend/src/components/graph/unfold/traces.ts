/** The spans of an agent's runs, from `GET /api/traces`. */

export interface Span {
  name: string;
  context: { trace_id: string; span_id: string };
  parent_id?: string;
  /** Nanoseconds */
  start_time: number;
  end_time: number;
  status?: { status_code?: string };
  attributes?: Record<string, unknown>;
}

export interface RunTrace {
  runId: string;
  correlationId: string | null;
  start: number;
  end: number;
  failed: boolean;
  /** The run's span first, then its descendants depth first, in start order */
  spans: { span: Span; depth: number }[];
}

/** How many of the agent's latest runs the Traces tab offers. */
export const TRACED_RUNS = 5;

/**
 * The agent's latest runs as traces: each `Agent.execute` span of the agent
 * (`agent.name`) with the spans below it. `task_id` is the run's id.
 */
export function runTraces(spans: Span[], agent: string, limit = TRACED_RUNS): RunTrace[] {
  const children = new Map<string, Span[]>();
  for (const span of spans) {
    if (!span.parent_id) continue;
    const siblings = children.get(span.parent_id) ?? [];
    siblings.push(span);
    children.set(span.parent_id, siblings);
  }

  const below = (root: Span) => {
    const ordered: { span: Span; depth: number }[] = [];
    const visit = (span: Span, depth: number) => {
      ordered.push({ span, depth });
      [...(children.get(span.context.span_id) ?? [])]
        .sort((a, b) => a.start_time - b.start_time)
        .forEach((child) => visit(child, depth + 1));
    };
    visit(root, 0);
    return ordered;
  };

  return spans
    .filter((span) => span.name === 'Agent.execute' && span.attributes?.['agent.name'] === agent)
    .sort((a, b) => b.start_time - a.start_time)
    .slice(0, limit)
    .map((root) => {
      const tree = below(root);
      return {
        runId: String(root.attributes?.task_id ?? root.context.span_id),
        correlationId: typeof root.attributes?.correlation_id === 'string' ? root.attributes.correlation_id : null,
        start: root.start_time,
        end: root.end_time,
        failed: tree.some(({ span }) => span.status?.status_code === 'ERROR'),
        spans: tree,
      };
    });
}
