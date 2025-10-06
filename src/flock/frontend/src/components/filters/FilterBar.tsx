import React from 'react';
import CorrelationIDFilter from './CorrelationIDFilter';
import TimeRangeFilter from './TimeRangeFilter';
import FilterPills from './FilterPills';
import styles from './FilterBar.module.css';

const FilterBar: React.FC = () => {
  return (
    <div className={styles.filterBar}>
      {/* Filter Controls */}
      <div className={styles.filterControls}>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>
            Correlation ID
          </label>
          <CorrelationIDFilter />
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>
            Time Range
          </label>
          <TimeRangeFilter />
        </div>
      </div>

      {/* Active Filter Pills */}
      <FilterPills />
    </div>
  );
};

export default FilterBar;
