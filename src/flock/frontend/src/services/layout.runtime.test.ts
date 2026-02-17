import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import { applyHierarchicalLayout } from './layout';

function makeSimpleChain(): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    { id: 'a', type: 'agent', position: { x: 0, y: 0 }, data: { name: 'A' } },
    { id: 'b', type: 'agent', position: { x: 0, y: 0 }, data: { name: 'B' } },
  ];

  const edges: Edge[] = [{ id: 'a-b', source: 'a', target: 'b' }];

  return { nodes, edges };
}

describe('layout runtime behavior', () => {
  it('honors configured rank spacing for hierarchical layout', () => {
    const { nodes, edges } = makeSimpleChain();

    const tight = applyHierarchicalLayout(nodes, edges, {
      direction: 'TB',
      nodeSpacing: 50,
      rankSpacing: 50,
    });

    const loose = applyHierarchicalLayout(nodes, edges, {
      direction: 'TB',
      nodeSpacing: 50,
      rankSpacing: 300,
    });

    const tightA = tight.nodes.find((n) => n.id === 'a')!;
    const tightB = tight.nodes.find((n) => n.id === 'b')!;
    const looseA = loose.nodes.find((n) => n.id === 'a')!;
    const looseB = loose.nodes.find((n) => n.id === 'b')!;

    const tightDistance = Math.abs(tightB.position.y - tightA.position.y);
    const looseDistance = Math.abs(looseB.position.y - looseA.position.y);

    expect(looseDistance).toBeGreaterThan(tightDistance);
  });

  it('uses measured dimensions when provided', () => {
    const { nodes, edges } = makeSimpleChain();

    const baseline = applyHierarchicalLayout(nodes, edges, {
      direction: 'TB',
    });

    const measured = applyHierarchicalLayout(nodes, edges, {
      direction: 'TB',
      dimensionsByNodeId: {
        a: { width: 220, height: 320 },
        b: { width: 220, height: 320 },
      },
    });

    const baselineA = baseline.nodes.find((n) => n.id === 'a')!;
    const baselineB = baseline.nodes.find((n) => n.id === 'b')!;
    const measuredA = measured.nodes.find((n) => n.id === 'a')!;
    const measuredB = measured.nodes.find((n) => n.id === 'b')!;

    const baselineDistance = Math.abs(baselineB.position.y - baselineA.position.y);
    const measuredDistance = Math.abs(measuredB.position.y - measuredA.position.y);

    expect(measuredDistance).toBeGreaterThan(baselineDistance);
  });

  it('applies bounded de-overlap refinement for dense constraints', () => {
    const { nodes, edges } = makeSimpleChain();

    const result = applyHierarchicalLayout(nodes, edges, {
      direction: 'TB',
      nodeSpacing: 0,
      rankSpacing: 0,
      minClearance: 280,
      deOverlapPasses: 12,
    });

    const a = result.nodes.find((n) => n.id === 'a')!;
    const b = result.nodes.find((n) => n.id === 'b')!;

    const width = 200;
    const height = 80;

    const centerAX = a.position.x + width / 2;
    const centerAY = a.position.y + height / 2;
    const centerBX = b.position.x + width / 2;
    const centerBY = b.position.y + height / 2;

    const dx = Math.abs(centerBX - centerAX);
    const dy = Math.abs(centerBY - centerAY);

    const requiredX = (width + width) / 2 + 280;
    const requiredY = (height + height) / 2 + 280;

    // Must be separated on at least one axis by required clearance envelope.
    expect(dx >= requiredX || dy >= requiredY).toBe(true);
  });
});
