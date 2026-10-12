import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';
import { lanesOf, titleOf } from './lanes';

const artifact = (id: string, correlationId: string, type: string, producedBy: string, timestamp: number, data: Record<string, unknown> = {}): Node => ({
  id,
  type: 'message',
  position: { x: 0, y: 0 },
  data: { artifactType: type, producedBy, timestamp, correlationId, payload: {}, consumedBy: [], ...data },
});
const decision = (choice: string, probability: number, extra: Record<string, unknown> = {}) => ({
  decision: { question: 'Route', kind: 'choice', choice, bestGuess: null, probabilities: { [choice]: probability }, confidence: probability, threshold: 0.8, model: 'demo', latencyMs: 50, ...extra },
});
const made = (source: string, target: string, agent: string): Edge => ({
  id: `${source}__${target}`,
  source,
  target,
  type: 'transformation',
  data: { transformerAgent: agent, runId: `${agent}-run` },
});

// The ticket triage: a done run, one waiting for review, one deciding, one writing
const nodes = [
  artifact('t1', 'c-1', 'app.SupportTicket', 'external', 1000, { payload: { subject: 'App crashes on login', message: 'It closes' } }),
  artifact('d1', 'c-1', 'Decision[app.Route]', 'triage', 1500, decision('tech', 0.95)),
  artifact('d2', 'c-1', 'Decision[app.Urgent]', 'urgency', 1600, decision('yes', 0.9)),
  artifact('r1', 'c-1', 'app.TeamReply', 'tech_support', 4400),
  artifact('p1', 'c-1', 'app.Page', 'pager', 4500),

  artifact('t2', 'c-2', 'app.SupportTicket', 'external', 2000, { payload: { subject: 'Something odd with my account' } }),
  artifact('d3', 'c-2', 'Decision[app.Route]', 'triage', 2100, decision('UNSURE', 0.46, { bestGuess: 'shipping' })),
  artifact('r2', 'c-2', 'app.TeamReply', 'supervisor', 5000),

  artifact('t3', 'c-3', 'app.SupportTicket', 'external', 3000, { payload: { subject: 'Where is my parcel?' } }),
  artifact('d4', 'c-3', 'Decision[app.Urgent]', 'urgency', 3100, decision('no', 0.71)),

  artifact('t4', 'c-4', 'app.SupportTicket', 'external', 2500, { payload: { subject: 'Refund not received' } }),
  artifact('d5', 'c-4', 'Decision[app.Route]', 'triage', 2600, decision('billing', 0.93)),
  artifact('s1', 'c-4', 'app.TeamReply', 'billing_team', 2700, { isStreaming: true, streamingText: 'Hi, thanks for' }),
];
const edges = [
  made('t1', 'd1', 'triage'),
  made('t1', 'd2', 'urgency'),
  made('d1', 'r1', 'tech_support'),
  made('d1', 'p1', 'pager'),
  made('d2', 'p1', 'pager'),
  made('t2', 'd3', 'triage'),
  made('d3', 'r2', 'supervisor'),
  made('t3', 'd4', 'urgency'),
  made('t4', 'd5', 'triage'),
];
const running = [
  { agent: 'triage', correlationId: 'c-3', artifacts: ['t3'] },
  { agent: 'billing_team', correlationId: 'c-4', artifacts: ['d5'] },
];

const ids = (lane: { columns: { cards: { id: string }[] }[] }) => lane.columns.map((column) => column.cards.map((card) => card.id));
const lane = (id: string) => lanesOf(nodes, edges, running).find((candidate) => candidate.id === id)!;

describe('lanesOf', () => {
  it('makes one lane per run, the newest on top', () => {
    expect(lanesOf(nodes, edges, running).map((each) => each.id)).toEqual(['c-3', 'c-4', 'c-2', 'c-1']);
  });

  it('puts artifacts in columns by what they came from, decisions about one subject in one', () => {
    expect(ids(lane('c-1'))).toEqual([['t1'], ['d1', 'd2'], ['r1', 'p1']]);
  });

  it('says how a done run went, under its first artifact\'s title', () => {
    expect(lane('c-1')).toMatchObject({
      title: 'App crashes on login',
      startedAt: 1000,
      count: 5,
      needsReview: false,
      status: { kind: 'done', text: 'done in 3.5 s · 5 artifacts' },
    });
  });

  it('takes the title from what the run started with, also when a wall clock stepped back', () => {
    // A VM's time sync set the clock back between the ticket and its decision
    const stepped = nodes.map((node) => (node.id === 'd1' ? { ...node, data: { ...node.data, timestamp: 900 } } : node));
    expect(lanesOf(stepped, edges, running).find((each) => each.id === 'c-1')).toMatchObject({
      title: 'App crashes on login',
      startedAt: 1000,
    });
  });

  it('takes the title from what the run started with while its outputs wait for their edges', () => {
    // The request came from another run; the writer's output has no edges until its run is done
    const prepared = [
      artifact('x0', 'c-9', 'app.Draft', 'external', 500),
      artifact('a1', 'c-5', 'app.Request', 'prep', 1000, { payload: { title: 'Prepared request' } }),
      artifact('o1', 'c-5', 'app.Reply', 'writer', 2000),
    ];
    const lanes = lanesOf(prepared, [made('x0', 'a1', 'prep')], [{ agent: 'writer', correlationId: 'c-5', artifacts: ['a1'] }]);
    expect(lanes.find((each) => each.id === 'c-5')).toMatchObject({ title: 'Prepared request', startedAt: 1000 });
  });

  it('keeps the title while an output waits for its edges after a clock stepped back', () => {
    const early = [
      artifact('a2', 'c-7', 'app.Request', 'external', 1000, { payload: { title: 'Prepared request' } }),
      artifact('o2', 'c-7', 'app.Reply', 'writer', 900, { payload: { reply: 'Done' } }),
    ];
    const lanes = lanesOf(early, [], [{ agent: 'writer', correlationId: 'c-7', artifacts: ['a2'] }]);
    expect(lanes.find((each) => each.id === 'c-7')).toMatchObject({ title: 'Prepared request', startedAt: 1000 });
  });

  it('keeps the title while the agent that wrote the first artifact runs again', () => {
    // A feedback loop: the writer runs again on the reviewer's feedback
    const loop = [
      artifact('w1', 'c-6', 'app.Draft', 'writer', 1000, { payload: { title: 'First draft' } }),
      artifact('f1', 'c-6', 'app.Feedback', 'reviewer', 2000, { payload: { note: 'Shorter, please' } }),
    ];
    const lanes = lanesOf(loop, [made('w1', 'f1', 'reviewer')], [{ agent: 'writer', correlationId: 'c-6', artifacts: ['f1'] }]);
    expect(lanes.find((each) => each.id === 'c-6')).toMatchObject({ title: 'First draft', startedAt: 1000 });
  });

  it('marks a run whose decision is unsure and unreviewed, and who answered it meanwhile', () => {
    const review = lane('c-2');
    expect(review).toMatchObject({ needsReview: true, status: { kind: 'review', text: 'needs review · answered by supervisor' } });
    // The route of an unsure decision is drawn dashed
    expect(review.columns.map((column) => column.unsureIn)).toEqual([false, false, true]);
  });

  it('does not ask again for a decision a person reviewed', () => {
    const reviewed = nodes.map((node) =>
      node.id === 'd3' ? { ...node, data: { ...node.data, ...decision('UNSURE', 0.46, { review: { choice: 'shipping', by: 'lead' } }) } } : node,
    );
    expect(lanesOf(reviewed, edges, running).find((each) => each.id === 'c-2')!.needsReview).toBe(false);
  });

  it('shows a deciding agent as a pending card next to what it decides about', () => {
    const deciding = lane('c-3');
    expect(deciding.status).toEqual({ kind: 'running', text: 'triage is deciding' });
    expect(ids(deciding)).toEqual([['t3'], ['d4', 'pending:triage']]);
    // Its type from what it published before
    expect(deciding.columns[1]!.cards[1]).toMatchObject({ state: 'pending', type: 'Decision[app.Route]', producedBy: 'triage' });
    expect(deciding.columns[1]!.activeIn).toBe(true);
    expect(deciding.count).toBe(2);
  });

  it('shows a writing agent\'s streaming artifact after what it consumed', () => {
    const writing = lane('c-4');
    expect(writing.status).toEqual({ kind: 'running', text: 'billing_team is writing' });
    expect(ids(writing)).toEqual([['t4'], ['d5'], ['s1']]);
    expect(writing.columns[2]!.cards[0]!.state).toBe('streaming');
    expect(writing.columns.map((column) => column.activeIn)).toEqual([false, false, true]);
  });

  it('places what a run published before its run is on the record after what the run consumed', () => {
    // The server draws a run's edges once the run is done; the stream that just ended has no payload yet
    const published = [
      ...nodes,
      artifact('r9', 'c-4', 'app.TeamReply', 'billing_team', 2800, { streamingText: 'Hi, thanks for your patience' }),
    ].filter((node) => node.id !== 's1');
    expect(ids(lanesOf(published, edges, running).find((each) => each.id === 'c-4')!)).toEqual([['t4'], ['d5'], ['r9']]);

    // The run ended too: the stream still goes last, not first
    const ended = lanesOf(published, edges, running.filter((run) => run.agent !== 'billing_team'));
    expect(ids(ended.find((each) => each.id === 'c-4')!)).toEqual([['t4'], ['d5'], ['r9']]);
  });

  it('says a lane with nothing on the record yet is running, not done', () => {
    const streamOnly = [artifact('s9', 'c-9', 'app.Digest', 'digest', 9000, { isStreaming: true, streamingText: 'Today' })];
    expect(lanesOf(streamOnly, [], [{ agent: 'digest', correlationId: 'c-9', artifacts: [] }])[0]!.status).toEqual({ kind: 'running', text: 'digest is writing' });
    // Its run already ended: no time to tell
    expect(lanesOf(streamOnly, [], [])[0]!.status).toEqual({ kind: 'done', text: 'done · 0 artifacts' });
  });

  it('places each stream after what its own run consumed, when an agent runs twice in a workflow', () => {
    const twice = [
      ...nodes,
      artifact('s2', 'c-4', 'app.TeamReply', 'billing_team', 2750, { isStreaming: true, streamingText: 'About the ticket', runId: 'run-b' }),
    ].map((node) => (node.id === 's1' ? { ...node, data: { ...node.data, runId: 'run-a' } } : node));
    const runs = [
      { runId: 'run-a', agent: 'billing_team', correlationId: 'c-4', artifacts: ['d5'] },
      { runId: 'run-b', agent: 'billing_team', correlationId: 'c-4', artifacts: ['t4'] },
    ];
    // run-b read the ticket itself (another subscription): its stream follows the ticket
    expect(ids(lanesOf(twice, edges, runs).find((each) => each.id === 'c-4')!)).toEqual([['t4'], ['d5', 's2'], ['s1']]);
  });

  it('names several running agents at once', () => {
    const both = [...running, { agent: 'urgency', correlationId: 'c-3', artifacts: ['t3'] }];
    expect(lanesOf(nodes, edges, both).find((each) => each.id === 'c-3')!.status.text).toBe('triage and 1 more are working');
  });
});

describe('titleOf', () => {
  it('takes the first text of a payload', () => {
    expect(titleOf({ priority: 2, subject: 'Refund not received', message: 'I returned the shoes' })).toBe('Refund not received');
    expect(titleOf({ n: 1 })).toBeNull();
    // A field that names it comes first, wherever it is
    expect(titleOf({ ticket_id: 'T-0010', title: 'Refund not received' })).toBe('Refund not received');
  });
});
