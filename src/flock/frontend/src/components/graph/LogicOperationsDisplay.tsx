import { memo } from 'react';
import { AgentLogicOperations } from '../../types/graph';

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
 */
const LogicOperationsDisplay = memo(({ logicOperations, compactNodeView = false }: LogicOperationsDisplayProps) => {
  if (!logicOperations || logicOperations.length === 0) {
    return null;
  }

  // Only show logic operations if agent is waiting
  const waitingOperations = logicOperations.filter(op => op.waiting_state?.is_waiting);

  if (waitingOperations.length === 0) {
    return null;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
      {waitingOperations.map((operation, idx) => (
        <div key={`logic-op-${idx}`}>
          {/* JoinSpec Waiting State */}
          {operation.join && operation.waiting_state?.correlation_groups && operation.waiting_state.correlation_groups.length > 0 && (
            <div style={{
              padding: '8px 10px',
              background: 'rgba(168, 85, 247, 0.08)',
              borderLeft: '3px solid var(--color-purple-500, #a855f7)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-xs)',
            }}>
              {operation.waiting_state.correlation_groups.map((group, groupIdx) => (
                <div key={`group-${groupIdx}`} style={{ marginBottom: groupIdx < operation.waiting_state!.correlation_groups!.length - 1 ? '8px' : '0' }}>
                  {/* Header: JoinSpec icon + correlation key */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    marginBottom: '6px',
                  }}>
                    <div style={{
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
                    }}>
                      ⋈
                    </div>
                    <div style={{
                      fontSize: '10px',
                      fontFamily: 'var(--font-family-mono)',
                      color: 'var(--color-purple-700, #7e22ce)',
                      fontWeight: 600,
                    }}>
                      {group.correlation_key}
                    </div>
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
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        color: 'var(--color-purple-600, #9333ea)',
                      }}>
                        <span style={{ fontWeight: 600 }}>{Object.keys(group.collected_types).length}</span>
                        {group.required_types && (
                          <span style={{ fontSize: '9px', opacity: 0.8 }}>/{Object.keys(group.required_types).length} types</span>
                        )}
                      </div>
                    )}

                    {/* Expiration timer */}
                    {group.expires_in_seconds !== null && group.expires_in_seconds !== undefined && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        color: group.expires_in_seconds < 30 ? 'var(--color-warning-light)' : 'var(--color-text-secondary)',
                        fontWeight: group.expires_in_seconds < 30 ? 600 : 400,
                      }}>
                        <span>⏱</span>
                        <span>{Math.round(group.expires_in_seconds)}s</span>
                      </div>
                    )}

                    {/* Elapsed time */}
                    {!compactNodeView && (
                      <div style={{
                        fontSize: '9px',
                        color: 'var(--color-text-tertiary)',
                        opacity: 0.7,
                      }}>
                        {Math.round(group.elapsed_seconds)}s elapsed
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* BatchSpec Waiting State */}
          {operation.batch && operation.waiting_state?.batch_state && (
            <div style={{
              padding: '8px 10px',
              background: 'rgba(251, 146, 60, 0.08)',
              borderLeft: '3px solid var(--color-orange-500, #fb923c)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-xs)',
            }}>
              {/* Header: BatchSpec icon */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginBottom: '6px',
              }}>
                <div style={{
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
                }}>
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
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: 'var(--color-orange-600, #ea580c)',
                  }}>
                    <span style={{ fontWeight: 600 }}>{operation.waiting_state.batch_state.items_collected}</span>
                    {operation.waiting_state.batch_state.items_target !== null && (
                      <>
                        <span style={{ fontSize: '9px', opacity: 0.8 }}>/{operation.waiting_state.batch_state.items_target} items</span>
                      </>
                    )}
                  </div>

                  {/* Timeout remaining */}
                  {operation.waiting_state.batch_state.timeout_remaining_seconds !== null && operation.waiting_state.batch_state.timeout_remaining_seconds !== undefined && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: operation.waiting_state.batch_state.timeout_remaining_seconds < 10 ? 'var(--color-warning-light)' : 'var(--color-text-secondary)',
                      fontWeight: operation.waiting_state.batch_state.timeout_remaining_seconds < 10 ? 600 : 400,
                    }}>
                      <span>⏱</span>
                      <span>{Math.round(operation.waiting_state.batch_state.timeout_remaining_seconds)}s</span>
                    </div>
                  )}
                </div>

                {/* Flush trigger indicator */}
                {!compactNodeView && operation.waiting_state.batch_state.will_flush && (
                  <div style={{
                    fontSize: '9px',
                    color: 'var(--color-text-tertiary)',
                    fontStyle: 'italic',
                  }}>
                    Will flush: {operation.waiting_state.batch_state.will_flush === 'on_size' ? 'on size' : operation.waiting_state.batch_state.will_flush === 'on_timeout' ? 'on timeout' : 'unknown'}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
});

LogicOperationsDisplay.displayName = 'LogicOperationsDisplay';

export default LogicOperationsDisplay;
