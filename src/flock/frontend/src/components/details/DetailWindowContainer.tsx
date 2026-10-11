import React from 'react';
import { useUIStore } from '../../store/uiStore';
import MessageDetailWindow from './MessageDetailWindow';

/**
 * The open artifact windows of the Blackboard view (metadata, payload,
 * consumption history), until artifact cards unfold in place (#565).
 * Agents unfold on the board instead.
 */
const DetailWindowContainer: React.FC = () => {
  const detailWindows = useUIStore((state) => state.detailWindows);

  return (
    <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 999 }}>
      <div style={{ position: 'relative', width: '100%', height: '100%', pointerEvents: 'none' }}>
        {Array.from(detailWindows.keys()).map((nodeId) => (
          <MessageDetailWindow key={nodeId} nodeId={nodeId} />
        ))}
      </div>
    </div>
  );
};

export default DetailWindowContainer;
