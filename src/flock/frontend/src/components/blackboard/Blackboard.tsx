/**
 * The Blackboard view: the board's runs as lanes, or its artifacts as a graph
 * (docs/internal/design-system/README.md, Blackboard view). The table of every
 * artifact is the timeline dock's History.
 */

import React, { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { prefersLessMotion } from '../graph/animatePositions';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import BlackboardGraph from './BlackboardGraph';
import Lane from './Lane';
import { lanesOf } from './lanes';
import styles from './Blackboard.module.css';

/** How far a glide moves an element right now (its transform's vertical offset) */
function translateY(element: HTMLElement): number {
  const transform = getComputedStyle(element).transform;
  if (!transform || transform === 'none') return 0;
  const values = transform.slice(transform.indexOf('(') + 1, -1).split(',').map(Number);
  return (transform.startsWith('matrix3d') ? values[13] : values[5]) ?? 0;
}

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

  // A lane that arrives or grows (a card arrives, one unfolds) moves the lanes
  // below: they glide from where they show instead of jumping (FLIP). Measured
  // on screen without the glide's own offset, so a scroll position the browser
  // keeps (scroll anchoring) moves nothing, and a glide that is interrupted
  // continues from where the lane is. A scroll measures again: it moves no lane.
  // A lane that changes its size while the board does not render (a card
  // unfolds, its details arrive) moves the lanes below as well (ResizeObserver)
  const lanesRef = useRef<HTMLDivElement>(null);
  const tops = useRef(new Map<string, number>());
  const glides = useRef(new Map<string, Animation>());
  const measure = () => {
    const now = new Map<string, number>();
    for (const slot of lanesRef.current?.querySelectorAll<HTMLElement>('[data-lane]') ?? []) {
      now.set(slot.dataset.lane!, slot.getBoundingClientRect().top - translateY(slot));
    }
    return now;
  };
  const flip = () => {
    const before = tops.current;
    const now = measure();
    for (const slot of lanesRef.current?.querySelectorAll<HTMLElement>('[data-lane]') ?? []) {
      const id = slot.dataset.lane!;
      const top = now.get(id)!;
      const was = before.get(id);
      if (was === undefined || Math.abs(was - top) < 1 || prefersLessMotion() || typeof slot.animate !== 'function') continue;
      // From where it shows: the running glide's offset, read before it is cancelled
      const offset = translateY(slot);
      glides.current.get(id)?.cancel();
      const glide = slot.animate([{ transform: `translateY(${was - top + offset}px)` }, { transform: 'translateY(0)' }], {
        duration: 320,
        easing: 'cubic-bezier(0.35, 0, 0.25, 1)',
      });
      glide.onfinish = () => {
        if (glides.current.get(id) === glide) glides.current.delete(id);
      };
      glides.current.set(id, glide);
    }
    // A lane that left takes its glide along
    for (const [id, glide] of glides.current) {
      if (now.has(id)) continue;
      glide.cancel();
      glides.current.delete(id);
    }
    tops.current = now;
  };
  const resizes = useRef<ResizeObserver | null>(null);
  const watched = useRef(new Set<Element>());
  const watch = () => {
    const observer = resizes.current;
    if (!observer) return;
    const slots = new Set<Element>(lanesRef.current?.querySelectorAll('[data-lane]') ?? []);
    for (const slot of watched.current) if (!slots.has(slot)) observer.unobserve(slot);
    for (const slot of slots) if (!watched.current.has(slot)) observer.observe(slot);
    watched.current = slots;
  };
  useLayoutEffect(() => {
    flip();
    watch();
  });
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    resizes.current = new ResizeObserver(() => flip());
    watch();
    return () => {
      resizes.current?.disconnect();
      resizes.current = null;
      watched.current = new Set();
    };
    // Once: flip and watch read refs only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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
        <div className={`board ${styles.lanes}`} ref={lanesRef} onScroll={() => (tops.current = measure())}>
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
