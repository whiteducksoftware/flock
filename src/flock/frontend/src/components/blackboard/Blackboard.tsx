/**
 * The Blackboard view: the board's runs as lanes, or the table of every
 * artifact (docs/internal/design-system/README.md, Blackboard view).
 */

import React, { useMemo } from 'react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import HistoricalArtifactsModule from '../modules/HistoricalArtifactsModule';
import Lane from './Lane';
import { lanesOf } from './lanes';
import styles from './Blackboard.module.css';

const Blackboard: React.FC = () => {
  const view = useUIStore((state) => state.blackboardView);
  const reviewOnly = useUIStore((state) => state.needsReviewOnly);
  const viewMode = useGraphStore((state) => state.viewMode);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const inFlight = useGraphStore((state) => state.inFlight);
  const truncated = useGraphStore((state) => state.truncated);

  const lanes = useMemo(
    () =>
      // Until the Blackboard's snapshot is in, the store holds the Flow's
      viewMode === 'blackboard'
        ? lanesOf(
            nodes,
            edges,
            [...inFlight.entries()].map(([runId, run]) => ({
              runId,
              agent: run.agent,
              correlationId: run.correlationId ?? null,
              artifacts: run.artifacts,
            })),
          )
        : [],
    [viewMode, nodes, edges, inFlight],
  );
  const shown = reviewOnly ? lanes.filter((lane) => lane.needsReview) : lanes;
  const artifacts = lanes.reduce((sum, lane) => sum + lane.count, 0);
  const review = lanes.filter((lane) => lane.needsReview).length;

  return (
    <div className={styles.view}>
      <div className={styles.toolbar}>
        <div className={styles.segs} role="group" aria-label="Show as">
          <button
            type="button"
            className="seg"
            aria-pressed={view === 'lanes'}
            onClick={() => useUIStore.getState().setBlackboardView('lanes')}
          >
            <Icon name="lanes" size={15} />
            Lanes
          </button>
          <button
            type="button"
            className="seg"
            aria-pressed={view === 'table'}
            onClick={() => useUIStore.getState().setBlackboardView('table')}
          >
            <Icon name="table" size={15} />
            Table
          </button>
        </div>
        {view === 'lanes' && (
          <span className={`mono num ${styles.counts}`}>
            {lanes.length} run{lanes.length === 1 ? '' : 's'} · {artifacts} artifact{artifacts === 1 ? '' : 's'} · {review} need
            {review === 1 ? 's' : ''} review
          </span>
        )}
        <span className={styles.spacer} />
        {view === 'lanes' && (
          <button
            type="button"
            className={`chip ${reviewOnly ? styles.on : ''}`}
            aria-pressed={reviewOnly}
            onClick={() => useUIStore.getState().setNeedsReviewOnly(!reviewOnly)}
          >
            <span className={`hatch ${styles.reviewMark}`} aria-hidden="true" />
            Needs review only
          </button>
        )}
      </div>
      {view === 'table' ? (
        <div className={styles.table}>
          <HistoricalArtifactsModule />
        </div>
      ) : (
        <div className={`board ${styles.lanes}`}>
          {shown.map((lane) => (
            <Lane key={lane.id} lane={lane} />
          ))}
          {reviewOnly && shown.length === 0 && lanes.length > 0 && <p className={styles.note}>No run needs a review.</p>}
          {truncated && <p className={styles.note}>The lanes hold the newest 500 artifacts; the table has the older ones.</p>}
        </div>
      )}
    </div>
  );
};

export default Blackboard;
