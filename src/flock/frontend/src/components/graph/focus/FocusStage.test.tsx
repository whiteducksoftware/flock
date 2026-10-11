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
    useGraphStore.setState({ nodes, edges });
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

    expect(await screen.findByText('Refund not received')).toBeTruthy();
    expect(screen.getByText('…Hi, thanks')).toBeTruthy();
    fireEvent.click(await screen.findByRole('button', { name: /e81a77/ }));
    expect(screen.getByRole('tab', { name: /Runs/ }).getAttribute('aria-selected')).toBe('true');
  });

  it('waits for the running run\'s output instead of showing an earlier one', async () => {
    useGraphStore.setState({
      nodes: nodes.map((node) => (node.id === 'billing_team' ? { ...node, data: { ...node.data, streamingTokens: [] } } : node)),
    });
    render(<FocusStage onOpenTrace={() => {}} />);

    expect(await screen.findByText('Waiting for output')).toBeTruthy();
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
