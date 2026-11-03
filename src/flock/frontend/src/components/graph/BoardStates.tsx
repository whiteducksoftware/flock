/**
 * What the board shows besides the graph: the connection banner, load
 * errors, the skeleton of the first load and the empty states.
 */

import React, { useEffect, useState } from 'react';
import { retryConnectionNow } from '../../services/websocket';
import { useFilterStore } from '../../store/filterStore';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { useWSStore } from '../../store/wsStore';
import { Icon } from '../icons/Icon';
import { liveState } from '../layout/connection';
import styles from './BoardStates.module.css';

/** Seconds until ``at``, counted down once a second. */
const useSecondsUntil = (at: number | null): number | null => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (at === null) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [at]);
  return at === null ? null : Math.max(0, Math.ceil((at - now) / 1000));
};

const ConnectionBanner: React.FC = () => {
  const status = useWSStore((state) => state.status);
  const attempts = useWSStore((state) => state.reconnectAttempts);
  const nextRetryAt = useWSStore((state) => state.nextRetryAt);
  const seconds = useSecondsUntil(nextRetryAt);
  const state = liveState(status, attempts);
  if (state !== 'reconnecting' && state !== 'offline') return null;

  return (
    <div className={`${styles.banner} ${styles.interactive}`}>
      <span className={`sdot ${state === 'offline' ? 'err' : ''} ${styles.waiting}`} aria-hidden />
      {state === 'offline' ? (
        <span>Offline · the board gets no updates</span>
      ) : (
        <>
          <span>
            {seconds === null ? 'Connection lost · reconnecting…' : `Connection lost · reconnecting in ${seconds} s`}
          </span>
          <span className={styles.quiet}>attempt {attempts}</span>
        </>
      )}
      <button type="button" className={`btn sm ${styles.end}`} onClick={retryConnectionNow}>
        Retry now
      </button>
    </div>
  );
};

const LoadError: React.FC<{ error: string }> = ({ error }) => (
  <div role="alert" className={`${styles.banner} ${styles.interactive}`}>
    <Icon name="error" size={14} style={{ color: 'var(--error)' }} />
    <span>The board could not load · {error}</span>
    <button
      type="button"
      className={`btn sm ${styles.end}`}
      // The store records a failed refresh as its error
      onClick={() => useGraphStore.getState().refreshCurrentView().catch(() => {})}
    >
      Retry
    </button>
  </div>
);

const Skeleton: React.FC = () => (
  <div role="status" aria-label="Loading the board" className={styles.skeleton}>
    {[0, 1].map((card) => (
      <div key={card} className={styles.card}>
        <span className="skel" style={{ height: 10, width: card ? '60%' : '70%' }} />
        <span className="skel" style={{ height: 8, width: card ? '85%' : '90%' }} />
        <span className="skel" style={{ height: 8, width: card ? '50%' : '60%' }} />
      </div>
    ))}
  </div>
);

const Empty: React.FC<{ onPublish: () => void }> = ({ onPublish }) => {
  // null: the blackboard's size is unknown (its summary did not load)
  const total = useFilterStore((state) => state.summary?.total ?? null);
  const mode = useUIStore((state) => state.mode);

  const showAll = () => {
    useFilterStore.getState().clearFilters();
    useFilterStore.getState().setTimeRange({ preset: 'all' });
  };

  let title = 'Nothing on the blackboard yet';
  let hint = 'Publish an artifact to start the first run.';
  let action = (
    <button type="button" className="btn primary sm" onClick={onPublish}>
      Publish
    </button>
  );
  if (total === null) {
    title = 'Nothing to show here';
    hint = 'No artifacts in this view.';
    action = (
      <button type="button" className="btn sm" onClick={showAll}>
        Show all
      </button>
    );
  } else if (total > 0 && mode === 'blackboard') {
    title = 'Nothing matches these filters';
    hint = `${total} artifacts are on the blackboard.`;
    action = (
      <button type="button" className="btn sm" onClick={showAll}>
        Show all
      </button>
    );
  } else if (total > 0) {
    // The Flow view shows every agent the flock has, whatever the filters
    title = 'No agents yet';
    hint = 'Agents appear here once the flock registers them.';
  }

  return (
    <div className={`${styles.empty} ${styles.interactive}`}>
      <span className={styles.title}>{title}</span>
      <span className={styles.hint}>{hint}</span>
      {action}
    </div>
  );
};

const BoardStates: React.FC<{ onPublish: () => void }> = ({ onPublish }) => {
  const hasNodes = useGraphStore((state) => state.nodes.length > 0);
  const isLoading = useGraphStore((state) => state.isLoading);
  const error = useGraphStore((state) => state.error);

  return (
    <div className={styles.layer}>
      <div className={styles.banners}>
        <ConnectionBanner />
        {error && <LoadError error={error} />}
      </div>
      {!hasNodes && isLoading && <Skeleton />}
      {!hasNodes && !isLoading && !error && <Empty onPublish={onPublish} />}
    </div>
  );
};

export default BoardStates;
