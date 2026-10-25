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

  it('keeps the title while another agent already consumes an output that waits for its edges', () => {
    const overlapping = [
      artifact('r3', 'c-8', 'app.Request', 'external', 1000, { payload: { title: 'Prepared request' } }),
      artifact('p3', 'c-8', 'app.Reply', 'writer', 900, { payload: { reply: 'Draft' } }),
    ];
    const running = [
      { agent: 'writer', correlationId: 'c-8', artifacts: ['r3'] },
      { agent: 'reviewer', correlationId: 'c-8', artifacts: ['p3'] },
    ];
    expect(lanesOf(overlapping, [], running).find((each) => each.id === 'c-8')).toMatchObject({ title: 'Prepared request', startedAt: 1000 });
  });

  it('keeps the title while two runs of the agent that wrote it overlap', () => {
    // writer runs on the feedback and, through another subscription, on an unrelated note
    const overlapping = [
      artifact('w4', 'c-10', 'app.Draft', 'writer', 1000, { payload: { title: 'First draft' } }),
      artifact('f4', 'c-10', 'app.Feedback', 'reviewer', 2000, { payload: { note: 'Shorter' } }),
      artifact('x4', 'c-10', 'app.Note', 'external', 3000, { payload: { title: 'Unrelated note' } }),
    ];
    const running = [
      { agent: 'writer', correlationId: 'c-10', artifacts: ['f4'] },
      { agent: 'writer', correlationId: 'c-10', artifacts: ['x4'] },
    ];
    expect(lanesOf(overlapping, [made('w4', 'f4', 'reviewer')], running).find((each) => each.id === 'c-10')).toMatchObject({
      title: 'First draft',
      startedAt: 1000,
    });
  });

  it('keeps the title while the agent that wrote the first artifact runs again', () => {
    // A feedback loop: the writer runs again on the reviewer's feedback
    const loop = [
      artifact('w1', 'c-6', 'app.Draft', 'writer', 1000, { payload: { title: 'First draft' } }),
      artifact('f1', 'c-6', 'app.Feedback', 'reviewer', 2000, { payload: { note: 'Shorter, please' } }),
    ];
    const lanes = lanesOf(loop, [made('w1', 'f1', 'reviewer')], [{ agent: 'writer', correlationId: 'c-6', artifacts: ['f1'] }]);
    expect(lanes.find((each) => each.id === 'c-6')).toMatchObject({ title: 'First draft', startedAt: 1000 });
    // Also after the clock stepped back between the draft and the feedback
    const stepped = loop.map((node) => (node.id === 'f1' ? { ...node, data: { ...node.data, timestamp: 900 } } : node));
    const again = lanesOf(stepped, [made('w1', 'f1', 'reviewer')], [{ agent: 'writer', correlationId: 'c-6', artifacts: ['f1'] }]);
    expect(again.find((each) => each.id === 'c-6')).toMatchObject({ title: 'First draft', startedAt: 1000 });
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

  it("places a stream whose input is not on the board yet after the lane's placeholders, and keeps it there (#642)", () => {
    // The deciders ended, their decisions come with the next snapshot; a team
    // already writes after one of them
    const board = [
      artifact('t5', 'c-5', 'app.SupportTicket', 'external', 7000),
      artifact('s5', 'c-5', 'app.TeamReply', 'shipping_team', 7300, { isStreaming: true, streamingText: 'Thanks for' }),
    ];
    const runs = [
      { agent: 'triage', correlationId: 'c-5', artifacts: ['t5'], types: ['app.SupportTicket'], produces: ['Decision[app.Route]'] },
      { agent: 'urgency', correlationId: 'c-5', artifacts: ['t5'], types: ['app.SupportTicket'], produces: ['Decision[app.Urgent]'] },
      { agent: 'shipping_team', correlationId: 'c-5', artifacts: ['d8', 't5'], types: ['Decision[app.Route]', 'app.SupportTicket'], produces: ['app.TeamReply'] },
    ];
    expect(ids(lanesOf(board, [], runs)[0]!)).toEqual([['t5'], ['pending:triage', 'pending:urgency'], ['s5']]);

    // The snapshot brings the decisions: the stream stays in its column
    const later = [
      ...board,
      artifact('d8', 'c-5', 'Decision[app.Route]', 'triage', 7100, decision('shipping', 0.9)),
      artifact('d9', 'c-5', 'Decision[app.Urgent]', 'urgency', 7150, decision('no', 0.8)),
    ];
    const laterEdges = [made('t5', 'd8', 'triage'), made('t5', 'd9', 'urgency')];
    expect(ids(lanesOf(later, laterEdges, [runs[2]!])[0]!)).toEqual([['t5'], ['d8', 'd9'], ['s5']]);
  });

  it("places a run that consumes a stream after the stream's column, not after its edges (#642)", () => {
    // billing_team still streams its reply; crm_sync already took it up
    const board = [
      artifact('t6', 'c-6', 'app.SupportTicket', 'external', 8000),
      artifact('d6', 'c-6', 'Decision[app.Route]', 'triage', 8100, decision('billing', 0.95)),
      artifact('s6', 'c-6', 'app.TeamReply', 'billing_team', 8200, { isStreaming: true, streamingText: 'The amount' }),
    ];
    const runs = [
      { agent: 'billing_team', correlationId: 'c-6', artifacts: ['d6'] },
      { agent: 'crm_sync', correlationId: 'c-6', artifacts: ['s6'] },
    ];
    expect(ids(lanesOf(board, [made('t6', 'd6', 'triage')], runs)[0]!)).toEqual([['t6'], ['d6'], ['s6'], ['pending:crm_sync']]);
  });

  it("places a run that waits for an input not on the board yet after the runs that make it (#642)", () => {
    // pager reads both decisions; the deciders ended, their decisions come with the next snapshot
    const board = [artifact('t7', 'c-7', 'app.SupportTicket', 'external', 9000)];
    const runs = [
      { agent: 'triage', correlationId: 'c-7', artifacts: ['t7'], types: ['app.SupportTicket'], produces: ['Decision[app.Route]'] },
      { agent: 'urgency', correlationId: 'c-7', artifacts: ['t7'], types: ['app.SupportTicket'], produces: ['Decision[app.Urgent]'] },
      { agent: 'pager', correlationId: 'c-7', artifacts: ['d10', 'd11'], types: ['Decision[app.Route]', 'Decision[app.Urgent]'], produces: ['app.Page'] },
    ];
    expect(ids(lanesOf(board, [], runs)[0]!)).toEqual([['t7'], ['pending:triage', 'pending:urgency'], ['pending:pager']]);

    // The decisions arrive: pager's placeholder stays in its column
    const later = [
      ...board,
      artifact('d10', 'c-7', 'Decision[app.Route]', 'triage', 9100, decision('tech', 0.9)),
      artifact('d11', 'c-7', 'Decision[app.Urgent]', 'urgency', 9150, decision('yes', 0.9)),
    ];
    const laterEdges = [made('t7', 'd10', 'triage'), made('t7', 'd11', 'urgency')];
    expect(ids(lanesOf(later, laterEdges, [runs[2]!])[0]!)).toEqual([['t7'], ['d10', 'd11'], ['pending:pager']]);
  });

  it('places a run that waits for an input after the runs that make that input only (#642)', () => {
    // tech_support writes from the summary and triage's decision, which comes with
    // the next snapshot; archiver works on another branch of the workflow
    const board = [
      artifact('t8', 'c-8', 'app.SupportTicket', 'external', 9500),
      artifact('a8', 'c-8', 'app.Summary', 'summarizer', 9600),
      artifact('b8', 'c-8', 'app.Translation', 'translator', 9700),
      artifact('s8', 'c-8', 'app.TeamReply', 'tech_support', 9800, { isStreaming: true, streamingText: 'We are on it' }),
    ];
    const branches = [made('t8', 'a8', 'summarizer'), made('a8', 'b8', 'translator')];
    const runs = [
      { agent: 'triage', correlationId: 'c-8', artifacts: ['t8'], types: ['app.SupportTicket'], produces: ['Decision[app.Route]'] },
      { agent: 'archiver', correlationId: 'c-8', artifacts: ['b8'], types: ['app.Translation'], produces: ['app.Archive'] },
      { agent: 'tech_support', correlationId: 'c-8', artifacts: ['a8', 'd12'], types: ['app.Summary', 'Decision[app.Route]'], produces: ['app.TeamReply'] },
    ];
    expect(ids(lanesOf(board, branches, runs)[0]!)).toEqual([['t8'], ['a8', 'pending:triage'], ['b8', 's8'], ['pending:archiver']]);
  });

  it('places runs that wait for each other in a chain in their order (#642)', () => {
    // A, B and C ran one after another before the next snapshot: none of their outputs is on the board
    const board = [artifact('t9', 'c-9', 'app.SupportTicket', 'external', 9900)];
    const runs = [
      { agent: 'a', correlationId: 'c-9', artifacts: ['t9'], types: ['app.SupportTicket'], produces: ['app.A'] },
      { agent: 'b', correlationId: 'c-9', artifacts: ['a9'], types: ['app.A'], produces: ['app.B'] },
      { agent: 'c', correlationId: 'c-9', artifacts: ['b9'], types: ['app.B'], produces: ['app.C'] },
    ];
    expect(ids(lanesOf(board, [], runs)[0]!)).toEqual([['t9'], ['pending:a'], ['pending:b'], ['pending:c']]);
  });

  it('places a run that waits for an artifact after the run that published it, not after another publisher of its type (#642)', () => {
    // writer_a and writer_b both write drafts; reviewer read writer_a's, which
    // comes with the next snapshot; writer_b works further down another branch
    const board = [
      artifact('t10', 'c-10', 'app.SupportTicket', 'external', 10000),
      artifact('m10', 'c-10', 'app.Summary', 'summarizer', 10100),
      artifact('n10', 'c-10', 'app.Note', 'noter', 10200),
    ];
    const branches = [made('t10', 'm10', 'summarizer'), made('m10', 'n10', 'noter')];
    const runs = [
      { agent: 'writer_a', correlationId: 'c-10', artifacts: ['t10'], types: ['app.SupportTicket'], produces: ['app.Draft'], published: ['dr-a'] },
      { agent: 'writer_b', correlationId: 'c-10', artifacts: ['n10'], types: ['app.Note'], produces: ['app.Draft'] },
      { agent: 'reviewer', correlationId: 'c-10', artifacts: ['dr-a'], types: ['app.Draft'], produces: ['app.Review'] },
    ];
    expect(ids(lanesOf(board, branches, runs)[0]!)).toEqual([['t10'], ['m10', 'pending:writer_a'], ['n10', 'pending:reviewer'], ['pending:writer_b']]);
  });

  it('does not take a running publisher of a type for an input whose run is known (#642)', () => {
    // reviewer waits for writer_a's draft (writer_a ended) and a note someone
    // published from outside; writer_b writes another draft further down
    const board = [
      artifact('t11', 'c-11', 'app.SupportTicket', 'external', 11000),
      artifact('m11', 'c-11', 'app.Summary', 'summarizer', 11100),
      artifact('n11', 'c-11', 'app.Note', 'noter', 11200),
    ];
    const branches = [made('t11', 'm11', 'summarizer'), made('m11', 'n11', 'noter')];
    const runs = [
      { agent: 'writer_a', correlationId: 'c-11', artifacts: ['t11'], types: ['app.SupportTicket'], produces: ['app.Draft'], published: ['dr-a'] },
      { agent: 'writer_b', correlationId: 'c-11', artifacts: ['n11'], types: ['app.Note'], produces: ['app.Draft'] },
      { agent: 'reviewer', correlationId: 'c-11', artifacts: ['dr-a', 'note-x'], types: ['app.Draft', 'app.Remark'], produces: ['app.Review'] },
    ];
    expect(ids(lanesOf(board, branches, runs)[0]!)).toEqual([['t11'], ['m11', 'pending:writer_a'], ['n11', 'pending:reviewer'], ['pending:writer_b']]);
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

describe('lane status', () => {
  it("says when a run's delivery failed", () => {
    const run = [
      artifact('x1', 'c-9', 'app.Reply', 'support', 1000, { payload: { text: 'Refunded' } }),
      artifact('x2', 'c-9', 'flock.sinks.models.Delivered', 'audit', 1200),
      artifact('x3', 'c-9', 'flock.sinks.models.DeliveryFailed', 'billing-api', 1300),
    ];
    const status = lanesOf(run, [made('x1', 'x2', 'audit'), made('x1', 'x3', 'billing-api')], [])[0]!.status;

    expect(status.kind).toBe('failed');
    expect(status.text).toBe('done in 300 ms · 3 artifacts · 1 delivery failed');
  });
});

describe('decision bundles (#668)', () => {
  const idea = (id: string, ts: number) => artifact(id, 'c-9', 'app.GameIdea', 'external', ts, { payload: { title: `Idea ${id}` } });
  const facet = (id: string, question: string, agent: string, ts: number, choice = 'move', extra: Record<string, unknown> = {}) =>
    artifact(id, 'c-9', `Decision[app.${question}]`, agent, ts, decision(choice, 0.8, { question, ...extra }));

  it("shows the decisions one decider made about one artifact as one card, other deciders' apart", () => {
    const nodes = [
      idea('i1', 1000),
      facet('a1', 'Action', 'facets_a', 1100),
      facet('a2', 'Board', 'facets_a', 1101, 'UNSURE', { bestGuess: 'grid' }),
      facet('b1', 'Action', 'facets_b', 1102),
      facet('b2', 'Board', 'facets_b', 1103),
      facet('u1', 'Urgent', 'urgency', 1104, 'no'),
    ];
    const edges = ['a1', 'a2', 'b1', 'b2', 'u1'].map((id) => made('i1', id, 'x'));
    const [only] = lanesOf(nodes, edges, []);
    expect(only!.columns[1]!.cards.map((card) => [card.id, card.decisions?.map((each) => each.id)])).toEqual([
      ['bundle:a1', ['a1', 'a2']],
      ['bundle:b1', ['b1', 'b2']],
      ['u1', undefined],
    ]);
    // The lane still counts and reviews every decision
    expect(only).toMatchObject({ count: 6, needsReview: true });
  });

  it('keeps the decisions about different artifacts in different bundles', () => {
    const nodes = [idea('i1', 1000), idea('i2', 1001), ...['1', '2', '3', '4'].map((n, k) => facet(`a${n}`, k % 2 ? 'Board' : 'Action', 'facets_a', 1100 + k))];
    const edges = [made('i1', 'a1', 'x'), made('i1', 'a2', 'x'), made('i2', 'a3', 'x'), made('i2', 'a4', 'x')];
    const [only] = lanesOf(nodes, edges, []);
    expect(only!.columns[1]!.cards.map((card) => card.decisions?.map((each) => each.id))).toEqual([
      ['a1', 'a2'],
      ['a3', 'a4'],
    ]);
  });

  it('dashes the arrow after a column of unsure answers also when they are bundled', () => {
    const nodes = [
      idea('i1', 1000),
      facet('a1', 'Action', 'facets_a', 1100, 'UNSURE'),
      facet('a2', 'Board', 'facets_a', 1101, 'UNSURE'),
      artifact('r1', 'c-9', 'app.Reply', 'supervisor', 1200),
    ];
    const edges = [made('i1', 'a1', 'x'), made('i1', 'a2', 'x'), made('a1', 'r1', 'supervisor'), made('a2', 'r1', 'supervisor')];
    const [only] = lanesOf(nodes, edges, []);
    expect(only!.columns.map((column) => column.unsureIn)).toEqual([false, false, true]);
  });

  it('groups by the subject a decision names, also when a filter hides the subject and its edges', () => {
    const about = (id: string, question: string, ts: number, subjects?: string[]) =>
      artifact(id, 'c-9', `Decision[app.${question}]`, 'facets_a', ts, {
        ...decision('move', 0.8, { question }),
        payload: subjects ? { subject_ids: subjects } : {},
      });
    // The ideas are filtered out, so are their edges; the decisions still name their subjects
    const nodes = [
      about('a1', 'Action', 1100, ['i1']),
      about('a2', 'Board', 1101, ['i1']),
      about('a3', 'Action', 1102, ['i2']),
      about('a4', 'Board', 1103, ['i2']),
      about('a5', 'Action', 1104),
      about('a6', 'Board', 1105),
    ];
    const [only] = lanesOf(nodes, [], []);
    // A decision about an unknown subject keeps its own card
    expect(only!.columns.flatMap((column) => column.cards).map((card) => card.decisions?.map((each) => each.id) ?? card.id)).toEqual([
      ['a1', 'a2'],
      ['a3', 'a4'],
      'a5',
      'a6',
    ]);
  });
});
