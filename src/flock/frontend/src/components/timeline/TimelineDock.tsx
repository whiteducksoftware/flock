/**
 * The timeline dock at the bottom of the board. Collapsed: the activity over
 * time, whose brush is the time filter. Expanded: traces, the artifact
 * history, metrics and the tracing settings
 * (docs/internal/design-system/README.md, Layout and Where everything went).
 */

import React, { useId } from 'react';
import { formatTimeRange, useFilterStore } from '../../store/filterStore';
import { type DockTab, useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import { nextTab } from '../graph/tabKeys';
import HistoricalArtifactsModule from '../modules/HistoricalArtifactsModule';
import TraceModuleJaeger from '../modules/TraceModuleJaeger';
import ActivityHistogram from './ActivityHistogram';
import { useActivity } from './useActivity';
import styles from './TimelineDock.module.css';

const TABS: { key: DockTab; label: string }[] = [
  { key: 'traces', label: 'Traces' },
  { key: 'history', label: 'History' },
  { key: 'metrics', label: 'Metrics' },
  { key: 'settings', label: 'Tracing settings' },
];

/** Bars of the histogram: one per minute of the last hour. */
const BUCKETS = 60;

const TimelineDock: React.FC = () => {
  const open = useUIStore((state) => state.dockOpen);
  const tab = useUIStore((state) => state.dockTab);
  const traceSearch = useUIStore((state) => state.traceSearch);
  const timeRange = useFilterStore((state) => state.timeRange);
  const { activity, domain } = useActivity(BUCKETS);
  const tabIds = useId();
  const range = formatTimeRange(timeRange);

  if (!open) {
    return (
      <footer aria-label="Timeline" className={styles.collapsed}>
        <div className={styles.summary}>
          <span className={styles.title}>
            Activity <span className={styles.faint}>· last hour</span>
          </span>
          <span className={`mono num ${styles.faint} ${styles.count}`}>
            {activity ? `${activity.total} artifact${activity.total === 1 ? '' : 's'}` : 'Loading…'}
          </span>
        </div>
        <div className={styles.middle}>
          <ActivityHistogram activity={activity} domain={domain} height={36} ticks />
        </div>
        <div className={styles.actions}>
          <button type="button" className="btn ghost" onClick={() => useUIStore.getState().openDock('history')}>
            <Icon name="history" size={15} />
            <span>History</span>
          </button>
          <button type="button" className="btn ghost" onClick={() => useUIStore.getState().openDock('traces')}>
            <Icon name="traces" size={15} />
            <span>Traces</span>
          </button>
          <button
            type="button"
            className="btn icon ghost"
            aria-label="Expand timeline dock"
            onClick={() => useUIStore.getState().openDock(tab)}
          >
            <Icon name="chevronUp" size={15} />
          </button>
        </div>
      </footer>
    );
  }

  return (
    <section aria-label="Timeline dock" className={styles.dock}>
      <div className={styles.head}>
        <div role="tablist" aria-label="Timeline dock" className={styles.tabs}>
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              role="tab"
              id={`${tabIds}-${key}`}
              aria-selected={tab === key}
              aria-controls={`${tabIds}-panel`}
              tabIndex={tab === key ? 0 : -1}
              className={styles.tab}
              onClick={() => useUIStore.getState().openDock(key)}
              onKeyDown={(event) => {
                const next = nextTab(
                  TABS.map((entry) => entry.key),
                  tab,
                  event.key,
                );
                if (!next) return;
                event.preventDefault();
                useUIStore.getState().openDock(next);
                document.getElementById(`${tabIds}-${next}`)?.focus();
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className={styles.mini}>
          <ActivityHistogram activity={activity} domain={domain} height={26} />
          <span className={`mono num ${styles.faint}`}>{range}</span>
        </div>
        <button
          type="button"
          className="btn icon ghost"
          aria-label="Collapse timeline dock"
          onClick={() => useUIStore.getState().closeDock()}
        >
          <Icon name="chevronDown" size={15} />
        </button>
      </div>
      <div id={`${tabIds}-panel`} role="tabpanel" aria-labelledby={`${tabIds}-${tab}`} tabIndex={0} className={styles.body}>
        {/* Keyed by the search, so a trace link opens on its correlation */}
        {tab === 'traces' && <TraceModuleJaeger key={traceSearch} views={['timeline', 'statistics']} search={traceSearch} />}
        {tab === 'history' && <HistoricalArtifactsModule />}
        {tab === 'metrics' && <TraceModuleJaeger views={['metrics', 'dependencies']} />}
        {tab === 'settings' && <TraceModuleJaeger views={['configuration', 'guide']} />}
      </div>
    </section>
  );
};

export default TimelineDock;
