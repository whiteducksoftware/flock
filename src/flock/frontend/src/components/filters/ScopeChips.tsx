/**
 * Scope chips: the header's view of the active filters. The time chip opens
 * the time range, each active filter is a chip that removes it, and + Filter
 * opens every facet with the saved presets (Ctrl+Shift+F).
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { formatTimeRange, useFilterStore, type ActiveFilter } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import { shortTypeName } from '../../utils/typeName';
import { Icon } from '../icons/Icon';
import ArtifactTypeFilter from './ArtifactTypeFilter';
import CorrelationIDFilter from './CorrelationIDFilter';
import ProducerFilter from './ProducerFilter';
import SavedFiltersControl from './SavedFiltersControl';
import TagFilter from './TagFilter';
import TimeRangeFilter from './TimeRangeFilter';
import VisibilityFilter from './VisibilityFilter';
import styles from './ScopeChips.module.css';

interface ScopeChip {
  filter: ActiveFilter;
  facet: string;
  value: string;
  shown: string;
}

const FACETS: [string, React.FC][] = [
  ['Presets', SavedFiltersControl],
  ['Correlation', CorrelationIDFilter],
  ['Artifact types', ArtifactTypeFilter],
  ['Producers', ProducerFilter],
  ['Tags', TagFilter],
  ['Visibility', VisibilityFilter],
];

const ScopeChips: React.FC = () => {
  const showFilters = useSettingsStore((state) => state.ui.showFilters);
  const setShowFilters = useSettingsStore((state) => state.setShowFilters);
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const types = useFilterStore((state) => state.selectedArtifactTypes);
  const producers = useFilterStore((state) => state.selectedProducers);
  const tags = useFilterStore((state) => state.selectedTags);
  const visibility = useFilterStore((state) => state.selectedVisibility);
  const removeFilter = useFilterStore((state) => state.removeFilter);
  const [showTime, setShowTime] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  const chips = useMemo(() => {
    const result: ScopeChip[] = [];
    const add = (filter: ActiveFilter, facet: string, shown: string) =>
      result.push({ filter, facet, value: String(filter.value), shown });
    if (correlationId) {
      add(
        { type: 'correlationId', value: correlationId, label: `Correlation ID: ${correlationId}` },
        'Correlation',
        correlationId.slice(0, 8),
      );
    }
    types.forEach((type) =>
      add({ type: 'artifactTypes', value: type, label: `Type: ${type}` }, 'Type', shortTypeName(type)),
    );
    producers.forEach((producer) =>
      add({ type: 'producers', value: producer, label: `Producer: ${producer}` }, 'Producer', producer),
    );
    tags.forEach((tag) => add({ type: 'tags', value: tag, label: `Tag: ${tag}` }, 'Tag', tag));
    visibility.forEach((kind) =>
      add({ type: 'visibility', value: kind, label: `Visibility: ${kind}` }, 'Visibility', kind),
    );
    return result;
  }, [correlationId, types, producers, tags, visibility]);

  // One popover at a time, also when a shortcut opens the filters
  useEffect(() => {
    if (showFilters) setShowTime(false);
  }, [showFilters]);

  // A click elsewhere closes the open popover; Esc closes the time range
  // (the dashboard's Esc closes the filters)
  useEffect(() => {
    if (!showFilters && !showTime) return;
    const onMouseDown = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) {
        setShowFilters(false);
        setShowTime(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setShowTime(false);
    };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [showFilters, showTime, setShowFilters]);

  return (
    <div ref={root} className={styles.scope}>
      <button
        type="button"
        className="chip"
        aria-haspopup="dialog"
        aria-expanded={showTime}
        onClick={() => {
          setShowTime(!showTime);
          setShowFilters(false);
        }}
      >
        <Icon name="scheduled" size={14} />
        <span>{formatTimeRange(timeRange)}</span>
        <Icon name="chevronDown" size={12} />
      </button>

      {chips.length > 0 && (
        <ul className={styles.chips} role="list" aria-label="Active filters">
          {chips.map(({ filter, facet, value, shown }) => (
            <li key={`${filter.type}:${value}`} className={`chip ${styles.chip}`} title={`${facet}: ${value}`}>
              <span className={styles.facet}>{facet}</span>
              <span className={styles.value}>{shown}</span>
              <button
                type="button"
                className={styles.remove}
                aria-label={`Remove ${facet} ${value}`}
                onClick={() => removeFilter(filter)}
              >
                <Icon name="close" size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        className="chip add"
        aria-haspopup="dialog"
        aria-expanded={showFilters}
        title="Filters (Ctrl+Shift+F)"
        onClick={() => {
          setShowFilters(!showFilters);
          setShowTime(false);
        }}
      >
        <Icon name="plus" size={13} />
        <span>Filter</span>
      </button>

      {showTime && (
        <div className={`${styles.popover} ${styles.time}`} role="dialog" aria-label="Time range">
          {/* A preset is a choice; a custom range needs its dates */}
          <TimeRangeFilter onPreset={(preset) => preset !== 'custom' && setShowTime(false)} />
        </div>
      )}

      {showFilters && (
        <div className={styles.popover} role="dialog" aria-label="Filters">
          {FACETS.map(([title, Facet]) => (
            <section key={title} className={styles.section}>
              <h3 className={styles.heading}>{title}</h3>
              <Facet />
            </section>
          ))}
        </div>
      )}
    </div>
  );
};

export default ScopeChips;
