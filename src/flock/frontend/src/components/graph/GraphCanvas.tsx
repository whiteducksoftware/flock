import { useCallback, useMemo, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  NodeChange,
  EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import AgentNode, { openTrace } from './AgentNode';
import { useDockViewport } from './useDockViewport';
import CanvasDock from './CanvasDock';
import FocusStage from './focus/FocusStage';
import MessageFlowEdge from './MessageFlowEdge';
import PendingJoinEdge from './PendingJoinEdge';
import PendingBatchEdge from './PendingBatchEdge';
import MiniMap from './MiniMap';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore, type AutoLayoutMode } from '../../store/uiStore';
import { useSettingsStore } from '../../store/settingsStore';
import {
  applyHierarchicalLayout,
  applyCircularLayout,
  applyGridLayout,
  applyRandomLayout
} from '../../services/layout';
import { usePersistence } from '../../hooks/usePersistence';
import {
  clearDebouncedAutoLayout,
  getEdgeIdSet,
  getNodeIdSet,
  hasNewEdgeAdditions,
  hasNewNodeAdditions,
  scheduleDebouncedAutoLayout,
  cardsResized,
  RESIZE_LAYOUT_DELAY_MS,
} from './autoLayoutTrigger';
import { motionMs } from './animatePositions';
import { revealGlide, revealViewport } from './reveal';
import { SETTLE_MS, asNewest, registerCanvas, whenOnBoard } from './canvasCommands';
import { cardSizes } from './cardSizes';
import { fromControl } from './nodeClick';
import { useUnfoldLayout } from './useUnfoldLayout';
import { useLayoutGlide } from './useLayoutGlide';
import { afterGlide, movedByHand } from './glideNodes';

const GraphCanvas: React.FC = () => {
  const {
    getIntersectingNodes,
    screenToFlowPosition,
    getViewport,
    setViewport,
    zoomIn,
    zoomOut,
    fitView,
    setCenter,
    getNode,
  } = useReactFlow();

  const mode = useUIStore((state) => state.mode);
  // With the timeline dock expanded the board is a strip of chips: no dock or minimap on it
  const dockOpen = useUIStore((state) => state.dockOpen);
  useDockViewport(dockOpen);
  const autoLayoutEnabled = useUIStore((state) => state.autoLayoutEnabled);
  const setAutoLayoutEnabled = useUIStore((state) => state.setAutoLayoutEnabled);
  const autoLayoutMode = useUIStore((state) => state.autoLayoutMode);
  const setAutoLayoutMode = useUIStore((state) => state.setAutoLayoutMode);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const generateAgentViewGraph = useGraphStore((state) => state.generateAgentViewGraph);
  const updateNodePosition = useGraphStore((state) => state.updateNodePosition);
  const persistNodePosition = useGraphStore((state) => state.saveNodePosition);

  // Graph settings from settings store
  const edgeType = useSettingsStore((state) => state.graph.edgeType);
  const edgeStrokeWidth = useSettingsStore((state) => state.graph.edgeStrokeWidth);
  const edgeAnimation = useSettingsStore((state) => state.graph.edgeAnimation);
  const nodeSpacing = useSettingsStore((state) => state.advanced.nodeSpacing);
  const rankSpacing = useSettingsStore((state) => state.advanced.rankSpacing);


  const autoLayoutDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousNodeIdsRef = useRef<Set<string> | null>(null);
  const previousEdgeIdsRef = useRef<Set<string> | null>(null);
  const previousModeRef = useRef(mode);
  const latestAutoLayoutModeRef = useRef(autoLayoutMode);
  // A layout that came due while a node is unfolded; folding runs it
  const layoutDueRef = useRef(false);

  // Persistence hook - loads positions on mount and handles debounced drag saves
  const { saveNodePosition: saveNodePositionDebounced } = usePersistence();

  // Memoize node types to prevent re-creation
  const nodeTypes = useMemo(
    () => ({
      agent: AgentNode,
    }),
    []
  );

  // Memoize edge types to prevent re-creation
  const edgeTypes = useMemo(
    () => ({
      message_flow: MessageFlowEdge,
      pending_join: PendingJoinEdge,  // Phase 1.5: Pending edges for JoinSpec correlation groups
      pending_batch: PendingBatchEdge, // Phase 1.5: Pending edges for BatchSpec accumulation
    }),
    []
  );

  // The board's data loads in useBoardData; new edge settings redraw the graph
  // (not on mount: the board loads it then). generateAgentViewGraph is a stable
  // zustand function; as a dependency it would loop on every node update.
  const edgeSettingsSeen = useRef(false);
  useEffect(() => {
    if (!edgeSettingsSeen.current) {
      edgeSettingsSeen.current = true;
      return;
    }
    // A failed load is the store's error, which the board shows
    generateAgentViewGraph().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edgeType, edgeStrokeWidth, edgeAnimation]);

  // The cards' sizes the last layout used: one that grows off them lays the board out again (#655)
  const laidOutRef = useRef<Record<string, { width: number; height: number }> | null>(null);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const updatedNodes = applyNodeChanges(changes, nodes);
      useGraphStore.setState({ nodes: updatedNodes });

      // With Auto-arrange on, a card that changed its size lays the board out again, centred, and
      // the nodes glide there (#655); an unfolded agent keeps its card's size and does not count
      if (
        autoLayoutEnabled &&
        changes.some((change) => change.type === 'dimensions') &&
        !useUIStore.getState().unfoldedNodeId &&
        cardsResized(laidOutRef.current, cardSizes)
      ) {
        scheduleDebouncedAutoLayout(
          autoLayoutDebounceRef,
          () => {
            if (useUIStore.getState().unfoldedNodeId) return;
            applyLayoutRef.current(latestAutoLayoutModeRef.current, { updateStoredMode: false });
          },
          RESIZE_LAYOUT_DELAY_MS,
        );
      }

      // Update position in store for persistence; a glide going on leaves the node to the hand that moves it
      changes.forEach((change) => {
        if (change.type === 'position' && change.position) {
          movedByHand(change.id);
          updateNodePosition(change.id, change.position);
        }
      });
    },
    [nodes, updateNodePosition, autoLayoutEnabled]
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const updatedEdges = applyEdgeChanges(changes, edges);
      useGraphStore.setState({ edges: updatedEdges });
    },
    [edges]
  );

  const collectRenderedNodeDimensions = useCallback(() => {
    const dimensionsByNodeId: Record<string, { width: number; height: number }> = {};
    const renderedNodes = document.querySelectorAll<HTMLElement>('.react-flow__node[data-id]');

    renderedNodes.forEach((element) => {
      const nodeId = element.getAttribute('data-id');
      if (!nodeId) {
        return;
      }

      // An agent's card, also while it shows as a chip (the dock expanded, zoomed out):
      // a layout from chip sizes overlaps once the cards are back
      const card = cardSizes.get(nodeId);
      const width = card?.width ?? element.offsetWidth;
      const height = card?.height ?? element.offsetHeight;
      if (width > 0 && height > 0) {
        dimensionsByNodeId[nodeId] = { width, height };
      }
    });

    return dimensionsByNodeId;
  }, []);

  // A new layout glides there; declared before useUnfoldLayout, so an unfold
  // finishes the glide before it makes room
  const glideTo = useLayoutGlide();

  // Generic layout handler (manual + auto-layout)
  const applyLayout = useCallback(
    (
      layoutType: AutoLayoutMode,
      options?: {
        // When true, persist selected layout as the user's preferred auto-layout mode.
        updateStoredMode?: boolean;
      }
    ) => {
      const { updateStoredMode = true } = options || {};

      if (updateStoredMode) {
        setAutoLayoutMode(layoutType);
      }

      // A node is unfolded: fold it, and the fold lays the board out in this mode
      if (useUIStore.getState().unfoldedNodeId) {
        latestAutoLayoutModeRef.current = layoutType;
        layoutDueRef.current = true;
        useUIStore.getState().fold();
        return;
      }

      // Get the React Flow pane element to find its actual center
      const pane = document.querySelector('.react-flow__pane');
      let viewportCenter = { x: 0, y: 0 };

      if (pane) {
        const rect = pane.getBoundingClientRect();
        // Convert screen center of the pane to flow coordinates
        viewportCenter = screenToFlowPosition({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        });
      }

      const dimensionsByNodeId = collectRenderedNodeDimensions();
      laidOutRef.current = dimensionsByNodeId;
      const hierarchicalBaseOptions = {
        center: viewportCenter,
        nodeSpacing,
        rankSpacing,
        dimensionsByNodeId,
      };

      let result;
      switch (layoutType) {
        case 'hierarchical-vertical':
          result = applyHierarchicalLayout(nodes, edges, {
            ...hierarchicalBaseOptions,
            direction: 'TB',
          });
          break;
        case 'hierarchical-horizontal':
          result = applyHierarchicalLayout(nodes, edges, {
            ...hierarchicalBaseOptions,
            direction: 'LR',
          });
          break;
        case 'circular':
          result = applyCircularLayout(nodes, edges, { center: viewportCenter });
          break;
        case 'grid':
          result = applyGridLayout(nodes, edges, { center: viewportCenter });
          break;
        case 'random':
          result = applyRandomLayout(nodes, edges, { center: viewportCenter });
          break;
        default:
          result = applyHierarchicalLayout(nodes, edges, {
            ...hierarchicalBaseOptions,
            direction: 'LR',
          });
      }

      // Only the positions change: the board's nodes may have changed since this layout's
      // render (a selection, a refresh), and those changes stay. They glide there (#650).
      // Persisted to IndexedDB to avoid snap-back on refresh.
      glideTo(new Map(result.nodes.map((node) => [node.id, node.position])));
      result.nodes.forEach((node) => {
        persistNodePosition(node.id, node.position);
      });

    },
    [
      nodes,
      edges,
      persistNodePosition,
      screenToFlowPosition,
      collectRenderedNodeDimensions,
      nodeSpacing,
      rankSpacing,
      setAutoLayoutMode,
      glideTo,
    ]
  );

  useEffect(() => {
    latestAutoLayoutModeRef.current = autoLayoutMode;
  }, [autoLayoutMode]);

  // New spacing in the settings lays the board out again (not on mount)
  const spacingSeen = useRef(false);
  useEffect(() => {
    if (!spacingSeen.current) {
      spacingSeen.current = true;
      return;
    }
    applyLayout(latestAutoLayoutModeRef.current, { updateStoredMode: false });
    // Only a change of the spacing: applyLayout changes with every node update
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeSpacing, rankSpacing]);

  // Auto-layout on topology-changing redraws (new nodes or new edges), debounced to avoid jumpy relayouts
  useEffect(() => {
    if (previousModeRef.current !== mode) {
      previousModeRef.current = mode;
      previousNodeIdsRef.current = getNodeIdSet(nodes);
      previousEdgeIdsRef.current = getEdgeIdSet(edges);
      return;
    }

    const currentNodeIds = getNodeIdSet(nodes);
    const currentEdgeIds = getEdgeIdSet(edges);

    const hasNewNodes = hasNewNodeAdditions(previousNodeIdsRef.current, currentNodeIds);
    const hasNewEdges = hasNewEdgeAdditions(previousEdgeIdsRef.current, currentEdgeIds);

    previousNodeIdsRef.current = currentNodeIds;
    previousEdgeIdsRef.current = currentEdgeIds;

    if (!autoLayoutEnabled || (!hasNewNodes && !hasNewEdges)) {
      return;
    }
    // While a node is unfolded the board waits; folding lays it out
    if (useUIStore.getState().unfoldedNodeId) {
      layoutDueRef.current = true;
      return;
    }

    scheduleDebouncedAutoLayout(autoLayoutDebounceRef, () => {
      // A node unfolded meanwhile: the fold lays the board out
      if (useUIStore.getState().unfoldedNodeId) {
        layoutDueRef.current = true;
        return;
      }
      applyLayout(latestAutoLayoutModeRef.current, {
        // Auto-layout should not overwrite the user's last explicit mode selection.
        updateStoredMode: false,
      });
    });
  }, [nodes, edges, mode, autoLayoutEnabled, applyLayout]);

  useEffect(() => {
    if (!autoLayoutEnabled) {
      clearDebouncedAutoLayout(autoLayoutDebounceRef);
    }
  }, [autoLayoutEnabled]);

  useEffect(() => {
    return () => {
      clearDebouncedAutoLayout(autoLayoutDebounceRef);
    };
  }, []);

  // Pans the board, as little as it takes, so the box is in view (with a margin)
  const reveal = useCallback(
    (box: { x: number; y: number; width: number; height: number }) => {
      const pane = document.querySelector('.react-flow')?.getBoundingClientRect();
      if (!pane) return;
      const next = revealViewport(getViewport(), box, pane);
      if (next) setViewport(next, revealGlide());
    },
    [getViewport, setViewport],
  );

  // Selects an agent, so Space unfolds it, and centers the board on it at the zoom it has
  const showNode = (nodeId: string) => {
    const node = getNode(nodeId);
    if (!node) return;
    useGraphStore.setState((state) => ({
      nodes: state.nodes.map((n) => (Boolean(n.selected) === (n.id === nodeId) ? n : { ...n, selected: n.id === nodeId })),
    }));
    const width = node.measured?.width ?? node.width ?? 0;
    const height = node.measured?.height ?? node.height ?? 0;
    void setCenter(node.position.x + width / 2, node.position.y + height / 2, {
      zoom: getViewport().zoom,
      duration: motionMs(300),
    });
    // The keyboard goes on from it, once the palette gave the focus back
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(`.react-flow__node[data-id="${CSS.escape(nodeId)}"]`)?.focus(),
    );
  };

  // The palette's commands on this board, registered once; they read the latest layout
  const applyLayoutRef = useRef(applyLayout);
  applyLayoutRef.current = applyLayout;
  useEffect(
    () =>
      registerCanvas(
        {
          kind: 'flow',
          zoomIn: () => void zoomIn({ duration: motionMs(200) }),
          zoomOut: () => void zoomOut({ duration: motionMs(200) }),
          fit: () => afterGlide(asNewest(() => void fitView({ padding: 0.1, duration: motionMs(300) }))),
          layout: (layoutMode) => applyLayoutRef.current(layoutMode),
          // A board that just mounted loads its agents and lays them out first
          show: (nodeId) => whenOnBoard(nodeId, () => showNode(nodeId), SETTLE_MS),
        },
        SETTLE_MS,
      ),
    // The React Flow functions are stable, showNode uses only them
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // Neighbors make room while a node is unfolded
  useUnfoldLayout({
    reveal,
    layoutDue: layoutDueRef,
    mode: autoLayoutMode,
    nodeSpacing,
    rankSpacing,
    collectDimensions: collectRenderedNodeDimensions,
    relayout: () => applyLayout(latestAutoLayoutModeRef.current, { updateStoredMode: false }),
  });

  // Node drag handler - prevent overlaps with collision detection
  const onNodeDrag = useCallback(
    (_event: React.MouseEvent | MouseEvent, node: Node) => {
      const intersections = getIntersectingNodes(node);

      // If there are intersecting nodes, snap back to prevent overlap
      if (intersections.length > 0) {
        // Revert to previous position by updating the nodes
        useGraphStore.setState((state) => ({
          nodes: state.nodes.map((n) =>
            n.id === node.id
              ? { ...n, position: n.position } // Keep previous position
              : n
          ),
        }));
      }
    },
    [getIntersectingNodes]
  );

  // Node drag stop handler - persist position with 300ms debounce
  const onNodeDragStop = useCallback(
    (_event: React.MouseEvent | MouseEvent, node: Node) => {
      const { transientPositions, setTransientPositions } = useGraphStore.getState();
      if (transientPositions) {
        // A node is unfolded: the move lasts until it folds and is not saved
        setTransientPositions(new Map(transientPositions).set(node.id, node.position));
        return;
      }
      saveNodePositionDebounced(node.id, node.position);
    },
    [saveNodePositionDebounced]
  );

  // A click unfolds an agent in place (a click inside the unfolded one, or on a control, changes nothing)
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    if (fromControl(event.target)) return;
    if (node.type === 'agent' && useUIStore.getState().unfoldedNodeId !== node.id) {
      useUIStore.getState().unfold(node.id);
    }
  }, []);

  // A double-click puts an agent in focus
  const onNodeDoubleClick = useCallback((event: React.MouseEvent, node: Node) => {
    if (fromControl(event.target)) return;
    if (node.type === 'agent') useUIStore.getState().focus(node.id);
  }, []);

  // The edges animate themselves while an artifact is in flight
  const defaultEdgeOptions = useMemo(() => ({ type: edgeType }), [edgeType]);

  // Arrowheads in the line color of the theme
  const themedEdges = useMemo(
    () =>
      edges.map((edge) =>
        edge.markerEnd && typeof edge.markerEnd === 'object'
          ? { ...edge, markerEnd: { ...edge.markerEnd, color: 'var(--line-2)', width: 14, height: 14 } }
          : edge,
      ),
    [edges],
  );

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ReactFlow
        nodes={nodes}
        edges={themedEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        // Space unfolds and folds the selected node; dragging the board pans it
        panActivationKeyCode={null}
        // Backspace would remove an agent from the view, not from the flock
        deleteKeyCode={null}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        style={{ backgroundColor: 'var(--board)' }}
      >
        <Background color="var(--dot)" bgColor="var(--board)" gap={22} size={1.3} />
        {!dockOpen && <MiniMap />}
      </ReactFlow>

      {!dockOpen && (
        <CanvasDock
          layout={autoLayoutMode}
          autoArrange={autoLayoutEnabled}
          onLayout={(mode) => applyLayout(mode)}
          onAutoArrange={setAutoLayoutEnabled}
        />
      )}

      <FocusStage onOpenTrace={openTrace} />
    </div>
  );
};

export default GraphCanvas;
