import { useCallback, useMemo, useEffect, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  NodeChange,
  EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import AgentNode from './AgentNode';
import MessageNode from './MessageNode';
import MessageFlowEdge from './MessageFlowEdge';
import TransformEdge from './TransformEdge';
import PendingJoinEdge from './PendingJoinEdge';
import PendingBatchEdge from './PendingBatchEdge';
import MiniMap from './MiniMap';
import { useGraphStore } from '../../store/graphStore';
import { useFilterStore } from '../../store/filterStore';
import { useUIStore } from '../../store/uiStore';
import { useModuleStore } from '../../store/moduleStore';
import { useSettingsStore } from '../../store/settingsStore';
import { moduleRegistry } from '../modules/ModuleRegistry';
import {
  applyHierarchicalLayout,
  applyCircularLayout,
  applyGridLayout,
  applyRandomLayout
} from '../../services/layout';
import { usePersistence } from '../../hooks/usePersistence';
import { v4 as uuidv4 } from 'uuid';

const GraphCanvas: React.FC = () => {
  const { fitView, getIntersectingNodes, screenToFlowPosition } = useReactFlow();

  const mode = useUIStore((state) => state.mode);
  const openDetailWindow = useUIStore((state) => state.openDetailWindow);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const generateAgentViewGraph = useGraphStore((state) => state.generateAgentViewGraph);
  const generateBlackboardViewGraph = useGraphStore((state) => state.generateBlackboardViewGraph);
  const updateNodePosition = useGraphStore ((state) => state.updateNodePosition);
  const addModule = useModuleStore((state) => state.addModule);
  // UI Optimization Migration (Phase 4 - Spec 002): Use filterStore.applyFilters (backend-driven)
  const applyFilters = useFilterStore((state) => state.applyFilters);

  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const selectedArtifactTypes = useFilterStore((state) => state.selectedArtifactTypes);
  const selectedProducers = useFilterStore((state) => state.selectedProducers);
  const selectedTags = useFilterStore((state) => state.selectedTags);
  const selectedVisibility = useFilterStore((state) => state.selectedVisibility);

  // Graph settings from settings store
  const edgeType = useSettingsStore((state) => state.graph.edgeType);
  const edgeStrokeWidth = useSettingsStore((state) => state.graph.edgeStrokeWidth);
  const edgeAnimation = useSettingsStore((state) => state.graph.edgeAnimation);

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [showModuleSubmenu, setShowModuleSubmenu] = useState(false);
  const [showLayoutSubmenu, setShowLayoutSubmenu] = useState(false);

  // Persistence hook - loads positions on mount and handles saves
  const { saveNodePosition } = usePersistence();

  // Memoize node types to prevent re-creation
  const nodeTypes = useMemo(
    () => ({
      agent: AgentNode,
      message: MessageNode,
    }),
    []
  );

  // Memoize edge types to prevent re-creation
  const edgeTypes = useMemo(
    () => ({
      message_flow: MessageFlowEdge,
      transformation: TransformEdge,
      pending_join: PendingJoinEdge,  // Phase 1.5: Pending edges for JoinSpec correlation groups
      pending_batch: PendingBatchEdge, // Phase 1.5: Pending edges for BatchSpec accumulation
    }),
    []
  );

  // UI Optimization Migration (Phase 4.1 - Spec 002): Generate graph when mode changes
  // Backend snapshot includes ALL latest data, no need to watch OLD agents/messages/runs Maps
  // Note: generateAgentViewGraph and generateBlackboardViewGraph are stable zustand functions
  // DO NOT add them to dependencies or it will cause infinite loop when nodes update
  useEffect(() => {
    if (mode === 'agent') {
      generateAgentViewGraph();
    } else {
      generateBlackboardViewGraph();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // Regenerate graph when edge settings change to apply new edge styles
  // Note: generateAgentViewGraph and generateBlackboardViewGraph are stable zustand functions
  // DO NOT add them to dependencies or it will cause infinite loop when nodes update
  useEffect(() => {
    if (mode === 'agent') {
      generateAgentViewGraph();
    } else {
      generateBlackboardViewGraph();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edgeType, edgeStrokeWidth, edgeAnimation, mode]);

  // Apply filters whenever filter store state changes
  useEffect(() => {
    applyFilters();
  }, [
    applyFilters,
    correlationId,
    timeRange.preset,
    timeRange.start,
    timeRange.end,
    selectedArtifactTypes.join('|'),
    selectedProducers.join('|'),
    selectedTags.join('|'),
    selectedVisibility.join('|'),
  ]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const updatedNodes = applyNodeChanges(changes, nodes);
      useGraphStore.setState({ nodes: updatedNodes });

      // Update position in store for persistence
      changes.forEach((change) => {
        if (change.type === 'position' && change.position) {
          updateNodePosition(change.id, change.position);
        }
      });
    },
    [nodes, updateNodePosition]
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const updatedEdges = applyEdgeChanges(changes, edges);
      useGraphStore.setState({ edges: updatedEdges });
    },
    [edges]
  );

  // Generic layout handler
  const applyLayout = useCallback((layoutType: string) => {
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

    let result;
    switch (layoutType) {
      case 'hierarchical-vertical':
        result = applyHierarchicalLayout(nodes, edges, { direction: 'TB', center: viewportCenter });
        break;
      case 'hierarchical-horizontal':
        result = applyHierarchicalLayout(nodes, edges, { direction: 'LR', center: viewportCenter });
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
        result = applyHierarchicalLayout(nodes, edges, { direction: 'TB', center: viewportCenter });
    }

    // Update nodes with new positions
    result.nodes.forEach((node) => {
      updateNodePosition(node.id, node.position);
    });

    useGraphStore.setState({ nodes: result.nodes });
    setContextMenu(null);
    setShowModuleSubmenu(false);
    setShowLayoutSubmenu(false);
  }, [nodes, edges, updateNodePosition, screenToFlowPosition]);

  // Auto-zoom handler
  const handleAutoZoom = useCallback(() => {
    fitView({ padding: 0.1, duration: 300 });
    setContextMenu(null);
    setShowModuleSubmenu(false);
  }, [fitView]);

  // Add module handler
  const handleAddModule = useCallback((moduleType: string, clickX: number, clickY: number) => {
    const moduleInstance = {
      id: uuidv4(),
      type: moduleType,
      position: { x: clickX, y: clickY },
      size: { width: 600, height: 400 },
      visible: true,
    };

    addModule(moduleInstance);
    setContextMenu(null);
    setShowModuleSubmenu(false);
  }, [addModule]);

  // Context menu handler
  const onPaneContextMenu = useCallback((event: React.MouseEvent | MouseEvent) => {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
    });
    setShowModuleSubmenu(false);
  }, []);

  // Close context menu on click outside
  const onPaneClick = useCallback(() => {
    setContextMenu(null);
    setShowModuleSubmenu(false);
    setShowLayoutSubmenu(false);
  }, []);

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
      saveNodePosition(node.id, node.position);
    },
    [saveNodePosition]
  );

  // Node double-click handler - open detail window
  const onNodeDoubleClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      openDetailWindow(node.id);
    },
    [openDetailWindow]
  );

  const defaultEdgeOptions = useMemo(
    () => ({
      type: edgeType,
      animated: edgeAnimation,
      style: {
        stroke: 'var(--color-edge-default)',
        strokeWidth: edgeStrokeWidth,
      },
    }),
    [edgeType, edgeAnimation, edgeStrokeWidth]
  );

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onNodeDoubleClick={onNodeDoubleClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        onPaneContextMenu={onPaneContextMenu}
        onPaneClick={onPaneClick}
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
        }}
      >
        <Background
          color="var(--color-border-subtle)"
          gap={16}
          size={1}
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
          }}
        />
        <Controls
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-default)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-lg)',
          }}
          showZoom={true}
          showFitView={true}
          showInteractive={true}
        />
        <MiniMap />
      </ReactFlow>

      {/* Context Menu */}
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            background: 'var(--color-bg-surface)',
            border: 'var(--border-default)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 1000,
            minWidth: 180,
          }}
        >
          <div style={{ position: 'relative' }}>
            <button
              onMouseEnter={() => setShowLayoutSubmenu(true)}
              onMouseLeave={(e) => {
                const relatedTarget = e.relatedTarget as HTMLElement;
                if (!relatedTarget || !relatedTarget.closest('.layout-submenu')) {
                  setShowLayoutSubmenu(false);
                }
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: 'var(--spacing-2) var(--spacing-4)',
                border: 'none',
                background: showLayoutSubmenu ? 'var(--color-bg-overlay)' : 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: 'var(--font-size-body-sm)',
                color: 'var(--color-text-primary)',
                transition: 'var(--transition-colors)',
              }}
            >
              <span>Auto Layout</span>
              <span style={{ marginLeft: 'var(--spacing-2)' }}>▶</span>
            </button>

            {/* Layout Submenu */}
            {showLayoutSubmenu && (
              <div
                className="layout-submenu"
                onMouseEnter={() => setShowLayoutSubmenu(true)}
                onMouseLeave={() => setShowLayoutSubmenu(false)}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: '100%',
                  background: 'var(--color-bg-surface)',
                  border: 'var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  boxShadow: 'var(--shadow-lg)',
                  zIndex: 1001,
                  minWidth: 180,
                }}
              >
                <button
                  onClick={() => applyLayout('hierarchical-vertical')}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: 'var(--spacing-2) var(--spacing-4)',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 'var(--font-size-body-sm)',
                    color: 'var(--color-text-primary)',
                    transition: 'var(--transition-colors)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--color-bg-overlay)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  Hierarchical (Vertical)
                </button>
                <button
                  onClick={() => applyLayout('hierarchical-horizontal')}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: 'var(--spacing-2) var(--spacing-4)',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 'var(--font-size-body-sm)',
                    color: 'var(--color-text-primary)',
                    transition: 'var(--transition-colors)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--color-bg-overlay)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  Hierarchical (Horizontal)
                </button>
                <button
                  onClick={() => applyLayout('circular')}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: 'var(--spacing-2) var(--spacing-4)',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 'var(--font-size-body-sm)',
                    color: 'var(--color-text-primary)',
                    transition: 'var(--transition-colors)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--color-bg-overlay)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  Circular
                </button>
                <button
                  onClick={() => applyLayout('grid')}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: 'var(--spacing-2) var(--spacing-4)',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 'var(--font-size-body-sm)',
                    color: 'var(--color-text-primary)',
                    transition: 'var(--transition-colors)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--color-bg-overlay)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  Grid
                </button>
                <button
                  onClick={() => applyLayout('random')}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: 'var(--spacing-2) var(--spacing-4)',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 'var(--font-size-body-sm)',
                    color: 'var(--color-text-primary)',
                    transition: 'var(--transition-colors)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--color-bg-overlay)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  Random
                </button>
              </div>
            )}
          </div>

          <button
            onClick={handleAutoZoom}
            style={{
              display: 'block',
              width: '100%',
              padding: 'var(--spacing-2) var(--spacing-4)',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: 'var(--font-size-body-sm)',
              color: 'var(--color-text-primary)',
              transition: 'var(--transition-colors)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--color-bg-overlay)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            Auto Zoom
          </button>

          <div style={{ position: 'relative' }}>
            <button
              onMouseEnter={() => setShowModuleSubmenu(true)}
              onMouseLeave={(e) => {
                // Only close submenu if not moving to submenu itself
                const relatedTarget = e.relatedTarget as HTMLElement;
                if (!relatedTarget || !relatedTarget.closest('.module-submenu')) {
                  setShowModuleSubmenu(false);
                }
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: 'var(--spacing-2) var(--spacing-4)',
                border: 'none',
                background: showModuleSubmenu ? 'var(--color-bg-overlay)' : 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: 'var(--font-size-body-sm)',
                color: 'var(--color-text-primary)',
                transition: 'var(--transition-colors)',
              }}
            >
              <span>Add Module</span>
              <span style={{ marginLeft: 'var(--spacing-2)' }}>▶</span>
            </button>

            {/* Module Submenu */}
            {showModuleSubmenu && (
              <div
                className="module-submenu"
                onMouseEnter={() => setShowModuleSubmenu(true)}
                onMouseLeave={() => setShowModuleSubmenu(false)}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: '100%',
                  background: 'var(--color-bg-surface)',
                  border: 'var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  boxShadow: 'var(--shadow-lg)',
                  zIndex: 1001,
                  minWidth: 160,
                }}
              >
                {moduleRegistry.getAll().map((module) => (
                  <button
                    key={module.id}
                    onClick={() => handleAddModule(module.id, contextMenu.x, contextMenu.y)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--gap-sm)',
                      width: '100%',
                      padding: 'var(--spacing-2) var(--spacing-4)',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 'var(--font-size-body-sm)',
                      color: 'var(--color-text-primary)',
                      transition: 'var(--transition-colors)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--color-bg-overlay)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    {module.icon && <span>{module.icon}</span>}
                    <span>{module.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default GraphCanvas;
