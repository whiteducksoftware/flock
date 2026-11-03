import React from 'react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { useWSStore } from '../../store/wsStore';
import { liveState } from './connection';
import styles from './LiveStatus.module.css';

/** The header's connection status, with the agents and how many run. */
const LiveStatus: React.FC = () => {
  const mode = useUIStore((state) => state.mode);
  const status = useWSStore((state) => state.status);
  const attempts = useWSStore((state) => state.reconnectAttempts);
  const agents = useGraphStore((state) => state.nodes.filter((node) => node.type === 'agent').length);
  const running = useGraphStore(
    (state) => [...state.agentStatus.values()].filter((value) => value === 'running').length,
  );
  const state = liveState(status, attempts);

  // Only the Flow view shows agents
  const meta =
    mode === 'agent'
      ? [agents > 0 && `${agents} agents`, running > 0 && `${running} running`].filter(Boolean).join(' · ')
      : '';

  return (
    <div role="status" aria-live="polite" className={styles.status}>
      {state === 'live' && (
        <>
          <span className={`sdot ${running > 0 ? 'run' : ''} ${styles.dot}`} aria-hidden />
          <span>Live</span>
          {meta && <span className={styles.meta}>{meta}</span>}
        </>
      )}
      {state === 'connecting' && (
        <>
          <span className={`sdot ${styles.dot}`} aria-hidden />
          <span>Connecting</span>
        </>
      )}
      {state === 'reconnecting' && (
        <>
          <span className={`sdot ${styles.dot} ${styles.waiting}`} aria-hidden />
          <span>Reconnecting ({attempts})</span>
        </>
      )}
      {state === 'offline' && (
        <>
          <span className={`sdot err ${styles.dot}`} aria-hidden />
          <span>Offline</span>
        </>
      )}
    </div>
  );
};

export default LiveStatus;
