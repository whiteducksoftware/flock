/**
 * The Blackboard as a graph: every artifact a card, every edge from what a
 * run consumed to what it published an arrow (docs/internal/design-system/
 * README.md, Blackboard view). The same artifacts as the lanes.
 */

import { type Edge, MarkerType, type Node, type XYPosition } from '@xyflow/react';
import { applyHierarchicalLayout } from '../../services/layout';
import type { AutoLayoutMode } from '../../store/uiStore';
import type { DecisionInfo } from '../graph/DecisionDisplay';
import { type LaneCard, type RunningRun, awaitsReview, bundleDecisions } from './lanes';

export type ArtifactNodeData = { card: LaneCard };
export type ArtifactNode = Node<ArtifactNodeData, 'artifact'>;

interface ArtifactData {
  artifactType?: string;
  producedBy?: string;
  timestamp?: number;
  correlationId?: string | null;
  decision?: DecisionInfo;
  isStreaming?: boolean;
  runId?: string | null;
}

/**
 * The graph of the board's artifacts (message nodes and their transformation
 * edges), positions left to the caller. `reviewOnly` keeps the runs with an
 * unsure decision no one reviewed. A streaming card is not on the record yet:
 * an arrow in flight ties it to what its run consumed (`running`).
 */
export function graphOf(
  nodes: Node[],
  edges: Edge[],
  reviewOnly: boolean,
  running: RunningRun[] = [],
): { nodes: ArtifactNode[]; edges: Edge[] } {
  let artifacts = nodes.filter((node) => node.type === 'message');
  if (reviewOnly) {
    const runs = new Set(
      artifacts
        .filter((node) => awaitsReview((node.data as ArtifactData).decision))
        .map((node) => (node.data as ArtifactData).correlationId ?? ''),
    );
    artifacts = artifacts.filter((node) => runs.has((node.data as ArtifactData).correlationId ?? ''));
  }
  const byId = new Map(artifacts.map((node) => [node.id, node]));

  const cards: ArtifactNode[] = artifacts.map((node) => {
    const data = node.data as ArtifactData;
    return {
      id: node.id,
      type: 'artifact',
      position: node.position,
      data: {
        card: {
          id: node.id,
          type: data.artifactType ?? null,
          producedBy: data.producedBy ?? '',
          timestamp: data.timestamp ?? 0,
          data: node.data as Record<string, unknown>,
          state: data.isStreaming ? 'streaming' : 'done',
        },
      },
    };
  });

  // A decider's decisions about one artifact are one card, as in the lanes (#668); its arrows go to and from that card
  const inputs = new Map<string, string[]>();
  for (const edge of edges) inputs.set(edge.target, [...(inputs.get(edge.target) ?? []), edge.source]);
  const runs = new Map<string, ArtifactNode[]>();
  for (const node of cards) runs.set(runOf(node), [...(runs.get(runOf(node)) ?? []), node]);
  const bundleOf = new Map<string, string>();
  const shown: ArtifactNode[] = [];
  for (const members of runs.values()) {
    const byCard = new Map(members.map((node) => [node.id, node]));
    for (const card of bundleDecisions(
      members.map((node) => node.data.card),
      (id) => inputs.get(id) ?? [],
    )) {
      if (!card.decisions) {
        shown.push(byCard.get(card.id)!);
        continue;
      }
      for (const decision of card.decisions) bundleOf.set(decision.id, card.id);
      shown.push({ id: card.id, type: 'artifact', position: byCard.get(card.decisions[0]!.id)!.position, data: { card } });
    }
  }
  const at = (id: string) => bundleOf.get(id) ?? id;

  const seen = new Map<string, Edge>();
  const arrows: Edge[] = [];
  for (const edge of edges) {
    const source = byId.get(edge.source);
    const [from, to] = [at(edge.source), at(edge.target)];
    if (!source || !byId.has(edge.target) || from === to) continue;
    // As in the lanes: what follows an unsure answer has a dashed arrow, also when a bundle's arrows merge
    const unsure = (source.data as ArtifactData).decision?.choice === 'UNSURE';
    const merged = seen.get(`${from}->${to}`);
    if (merged) {
      if (unsure) merged.style = { ...merged.style, strokeDasharray: '5 4' };
      continue;
    }
    const arrow: Edge = {
      id: from === edge.source && to === edge.target ? edge.id : `${from}__${to}`,
      source: from,
      target: to,
      type: 'smoothstep',
      style: { stroke: 'var(--line-2)', strokeWidth: 1.5, ...(unsure && { strokeDasharray: '5 4' }) },
      markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--line-2)', width: 14, height: 14 },
    };
    seen.set(`${from}->${to}`, arrow);
    arrows.push(arrow);
  }
  for (const node of artifacts) {
    const data = node.data as ArtifactData;
    if (!data.isStreaming || !data.runId) continue;
    const run = running.find((each) => each.runId === data.runId);
    for (const source of [...new Set(run?.artifacts.filter((id) => byId.has(id)).map(at) ?? [])]) {
      arrows.push({
        id: `${source}__${node.id}__flight`,
        source,
        target: node.id,
        type: 'smoothstep',
        animated: true,
        style: { stroke: 'var(--signal)', strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--signal)', width: 14, height: 14 },
      });
    }
  }
  return { nodes: shown, edges: arrows };
}

type Size = { width: number; height: number };
type HierarchicalMode = 'hierarchical-horizontal' | 'hierarchical-vertical';

/** The run (correlation) of a card */
const runOf = (node: ArtifactNode) => (node.data.card.data as ArtifactData).correlationId ?? '';

/** The cards grouped by run, oldest run first (by its first card). */
function runsOf(nodes: ArtifactNode[]): ArtifactNode[][] {
  const runs = new Map<string, ArtifactNode[]>();
  for (const node of nodes) runs.set(runOf(node), [...(runs.get(runOf(node)) ?? []), node]);
  const first = (members: ArtifactNode[]) => Math.min(...members.map((node) => node.data.card.timestamp));
  return [...runs.values()].sort((a, b) => first(a) - first(b));
}

/** One run laid out on its own, at dagre's coordinates. */
function layoutRun(members: ArtifactNode[], edges: Edge[], mode: HierarchicalMode, sizes: Record<string, Size>) {
  const ids = new Set(members.map((node) => node.id));
  const inside = edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target));
  const { nodes: placed } = applyHierarchicalLayout(members as Node[], inside, {
    direction: mode === 'hierarchical-vertical' ? 'TB' : 'LR',
    dimensionsByNodeId: sizes,
    nodeSpacing: 40,
    rankSpacing: 90,
  });
  return new Map(placed.map((node) => [node.id, node.position]));
}

/** Where a run's cards are: their box. */
function boxOf(members: [string, XYPosition][], sizes: Record<string, Size>) {
  const size = (id: string) => sizes[id] ?? { width: 0, height: 0 };
  const left = Math.min(...members.map(([, at]) => at.x));
  const top = Math.min(...members.map(([, at]) => at.y));
  const right = Math.max(...members.map(([id, at]) => at.x + size(id).width));
  const bottom = Math.max(...members.map(([id, at]) => at.y + size(id).height));
  return { left, top, width: right - left, height: bottom - top };
}

/**
 * The slot of every run: as large as the largest run, so a run that grows
 * (down or across when top down, to the right when left to right) has room.
 */
function slotOf(boxes: { width: number; height: number }[]): Size {
  return {
    width: Math.max(0, ...boxes.map((box) => box.width)),
    height: Math.max(0, ...boxes.map((box) => box.height)),
  };
}

interface PackOptions {
  /** Where the first row starts */
  origin?: XYPosition;
  /** How far into the first row the first run goes */
  startX?: number;
  /** The slot of every run (`slotOf` the runs if not given) */
  slot?: Size;
  gap?: number;
}

/**
 * A hierarchical layout of many runs: each run (correlation) laid out on its
 * own, the runs in rows of at most `rowWidth`, oldest first, so new runs come
 * at the end. Every run takes a slot as large as the largest run, so a run that
 * grows has room and the runs line up. One layout of the whole board stacks
 * the runs in a column too tall to read. `newestRow`: the cards of the last
 * row, for the first view.
 */
export function packRuns(
  nodes: ArtifactNode[],
  edges: Edge[],
  mode: HierarchicalMode,
  sizes: Record<string, Size>,
  rowWidth: number,
  { origin = { x: 0, y: 0 }, startX = 0, slot, gap = 80 }: PackOptions = {},
): { positions: Map<string, XYPosition>; newestRow: string[] } {
  const blocks = runsOf(nodes).map((members) => {
    const placed = [...layoutRun(members, edges, mode, sizes).entries()];
    return { placed, box: boxOf(placed, sizes) };
  });
  const cell = slot ?? slotOf(blocks.map((block) => block.box));
  const positions = new Map<string, XYPosition>();
  let newestRow: string[] = [];
  let x = startX;
  let y = 0;
  let rowHeight = 0;
  for (const { placed, box } of blocks) {
    const width = Math.max(cell.width, box.width);
    // The next row once this one is full
    if (x > 0 && x + width > rowWidth) {
      x = 0;
      y += rowHeight + gap;
      rowHeight = 0;
      newestRow = [];
    }
    for (const [id, at] of placed) positions.set(id, { x: origin.x + at.x - box.left + x, y: origin.y + at.y - box.top + y });
    newestRow.push(...placed.map(([id]) => id));
    x += width + gap;
    rowHeight = Math.max(rowHeight, cell.height, box.height);
  }
  return { positions, newestRow };
}

const overlaps = (a: ReturnType<typeof boxOf>, b: ReturnType<typeof boxOf>) =>
  a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height;

/**
 * Places new cards and leaves the other runs where they are: a run that gets
 * a card is laid out again from where it starts, in its slot, or, when it
 * outgrew the slot and would cover a neighbour, moves to free room as new
 * runs do: the free slots after the last row's runs, then rows below
 * (`packRuns`).
 */
export function placeFresh(
  nodes: ArtifactNode[],
  edges: Edge[],
  fresh: Set<string>,
  mode: AutoLayoutMode,
  sizes: Record<string, Size>,
  rowWidth: number,
  gap = 80,
): Map<string, XYPosition> {
  const direction: HierarchicalMode = mode === 'hierarchical-vertical' ? 'hierarchical-vertical' : 'hierarchical-horizontal';
  const positions = new Map<string, XYPosition>();
  const runs = runsOf(nodes);
  // Where every run with placed cards is now
  const boxes = new Map<ArtifactNode[], ReturnType<typeof boxOf>>();
  for (const members of runs) {
    const placed = members.filter((node) => !fresh.has(node.id));
    if (placed.length > 0) boxes.set(members, boxOf(placed.map((node) => [node.id, node.position]), sizes));
  }
  const moving: ArtifactNode[] = [];
  for (const members of runs) {
    if (!members.some((node) => fresh.has(node.id))) continue;
    const corner = boxes.get(members);
    if (!corner) {
      moving.push(...members);
      continue;
    }
    // The run laid out again from where it starts (its decisions fan out under
    // its ticket: a layout around one placed card would reach the next run)
    const layout = [...layoutRun(members, edges, direction, sizes).entries()];
    const box = boxOf(layout, sizes);
    const placed = layout.map(([id, at]): [string, XYPosition] => [id, { x: corner.left + at.x - box.left, y: corner.top + at.y - box.top }]);
    const grown = boxOf(placed, sizes);
    if ([...boxes].some(([other, otherBox]) => other !== members && overlaps(grown, otherBox))) {
      // Outgrew its slot: to free room, all its cards
      boxes.delete(members);
      moving.push(...members);
      continue;
    }
    for (const [id, at] of placed) positions.set(id, at);
    // What it takes now counts for the runs placed after it
    boxes.set(members, grown);
  }
  if (moving.length === 0) return positions;
  const placedBoxes = [...boxes.values()];
  if (placedBoxes.length === 0) {
    for (const [id, at] of packRuns(moving, edges, direction, sizes, rowWidth, { gap }).positions) positions.set(id, at);
    return positions;
  }
  // The slots of the placed runs; the last row's free slots first
  const slot = slotOf(placedBoxes);
  const left = Math.min(...placedBoxes.map((box) => box.left));
  const rowTop = Math.max(...placedBoxes.map((box) => box.top));
  const lastRow = placedBoxes.filter((box) => box.top === rowTop);
  const next = Math.max(...lastRow.map((box) => box.left + Math.max(slot.width, box.width))) + gap - left;
  const rowHeight = Math.max(slot.height, ...lastRow.map((box) => box.height));
  // A run that moves for room is larger than the slot: the slot grows with it
  const moved = runsOf(moving).map((members) => boxOf([...layoutRun(members, edges, direction, sizes).entries()], sizes));
  const cell = slotOf([slot, ...moved]);
  const room = next + cell.width <= rowWidth;
  let packed = packRuns(
    moving,
    edges,
    direction,
    sizes,
    rowWidth,
    room
      ? { origin: { x: left, y: rowTop }, startX: next, slot: cell, gap }
      : { origin: { x: left, y: rowTop + rowHeight + gap }, slot: cell, gap },
  ).positions;
  // The last row's free slots are free only in rows: in a grid or a circle a
  // taller card may reach into them. Anything in the way: below every card
  const clear = runsOf(moving).every((members) => {
    const box = boxOf(members.map((node) => [node.id, packed.get(node.id)!]), sizes);
    return placedBoxes.every((other) => !overlaps(box, other));
  });
  if (!clear) {
    const bottom = Math.max(...placedBoxes.map((box) => box.top + box.height));
    packed = packRuns(moving, edges, direction, sizes, rowWidth, { origin: { x: left, y: bottom + gap }, slot: cell, gap }).positions;
  }
  for (const [id, at] of packed) positions.set(id, at);
  return positions;
}

/** How to place a snapshot's cards: all of them, or only the new ones around the placed. */
export function placementOf({
  autoArrange,
  firstLoad,
  fresh,
}: {
  autoArrange: boolean;
  /** Nothing is on the board yet */
  firstLoad: boolean;
  fresh: Set<string>;
}): 'all' | Set<string> {
  return autoArrange || firstLoad ? 'all' : fresh;
}

/** The cards that new edges between cards on the board reach (an edge drawn once its run finished). */
export function newEdgeTargets(known: Set<string>, edges: Edge[], cards: Set<string>): Set<string> {
  return new Set(
    edges.filter((edge) => !known.has(edge.id) && cards.has(edge.source) && cards.has(edge.target)).map((edge) => edge.target),
  );
}
