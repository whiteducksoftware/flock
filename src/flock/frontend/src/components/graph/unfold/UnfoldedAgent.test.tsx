import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useUIStore } from '../../../store/uiStore';
import type { PortRow } from '../card/cardModel';
import type { StreamEvent } from './LiveTab';
import UnfoldedAgent from './UnfoldedAgent';

// A websocket client the tests drive
const listeners = new Map<string, Set<(data: unknown) => void>>();
const emit = (type: string, data: unknown) => listeners.get(type)?.forEach((listener) => listener(data));
vi.mock('../../../services/websocket', () => ({
  getWebSocketClient: () => ({
    on: (type: string, listener: (data: unknown) => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(listener);
    },
    off: (type: string, listener: (data: unknown) => void) => listeners.get(type)?.delete(listener),
  }),
}));

/** Answers the dashboard's API from `routes`, by path. */
const serve = (routes: Record<string, unknown>) => {
  const fetch = vi.fn(async (url: string) => {
    const body = routes[url];
    return body === undefined
      ? new Response('not found', { status: 404 })
      : new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
};

const token = (content: string, sequence: number): StreamEvent => ({
  agent_name: 'billing_team',
  run_id: 'r1',
  output_type: 'llm_token',
  content,
  sequence,
  is_final: false,
});

const RUNS = {
  runs: [
    {
      run_id: '5a1f02aa-0000',
      start_time: '2026-10-11T12:00:42Z',
      duration_ms: null,
      status: 'active',
      metrics: { artifacts_produced: 0 },
    },
    {
      run_id: '9c3450bb-0000',
      start_time: '2026-10-11T12:00:41Z',
      duration_ms: 61,
      status: 'completed',
      metrics: { tokens_used: 1200, cost_usd: 0.0012, artifacts_produced: 1 },
    },
    {
      run_id: 'b20c19cc-0000',
      start_time: '2026-10-11T12:00:40Z',
      duration_ms: 1500,
      status: 'error',
      metrics: { tokens_used: 300, cost_usd: null, artifacts_produced: 0 },
      error_type: 'TimeoutError',
      error_message: 'The CRM did not answer',
    },
  ],
};

const rows: PortRow[] = [
  { dir: 'in', type: 'app.SupportTicket', label: 'SupportTicket', decision: false, count: 8, times: 1 },
  { dir: 'out', type: 'app.Reply', label: 'Reply', decision: false, count: 7, times: 1 },
];

const renderAgent = (props: Partial<React.ComponentProps<typeof UnfoldedAgent>> = {}) =>
  render(
    <UnfoldedAgent
      id="billing_team"
      agent={{
        name: 'billing_team',
        status: 'running',
        description: 'Answers billing tickets',
        model: 'azure/gpt-4.1',
        recvCount: 8,
        sentCount: 7,
      }}
      status="running"
      dot={<span />}
      tag={<span>LLM</span>}
      handles={null}
      rows={rows}
      states={<div data-testid="states">ticker</div>}
      onOpenTrace={() => {}}
      {...props}
    />,
  );

describe('UnfoldedAgent', () => {
  beforeEach(() => {
    serve({ '/api/agents/billing_team/runs': RUNS });
    useUIStore.setState({ unfoldedNodeId: 'billing_team' });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    listeners.clear();
  });

  it('shows the header, what the agent is, its ports and the Overview', async () => {
    renderAgent();

    expect(screen.getByText('billing_team')).toBeTruthy();
    expect(screen.getByText('Answers billing tickets')).toBeTruthy();
    expect(screen.getByText('azure/gpt-4.1')).toBeTruthy();
    expect(screen.getByTitle('app.SupportTicket').textContent).toBe('inSupportTicket8');
    expect(screen.getByRole('tab', { name: 'Overview' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('states')).toBeTruthy();
    // History counts the messages; Runs the runs once they are read
    expect(screen.getByRole('tab', { name: 'History 15' })).toBeTruthy();
    await screen.findByRole('tab', { name: 'Runs 3' });
    // Runs in numbers: the unpriced run adds tokens but no cost
    const overview = screen.getByTestId('overview');
    expect(overview.textContent).toContain('Failed1');
    expect(overview.textContent).toContain('Tokens1,500');
    expect(overview.textContent).toContain('Cost$0.0012');
  });

  it('names a decider\'s decision model and threshold', () => {
    renderAgent({
      agent: { name: 'triage', status: 'idle', model: null },
      decider: { model: 'azure/decision-1', threshold: 0.8, questions: [] } as never,
    });

    // Under the name; the decider's answers name it too until the decision kit (#566)
    const named = screen.getAllByText('azure/decision-1 · threshold 0.80');
    expect(named.some((element) => element.className.includes('model'))).toBe(true);
  });

  it('folds with its button, and the click goes no further', () => {
    const outside = vi.fn();
    render(
      <div onClick={outside}>
        <UnfoldedAgent
          id="billing_team"
          agent={{ name: 'billing_team' }}
          status="idle"
          dot={null}
          tag={null}
          handles={null}
          rows={[]}
          states={null}
          onOpenTrace={() => {}}
        />
      </div>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fold back to a card' }));

    expect(useUIStore.getState().unfoldedNodeId).toBeNull();
    expect(outside).not.toHaveBeenCalled();
  });

  it('lists the runs with their result, tokens and cost', async () => {
    renderAgent();
    fireEvent.click(screen.getByRole('tab', { name: /Runs/ }));

    const runs = await screen.findByTestId('runs');
    expect(within(screen.getByTestId('run-5a1f02aa-0000')).getByText('running')).toBeTruthy();
    expect(screen.getByTestId('run-9c3450bb-0000').textContent).toContain('61 ms1 artifact1,200$0.0012');
    // Unpriced: tokens and no cost
    expect(screen.getByTestId('run-b20c19cc-0000').textContent).toContain('1.5 sTimeoutError300—');
    expect(runs.textContent).toContain('The CRM did not answer');
  });

  it('reads the runs again while the agent runs, as runs start and end', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetch = serve({ '/api/agents/billing_team/runs': RUNS });
    renderAgent();
    await screen.findByRole('tab', { name: 'Runs 3' });
    const reads = () => fetch.mock.calls.filter(([url]) => url === '/api/agents/billing_team/runs').length;
    const before = reads();

    await act(async () => {
      vi.advanceTimersByTime(3100);
    });

    expect(reads()).toBe(before + 1);
    vi.useRealTimers();
  });

  it('keeps the newest runs when an older read answers last', async () => {
    const answers: ((runs: unknown) => void)[] = [];
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            answers.push((runs) => resolve(new Response(JSON.stringify({ runs }))));
          }),
      ),
    );
    renderAgent();
    // A poll starts a second read while the first is still out
    await act(async () => {
      vi.advanceTimersByTime(3100);
    });
    expect(answers).toHaveLength(2);

    await act(async () => answers[1]!(RUNS.runs));
    await act(async () => answers[0]!([]));

    expect(screen.getByRole('tab', { name: 'Runs 3' })).toBeTruthy();
    vi.useRealTimers();
  });

  it('shows the history, newest first, and opens a payload', async () => {
    serve({
      '/api/agents/billing_team/runs': RUNS,
      '/api/artifacts/history/billing_team': {
        messages: [
          {
            id: 'm2',
            type: 'Decision[app.Route]',
            direction: 'published',
            payload: { text: 'Your refund is on its way' },
            timestamp: '2026-10-11T12:00:43Z',
            correlation_id: '9c34aaaa',
          },
          {
            id: 'm1',
            type: 'app.SupportTicket',
            direction: 'consumed',
            payload: { subject: 'Refund not received' },
            timestamp: '2026-10-11T12:00:40Z',
            consumed_at: '2026-10-11T12:00:41Z',
            correlation_id: '9c34aaaa',
          },
        ],
      },
    });
    renderAgent();
    fireEvent.click(screen.getByRole('tab', { name: /History/ }));

    const history = await screen.findByTestId('history');
    const [published, consumed] = within(history).getAllByRole('button');
    expect(published!.textContent).toContain('↑◆ RouteYour refund is on its way9c34');
    expect(consumed!.textContent).toContain('↓SupportTicketRefund not received9c34');

    fireEvent.click(consumed!);
    expect(consumed!.getAttribute('aria-expanded')).toBe('true');
    expect(history.textContent).toContain('"subject": "Refund not received"');
  });

  it('streams the output after its history, without repeating it on the next opening', async () => {
    serve({
      '/api/agents/billing_team/runs': RUNS,
      '/api/streaming-history/billing_team': { events: [token('We ', 0), token('have ', 1)] },
    });
    const { unmount } = renderAgent();
    fireEvent.click(screen.getByRole('tab', { name: 'Live' }));

    await waitFor(() => expect(screen.getByTestId('live').textContent).toContain('We have'));
    act(() => emit('streaming_output', token('refunded', 2)));
    expect(screen.getByTestId('live').textContent).toBe('We have refunded▍');

    // Opened again: the history only (the server has the new token by then)
    serve({
      '/api/agents/billing_team/runs': RUNS,
      '/api/streaming-history/billing_team': { events: [token('We ', 0), token('have ', 1), token('refunded', 2)] },
    });
    unmount();
    renderAgent();
    fireEvent.click(screen.getByRole('tab', { name: 'Live' }));
    await waitFor(() => expect(screen.getByTestId('live').textContent).toBe('We have refunded▍'));
  });

  it('says when the output so far could not be read, and still streams', async () => {
    serve({ '/api/agents/billing_team/runs': RUNS });
    renderAgent();
    fireEvent.click(screen.getByRole('tab', { name: 'Live' }));

    await waitFor(() => expect(screen.getByTestId('live').textContent).toContain('could not be read (404)'));
    act(() => emit('streaming_output', token('refunded', 2)));
    expect(screen.getByTestId('live').textContent).toContain('refunded');
  });

  it('keeps a live event that came before the history once', async () => {
    let answer: (value: Response) => void = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url.startsWith('/api/streaming-history')
          ? new Promise<Response>((resolve) => {
              answer = resolve;
            })
          : Promise.resolve(new Response(JSON.stringify(RUNS))),
      ),
    );
    renderAgent();
    fireEvent.click(screen.getByRole('tab', { name: 'Live' }));

    // One live token the history has too, one it has not
    act(() => {
      emit('streaming_output', token('have ', 1));
      emit('streaming_output', token('refunded', 2));
    });
    await act(async () => answer(new Response(JSON.stringify({ events: [token('We ', 0), token('have ', 1)] }))));

    await waitFor(() => expect(screen.getByTestId('live').textContent).toBe('We have refunded▍'));
  });

  it('shows where a run\'s time went, and opens its trace', async () => {
    const MS = 1_000_000;
    serve({
      '/api/agents/billing_team/runs': RUNS,
      '/api/traces/agents/billing_team?runs=5': [
        {
          name: 'Agent.execute',
          context: { trace_id: 't', span_id: 'a' },
          start_time: 0,
          end_time: 61 * MS,
          attributes: { 'agent.name': 'billing_team', task_id: '9c3450bb', correlation_id: 'c-9' },
        },
        { name: 'Flock.publish', context: { trace_id: 't', span_id: 'b' }, parent_id: 'a', start_time: 55 * MS, end_time: 58 * MS },
      ],
    });
    const onOpenTrace = vi.fn();
    renderAgent({ onOpenTrace });
    fireEvent.click(screen.getByRole('tab', { name: 'Traces' }));

    const traces = await screen.findByTestId('traces');
    expect(traces.textContent).toContain('Run 9c3450 · 61 ms');
    expect(traces.textContent).toContain('Flock.publish3 ms');
    fireEvent.click(screen.getByRole('button', { name: 'Open in the trace viewer →' }));
    expect(onOpenTrace).toHaveBeenCalledWith('c-9');
  });
});
