import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';
import { graphOf, newEdgeTargets, packRuns, placeFresh, placementOf } from './graph';

const artifact = (id: string, data: Record<string, unknown> = {}): Node => ({
  id,
  type: 'message',
  position: { x: 0, y: 0 },
  data: { artifactType: 'app.Ticket', producedBy: 'external', timestamp: 1, correlationId: 'c-1', payload: {}, ...data },
});
const edge = (source: string, target: string): Edge => ({ id: `${source}-${target}`, source, target, type: 'transformation' });

describe('graphOf', () => {
  it('makes a card of every artifact and an arrow of every edge between them', () => {
    const { nodes, edges } = graphOf(
      [
        artifact('a-1'),
        artifact('a-2', { artifactType: 'Decision[app.Route]', producedBy: 'triage' }),
        { id: 'triage', type: 'agent', position: { x: 0, y: 0 }, data: {} },
      ],
      [edge('a-1', 'a-2'), edge('a-0', 'a-2')],
      false,
    );

    expect(nodes.map((node) => [node.id, node.type, node.data.card.type, node.data.card.producedBy, node.data.card.state])).toEqual([
      ['a-1', 'artifact', 'app.Ticket', 'external', 'done'],
      ['a-2', 'artifact', 'Decision[app.Route]', 'triage', 'done'],
    ]);
    // Only edges between artifacts on the board
    expect(edges.map((each) => [each.source, each.target])).toEqual([['a-1', 'a-2']]);
    expect(edges[0]!.markerEnd).toBeTruthy();
  });

  it('keeps streaming previews as streaming cards', () => {
    const { nodes } = graphOf([artifact('a-1', { isStreaming: true, streamingText: 'Dear' })], [], false);

    expect(nodes[0]!.data.card.state).toBe('streaming');
  });

  it('ties a streaming card to what its run consumed, with an arrow in flight', () => {
    const { edges } = graphOf(
      [artifact('t-1'), artifact('s-1', { isStreaming: true, runId: 'run-1', producedBy: 'writer' })],
      [],
      false,
      [{ runId: 'run-1', agent: 'writer', correlationId: 'c-1', artifacts: ['t-1', 'gone'] }],
    );

    expect(edges.map((each) => [each.source, each.target, each.animated])).toEqual([['t-1', 's-1', true]]);
  });

  it('dashes what comes from an unsure decision', () => {
    const { edges } = graphOf(
      [
        artifact('d-1', { artifactType: 'Decision[app.Route]', decision: { choice: 'UNSURE' } }),
        artifact('d-2', { artifactType: 'Decision[app.Route]', decision: { choice: 'billing' } }),
        artifact('r-1'),
        artifact('r-2'),
      ],
      [edge('d-1', 'r-1'), edge('d-2', 'r-2')],
      false,
    );

    expect(edges.map((each) => Boolean(each.style?.strokeDasharray))).toEqual([true, false]);
  });

  it('narrows to the runs that need a review', () => {
    const { nodes, edges } = graphOf(
      [
        artifact('a-1', { correlationId: 'c-1' }),
        artifact('d-1', { correlationId: 'c-1', artifactType: 'Decision[app.Route]', decision: { choice: 'UNSURE', kind: 'choice' } }),
        artifact('a-2', { correlationId: 'c-2' }),
      ],
      [edge('a-1', 'd-1')],
      true,
    );

    expect(nodes.map((node) => node.id)).toEqual(['a-1', 'd-1']);
    expect(edges).toHaveLength(1);
  });
});

describe('packRuns', () => {
  const size = { width: 236, height: 120 };
  const run = (id: string, timestamp: number) => [
    artifact(`${id}-t`, { correlationId: id, timestamp }),
    artifact(`${id}-d`, { correlationId: id, timestamp: timestamp + 1 }),
  ];

  it('lays each run out on its own and puts the runs in rows, oldest first', () => {
    const { nodes, edges } = graphOf(
      [...run('new', 3), ...run('mid', 2), ...run('old', 1)],
      [edge('old-t', 'old-d'), edge('mid-t', 'mid-d'), edge('new-t', 'new-d')],
      false,
    );
    const sizes = Object.fromEntries(nodes.map((node) => [node.id, size]));

    // Room for two runs in a row
    const { positions, newestRow } = packRuns(nodes, edges, 'hierarchical-horizontal', sizes, 1400);

    const at = (id: string) => positions.get(id)!;
    // Inside a run, left to right
    expect(at('new-t').x).toBeLessThan(at('new-d').x);
    expect(at('new-t').y).toBe(at('new-d').y);
    // The oldest run top left, the next to its right, the newest in the next row
    expect(at('old-t')).toEqual({ x: 0, y: 0 });
    expect(at('old-t').x).toBeLessThan(at('mid-t').x);
    expect(at('old-t').y).toBe(at('mid-t').y);
    expect(at('new-t').y).toBeGreaterThan(at('old-t').y + size.height);
    expect(newestRow.sort()).toEqual(['new-d', 'new-t']);

    // Left to right a run grows to the right: every run as wide as the widest
    expect(at('mid-t').x - at('old-t').x).toBeGreaterThanOrEqual(at('old-d').x + size.width - at('old-t').x);

    // Top down a run grows down and, as its decisions fan out, sideways: slots as large as the largest run
    const down = packRuns(
      [...nodes, ...graphOf([artifact('wide-t', { correlationId: 'wide', timestamp: 0 }), artifact('wide-a', { correlationId: 'wide', timestamp: 0.5 }), artifact('wide-b', { correlationId: 'wide', timestamp: 0.6 })], [], false).nodes],
      [...edges, edge('wide-t', 'wide-a'), edge('wide-t', 'wide-b')],
      'hierarchical-vertical',
      { ...sizes, 'wide-t': size, 'wide-a': size, 'wide-b': size },
      5000,
    ).positions;
    // wide (two cards across) comes first; every slot as wide as it
    expect(down.get('mid-t')!.x - down.get('old-t')!.x).toBe(down.get('old-t')!.x - down.get('wide-a')!.x);
    expect(down.get('old-t')!.x - down.get('wide-a')!.x).toBeGreaterThanOrEqual(2 * size.width + 40);

    // No two cards overlap
    const boxes = [...positions.values()];
    for (let i = 0; i < boxes.length; i += 1)
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i]!;
        const b = boxes[j]!;
        const apart = a.x + size.width <= b.x || b.x + size.width <= a.x || a.y + size.height <= b.y || b.y + size.height <= a.y;
        expect(apart).toBe(true);
      }
  });
});

describe('placeFresh', () => {
  const size = { width: 236, height: 120 };

  it('leaves placed cards where they are: a new card joins its run, a new run starts a row below everything', () => {
    const raw = [
      artifact('a-t', { correlationId: 'a', timestamp: 1 }),
      artifact('a-d', { correlationId: 'a', timestamp: 2 }),
      artifact('b-t', { correlationId: 'b', timestamp: 3 }),
    ];
    const { nodes: all, edges } = graphOf(raw, [edge('a-t', 'a-d')], false);
    const placed = new Map([
      ['a-t', { x: 500, y: 300 }],
      ['b-t', { x: 0, y: 900 }],
    ]);
    const nodes = all.map((node) => (placed.has(node.id) ? { ...node, position: placed.get(node.id)! } : node));
    const sizes = Object.fromEntries(nodes.map((node) => [node.id, size]));

    const positions = placeFresh(nodes, edges, new Set(['a-d']), 'hierarchical-horizontal', sizes, 1400);

    // Run a is laid out again where it starts: a-t stays, a-d comes after it on its line; run b does not move
    expect(positions.get('a-t')).toEqual({ x: 500, y: 300 });
    expect(positions.get('a-d')!.x).toBeGreaterThan(500 + size.width);
    expect(positions.get('a-d')!.y).toBe(300);
    expect(positions.has('b-t')).toBe(false);

    // A whole new run takes the next slot in the last row, or starts a row below
    const { nodes: more, edges: moreEdges } = graphOf(
      [...raw, artifact('c-t', { correlationId: 'c', timestamp: 4 })],
      [edge('a-t', 'a-d')],
      false,
    );
    const now = more.map((node) => ({ ...node, position: placed.get(node.id) ?? positions.get(node.id) ?? node.position }));
    // Run b sits alone in the last row (y 900): c comes right of it
    const next = placeFresh(now, moreEdges, new Set(['c-t']), 'hierarchical-horizontal', { ...sizes, 'c-t': size }, 1400);
    expect(next.get('c-t')!.y).toBe(900);
    expect(next.get('c-t')!.x).toBeGreaterThan(size.width);
    // No room left in that row: a row below everything
    const narrow = placeFresh(now, moreEdges, new Set(['c-t']), 'hierarchical-horizontal', { ...sizes, 'c-t': size }, 300);
    expect(narrow.get('c-t')!.y).toBeGreaterThanOrEqual(900 + size.height);
    expect(narrow.get('c-t')!.x).toBe(0);
  });
});

describe('placeFresh, a run that outgrows its slot', () => {
  const size = { width: 236, height: 120 };

  it('moves to free room instead of growing into its neighbour', () => {
    // Two runs of one card each: slots only one card wide
    const raw = [
      artifact('a-t', { correlationId: 'a', timestamp: 1 }),
      artifact('b-t', { correlationId: 'b', timestamp: 2 }),
      artifact('a-1', { correlationId: 'a', timestamp: 3 }),
      artifact('a-2', { correlationId: 'a', timestamp: 4 }),
    ];
    const { nodes: all, edges } = graphOf(raw, [edge('a-t', 'a-1'), edge('a-t', 'a-2')], false);
    const placed = new Map([
      ['a-t', { x: 0, y: 0 }],
      ['b-t', { x: 316, y: 0 }],
    ]);
    const nodes = all.map((node) => ({ ...node, position: placed.get(node.id) ?? node.position }));
    const sizes = Object.fromEntries(nodes.map((node) => [node.id, size]));

    // Top down, a's two children fan out to 512 px: at its corner it would cover b
    const positions = placeFresh(nodes, edges, new Set(['a-1', 'a-2']), 'hierarchical-vertical', sizes, 5000);

    const at = (id: string) => positions.get(id) ?? placed.get(id)!;
    const boxes = ['a-t', 'a-1', 'a-2', 'b-t'].map((id) => ({ id, ...at(id) }));
    for (let i = 0; i < boxes.length; i += 1)
      for (let j = i + 1; j < boxes.length; j += 1) {
        const p = boxes[i]!;
        const q = boxes[j]!;
        expect(p.x + size.width <= q.x || q.x + size.width <= p.x || p.y + size.height <= q.y || q.y + size.height <= p.y).toBe(true);
      }
    // b stays; a's cards keep together, its root above its children
    expect(positions.has('b-t')).toBe(false);
    expect(at('a-t').y).toBeLessThan(at('a-1').y);
  });
});

describe('placementOf', () => {
  it('lays all cards out on the first load and with auto-arrange, else only the new ones', () => {
    const fresh = new Set(['x']);
    expect(placementOf({ autoArrange: false, firstLoad: true, fresh })).toBe('all');
    expect(placementOf({ autoArrange: false, firstLoad: false, fresh })).toBe(fresh);
    expect(placementOf({ autoArrange: true, firstLoad: false, fresh })).toBe('all');
  });
});

describe('newEdgeTargets', () => {
  it('names the cards an edge newly reaches between cards already on the board', () => {
    const known = new Set(['a-t-a-d']);
    const cards = new Set(['a-t', 'a-d', 'b-t', 'b-d']);

    expect(newEdgeTargets(known, [edge('a-t', 'a-d'), edge('b-t', 'b-d'), edge('b-t', 'gone')], cards)).toEqual(new Set(['b-d']));
  });
});
