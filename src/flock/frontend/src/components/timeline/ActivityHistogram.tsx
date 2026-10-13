/**
 * Artifacts over time as bars, with the time filter as a brush on them:
 * drag across the bars to set it. Errors are coral marks; the right edge is now.
 */

import React, { useRef, useState } from 'react';
import { useFilterStore } from '../../store/filterStore';
import { type Domain, brushOf, rangeFromBrush, ticksOf } from './activity';
import type { Activity } from './useActivity';
import styles from './TimelineDock.module.css';

interface ActivityHistogramProps {
  activity: Activity | null;
  domain: Domain;
  /** Bar area height in px */
  height: number;
  ticks?: boolean;
}

const ActivityHistogram: React.FC<ActivityHistogramProps> = ({ activity, domain, height, ticks = false }) => {
  const timeRange = useFilterStore((state) => state.timeRange);
  const setTimeRange = useFilterStore((state) => state.setTimeRange);
  const area = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const counts = activity?.counts ?? [];
  const max = Math.max(1, ...counts);
  const brush = drag
    ? { from: Math.min(drag.from, drag.to), to: Math.max(drag.from, drag.to) }
    : brushOf(timeRange, domain, domain.end);
  const span = domain.end - domain.start;

  const shareAt = (clientX: number) => {
    const rect = area.current!.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - rect.left) / Math.max(1, rect.width)));
  };

  const onPointerDown = (event: React.PointerEvent) => {
    if (event.button !== 0) return;
    area.current?.setPointerCapture?.(event.pointerId);
    const at = shareAt(event.clientX);
    setDrag({ from: at, to: at });
  };
  const onPointerMove = (event: React.PointerEvent) => {
    if (drag) setDrag({ ...drag, to: shareAt(event.clientX) });
  };
  const onPointerUp = (event: React.PointerEvent) => {
    if (!drag) return;
    const to = shareAt(event.clientX);
    const from = Math.min(drag.from, to);
    const end = Math.max(drag.from, to);
    setDrag(null);
    // A click is not a brush
    if (end - from < 0.01) return;
    const bucketMs = (activity?.bucketSeconds ?? span / 60_000) * 1000;
    setTimeRange(rangeFromBrush(domain.start + from * span, domain.start + end * span, domain.end, bucketMs));
  };

  return (
    <div className={styles.histogram}>
      <div
        ref={area}
        className={styles.bars}
        style={{ height }}
        role="group"
        aria-label="Activity: drag across the bars to set the time filter"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        data-testid="activity"
      >
        {counts.map((count, index) => (
          <div
            key={index}
            className={styles.bar}
            data-in={(index + 0.5) / counts.length >= brush.from && (index + 0.5) / counts.length <= brush.to ? '' : undefined}
            style={{ height: `${Math.max(count > 0 ? 8 : 4, (count / max) * 100)}%` }}
            title={`${count} artifact${count === 1 ? '' : 's'}`}
          />
        ))}
        {activity?.errors.map((errors, index) =>
          errors > 0 ? (
            <span
              key={`e${index}`}
              className={styles.error}
              style={{ left: `${((index + 0.5) / counts.length) * 100}%` }}
              title={`${errors} error${errors === 1 ? '' : 's'}`}
            />
          ) : null,
        )}
        <div
          className={styles.brush}
          aria-hidden
          data-testid="brush"
          style={{ left: `${brush.from * 100}%`, right: `${(1 - brush.to) * 100}%` }}
        />
        <span className={styles.now} aria-hidden />
      </div>
      {ticks && (
        <div className={`mono num ${styles.ticks}`}>
          {ticksOf(domain, 5).map((tick) => (
            <span key={tick.at} className={tick.label === 'now' ? styles.nowLabel : undefined}>
              {tick.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default ActivityHistogram;
