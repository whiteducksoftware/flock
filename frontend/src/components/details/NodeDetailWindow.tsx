import React, { useCallback } from 'react';
import { Rnd } from 'react-rnd';
import { useUIStore } from '../../store/uiStore';
import LiveOutputTab from './LiveOutputTab';
import MessageHistoryTab from './MessageHistoryTab';
import RunStatusTab from './RunStatusTab';

interface NodeDetailWindowProps {
  nodeId: string;
  nodeType?: 'agent' | 'message';
}

const NodeDetailWindow: React.FC<NodeDetailWindowProps> = ({ nodeId, nodeType = 'agent' }) => {
  const window = useUIStore((state) => state.detailWindows.get(nodeId));
  const updateDetailWindow = useUIStore((state) => state.updateDetailWindow);
  const closeDetailWindow = useUIStore((state) => state.closeDetailWindow);

  const handleClose = useCallback(() => {
    closeDetailWindow(nodeId);
  }, [nodeId, closeDetailWindow]);

  const handleTabSwitch = useCallback(
    (tab: 'liveOutput' | 'messageHistory' | 'runStatus') => {
      updateDetailWindow(nodeId, { activeTab: tab });
    },
    [nodeId, updateDetailWindow]
  );

  if (!window) return null;

  const { position, size, activeTab } = window;

  return (
    <Rnd
      position={position}
      size={size}
      onDragStop={(_e, d) => {
        updateDetailWindow(nodeId, {
          position: { x: d.x, y: d.y },
        });
      }}
      onResizeStop={(_e, _direction, ref, _delta, position) => {
        updateDetailWindow(nodeId, {
          size: {
            width: parseInt(ref.style.width, 10),
            height: parseInt(ref.style.height, 10),
          },
          position,
        });
      }}
      minWidth={600}
      minHeight={400}
      bounds="parent"
      dragHandleClassName="window-header"
      style={{
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        pointerEvents: 'all',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          height: '100%',
          background: 'var(--color-glass-bg)',
          border: 'var(--border-width-1) solid var(--color-glass-border)',
          borderRadius: 'var(--radius-xl)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-xl)',
          backdropFilter: 'blur(var(--blur-lg))',
          WebkitBackdropFilter: 'blur(var(--blur-lg))',
        }}
      >
        {/* Header */}
        <div
          className="window-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--space-component-md) var(--space-component-lg)',
            background: 'rgba(42, 42, 50, 0.5)',
            borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
            cursor: 'move',
            userSelect: 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-md)' }}>
            <div
              style={{
                width: '10px',
                height: '10px',
                borderRadius: 'var(--radius-circle)',
                background: nodeType === 'agent' ? 'var(--color-primary-500)' : 'var(--color-warning)',
                boxShadow: nodeType === 'agent'
                  ? '0 0 8px var(--color-primary-500)'
                  : '0 0 8px var(--color-warning)',
              }}
            />
            <span
              style={{
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                fontFamily: 'var(--font-family-sans)',
              }}
            >
              {nodeType === 'agent' ? 'Agent' : 'Message'}: {nodeId}
            </span>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close window"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-h3)',
              cursor: 'pointer',
              padding: 'var(--spacing-1) var(--spacing-2)',
              lineHeight: 1,
              borderRadius: 'var(--radius-md)',
              transition: 'var(--transition-colors)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-error)';
              e.currentTarget.style.background = 'var(--color-error-bg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-secondary)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div
          style={{
            display: 'flex',
            gap: 'var(--gap-sm)',
            padding: 'var(--space-component-sm) var(--space-component-lg)',
            background: 'rgba(35, 35, 41, 0.4)',
            borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
          }}
        >
          {(['liveOutput', 'messageHistory', 'runStatus'] as const).map((tab) => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => handleTabSwitch(tab)}
                style={{
                  position: 'relative',
                  padding: 'var(--space-component-sm) var(--space-component-md)',
                  background: isActive ? 'var(--color-bg-surface)' : 'transparent',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  fontSize: 'var(--font-size-body-sm)',
                  fontWeight: isActive ? 'var(--font-weight-semibold)' : 'var(--font-weight-medium)',
                  fontFamily: 'var(--font-family-sans)',
                  cursor: 'pointer',
                  transition: 'var(--transition-colors)',
                  borderBottom: isActive
                    ? '2px solid var(--color-primary-500)'
                    : '2px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'var(--color-bg-elevated)';
                    e.currentTarget.style.color = 'var(--color-text-primary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = 'var(--color-text-secondary)';
                  }
                }}
              >
                {tab === 'liveOutput'
                  ? 'Live Output'
                  : tab === 'messageHistory'
                  ? 'Message History'
                  : 'Run Status'}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            background: 'var(--color-bg-surface)',
          }}
        >
          {activeTab === 'liveOutput' && <LiveOutputTab nodeId={nodeId} nodeType={nodeType} />}
          {activeTab === 'messageHistory' && (
            <MessageHistoryTab nodeId={nodeId} nodeType={nodeType} />
          )}
          {activeTab === 'runStatus' && <RunStatusTab nodeId={nodeId} nodeType={nodeType} />}
        </div>
      </div>
    </Rnd>
  );
};

export default NodeDetailWindow;
