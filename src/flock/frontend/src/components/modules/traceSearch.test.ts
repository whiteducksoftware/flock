import { describe, expect, it } from 'vitest';
import { matchesTrace, parseTraceSearch } from './traceSearch';

const span = (name: string, attributes: Record<string, unknown> = {}, error = false) => ({
  name,
  attributes,
  status: { status_code: error ? 'ERROR' : 'OK' },
});

const billing = {
  traceId: 'abc123',
  hasError: true,
  spans: [span('Agent.execute', { 'agent.name': 'billing_team', correlation_id: 'c-9' }), span('LM.call', {}, true)],
};
const triage = {
  traceId: 'def456',
  hasError: false,
  spans: [span('Agent.execute', { 'agent.name': 'triage' }), span('DecisionEngine.evaluate')],
};

describe('trace search', () => {
  it('reads agent:, service: and status: terms and keeps the rest as text', () => {
    expect(parseTraceSearch('agent:billing_team status:error refund')).toEqual({
      agent: 'billing_team',
      service: null,
      status: 'error',
      text: 'refund',
    });
    expect(parseTraceSearch('  service:DecisionEngine  ')).toEqual({ agent: null, service: 'decisionengine', status: null, text: '' });
  });

  it('finds traces by agent, service, status and text', () => {
    const find = (query: string) => [billing, triage].filter((trace) => matchesTrace(trace, parseTraceSearch(query))).map((trace) => trace.traceId);

    expect(find('agent:billing_team')).toEqual(['abc123']);
    expect(find('status:error')).toEqual(['abc123']);
    expect(find('status:ok')).toEqual(['def456']);
    expect(find('service:decisionengine')).toEqual(['def456']);
    expect(find('c-9')).toEqual(['abc123']);
    expect(find('def4')).toEqual(['def456']);
    expect(find('agent:triage status:error')).toEqual([]);
    expect(find('')).toEqual(['abc123', 'def456']);
  });
});
