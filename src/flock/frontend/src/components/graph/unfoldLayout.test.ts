import { describe, expect, it } from 'vitest';
import type { Edge, Node, XYPosition } from '@xyflow/react';
import { UNFOLDED_SIZE, unfoldedPositions } from './unfoldLayout';

const CARD = { width: 260, height: 120 };

const card = (id: string, x: number, y: number): Node => ({ id, type: 'agent', position: { x, y }, data: {} });
const edge = (source: string, target: string): Edge => ({ id: `${source}-${target}`, source, target });

/** The triage flock, laid out left to right as cards. */
const nodes = [
  card('intake', 0, 200),
  card('triage', 400, 200),
  card('urgency', 400, 400),
  card('billing', 800, 0),
  card('tech', 800, 200),
  card('pager', 1200, 300),
];
const edges = [
  edge('intake', 'triage'),
  edge('intake', 'urgency'),
  edge('triage', 'billing'),
  edge('triage', 'tech'),
  edge('triage', 'pager'),
  edge('urgency', 'pager'),
];
const dimensions = Object.fromEntries(nodes.map((node) => [node.id, CARD]));

/** Pairs of nodes whose boxes overlap, with `unfolded` at its unfolded size. */
const overlapping = (positions: Map<string, XYPosition>, unfolded: string) => {
  const size = (id: string) => (id === unfolded ? UNFOLDED_SIZE : CARD);
  const ids = [...positions.keys()];
  const pairs: string[] = [];
  ids.forEach((a, i) =>
    ids.slice(i + 1).forEach((b) => {
      const pa = positions.get(a)!;
      const pb = positions.get(b)!;
      const apart =
        pa.x + size(a).width <= pb.x || pb.x + size(b).width <= pa.x || pa.y + size(a).height <= pb.y || pb.y + size(b).height <= pa.y;
      if (!apart) pairs.push(`${a}/${b}`);
    }),
  );
  return pairs;
};

describe('unfoldedPositions', () => {
  it('reruns the hierarchical layout with the unfolded size, so no node overlaps', () => {
    const positions = unfoldedPositions(nodes, edges, 'triage', {
      mode: 'hierarchical-horizontal',
      dimensions,
      nodeSpacing: 75,
      rankSpacing: 150,
    });

    expect(positions.size).toBe(nodes.length);
    expect(overlapping(positions, 'triage')).toEqual([]);
  });

  it('keeps the unfolded node where it was, and the neighbors make room around it', () => {
    const positions = unfoldedPositions(nodes, edges, 'triage', { mode: 'hierarchical-horizontal', dimensions });

    expect(positions.get('triage')).toEqual({ x: 400, y: 200 });
    // Left to right: what triage reads is left of it, what it decides right of its unfolded width
    expect(positions.get('intake')!.x + CARD.width).toBeLessThanOrEqual(400);
    expect(positions.get('tech')!.x).toBeGreaterThanOrEqual(400 + UNFOLDED_SIZE.width);
  });

  it('inserts room in the free layouts and keeps their arrangement', () => {
    const positions = unfoldedPositions(nodes, edges, 'triage', { mode: 'grid', dimensions });
    const wider = UNFOLDED_SIZE.width - CARD.width;
    const taller = UNFOLDED_SIZE.height - CARD.height;

    expect(Object.fromEntries(positions)).toEqual({
      intake: { x: 0, y: 200 }, // left of it
      triage: { x: 400, y: 200 },
      urgency: { x: 400, y: 400 + taller }, // below it
      billing: { x: 800 + wider, y: 0 }, // right of it
      tech: { x: 800 + wider, y: 200 },
      pager: { x: 1200 + wider, y: 300 },
    });
    expect(overlapping(positions, 'triage')).toEqual([]);
  });
});
