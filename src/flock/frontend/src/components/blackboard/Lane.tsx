/** One run as a lane: its header, then its artifacts left to right, arrows between. */

import React, { useState } from 'react';
import { prefersLessMotion } from '../graph/animatePositions';
import { clockTime, shortId } from '../graph/unfold/format';
import { Icon } from '../icons/Icon';
import ArtifactCard from './ArtifactCard';
import type { Lane as LaneModel, LaneColumn } from './lanes';
import styles from './Blackboard.module.css';

const StatusMark: React.FC<{ kind: LaneModel['status']['kind'] }> = ({ kind }) =>
  kind === 'running' ? (
    <span className="sdot run" aria-hidden="true" />
  ) : kind === 'review' ? (
    <span className={`hatch ${styles.reviewMark}`} aria-hidden="true" />
  ) : kind === 'failed' ? (
    <span className={styles.failedMark}>
      <Icon name="error" size={12} />
    </span>
  ) : (
    <Icon name="check" size={12} />
  );

/** Amber while what it leads to is being made; dashed when it is the route of unsure decisions. */
const Arrow: React.FC<{ column: LaneColumn }> = ({ column }) => (
  <div className={`${styles.arrow} ${column.activeIn ? styles.arrowActive : ''}`} aria-hidden="true">
    <svg width="26" height="10" viewBox="0 0 26 10">
      <line x1="0" y1="5" x2="22" y2="5" stroke="currentColor" strokeWidth="1.4" strokeDasharray={column.unsureIn ? '3 3' : undefined} />
      <path d="M18 1.5 L23 5 L18 8.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  </div>
);

/** `entering`: the lane arrived while the board showed; it fades in while the lanes below glide (#642). */
const Lane: React.FC<{ lane: LaneModel; entering?: boolean }> = ({ lane, entering = false }) => {
  const [opening, setOpening] = useState(() => entering && !prefersLessMotion());
  return (
    <div
      className={opening ? styles.entering : undefined}
      data-lane={lane.id}
      onAnimationEnd={(event) => {
        if (event.target === event.currentTarget) setOpening(false);
      }}
    >
      <section className={styles.lane} aria-label={`Run ${shortId(lane.id, 4) || 'without a correlation'}`} data-entering={opening || undefined}>
        <header className={styles.laneHead}>
          <span className={`mono ${styles.runLine}`}>
            <StatusMark kind={lane.status.kind} />
            run {shortId(lane.id, 4) || '—'} · {clockTime(lane.startedAt)}
          </span>
          {lane.title && <span className={styles.title}>{lane.title}</span>}
          <span
            className={
              lane.status.kind === 'running' ? styles.statusRunning : lane.status.kind === 'failed' ? styles.statusFailed : styles.status
            }
          >
            {lane.status.text}
          </span>
        </header>
        <div className={styles.columns}>
          {lane.columns.map((column, index) => (
            <React.Fragment key={index}>
              {index > 0 && <Arrow column={column} />}
              <div className={styles.column}>
                {column.cards.map((card) => (
                  <ArtifactCard key={card.id} card={card} />
                ))}
              </div>
            </React.Fragment>
          ))}
        </div>
      </section>
    </div>
  );
};

export default Lane;
