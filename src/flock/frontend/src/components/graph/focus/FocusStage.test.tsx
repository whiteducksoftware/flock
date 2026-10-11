import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { Edge, Node } from '@xyflow/react';
import { useGraphStore } from '../../../store/graphStore';
import { useUIStore } from '../../../store/uiStore';
import FocusStage from './FocusStage';

vi.mock('../../../services/websocket', () => ({
  getWebSocketClient: () => ({ on: () => {}, off: () => {} }),
}));

const agent = (id: string, data: Record<string, unknown> = {}): Node => ({
  id,
  type: 'agent',
  position: { x: 0, y: 0 },
  data: { name: id, status: 'idle', ...data },
});
const flow = (source: string, target: string, messageType: string, decisionChoice?: string): Edge => ({
  id: `${source}-${target}-${messageType}`,
  source,
  target,
  type: 'message_flow',
  data: { messageType, messageCount: 1, decisionChoice },
});

const nodes = [
  agent('external', { outputTypes: ['app.SupportTicket'] }),
  agent('triage', { subscriptions: ['app.SupportTicket'], outputTypes: ['Decision[app.Route]'] }),
  agent('billing_team', {
    status: 'running',
    description: 'Answers billing questions as the billing team',
    model: 'openai/gpt-4.1',
    engineTag: 'LLM',
    subscriptions: ['Decision[app.Route]'],
    typeLabels: { 'Decision[app.Route]': '◆ Route.billing' },
    outputTypes: ['app.TeamReply'],
    recvCount: 2,
    sentCount: 1,
    streamingTokens: ['Hi, ', 'thanks'],
  }),
];
const edges = [flow('external', 'triage', 'app.SupportTicket'), flow('triage', 'billing_team', 'Decision[app.Route]', 'billing')];

const serve = () =>
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const routes: Record<string, unknown> = {
        '/api/agents/billing_team/runs': {
          runs: [
            { run_id: '7c1e04aa', start_time: new Date(Date.now() - 2100).toISOString(), status: 'active', metrics: {} },
            {
              run_id: 'e81a77bb',
              start_time: '2026-10-11T12:00:00Z',
              duration_ms: 2600,
              status: 'completed',
              metrics: { tokens_used: 412, cost_usd: 0.004, artifacts_produced: 1 },
            },
          ],
        },
        '/api/artifacts/history/billing_team': {
          messages: [
            {
              id: 'm1',
              type: 'app.SupportTicket',
              direction: 'consumed',
              payload: { subject: 'Refund not received', message: 'I returned the shoes two weeks ago.' },
              timestamp: '2026-10-11T12:00:41Z',
              correlation_id: '9c34aaaa',
            },
          ],
        },
        '/api/streaming-history/billing_team': { events: [] },
        // The running run took a decision; the handle delivers its subject
        '/api/v1/artifacts/d-1?images=thumbnails': {
          id: 'd-1',
          type: 'flock.decisions.Decision[app.Route]',
          payload: { choice: 'billing', subject_ids: ['t-2'] },
          created_at: '2026-10-11T12:01:10Z',
          correlation_id: '5d21bbbb',
        },
        '/api/v1/artifacts/t-2?images=thumbnails': {
          id: 't-2',
          type: 'app.SupportTicket',
          payload: { subject: 'Charged twice', photo: 'A photo, 1200 × 800 PNG' },
          images: [{ path: 'photo', mime_type: 'image/png', thumb: 'data:image/png;base64,AAAA' }],
          created_at: '2026-10-11T12:01:08Z',
          correlation_id: '5d21bbbb',
        },
        '/api/artifact-types': {
          artifact_types: [
            { name: 'app.SupportTicket', schema: { properties: { subject: { type: 'string' } }, required: ['subject'] } },
            { name: 'app.TeamReply', schema: { properties: { reply: { type: 'string', description: 'Short answer' } } } },
          ],
        },
      };
      const body = routes[url];
      return body === undefined ? new Response('', { status: 404 }) : new Response(JSON.stringify(body));
    }),
  );

describe('FocusStage', () => {
  beforeEach(() => {
    serve();
    useGraphStore.setState({
      nodes,
      edges,
      inFlight: new Map([['7c1e04aa', { agent: 'billing_team', types: ['Decision[app.Route]'], artifacts: ['d-1'] }]]),
      runTails: new Map([['7c1e04aa', 'Hi, thanks']]),
    });
    useUIStore.setState({ focusedNodeId: 'billing_team' });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    useUIStore.setState({ focusedNodeId: null });
  });

  it('puts the agent on a stage: status, name, engine and model, description, activity', async () => {
    render(<FocusStage onOpenTrace={() => {}} />);

    const stage = screen.getByRole('dialog', { name: 'billing_team in focus' });
    expect(within(stage).getByRole('heading', { name: 'billing_team' })).toBeTruthy();
    expect(stage.textContent).toContain('LLM');
    expect(stage.textContent).toContain('openai/gpt-4.1');
    expect(stage.textContent).toContain('Answers billing questions as the billing team');
    await screen.findByText(/^running · \d/);
    // The back button takes the keyboard focus
    expect(document.activeElement?.textContent).toContain('Board');
  });

  it('shows its place in the flow, and each entry focuses that node', () => {
    render(<FocusStage onOpenTrace={() => {}} />);

    const lineage = screen.getByRole('navigation', { name: 'Lineage' });
    expect(lineage.textContent).toBe('externalSupportTickettriage◆ Route.billingbilling_teamTeamReplyno consumers yet');

    fireEvent.click(within(lineage).getByRole('button', { name: /triage/ }));
    expect(useUIStore.getState().focusedNodeId).toBe('triage');
  });

  it('shows what it works on next to the stream, and earlier runs', async () => {
    render(<FocusStage onOpenTrace={() => {}} />);

    // The running run's subject, not the last run's input from the history
    expect(await screen.findByText('Charged twice')).toBeTruthy();
    expect(screen.queryByText('Refund not received')).toBeNull();
    expect(screen.getByText('…Hi, thanks')).toBeTruthy();
    fireEvent.click(await screen.findByRole('button', { name: /e81a77/ }));
    expect(screen.getByRole('tab', { name: /Runs/ }).getAttribute('aria-selected')).toBe('true');
  });

  it('waits for the running run\'s output instead of showing an earlier one', async () => {
    useGraphStore.setState({ runTails: new Map() });
    render(<FocusStage onOpenTrace={() => {}} />);

    expect(await screen.findByText('Waiting for output')).toBeTruthy();
  });

  it('shows the output of the run whose input it shows, when runs overlap', async () => {
    useGraphStore.setState({
      inFlight: new Map([
        ['older', { agent: 'billing_team', types: ['app.SupportTicket'], artifacts: ['t-9'] }],
        ['7c1e04aa', { agent: 'billing_team', types: ['Decision[app.Route]'], artifacts: ['d-1'] }],
      ]),
      runTails: new Map([
        ['older', 'An answer to another ticket'],
        ['7c1e04aa', 'About the double charge'],
      ]),
    });
    render(<FocusStage onOpenTrace={() => {}} />);

    expect(await screen.findByText('Charged twice')).toBeTruthy();
    expect(screen.getByText('…About the double charge')).toBeTruthy();
    expect(screen.queryByText(/another ticket/)).toBeNull();
  });

  it('shows the thumbnails of an input\'s images', async () => {
    render(<FocusStage onOpenTrace={() => {}} />);

    expect(await screen.findByRole('button', { name: 'Open photo' })).toBeTruthy();
  });

  it('says when the running run\'s input is not known, and shows the last input once idle', async () => {
    // A run that started before the dashboard connected
    useGraphStore.setState({ inFlight: new Map() });
    const { unmount } = render(<FocusStage onOpenTrace={() => {}} />);
    expect(await screen.findByText('Not known for this run')).toBeTruthy();
    expect(screen.queryByText('Refund not received')).toBeNull();
    unmount();

    useGraphStore.setState({
      nodes: nodes.map((node) => (node.id === 'billing_team' ? { ...node, data: { ...node.data, status: 'idle' } } : node)),
    });
    render(<FocusStage onOpenTrace={() => {}} />);
    expect(await screen.findByText('Refund not received')).toBeTruthy();
  });

  it('says how long ago an idle agent\'s last run ended', async () => {
    const started = new Date(Date.now() - 60_000).toISOString();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.endsWith('/runs')
          ? new Response(JSON.stringify({ runs: [{ run_id: 'r1', start_time: started, duration_ms: 50_000, status: 'completed', metrics: {} }] }))
          : new Response(JSON.stringify({ messages: [], events: [] })),
      ),
    );
    useGraphStore.setState({
      nodes: nodes.map((node) => (node.id === 'billing_team' ? { ...node, data: { ...node.data, status: 'idle' } } : node)),
    });
    render(<FocusStage onOpenTrace={() => {}} />);

    // Ended 10 s ago, though it started a minute ago
    expect(await screen.findByText(/^last run 1\d s ago$/)).toBeTruthy();
  });

  it('reads the history once for Live and History, and lets the keyboard into its tab panel', async () => {
    const fetch = vi.mocked(globalThis.fetch);
    render(<FocusStage onOpenTrace={() => {}} />);
    await screen.findByText('Charged twice');

    fireEvent.click(screen.getByRole('tab', { name: /History/ }));
    await screen.findByTestId('history');

    expect(fetch.mock.calls.filter(([url]) => url === '/api/artifacts/history/billing_team')).toHaveLength(1);
    expect(screen.getByRole('tabpanel').tabIndex).toBe(0);
  });

  it('is a dialog that leaves the header usable (not modal)', () => {
    render(<FocusStage onOpenTrace={() => {}} />);

    expect(screen.getByRole('dialog').hasAttribute('aria-modal')).toBe(false);
  });

  it('shows the contract with the fields of each type', async () => {
    render(<FocusStage onOpenTrace={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Contract' }));

    const contract = await screen.findByTestId('contract');
    expect(within(contract).getByLabelText('Consumes').textContent).toContain(
      '◆ Route.billingdecision handle · receives the SupportTicketsubjectstr',
    );
    expect(within(contract).getByLabelText('Publishes').textContent).toContain('TeamReplyreply?str · Short answer');
  });

  it('shows the fields of each subject a handle may bring', async () => {
    useGraphStore.setState({
      nodes: nodes.map((node) =>
        node.id === 'triage' ? { ...node, data: { ...node.data, subscriptions: ['app.SupportTicket', 'app.TeamReply'] } } : node,
      ),
    });
    render(<FocusStage onOpenTrace={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Contract' }));

    const consumes = within(await screen.findByTestId('contract')).getByLabelText('Consumes');
    expect(consumes.textContent).toContain('SupportTicketsubjectstr');
    expect(consumes.textContent).toContain('TeamReplyreply?str · Short answer');
  });

  it('moves between its tabs with the arrow keys', () => {
    render(<FocusStage onOpenTrace={() => {}} />);
    expect(screen.getAllByRole('tab').map((tab) => tab.tabIndex)).toEqual([0, -1, -1, -1, -1]);

    fireEvent.keyDown(screen.getByRole('tab', { name: 'Live' }), { key: 'ArrowLeft' });

    expect(screen.getByRole('tab', { name: 'Traces' }).getAttribute('aria-selected')).toBe('true');
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Traces' }));
  });

  it('returns to the board with its back button, and ends when the node leaves the board', () => {
    const { rerender } = render(<FocusStage onOpenTrace={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Board/ }));
    expect(useUIStore.getState().focusedNodeId).toBeNull();

    useUIStore.setState({ focusedNodeId: 'gone' });
    rerender(<FocusStage onOpenTrace={() => {}} />);
    expect(useUIStore.getState().focusedNodeId).toBeNull();
  });
});
