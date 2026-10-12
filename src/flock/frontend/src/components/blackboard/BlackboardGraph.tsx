/**
 * The Blackboard as a graph (#614): the artifacts of the board as cards on a
 * canvas, arrows from what a run consumed to what it published. A click
 * unfolds a card in place, as in the lanes. The canvas dock lays it out.
 * Without auto-arrange (the default) placed cards stay where they are: new
 * ones join their run, new runs take the next free slot. Moved cards stay
 * while the view is open; a new visit lays the board out afresh (its window
 * of artifacts and its slots differ, so saved places would scatter a run).
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Background,
  Handle,
  type NodeChange,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type XYPosition,
  applyNodeChanges,
  useNodesInitialized,
  useReactFlow,
} from '@xyflow/react';
import { applyCircularLayout, applyGridLayout, applyRandomLayout } from '../../services/layout';
import { useFilterStore } from '../../store/filterStore';
import { blackboardFilterKey, useGraphStore } from '../../store/graphStore';
import { type AutoLayoutMode, useUIStore } from '../../store/uiStore';
import { motionMs } from '../graph/animatePositions';
import CanvasDock from '../graph/CanvasDock';
import { registerCanvas } from '../graph/canvasCommands';
import { useDockViewport } from '../graph/useDockViewport';
import MiniMap from '../graph/MiniMap';
import ArtifactCard from './ArtifactCard';
import { type ArtifactNode, graphOf, newEdgeTargets, packRuns, placeFresh, placementOf } from './graph';
import styles from './Blackboard.module.css';

/** A card's size before it is measured (a folded card is 236 px wide) */
const ESTIMATE = { width: 236, height: 120 };

/** The margin around what a view shows, in pixels */
const EDGE = 24;

/** The smallest zoom at which a whole board is still read: smaller, the first view shows the newest row */
const READABLE_ZOOM = 0.6;

/** At this zoom the first row of runs fills the board's width */
const FIRST_ROW_ZOOM = 0.75;

/** The board's smallest zoom */
const MIN_ZOOM = 0.1;

/** Every card's size: measured, else the estimate. */
const sizesOf = (nodes: ArtifactNode[]) =>
  Object.fromEntries(
    nodes.map((node) => [
      node.id,
      { width: node.measured?.width ?? ESTIMATE.width, height: node.measured?.height ?? ESTIMATE.height },
    ]),
  );

/**
 * Positions of every card in a layout mode, from their measured sizes. The
 * hierarchical modes lay each run out on its own and set the runs in rows,
 * oldest first (`packRuns`); `newestRow` holds the last row's cards.
 */
function layoutOf(
  mode: AutoLayoutMode,
  nodes: ArtifactNode[],
  edges: Parameters<typeof applyGridLayout>[1],
  rowWidth: number,
): { positions: Map<string, XYPosition>; newestRow: string[] } {
  const dimensionsByNodeId = sizesOf(nodes);
  if (mode === 'hierarchical-horizontal' || mode === 'hierarchical-vertical') {
    return packRuns(nodes, edges, mode, dimensionsByNodeId, rowWidth);
  }
  const options = { dimensionsByNodeId, center: { x: 0, y: 0 } };
  const result =
    mode === 'circular'
      ? applyCircularLayout(nodes, edges, options)
      : mode === 'grid'
        ? applyGridLayout(nodes, edges, options)
        : applyRandomLayout(nodes, edges, options);
  return { positions: new Map(result.nodes.map((node) => [node.id, node.position])), newestRow: [] };
}

/** An artifact card on the canvas; a drag does not unfold it. */
const ArtifactGraphNode: React.FC<NodeProps<ArtifactNode>> = ({ data, sourcePosition, targetPosition }) => {
  const unfolded = useUIStore((state) => state.unfoldedArtifactId === data.card.id);
  const down = useRef<{ x: number; y: number } | null>(null);
  return (
    // An unfolded card scrolls and selects its text instead of moving the board
    <div
      className={unfolded ? 'nodrag nowheel' : undefined}
      onPointerDownCapture={(event) => {
        down.current = { x: event.clientX, y: event.clientY };
      }}
      onClickCapture={(event) => {
        const from = down.current;
        down.current = null;
        // A keyboard click (Enter, Space on a button) has no pointer behind it
        if (!from || event.detail === 0) return;
        if (Math.hypot(event.clientX - from.x, event.clientY - from.y) > 4) event.stopPropagation();
      }}
    >
      <Handle type="target" position={targetPosition ?? Position.Left} isConnectable={false} className={styles.handle} />
      <ArtifactCard card={data.card} />
      <Handle type="source" position={sourcePosition ?? Position.Right} isConnectable={false} className={styles.handle} />
    </div>
  );
};

const nodeTypes = { artifact: ArtifactGraphNode };

const Canvas: React.FC = () => {
  const storeNodes = useGraphStore((state) => state.nodes);
  const storeEdges = useGraphStore((state) => state.edges);
  const inFlight = useGraphStore((state) => state.inFlight);
  const settling = useGraphStore((state) => state.settling);
  const viewMode = useGraphStore((state) => state.viewMode);
  const loading = useGraphStore((state) => state.isLoading);
  const reviewOnly = useUIStore((state) => state.needsReviewOnly);
  const unfoldedId = useUIStore((state) => state.unfoldedArtifactId);
  const layoutMode = useUIStore((state) => state.graphLayout);
  const autoArrange = useUIStore((state) => state.graphAutoArrange);
  const dockOpen = useUIStore((state) => state.dockOpen);
  // With the timeline dock expanded the board is a strip: the cards in view fit
  // into it (all 500 would be specks), and the view comes back on collapse. Opened
  // with the dock expanded, the graph's first view is its own
  const board = useRef<HTMLDivElement>(null);
  const { getNodes, getViewport: viewportNow } = useReactFlow();
  const forgetDockView = useDockViewport(dockOpen, (pane) => {
    const { x, y, zoom } = viewportNow();
    return getNodes()
      .filter((node) => {
        const left = node.position.x * zoom + x;
        const top = node.position.y * zoom + y;
        const right = left + (node.measured?.width ?? ESTIMATE.width) * zoom;
        const bottom = top + (node.measured?.height ?? ESTIMATE.height) * zoom;
        return right > 0 && left < pane.width && bottom > 0 && top < pane.height;
      })
      .map((node) => node.id);
  }, { fitOnMount: false });
  const { fitView, zoomIn, zoomOut, getViewport, setViewport, setCenter, getNode } = useReactFlow();
  const initialized = useNodesInitialized();

  // Until the Blackboard's snapshot is in, the store holds the Flow's
  const graph = useMemo(
    () =>
      viewMode === 'blackboard'
        ? graphOf(
            storeNodes,
            storeEdges,
            reviewOnly,
            // Runs that ended keep their placeholders until their output is on the board (#642)
            [...inFlight.entries(), ...settling.entries()].map(([runId, run]) => ({
              runId,
              agent: run.agent,
              correlationId: run.correlationId ?? null,
              artifacts: run.artifacts,
              types: run.types,
              produces: run.produces,
            })),
          )
        : { nodes: [], edges: [] },
    [viewMode, storeNodes, storeEdges, reviewOnly, inFlight, settling],
  );

  const [nodes, setNodes] = useState<ArtifactNode[]>([]);
  const [viewTick, setViewTick] = useState(0);
  // A layout to run again once the new cards are measured: all cards, or the new ones
  const pending = useRef<'all' | Set<string> | null>(null);
  const fitted = useRef(false);

  // The newest row of runs, which the first view shows
  const newestRow = useRef<string[]>([]);

  /**
   * Lays out the cards: all of them (`'all'`), or only the new ones, around
   * the placed cards, which stay where they are.
   */
  const arrange = useCallback(
    (which: 'all' | Set<string>, mode: AutoLayoutMode, current: ArtifactNode[]) => {
      // A row of runs fills the board's width at FIRST_ROW_ZOOM
      const rowWidth = Math.max(800, (board.current?.clientWidth ?? 1200) / FIRST_ROW_ZOOM);
      const positions =
        which === 'all'
          ? (() => {
              const layout = layoutOf(mode, current, graph.edges, rowWidth);
              newestRow.current = layout.newestRow;
              return layout.positions;
            })()
          : placeFresh(current, graph.edges, which, mode, sizesOf(current), rowWidth);
      return current.map((node) => {
        const position = positions.get(node.id);
        return position ? { ...node, position } : node;
      });
    },
    [graph.edges],
  );

  // The edges the board has seen: one drawn later (once its run finished) lays its run out again
  const knownEdges = useRef<Set<string> | null>(null);

  // The snapshot's cards: kept ones keep their place and size, new ones get a place
  useEffect(() => {
    setNodes((previous) => {
      const before = new Map(previous.map((node) => [node.id, node]));
      const fresh = new Set<string>();
      const next = graph.nodes.map((node) => {
        const kept = before.get(node.id);
        if (kept) return { ...kept, data: node.data };
        fresh.add(node.id);
        return node;
      });
      const firstLoad = previous.length === 0;
      if (knownEdges.current && !firstLoad) {
        const placed = new Set(previous.map((node) => node.id));
        for (const id of newEdgeTargets(knownEdges.current, graph.edges, placed)) fresh.add(id);
      }
      knownEdges.current = new Set(graph.edges.map((edge) => edge.id));
      if (fresh.size === 0) return next;
      // Auto-arrange lays out the whole board, else only the new cards (a first visit all
      // of them). Until the first view is shown, all of them too: a card that streams can
      // come before the snapshot, whose cards would else only be added below it
      const which = placementOf({ autoArrange, firstLoad: firstLoad || !fitted.current, fresh });
      pending.current = which;
      return arrange(which, layoutMode, next);
    });
  }, [graph.nodes, graph.edges, autoArrange, layoutMode, arrange]);

  // Once the new cards have their size, the layout runs again with it
  // (firstView: the first view is due)
  const firstView = useRef(false);
  useEffect(() => {
    if (!initialized || !pending.current) return;
    const which = pending.current;
    pending.current = null;
    setNodes((current) => {
      const next = arrange(which, layoutMode, current);
      if (!fitted.current) firstView.current = true;
      return next;
    });
  }, [initialized, arrange, layoutMode]);

  // The first view: the whole board if it reads at READABLE_ZOOM, else the newest row
  // of runs at the top, readable; Fit shows them all.
  // From the positions just set, which React Flow may not have yet. It waits until the
  // board holds the snapshot's cards (a render after it arrives), laid out with their
  // size: a layout chosen while the board loads, or a card that streams before the
  // snapshot, would else be shown instead of the board
  useEffect(() => {
    if (!firstView.current || fitted.current || loading || pending.current) return;
    const synced = nodes.length === graph.nodes.length && graph.nodes.every((node, index) => nodes[index]?.id === node.id);
    if (nodes.length === 0 || !synced) return;
    firstView.current = false;
    fitted.current = true;
    const laid = nodes;
    const width = board.current?.clientWidth ?? 0;
    const height = board.current?.clientHeight ?? 0;
    // A board that fits at a readable zoom shows whole (a filtered one, a small one)
    const rightOf = (node: ArtifactNode) => node.position.x + (node.measured?.width ?? ESTIMATE.width);
    const bottomOf = (node: ArtifactNode) => node.position.y + (node.measured?.height ?? ESTIMATE.height);
    const whole = laid.length > 0 && {
      left: Math.min(...laid.map((node) => node.position.x)),
      top: Math.min(...laid.map((node) => node.position.y)),
      right: Math.max(...laid.map(rightOf)),
      bottom: Math.max(...laid.map(bottomOf)),
    };
    const wholeZoom =
      whole && width > 0 && height > 0
        ? Math.min(1, (width - 2 * EDGE) / (whole.right - whole.left), (height - 2 * EDGE) / (whole.bottom - whole.top))
        : null;
    if (whole && wholeZoom !== null && wholeZoom >= READABLE_ZOOM) {
      void setViewport({ x: EDGE - whole.left * wholeZoom, y: EDGE - whole.top * wholeZoom, zoom: wholeZoom });
      return;
    }
    const ids = new Set(newestRow.current);
    const row = laid.filter((node) => ids.has(node.id));
    if (row.length === 0 || width === 0) {
      // No rows (a grid, a circle, random places): the whole board if it fits at the
      // smallest zoom, else as much as that shows around the newest card (a circle of
      // hundreds of cards is empty in its middle, where a fit would look)
      const newest = laid.reduce<ArtifactNode | null>(
        (last, node) => (!last || node.data.card.timestamp > last.data.card.timestamp ? node : last),
        null,
      );
      if (newest && wholeZoom !== null && wholeZoom < MIN_ZOOM) {
        void setCenter(
          newest.position.x + (newest.measured?.width ?? ESTIMATE.width) / 2,
          newest.position.y + (newest.measured?.height ?? ESTIMATE.height) / 2,
          { zoom: MIN_ZOOM },
        );
        return;
      }
      requestAnimationFrame(() => void fitView({ padding: 0.08, maxZoom: 1 }));
      return;
    }
    const left = Math.min(...row.map((node) => node.position.x));
    const top = Math.min(...row.map((node) => node.position.y));
    const right = Math.max(...row.map((node) => node.position.x + (node.measured?.width ?? ESTIMATE.width)));
    const zoom = Math.min(1, (width - 2 * EDGE) / Math.max(1, right - left));
    void setViewport({ x: EDGE - left * zoom, y: EDGE - top * zoom, zoom });
  }, [nodes, graph.nodes, viewTick, loading, fitView, setViewport, setCenter]);

  // A change of what the board shows (its filters, Needs review only) lays it out
  // afresh and shows its newest row, as a first visit does, once the result is in:
  // the snapshot that answers the new filters (whatever answers arrive in between),
  // at once for the review filter, which the graph applies itself. The cards kept
  // their places from the full board, too far apart to fit. Live updates keep the
  // layout and the view
  const answered = useGraphStore((state) => state.blackboardFilters);
  const asked = useFilterStore(() => blackboardFilterKey());
  // The filters the layout was made for (null: none yet, the first load lays out)
  const laidOutFor = useRef<string | null>(null);
  const viewAfterDock = useRef(false);
  useEffect(() => {
    if (dockOpen || !viewAfterDock.current) return;
    viewAfterDock.current = false;
    fitted.current = false;
    firstView.current = true;
    setViewTick((tick) => tick + 1);
  }, [dockOpen]);
  const reviewShown = useRef(reviewOnly);
  useEffect(() => {
    if (!initialized || pending.current || answered === null) return;
    // The board holds the snapshot's cards (they are set a render after it arrives)
    const synced = nodes.length === graph.nodes.length && graph.nodes.every((node, index) => nodes[index]?.id === node.id);
    if (!synced) return;
    if (laidOutFor.current === null) {
      laidOutFor.current = answered;
      reviewShown.current = reviewOnly;
      return;
    }
    const newFilters = answered === asked && answered !== laidOutFor.current;
    const newReview = reviewShown.current !== reviewOnly;
    if (!newFilters && !newReview) return;
    laidOutFor.current = answered;
    reviewShown.current = reviewOnly;
    forgetDockView();
    // Laid out in the dock's strip: the first view comes again for the full board
    viewAfterDock.current = useUIStore.getState().dockOpen;
    fitted.current = false;
    firstView.current = true;
    setNodes((current) => arrange('all', layoutMode, current));
  }, [nodes, graph.nodes, initialized, answered, asked, reviewOnly, arrange, layoutMode]);

  // The graph shows artifacts; it removes none (only the snapshot does)
  const onNodesChange = useCallback((changes: NodeChange<ArtifactNode>[]) => {
    setNodes((current) => applyNodeChanges(changes.filter((change) => change.type !== 'remove'), current));
  }, []);

  // A layout chosen in the canvas dock or the palette: the cards move, so the first
  // view comes again (a grid or a circle centers on the origin, far from the newest row),
  // and once more for the full board after the dock's strip
  const layout = useCallback(
    (mode: AutoLayoutMode) => {
      useUIStore.getState().setGraphLayout(mode);
      forgetDockView();
      viewAfterDock.current = useUIStore.getState().dockOpen;
      fitted.current = false;
      firstView.current = true;
      setNodes((current) => arrange('all', mode, current));
    },
    [arrange, forgetDockView],
  );

  // The palette's canvas commands on this board
  const layoutRef = useRef(layout);
  layoutRef.current = layout;
  useEffect(
    () =>
      registerCanvas({
        kind: 'graph',
        zoomIn: () => void zoomIn({ duration: motionMs(200) }),
        zoomOut: () => void zoomOut({ duration: motionMs(200) }),
        fit: () => void fitView({ padding: 0.1, duration: motionMs(300) }),
        layout: (mode) => layoutRef.current(mode),
        show: (nodeId) => {
          const node = getNode(nodeId);
          if (!node) return;
          const width = node.measured?.width ?? ESTIMATE.width;
          const height = node.measured?.height ?? ESTIMATE.height;
          void setCenter(node.position.x + width / 2, node.position.y + height / 2, {
            zoom: getViewport().zoom,
            duration: motionMs(300),
          });
        },
      }),
    // The React Flow functions are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // An unfolded card moves into view, as little as it takes (once it has its size)
  useEffect(() => {
    if (!unfoldedId) return;
    const frame = requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        const node = getNode(unfoldedId);
        const pane = board.current;
        if (!node || !pane) return;
        const { x, y, zoom } = getViewport();
        const shift = (start: number, size: number, room: number) => {
          const from = start * zoom;
          const to = from + size * zoom;
          if (to - from > room - 2 * EDGE || from < EDGE) return EDGE - from;
          if (to > room - EDGE) return room - EDGE - to;
          return 0;
        };
        const dx = shift(node.position.x + x / zoom, node.measured?.width ?? 0, pane.clientWidth);
        const dy = shift(node.position.y + y / zoom, node.measured?.height ?? 0, pane.clientHeight);
        if (dx || dy) void setViewport({ x: x + dx, y: y + dy, zoom }, { duration: motionMs(200) });
      }),
    );
    return () => cancelAnimationFrame(frame);
  }, [unfoldedId, getNode, getViewport, setViewport]);

  // Arrows run the way the layout does: down when top down, else to the right;
  // the unfolded card above its neighbours
  const down = layoutMode === 'hierarchical-vertical';
  const shown = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        sourcePosition: down ? Position.Bottom : Position.Right,
        targetPosition: down ? Position.Top : Position.Left,
        zIndex: node.id === unfoldedId ? 1000 : 0,
      })),
    [nodes, unfoldedId, down],
  );

  return (
    <div ref={board} className={styles.graph}>
      <ReactFlow
        nodes={shown}
        edges={graph.edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        nodesConnectable={false}
        // Backspace would remove a card from the view, not from the blackboard
        deleteKeyCode={null}
        minZoom={MIN_ZOOM}
        style={{ backgroundColor: 'var(--board)' }}
      >
        <Background color="var(--dot)" bgColor="var(--board)" gap={22} size={1.3} />
        {!dockOpen && <MiniMap />}
      </ReactFlow>
      {!dockOpen && (
        <CanvasDock
          layout={layoutMode}
          autoArrange={autoArrange}
          onLayout={layout}
          onAutoArrange={(on) => useUIStore.getState().setGraphAutoArrange(on)}
        />
      )}
    </div>
  );
};

const BlackboardGraph: React.FC = () => (
  <ReactFlowProvider>
    <Canvas />
  </ReactFlowProvider>
);

export default BlackboardGraph;
