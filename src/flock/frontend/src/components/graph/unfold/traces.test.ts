import { describe, expect, it } from 'vitest';
import { runTraces, type Span } from './traces';

const MS = 1_000_000;

const span = (id: string, name: string, start: number, end: number, extra: Partial<Span> = {}): Span => ({
  name,
  context: { trace_id: 't1', span_id: id },
  start_time: start * MS,
  end_time: end * MS,
  ...extra,
});

describe('runTraces', () => {
  const spans: Span[] = [
    span('a', 'Agent.execute', 0, 61, { attributes: { 'agent.name': 'triage', task_id: 'run-1', correlation_id: 'c-1' } }),
    span('b', 'Flock.publish', 55, 58, { parent_id: 'a' }),
    span('c', 'DecisionEngine.evaluate', 5, 52, { parent_id: 'a' }),
    span('d', 'provider.decide', 6, 50, { parent_id: 'c', status: { status_code: 'ERROR' } }),
    span('e', 'Agent.execute', 100, 130, { attributes: { 'agent.name': 'triage', task_id: 'run-2' } }),
    span('f', 'Agent.execute', 200, 210, { attributes: { 'agent.name': 'billing', task_id: 'run-3' } }),
  ];

  it('finds the agent\'s runs, newest first, each with the spans below it in order', () => {
    const traces = runTraces(spans, 'triage');

    expect(traces.map((trace) => trace.runId)).toEqual(['run-2', 'run-1']);
    const run = traces[1]!;
    expect(run.spans.map(({ span, depth }) => [span.name, depth])).toEqual([
      ['Agent.execute', 0],
      ['DecisionEngine.evaluate', 1],
      ['provider.decide', 2],
      ['Flock.publish', 1],
    ]);
    expect(run).toMatchObject({ correlationId: 'c-1', failed: true, start: 0, end: 61 * MS });
    expect(traces[0]).toMatchObject({ correlationId: null, failed: false });
  });

  it('keeps the latest runs only', () => {
    expect(runTraces(spans, 'triage', 1).map((trace) => trace.runId)).toEqual(['run-2']);
  });
});
