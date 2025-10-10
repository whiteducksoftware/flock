import React from 'react';
import CorrelationIDFilter from './CorrelationIDFilter';
import TimeRangeFilter from './TimeRangeFilter';
import ArtifactTypeFilter from './ArtifactTypeFilter';
import ProducerFilter from './ProducerFilter';
import TagFilter from './TagFilter';
import VisibilityFilter from './VisibilityFilter';
import SavedFiltersControl from './SavedFiltersControl';
import styles from './FilterFlyout.module.css';

interface FilterFlyoutProps {
  onClose: () => void;
}

const FilterFlyout: React.FC<FilterFlyoutProps> = ({ onClose }) => {
  return (
    <aside className={styles.panel} role="dialog" aria-label="Filters">
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>Filters</h2>
          <p className={styles.subtitle}>Slice historical data without losing your place.</p>
        </div>
        <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Close filters">
          ×
        </button>
      </header>

      <div className={styles.content}>
        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Presets</h3>
          <SavedFiltersControl />
        </section>

        <div className={styles.separator} role="presentation" />

        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Correlation</h3>
          <CorrelationIDFilter />
        </section>

        <div className={styles.separator} role="presentation" />

        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Time Range</h3>
          <TimeRangeFilter />
        </section>

        <div className={styles.separator} role="presentation" />

        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Artifact Types</h3>
          <ArtifactTypeFilter />
        </section>

        <div className={styles.separator} role="presentation" />

        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Producers</h3>
          <ProducerFilter />
        </section>

        <div className={styles.separator} role="presentation" />

        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Tags</h3>
          <TagFilter />
        </section>

        <div className={styles.separator} role="presentation" />

        <section className={styles.section}>
          <h3 className={styles.sectionLabel}>Visibility</h3>
          <VisibilityFilter />
        </section>
      </div>
    </aside>
  );
};

export default FilterFlyout;
