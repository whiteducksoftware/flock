import { memo, useState, useEffect, useRef } from 'react';
import { AgentLogicOperations, CorrelationGroupState } from '../../types/graph';

interface LogicOperationsDisplayProps {
  logicOperations: AgentLogicOperations[];
  compactNodeView?: boolean;
}

/**
 * Phase 1.4: Logic Operations UX - Visual display component
 *
 * Displays JoinSpec and BatchSpec waiting states in agent nodes:
 * - JoinSpec: Shows correlation groups, waiting_for types, expiration timers
 * - BatchSpec: Shows items collected, target size, timeout remaining
 *
 * Enhanced with:
 * - Client-side timer countdown for real-time updates
 * - Truncation for long correlation keys
 * - Batch progress bars
 * - Timeout warning animations
 * - Copy-to-clipboard for correlation keys
 * - Flash animations on updates
 * - Accessibility attributes
 */
const LogicOperationsDisplay = memo(({ logicOperations, compactNodeView = false }: LogicOperationsDisplayProps) => {
  const [clientTime, setClientTime] = useState(Date.now());
  const [flashingGroups, setFlashingGroups] = useState<Set<string>>(new Set());
  const prevGroupsRef = useRef<Map<string, CorrelationGroupState>>(new Map());

  // Client-side timer: Update every second for real-time countdown
  useEffect(() => {
    const interval = setInterval(() => {
      setClientTime(Date.now());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Detect new/updated correlation groups for flash animation
  useEffect(() => {
    if (!logicOperations) return;

    const newFlashing = new Set<string>();

    logicOperations.forEach(op => {
      if (op.waiting_state?.correlation_groups) {
        op.waiting_state.correlation_groups.forEach(group => {
          const key = `${op.subscription_index}-${group.correlation_key}`;
          const prev = prevGroupsRef.current.get(key);

          if (!prev || JSON.stringify(prev.collected_types) !== JSON.stringify(group.collected_types)) {
            newFlashing.add(key);
            prevGroupsRef.current.set(key, group);
          }
        });
      }
    });

    if (newFlashing.size > 0) {
      setFlashingGroups(newFlashing);
      const timer = setTimeout(() => setFlashingGroups(new Set()), 500);
      return () => clearTimeout(timer);
    }
  }, [logicOperations]);

  if (!logicOperations || logicOperations.length === 0) {
    return null;
  }

  // Only show logic operations if agent is waiting
  const waitingOperations = logicOperations.filter(op => op.waiting_state?.is_waiting);

  if (waitingOperations.length === 0) {
    return null;
  }

  // Helper: Truncate long correlation keys
  const truncateKey = (key: string, maxLength: number = 20): string => {
    if (!key || key.length <= maxLength) return key;
    return `${key.substring(0, maxLength - 3)}...`;
  };

  // Helper: Copy to clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {
      // Silently fail if clipboard not available
    });
  };

  // Helper: Calculate client-side elapsed/remaining time
  const calculateClientTime = (createdAt: string, serverElapsed: number, serverRemaining: number | null) => {
    if (!createdAt) return { elapsed: serverElapsed, remaining: serverRemaining };

    try {
      const created = new Date(createdAt).getTime();
      const now = clientTime;
      const clientElapsed = (now - created) / 1000; // seconds

      let clientRemaining = serverRemaining;
      if (serverRemaining !== null && serverRemaining !== undefined) {
        const totalWindow = serverElapsed + serverRemaining;
        clientRemaining = Math.max(0, totalWindow - clientElapsed);
      }

      return {
        elapsed: Math.max(0, clientElapsed),
        remaining: clientRemaining,
      };
    } catch {
      return { elapsed: serverElapsed, remaining: serverRemaining };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
      {waitingOperations.map((operation, idx) => (
        <div key={`logic-op-${idx}`}>
          {/* JoinSpec Waiting State */}
          {operation.join && operation.waiting_state?.correlation_groups && operation.waiting_state.correlation_groups.length > 0 && (
            <div
              style={{
                padding: '8px 10px',
                background: 'rgba(168, 85, 247, 0.08)',
                borderLeft: '3px solid var(--color-purple-500, #a855f7)',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-xs)',
              }}
              role="region"
              aria-label="JoinSpec correlation groups"
            >
              {operation.waiting_state.correlation_groups.map((group, groupIdx) => {
                const groupKey = `${operation.subscription_index}-${group.correlation_key}`;
                const isFlashing = flashingGroups.has(groupKey);
                const { elapsed, remaining } = calculateClientTime(
                  group.created_at,
                  group.elapsed_seconds,
                  group.expires_in_seconds
                );
                const isUrgent = remaining !== null && remaining < 30;
                const isCritical = remaining !== null && remaining < 10;

                return (
                  <div
                    key={`group-${groupIdx}`}
                    style={{
                      marginBottom: groupIdx < operation.waiting_state!.correlation_groups!.length - 1 ? '8px' : '0',
                      background: isFlashing ? 'rgba(168, 85, 247, 0.15)' : 'transparent',
                      padding: isFlashing ? '4px' : '0',
                      borderRadius: 'var(--radius-sm)',
                      transition: 'all 0.3s ease',
                    }}
                  >
                    {/* Header: JoinSpec icon + correlation key */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      marginBottom: '6px',
                    }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: '20px',
                          height: '20px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--color-purple-100, #f3e8ff)',
                          color: 'var(--color-purple-700, #7e22ce)',
                          fontSize: '12px',
                          fontWeight: 700,
                        }}
                        aria-label="Correlation join operation"
                      >
                        ⋈
                      </div>
                      <div
                        style={{
                          fontSize: '10px',
                          fontFamily: 'var(--font-family-mono)',
                          color: 'var(--color-purple-700, #7e22ce)',
                          fontWeight: 600,
                          cursor: 'pointer',
                          userSelect: 'none',
                        }}
                        title={`${group.correlation_key}\nClick to copy`}
                        onClick={() => copyToClipboard(group.correlation_key)}
                      >
                        {truncateKey(group.correlation_key)}
                      </div>
                      {group.correlation_key.length > 20 && (
                        <button
                          onClick={() => copyToClipboard(group.correlation_key)}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '10px',
                            padding: '0',
                            color: 'var(--color-purple-600, #9333ea)',
                            opacity: 0.7,
                          }}
                          title="Copy full correlation key"
                          aria-label="Copy correlation key to clipboard"
                        >
                          📋
                        </button>
                      )}
                    </div>

                    {/* Waiting for types */}
                    {!compactNodeView && group.waiting_for && group.waiting_for.length > 0 && (
                      <div style={{ marginBottom: '4px' }}>
                        <div style={{
                          fontSize: '9px',
                          color: 'var(--color-text-tertiary)',
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px',
                          fontWeight: 600,
                          marginBottom: '3px',
                        }}>
                          Waiting for:
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {group.waiting_for.map((type, typeIdx) => (
                            <div
                              key={`waiting-${typeIdx}`}
                              style={{
                                padding: '2px 6px',
                                background: 'var(--color-purple-100, #f3e8ff)',
                                color: 'var(--color-purple-700, #7e22ce)',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '9px',
                                fontFamily: 'var(--font-family-mono)',
                                fontWeight: 600,
                              }}
                              title={`Missing artifact type: ${type}`}
                            >
                              {type}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Progress & Expiration */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                      {/* Collected types indicator */}
                      {group.collected_types && Object.keys(group.collected_types).length > 0 && (
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: 'var(--color-purple-600, #9333ea)',
                          }}
                          title={`Collected ${Object.keys(group.collected_types).length} out of ${Object.keys(group.required_types || {}).length} required types`}
                        >
                          <span style={{ fontWeight: 600 }}>{Object.keys(group.collected_types).length}</span>
                          {group.required_types && (
                            <span style={{ fontSize: '9px', opacity: 0.8 }}>/{Object.keys(group.required_types).length} types</span>
                          )}
                        </div>
                      )}

                      {/* Expiration timer with client-side countdown */}
                      {remaining !== null && remaining !== undefined && (
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: isCritical
                              ? 'var(--color-error, #ef4444)'
                              : isUrgent
                              ? 'var(--color-warning-light)'
                              : 'var(--color-text-secondary)',
                            fontWeight: isUrgent ? 600 : 400,
                            animation: isCritical ? 'pulse 1s infinite' : 'none',
                          }}
                          title={`Expires in ${Math.round(remaining)} seconds`}
                          aria-live="polite"
                          aria-atomic="true"
                        >
                          <span>⏱</span>
                          <span>{Math.round(remaining)}s</span>
                        </div>
                      )}

                      {/* Elapsed time */}
                      {!compactNodeView && (
                        <div
                          style={{
                            fontSize: '9px',
                            color: 'var(--color-text-tertiary)',
                            opacity: 0.7,
                          }}
                          title={`Elapsed time: ${Math.round(elapsed)} seconds`}
                        >
                          {Math.round(elapsed)}s elapsed
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* BatchSpec Waiting State */}
          {operation.batch && operation.waiting_state?.batch_state && (
            <div
              style={{
                padding: '8px 10px',
                background: 'rgba(251, 146, 60, 0.08)',
                borderLeft: '3px solid var(--color-orange-500, #fb923c)',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-xs)',
              }}
              role="region"
              aria-label="BatchSpec accumulation"
            >
              {(() => {
                const batchState = operation.waiting_state.batch_state;
                const { remaining } = calculateClientTime(
                  batchState.created_at,
                  batchState.elapsed_seconds,
                  batchState.timeout_remaining_seconds || null
                );
                const isTimeoutUrgent = remaining !== null && remaining < 10;
                const progressPercent = batchState.items_target
                  ? (batchState.items_collected / batchState.items_target) * 100
                  : 0;

                return (
                  <>
                    {/* Header: BatchSpec icon */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      marginBottom: '6px',
                    }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: '20px',
                          height: '20px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--color-orange-100, #ffedd5)',
                          color: 'var(--color-orange-700, #c2410c)',
                          fontSize: '12px',
                          fontWeight: 700,
                        }}
                        aria-label="Batch accumulation operation"
                      >
                        ⊞
                      </div>
                      <div style={{
                        fontSize: '10px',
                        fontFamily: 'var(--font-family-mono)',
                        color: 'var(--color-orange-700, #c2410c)',
                        fontWeight: 600,
                      }}>
                        Batch Accumulating
                      </div>
                    </div>

                    {/* Batch progress */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {/* Items collected */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: 'var(--color-orange-600, #ea580c)',
                          }}
                          title={`Collected ${batchState.items_collected} items${batchState.items_target ? ` out of ${batchState.items_target}` : ''}`}
                        >
                          <span style={{ fontWeight: 600 }}>{batchState.items_collected}</span>
                          {batchState.items_target !== null && (
                            <>
                              <span style={{ fontSize: '9px', opacity: 0.8 }}>/{batchState.items_target} items</span>
                            </>
                          )}
                        </div>

                        {/* Timeout remaining with client-side countdown */}
                        {remaining !== null && remaining !== undefined && (
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              color: isTimeoutUrgent ? 'var(--color-error, #ef4444)' : 'var(--color-text-secondary)',
                              fontWeight: isTimeoutUrgent ? 600 : 400,
                              animation: isTimeoutUrgent ? 'pulse 1s infinite' : 'none',
                            }}
                            title={`Timeout in ${Math.round(remaining)} seconds`}
                            aria-live="polite"
                            aria-atomic="true"
                          >
                            <span>⏱</span>
                            <span>{Math.round(remaining)}s</span>
                          </div>
                        )}
                      </div>

                      {/* Progress bar (only if target is set) */}
                      {batchState.items_target !== null && (
                        <div
                          style={{
                            width: '100%',
                            height: '4px',
                            background: 'var(--color-orange-100, #ffedd5)',
                            borderRadius: '2px',
                            overflow: 'hidden',
                            marginTop: '2px'
                          }}
                          title={`Progress: ${Math.round(progressPercent)}%`}
                          role="progressbar"
                          aria-valuenow={batchState.items_collected}
                          aria-valuemin={0}
                          aria-valuemax={batchState.items_target}
                        >
                          <div style={{
                            width: `${Math.min(100, progressPercent)}%`,
                            height: '100%',
                            background: 'var(--color-orange-500, #fb923c)',
                            transition: 'width 0.3s ease',
                          }} />
                        </div>
                      )}

                      {/* Flush trigger indicator */}
                      {!compactNodeView && batchState.will_flush && (
                        <div style={{
                          fontSize: '9px',
                          color: 'var(--color-text-tertiary)',
                          fontStyle: 'italic',
                        }}>
                          Will flush: {batchState.will_flush === 'on_size' ? 'on size' : batchState.will_flush === 'on_timeout' ? 'on timeout' : 'unknown'}
                        </div>
                      )}
                    </div>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      ))}
    </div>
  );
});

LogicOperationsDisplay.displayName = 'LogicOperationsDisplay';

export default LogicOperationsDisplay;
