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
  const mode = useUIStore((state) => state.mode);
  const agents = useGraphStore((state) => state.agents);
  const messages = useGraphStore((state) => state.messages);

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
          // Determine node type based on mode and what exists
          let nodeType: 'agent' | 'message' = 'agent';

          if (mode === 'agent') {
            // In agent view, check if it's an agent
            if (agents.has(nodeId)) {
              nodeType = 'agent';
            }
          } else if (mode === 'blackboard') {
            // In blackboard view, nodes are messages
            if (messages.has(nodeId)) {
              nodeType = 'message';
            }
          }

          return <NodeDetailWindow key={nodeId} nodeId={nodeId} nodeType={nodeType} />;
        })}
      </div>
    </div>
  );
};

export default DetailWindowContainer;
