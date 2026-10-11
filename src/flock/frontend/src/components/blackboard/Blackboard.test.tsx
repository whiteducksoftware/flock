import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { Edge, Node } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import Blackboard from './Blackboard';

vi.mock('../modules/HistoricalArtifactsModule', () => ({ default: () => <div data-testid="table" /> }));

const artifact = (id: string, correlationId: string, type: string, producedBy: string, timestamp: number, data: Record<string, unknown> = {}): Node => ({
  id,
  type: 'message',
  position: { x: 0, y: 0 },
  data: { artifactType: type, producedBy, timestamp, correlationId, payload: {}, consumedBy: [], visibilityKind: 'Public', ...data },
});
const decision = (choice: string, probability: number, extra: Record<string, unknown> = {}) => ({
  decision: {
    question: 'Route',
    kind: 'choice',
    choice,
    bestGuess: null,
    probabilities: { [choice]: probability },
    confidence: probability,
    threshold: 0.8,
    model: 'azure/decision-1',
    latencyMs: 58,
    ...extra,
  },
});
const made = (source: string, target: string, agent: string): Edge => ({ id: `${source}__${target}`, source, target, type: 'transformation', data: { transformerAgent: agent } });

const nodes = [
  artifact('t1', 'aaaa1111-0000', 'app.SupportTicket', 'external', 1000, { payload: { subject: 'App crashes on login', message: 'It closes right after' } }),
  artifact('d1', 'aaaa1111-0000', 'Decision[app.Route]', 'triage', 1500, { ...decision('tech', 0.95), consumedBy: ['tech_support'] }),
  artifact('r1', 'aaaa1111-0000', 'app.TeamReply', 'tech_support', 4500, { payload: { team: 'tech', reply: 'Sorry about that' } }),
  artifact('t2', 'bbbb2222-0000', 'app.SupportTicket', 'external', 2000, { payload: { subject: 'Something odd with my account' } }),
  artifact('d2', 'bbbb2222-0000', 'Decision[app.Route]', 'triage', 2100, decision('UNSURE', 0.46, { bestGuess: 'shipping', probabilities: { shipping: 0.46, billing: 0.44 } })),
  artifact('t3', 'cccc3333-0000', 'app.SupportTicket', 'external', 3000, { payload: { subject: 'Refund not received' } }),
  artifact('s1', 'cccc3333-0000', 'app.TeamReply', 'billing_team', 3100, { isStreaming: true, streamingText: 'Hi, thanks for your patience' }),
];
const edges = [made('t1', 'd1', 'triage'), made('d1', 'r1', 'tech_support'), made('t2', 'd2', 'triage')];

const lane = (run: string) => screen.getByRole('region', { name: `Run ${run}` });

describe('Blackboard', () => {
  beforeEach(() => {
    useGraphStore.setState({
      viewMode: 'blackboard',
      nodes,
      edges,
      inFlight: new Map([['r-9', { agent: 'billing_team', types: ['app.SupportTicket'], artifacts: ['t3'], correlationId: 'cccc3333-0000' }]]),
      truncated: false,
    });
    useUIStore.setState({ blackboardView: 'lanes', needsReviewOnly: false, unfoldedArtifactId: null });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === '/api/v1/artifacts/d1?images=thumbnails&embed_meta=true'
          ? new Response(
              JSON.stringify({
                id: 'd1',
                type: 'Decision[app.Route]',
                payload: { choice: 'tech' },
                produced_by: 'triage',
                created_at: '2026-10-11T12:00:01Z',
                correlation_id: 'aaaa1111-0000',
                partition_key: null,
                tags: ['support'],
                visibility: { kind: 'Public' },
                visibility_kind: 'Public',
                consumed_by: ['tech_support'],
                consumptions: [{ artifact_id: 'd1', consumer: 'tech_support', run_id: '7f3a2b91-4c0d-4e2a-9b1e-3d5f6a7b8c9d', correlation_id: 'aaaa1111-0000', consumed_at: '2026-10-11T12:00:02Z' }],
              }),
            )
          : new Response('', { status: 404 }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    useUIStore.setState({ blackboardView: 'lanes', needsReviewOnly: false, unfoldedArtifactId: null });
  });

  it('shows each run as a lane, newest on top, with its status and its artifacts by column', () => {
    render(<Blackboard />);

    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Run cccc', 'Run bbbb', 'Run aaaa']);
    const done = lane('aaaa');
    expect(done.textContent).toContain('App crashes on login');
    expect(done.textContent).toContain('done in 3.5 s · 3 artifacts');
    // Type and producer, two fields of the payload, a decision's answer
    expect(within(done).getByRole('button', { name: 'SupportTicket by external' }).textContent).toContain('subjectApp crashes on login');
    expect(within(done).getByRole('button', { name: '◆ Route by triage' }).textContent).toContain('tech0.95');
  });

  it('shows an unsure decision with its best guess, and the run as needing review', () => {
    render(<Blackboard />);

    const review = lane('bbbb');
    expect(review.textContent).toContain('needs review');
    expect(within(review).getByRole('button', { name: '◆ Route by triage' }).textContent).toContain('UNSUREshipping 0.46');
  });

  it('shows what a running agent writes as it streams', () => {
    render(<Blackboard />);

    const running = lane('cccc');
    expect(running.textContent).toContain('billing_team is writing');
    expect(within(running).getByRole('button', { name: 'TeamReply by billing_team' }).textContent).toContain('Hi, thanks for your patience');
  });

  it('counts runs, artifacts and reviews, and narrows to the runs that need a review', () => {
    render(<Blackboard />);
    expect(screen.getByText('3 runs · 7 artifacts · 1 needs review')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Needs review only' }));
    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Run bbbb']);
    expect(screen.getByRole('button', { name: 'Needs review only' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('unfolds a card in place with what it read by ID, and folds it', async () => {
    render(<Blackboard />);

    fireEvent.click(within(lane('aaaa')).getByRole('button', { name: '◆ Route by triage', expanded: false }));
    const card = screen.getByRole('article', { name: '◆ Route by triage' });
    expect(card.textContent).toContain('by triage · 58 ms');
    expect(card.textContent).toContain('azure/decision-1');
    // Its consumption history, from the artifact read by ID
    expect(await within(card).findByText('run 7f3a2b')).toBeTruthy();
    expect(card.textContent).toContain('support');

    fireEvent.click(within(card).getByRole('button', { name: 'Fold' }));
    expect(screen.queryByRole('article')).toBeNull();
  });

  it('keeps the output so far of a streaming card it unfolds, and reads it once it is published', async () => {
    render(<Blackboard />);

    fireEvent.click(within(lane('cccc')).getByRole('button', { name: 'TeamReply by billing_team', expanded: false }));
    const card = screen.getByRole('article', { name: 'TeamReply by billing_team' });
    expect(card.textContent).toContain('Hi, thanks for your patience');
    // Not on the record yet: nothing to read
    expect(card.textContent).toContain('Not published yet');
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).not.toContain('/api/v1/artifacts/s1?images=thumbnails&embed_meta=true');

    act(() =>
      useGraphStore.setState({
        nodes: nodes.map((node) =>
          node.id === 's1' ? { ...node, data: { ...node.data, isStreaming: false, payload: { reply: 'Hi, thanks for your patience.' } } } : node,
        ),
        edges: [...edges, made('t3', 's1', 'billing_team')],
      }),
    );
    await waitFor(() =>
      expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toContain('/api/v1/artifacts/s1?images=thumbnails&embed_meta=true'),
    );
  });

  it('unfolds a card with the keyboard', () => {
    render(<Blackboard />);

    fireEvent.keyDown(within(lane('aaaa')).getByRole('button', { name: 'SupportTicket by external', expanded: false }), { key: 'Enter' });
    expect(useUIStore.getState().unfoldedArtifactId).toBe('t1');
  });

  it('says when the lanes hold only the newest artifacts', () => {
    useGraphStore.setState({ truncated: true });
    render(<Blackboard />);

    expect(screen.getByText(/newest 500 artifacts/)).toBeTruthy();
  });

  it('switches to the table', () => {
    render(<Blackboard />);

    fireEvent.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByTestId('table')).toBeTruthy();
    expect(screen.queryAllByRole('region')).toHaveLength(0);
    expect(useUIStore.getState().blackboardView).toBe('table');
  });
});
