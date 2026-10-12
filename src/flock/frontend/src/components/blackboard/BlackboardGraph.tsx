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
import { useGraphStore } from '../../store/graphStore';
import { type AutoLayoutMode, useUIStore } from '../../store/uiStore';
import { motionMs } from '../graph/animatePositions';
import CanvasDock from '../graph/CanvasDock';
import { registerCanvas } from '../graph/canvasCommands';
import MiniMap from '../graph/MiniMap';
import ArtifactCard from './ArtifactCard';
import { type ArtifactNode, graphOf, newEdgeTargets, packRuns, placeFresh, placementOf } from './graph';
import styles from './Blackboard.module.css';

/** A card's size before it is measured (a folded card is 236 px wide) */
const ESTIMATE = { width: 236, height: 120 };

/** The margin around what a view shows, in pixels */
const EDGE = 24;

/** At this zoom the first row of runs fills the board's width */
const FIRST_ROW_ZOOM = 0.75;

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
        if (from && Math.hypot(event.clientX - from.x, event.clientY - from.y) > 4) event.stopPropagation();
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
  const viewMode = useGraphStore((state) => state.viewMode);
  const reviewOnly = useUIStore((state) => state.needsReviewOnly);
  const unfoldedId = useUIStore((state) => state.unfoldedArtifactId);
  const layoutMode = useUIStore((state) => state.graphLayout);
  const autoArrange = useUIStore((state) => state.graphAutoArrange);
  const dockOpen = useUIStore((state) => state.dockOpen);
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
            [...inFlight.entries()].map(([runId, run]) => ({ runId, agent: run.agent, correlationId: run.correlationId ?? null, artifacts: run.artifacts })),
          )
        : { nodes: [], edges: [] },
    [viewMode, storeNodes, storeEdges, reviewOnly, inFlight],
  );

  const [nodes, setNodes] = useState<ArtifactNode[]>([]);
  // A layout to run again once the new cards are measured: all cards, or the new ones
  const pending = useRef<'all' | Set<string> | null>(null);
  const fitted = useRef(false);

  const board = useRef<HTMLDivElement>(null);
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
      // Auto-arrange lays out the whole board, else only the new cards (a first visit all of them)
      const which = placementOf({ autoArrange, firstLoad, fresh });
      pending.current = which;
      return arrange(which, layoutMode, next);
    });
  }, [graph.nodes, graph.edges, autoArrange, layoutMode, arrange]);

  // Once the new cards have their size, the layout runs again with it
  const firstView = useRef<ArtifactNode[] | null>(null);
  useEffect(() => {
    if (!initialized || !pending.current) return;
    const which = pending.current;
    pending.current = null;
    setNodes((current) => {
      const next = arrange(which, layoutMode, current);
      if (!fitted.current) firstView.current = next;
      return next;
    });
  }, [initialized, arrange, layoutMode]);

  // The first view: the newest row of runs at the top, readable; Fit shows them all.
  // From the positions just set, which React Flow may not have yet
  useEffect(() => {
    const laid = firstView.current;
    if (!laid || fitted.current) return;
    firstView.current = null;
    fitted.current = true;
    const ids = new Set(newestRow.current);
    const row = laid.filter((node) => ids.has(node.id));
    const width = board.current?.clientWidth ?? 0;
    if (row.length === 0 || width === 0) {
      requestAnimationFrame(() => void fitView({ padding: 0.08, maxZoom: 1 }));
      return;
    }
    const left = Math.min(...row.map((node) => node.position.x));
    const top = Math.min(...row.map((node) => node.position.y));
    const right = Math.max(...row.map((node) => node.position.x + (node.measured?.width ?? ESTIMATE.width)));
    const zoom = Math.min(1, (width - 2 * EDGE) / Math.max(1, right - left));
    void setViewport({ x: EDGE - left * zoom, y: EDGE - top * zoom, zoom });
  }, [nodes, fitView, setViewport]);

  // A change of what the board shows (its filters, Needs review only) lays it out
  // afresh and shows its newest row, as a first visit does, once the result is in:
  // the snapshot for new filters, at once for the review filter, which the graph
  // applies itself. The cards kept their places from the full board, too far apart
  // to fit. Live updates keep the layout and the view
  const loading = useGraphStore((state) => state.isLoading);
  const filterKey = useFilterStore((state) =>
    JSON.stringify([
      state.correlationId,
      state.selectedArtifactTypes,
      state.selectedProducers,
      state.selectedTags,
      state.selectedVisibility,
      state.timeRange,
    ]),
  );
  const refit = useRef<'snapshot' | 'local' | null>(null);
  const snapshotLoaded = useRef(false);
  const showing = useRef({ filterKey, reviewOnly });
  useEffect(() => {
    if (showing.current.filterKey !== filterKey) {
      refit.current = 'snapshot';
      snapshotLoaded.current = false;
    } else if (showing.current.reviewOnly !== reviewOnly) {
      refit.current = 'local';
    }
    showing.current = { filterKey, reviewOnly };
  }, [filterKey, reviewOnly]);
  useEffect(() => {
    if (refit.current === 'snapshot' && loading) snapshotLoaded.current = true;
  }, [loading]);
  useEffect(() => {
    if (!refit.current || !initialized || pending.current) return;
    if (refit.current === 'snapshot' && (!snapshotLoaded.current || loading)) return;
    refit.current = null;
    fitted.current = false;
    setNodes((current) => {
      const next = arrange('all', layoutMode, current);
      firstView.current = next;
      return next;
    });
  }, [nodes, initialized, loading, arrange, layoutMode]);

  // The graph shows artifacts; it removes none (only the snapshot does)
  const onNodesChange = useCallback((changes: NodeChange<ArtifactNode>[]) => {
    setNodes((current) => applyNodeChanges(changes.filter((change) => change.type !== 'remove'), current));
  }, []);

  const layout = useCallback(
    (mode: AutoLayoutMode) => {
      useUIStore.getState().setGraphLayout(mode);
      setNodes((current) => arrange('all', mode, current));
    },
    [arrange],
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
        minZoom={0.1}
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
