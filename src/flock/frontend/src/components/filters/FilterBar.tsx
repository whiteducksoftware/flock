import React from 'react';
import CorrelationIDFilter from './CorrelationIDFilter';
import TimeRangeFilter from './TimeRangeFilter';
import ArtifactTypeFilter from './ArtifactTypeFilter';
import ProducerFilter from './ProducerFilter';
import TagFilter from './TagFilter';
import VisibilityFilter from './VisibilityFilter';
import SavedFiltersControl from './SavedFiltersControl';
import FilterPills from './FilterPills';
import styles from './FilterBar.module.css';

const FilterBar: React.FC = () => {
  return (
    <div className={styles.filterBar}>
      {/* Filter Controls */}
      <div className={styles.filterControls}>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Correlation ID</label>
          <CorrelationIDFilter />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Time Range</label>
          <TimeRangeFilter />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Artifact Types</label>
          <ArtifactTypeFilter />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Producers</label>
          <ProducerFilter />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Tags</label>
          <TagFilter />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Visibility</label>
          <VisibilityFilter />
        </div>

        <div className={`${styles.filterGroup} ${styles.savedFilters}`}>
          <label className={styles.filterLabel}>Saved Presets</label>
          <SavedFiltersControl />
        </div>
      </div>

      <FilterPills />
    </div>
  );
};

export default FilterBar;
