import { memo, useState, useEffect, useRef } from 'react';
import { NodeProps, Handle, Position } from '@xyflow/react';
import { useUIStore } from '../../store/uiStore';
import { useSettingsStore } from '../../store/settingsStore';
import LogicOperationsDisplay from './LogicOperationsDisplay';

// UI Optimization Migration (Phase 4.1 - Spec 002): Backend GraphNode.data is Record<string, any>
// Agent-specific properties populated by backend snapshot
const AgentNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as Record<string, any>;
  const name = nodeData.name;
  const status = nodeData.status;
  const sentCount = nodeData.sentCount;
  const recvCount = nodeData.recvCount;
  const subscriptions = nodeData.subscriptions || [];
  const outputTypes = nodeData.outputTypes || [];
  const receivedByType = nodeData.receivedByType || {};
  const sentByType = nodeData.sentByType || {};
  const streamingTokens = nodeData.streamingTokens || [];
  const logicOperations = nodeData.logicOperations || []; // Phase 1.4: Logic operations state

  // Merge known types with actual counts - show all types even with 0 count
  // Start with actual counts, then add known types that haven't happened yet
  const displayReceivedByType: Record<string, number> = { ...receivedByType };
  subscriptions.forEach((type: string) => {
    if (!(type in displayReceivedByType)) {
      displayReceivedByType[type] = 0;
    }
  });

  const displaySentByType: Record<string, number> = { ...sentByType };
  outputTypes.forEach((type: string) => {
    if (!(type in displaySentByType)) {
      displaySentByType[type] = 0;
    }
  });

  // Track which types just changed for flash animation
  const [flashingKeys, setFlashingKeys] = useState<Set<string>>(new Set());
  const prevCounts = useRef<Record<string, number>>({});

  // Detect changes and trigger flash
  useEffect(() => {
    // Check only actual received/sent counts for flashing (not predicted types)
    const allCounts = { ...receivedByType, ...sentByType };
    const changedKeys = new Set<string>();

    Object.entries(allCounts).forEach(([key, count]) => {
      const numCount = count as number;
      if (prevCounts.current[key] !== undefined && prevCounts.current[key] !== numCount) {
        changedKeys.add(key);
      }
      prevCounts.current[key] = numCount;
    });

    if (changedKeys.size > 0) {
      setFlashingKeys(changedKeys);
      const timer = setTimeout(() => setFlashingKeys(new Set()), 500);
      return () => clearTimeout(timer);
    }
  }, [receivedByType, sentByType]);

  const handleDoubleClick = () => {
    useUIStore.getState().openDetailWindow(name);
  };

  // Appearance settings from settings store
  const agentIdleColor = useSettingsStore((state) => state.appearance.agentIdleColor);
  const agentActiveColor = useSettingsStore((state) => state.appearance.agentActiveColor);
  const agentErrorColor = useSettingsStore((state) => state.appearance.agentErrorColor);
  const nodeShadow = useSettingsStore((state) => state.appearance.nodeShadow);
  const showStatusPulse = useSettingsStore((state) => state.appearance.showStatusPulse);
  const compactNodeView = useSettingsStore((state) => state.appearance.compactNodeView);

  // Status styling: customizable colors from settings
  const getStatusStyle = () => {
    if (status === 'running') {
      return {
        indicatorColor: agentActiveColor,
        borderColor: agentActiveColor,
        borderWidth: '3px', // Thick border for active
      };
    } else if (status === 'error') {
      return {
        indicatorColor: agentErrorColor,
        borderColor: agentErrorColor,
        borderWidth: '2px',
      };
    } else {
      // idle
      return {
        indicatorColor: agentIdleColor,
        borderColor: agentIdleColor,
        borderWidth: '2px',
      };
    }
  };

  const statusStyle = getStatusStyle();

  // Shadow mapping
  const shadowMap = {
    none: 'none',
    small: 'var(--shadow-sm)',
    medium: 'var(--shadow-md)',
    large: 'var(--shadow-lg)',
  };

  const baseShadow = shadowMap[nodeShadow];
  const selectedShadow = selected ? 'var(--shadow-lg), var(--shadow-glow-primary)' : baseShadow;

  return (
    <div
      className={`agent-node ${selected ? 'selected' : ''}`}
      onDoubleClick={handleDoubleClick}
      style={{
        padding: compactNodeView ? 'var(--space-component-sm)' : 'var(--space-component-md)',
        border: `${statusStyle.borderWidth} solid ${statusStyle.borderColor}`,
        borderRadius: 'var(--radius-lg)',
        backgroundColor: 'var(--color-bg-surface)',
        minWidth: compactNodeView ? '160px' : '200px',
        maxWidth: '300px',
        boxShadow: selectedShadow,
        cursor: 'pointer',
        transition: 'var(--transition-all)',
      }}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-2)' }}>
        <span style={{
          fontWeight: 600,
          fontSize: compactNodeView ? '14px' : '16px',
          color: 'var(--color-text-primary)',
          lineHeight: 1.4,
        }}>{name}</span>
        <span
          style={{
            width: compactNodeView ? '12px' : '14px',
            height: compactNodeView ? '12px' : '14px',
            borderRadius: '50%',
            backgroundColor: statusStyle.indicatorColor,
            display: 'inline-block',
            flexShrink: 0,
            marginLeft: 'var(--spacing-2)',
            animation: (status === 'running' && showStatusPulse) ? 'pulse 2s infinite' : 'none',
          }}
          title={status}
        />
      </div>
      {!compactNodeView && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {/* Per-type input breakdown */}
          {Object.entries(displayReceivedByType).map(([type, count]) => {
            const isFlashing = flashingKeys.has(type);
            return (
              <div
                key={`in-${type}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--spacing-2)',
                  padding: '6px 10px',
                  background: isFlashing ? 'var(--color-info-bg)' : 'rgba(59, 130, 246, 0.08)',
                  borderLeft: '3px solid var(--color-info)',
                  borderRadius: 'var(--radius-md)',
                  transition: 'var(--transition-all)',
                  boxShadow: isFlashing ? 'var(--shadow-glow-primary)' : 'var(--shadow-xs)',
                }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '20px',
                  height: '20px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-info-bg)',
                  color: 'var(--color-info-light)',
                  fontSize: '12px',
                  fontWeight: 700,
                }}>
                  ↓
                </div>
                <div style={{
                  minWidth: '24px',
                  height: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 'var(--radius-full)',
                  background: isFlashing ? 'var(--color-info)' : 'var(--color-info-bg)',
                  color: isFlashing ? 'var(--color-text-on-primary)' : 'var(--color-info-light)',
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '0 var(--spacing-2)',
                  transition: 'var(--transition-all)',
                }}>
                  {count}
                </div>
                <div style={{
                  flex: 1,
                  fontSize: '11px',
                  fontFamily: 'var(--font-family-mono)',
                  color: 'var(--color-text-secondary)',
                  fontWeight: 500,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {type}
                </div>
              </div>
            );
          })}
          {/* Per-type output breakdown */}
          {Object.entries(displaySentByType).map(([type, count]) => {
            const isFlashing = flashingKeys.has(type);
            return (
              <div
                key={`out-${type}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--spacing-2)',
                  padding: '6px 10px',
                  background: isFlashing ? 'var(--color-success-bg)' : 'rgba(16, 185, 129, 0.08)',
                  borderLeft: '3px solid var(--color-success)',
                  borderRadius: 'var(--radius-md)',
                  transition: 'var(--transition-all)',
                  boxShadow: isFlashing ? 'var(--shadow-glow-success)' : 'var(--shadow-xs)',
                }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '20px',
                  height: '20px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-success-bg)',
                  color: 'var(--color-success-light)',
                  fontSize: '12px',
                  fontWeight: 700,
                }}>
                  ↑
                </div>
                <div style={{
                  minWidth: '24px',
                  height: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 'var(--radius-full)',
                  background: isFlashing ? 'var(--color-success)' : 'var(--color-success-bg)',
                  color: isFlashing ? 'var(--color-text-on-primary)' : 'var(--color-success-light)',
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '0 var(--spacing-2)',
                  transition: 'var(--transition-all)',
                }}>
                  {count}
                </div>
                <div style={{
                  flex: 1,
                  fontSize: '11px',
                  fontFamily: 'var(--font-family-mono)',
                  color: 'var(--color-text-secondary)',
                  fontWeight: 500,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {type}
                </div>
              </div>
            );
          })}
          {/* Fallback to totals if no per-type data yet */}
          {Object.keys(displayReceivedByType).length === 0 && Object.keys(displaySentByType).length === 0 && (
            <div style={{ fontSize: '11px', color: 'var(--color-text-tertiary)', opacity: 0.6 }}>
              <span>↓ {recvCount} in</span>
              <span style={{ marginLeft: 'var(--spacing-2)' }}>↑ {sentCount} out</span>
            </div>
          )}
          {/* News ticker for streaming tokens */}
          {streamingTokens.length > 0 && (
            <div style={{
              padding: '4px 8px',
              background: 'rgba(250, 204, 21, 0.08)',
              borderLeft: '2px solid var(--color-warning)',
              borderRadius: 'var(--radius-sm)',
              overflow: 'hidden',
              minWidth: 0,
              display: 'flex',
              justifyContent: 'center',
            }}>
              <div style={{
                width: '200px',
                fontSize: '10px',
                fontFamily: 'var(--font-family-mono)',
                color: 'var(--color-warning-light)',
                fontWeight: 500,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {streamingTokens.join('')}
              </div>
            </div>
          )}
          {/* Phase 1.4: Logic Operations Display (JoinSpec/BatchSpec waiting states) */}
          <LogicOperationsDisplay logicOperations={logicOperations} compactNodeView={compactNodeView} />
        </div>
      )}
      {compactNodeView && (
        <div style={{ display: 'flex', gap: 'var(--spacing-4)', fontSize: '11px', color: 'var(--color-text-tertiary)' }}>
          <span title="Received">↓ {recvCount} <span style={{ fontSize: '10px', opacity: 0.7 }}>in</span></span>
          <span title="Sent">↑ {sentCount} <span style={{ fontSize: '10px', opacity: 0.7 }}>out</span></span>
        </div>
      )}
    </div>
  );
});

AgentNode.displayName = 'AgentNode';

export default AgentNode;
