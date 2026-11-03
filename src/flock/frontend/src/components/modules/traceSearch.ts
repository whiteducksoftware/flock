/**
 * The trace search of the timeline dock: `agent:billing_team status:error`
 * narrows by agent and status, `service:DecisionEngine` by the spans' class;
 * other words search names, ids and attribute values.
 */

export interface TraceSearch {
  agent: string | null;
  service: string | null;
  status: 'error' | 'ok' | null;
  text: string;
}

interface SearchableSpan {
  name: string;
  attributes: Record<string, unknown>;
}

interface SearchableTrace {
  traceId: string;
  hasError: boolean;
  spans: SearchableSpan[];
}

export function parseTraceSearch(query: string): TraceSearch {
  const search: TraceSearch = { agent: null, service: null, status: null, text: '' };
  const words: string[] = [];
  for (const word of query.trim().split(/\s+/).filter(Boolean)) {
    const [key, ...rest] = word.split(':');
    const value = rest.join(':');
    if (key === 'agent' && value) search.agent = value;
    else if (key === 'service' && value) search.service = value.toLowerCase();
    else if (key === 'status' && (value === 'error' || value === 'ok')) search.status = value;
    else words.push(word);
  }
  search.text = words.join(' ').toLowerCase();
  return search;
}

export function matchesTrace(trace: SearchableTrace, search: TraceSearch): boolean {
  if (search.status === 'error' && !trace.hasError) return false;
  if (search.status === 'ok' && trace.hasError) return false;
  if (search.agent && !trace.spans.some((span) => span.attributes['agent.name'] === search.agent)) return false;
  if (search.service && !trace.spans.some((span) => span.name.toLowerCase().split('.')[0] === search.service)) return false;
  if (!search.text) return true;
  return (
    trace.traceId.toLowerCase().includes(search.text) ||
    trace.spans.some(
      (span) =>
        span.name.toLowerCase().includes(search.text) ||
        Object.values(span.attributes).some((value) => typeof value === 'string' && value.toLowerCase().includes(search.text)),
    )
  );
}
