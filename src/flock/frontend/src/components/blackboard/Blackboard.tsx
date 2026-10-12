/**
 * The Blackboard view: the board's runs as lanes, or its artifacts as a graph
 * (docs/internal/design-system/README.md, Blackboard view). The table of every
 * artifact is the timeline dock's History.
 */

import React, { useMemo, useRef } from 'react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import BlackboardGraph from './BlackboardGraph';
import Lane from './Lane';
import { lanesOf } from './lanes';
import { useLaneMotion } from './useLaneMotion';
import styles from './Blackboard.module.css';

const Blackboard: React.FC = () => {
  const view = useUIStore((state) => state.blackboardView);
  const reviewOnly = useUIStore((state) => state.needsReviewOnly);
  const viewMode = useGraphStore((state) => state.viewMode);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const inFlight = useGraphStore((state) => state.inFlight);
  const settling = useGraphStore((state) => state.settling);
  const truncated = useGraphStore((state) => state.truncated);

  const lanes = useMemo(
    () =>
      // Until the Blackboard's snapshot is in, the store holds the Flow's
      viewMode === 'blackboard'
        ? lanesOf(
            nodes,
            edges,
            // Runs that ended keep their placeholders until their output is on the board (#642)
            [...inFlight.entries(), ...settling.entries()].map(([runId, run]) => ({
              runId,
              agent: run.agent,
              correlationId: run.correlationId ?? null,
              artifacts: run.artifacts,
              types: run.types,
              produces: run.produces,
              published: run.published,
            })),
          )
        : [],
    [viewMode, nodes, edges, inFlight, settling],
  );
  // Lanes that arrive while the board shows fade in (#642); those it first showed are just there
  const firstLanes = useRef<Set<string> | null>(null);
  if (firstLanes.current === null && lanes.length > 0) firstLanes.current = new Set(lanes.map((lane) => lane.id));

  // Lanes, and what is in them, glide instead of jumping (#642, #652)
  const lanesRef = useRef<HTMLDivElement>(null);
  const remeasure = useLaneMotion(lanesRef);
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
            aria-pressed={view === 'graph'}
            onClick={() => useUIStore.getState().setBlackboardView('graph')}
          >
            <Icon name="graph" size={15} />
            Graph
          </button>
        </div>
        <span className={`mono num ${styles.counts}`}>
          {lanes.length} run{lanes.length === 1 ? '' : 's'} · {artifacts} artifact{artifacts === 1 ? '' : 's'} · {review} need
          {review === 1 ? 's' : ''} review
          {view === 'graph' && truncated && ' · the newest 500, older ones in History'}
        </span>
        <span className={styles.spacer} />
        <button
          type="button"
          className={`chip ${reviewOnly ? styles.on : ''}`}
          aria-pressed={reviewOnly}
          onClick={() => useUIStore.getState().setNeedsReviewOnly(!reviewOnly)}
        >
          <span className={`hatch ${styles.reviewMark}`} aria-hidden="true" />
          Needs review only
        </button>
      </div>
      {view === 'graph' ? (
        <BlackboardGraph />
      ) : (
        <div className={`board ${styles.lanes}`} ref={lanesRef} onScroll={remeasure}>
          {shown.map((lane) => (
            <Lane key={lane.id} lane={lane} entering={firstLanes.current !== null && !firstLanes.current.has(lane.id)} />
          ))}
          {reviewOnly && shown.length === 0 && lanes.length > 0 && <p className={styles.note}>No run needs a review.</p>}
          {truncated && (
            <p className={styles.note}>The lanes hold the newest 500 artifacts; History in the timeline dock has the older ones.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default Blackboard;
