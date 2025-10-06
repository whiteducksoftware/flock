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
import MiniMap from './MiniMap';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { useModuleStore } from '../../store/moduleStore';
import { useSettingsStore } from '../../store/settingsStore';
import { moduleRegistry } from '../modules/ModuleRegistry';
import { applyDagreLayout } from '../../services/layout';
import { usePersistence } from '../../hooks/usePersistence';
import { v4 as uuidv4 } from 'uuid';

const GraphCanvas: React.FC = () => {
  const { fitView, getIntersectingNodes } = useReactFlow();

  const mode = useUIStore((state) => state.mode);
  const openDetailWindow = useUIStore((state) => state.openDetailWindow);
  const layoutDirection = useSettingsStore((state) => state.advanced.layoutDirection);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const agents = useGraphStore((state) => state.agents);
  const messages = useGraphStore((state) => state.messages);
  const runs = useGraphStore((state) => state.runs);
  const generateAgentViewGraph = useGraphStore((state) => state.generateAgentViewGraph);
  const generateBlackboardViewGraph = useGraphStore((state) => state.generateBlackboardViewGraph);
  const updateNodePosition = useGraphStore((state) => state.updateNodePosition);
  const addModule = useModuleStore((state) => state.addModule);

  // Graph settings from settings store
  const edgeType = useSettingsStore((state) => state.graph.edgeType);
  const edgeStrokeWidth = useSettingsStore((state) => state.graph.edgeStrokeWidth);
  const edgeAnimation = useSettingsStore((state) => state.graph.edgeAnimation);

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [showModuleSubmenu, setShowModuleSubmenu] = useState(false);

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
    }),
    []
  );

  // Generate graph when mode changes OR when agents/messages/runs change
  useEffect(() => {
    if (mode === 'agent') {
      generateAgentViewGraph();
    } else {
      generateBlackboardViewGraph();
    }
  }, [mode, agents, messages, runs, generateAgentViewGraph, generateBlackboardViewGraph]);

  // Regenerate graph when edge settings change to apply new edge styles
  useEffect(() => {
    if (mode === 'agent') {
      generateAgentViewGraph();
    } else {
      generateBlackboardViewGraph();
    }
  }, [edgeType, edgeStrokeWidth, edgeAnimation, mode, generateAgentViewGraph, generateBlackboardViewGraph]);

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

  // Auto-layout handler
  const handleAutoLayout = useCallback(() => {
    const nodeSpacing = useSettingsStore.getState().advanced.nodeSpacing;
    const rankSpacing = useSettingsStore.getState().advanced.rankSpacing;
    const layoutedNodes = applyDagreLayout(nodes, edges, layoutDirection || 'TB', nodeSpacing, rankSpacing);

    // Update nodes with new positions
    layoutedNodes.forEach((node) => {
      updateNodePosition(node.id, node.position);
    });

    useGraphStore.setState({ nodes: layoutedNodes });
    setContextMenu(null);
    setShowModuleSubmenu(false);
  }, [nodes, edges, layoutDirection, updateNodePosition]);

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
          <button
            onClick={handleAutoLayout}
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
            Auto Layout
          </button>

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
