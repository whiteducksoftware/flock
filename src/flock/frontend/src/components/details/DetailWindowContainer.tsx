import React from 'react';
import { useUIStore } from '../../store/uiStore';
import { useGraphStore } from '../../store/graphStore';
import NodeDetailWindow from './NodeDetailWindow';

/**
 * Container component that renders all open detail windows.
 * Manages multiple floating windows with independent drag/resize.
 */
const DetailWindowContainer: React.FC = () => {
  const detailWindows = useUIStore((state) => state.detailWindows);
  const nodes = useGraphStore((state) => state.nodes);

  // Convert Map to array for rendering
  const windowEntries = Array.from(detailWindows.entries());

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        pointerEvents: 'none',
        zIndex: 999,
      }}
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      >
        {windowEntries.map(([nodeId, _window]) => {
          // UI Optimization Migration (Phase 4.1): Read node type from state.nodes
          const node = nodes.find((n) => n.id === nodeId);
          const nodeType: 'agent' | 'message' = node?.type === 'agent' ? 'agent' : 'message';

          return <NodeDetailWindow key={nodeId} nodeId={nodeId} nodeType={nodeType} />;
        })}
      </div>
    </div>
  );
};

export default DetailWindowContainer;
