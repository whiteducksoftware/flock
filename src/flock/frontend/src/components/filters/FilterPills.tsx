import React from 'react';
import { useFilterStore } from '../../store/filterStore';
import styles from './FilterPills.module.css';

const FilterPills: React.FC = () => {
  // Select the actual state values for reactivity, then derive filters
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const removeFilter = useFilterStore((state) => state.removeFilter);

  // Derive active filters from state
  const activeFilters: Array<{ type: 'correlationId' | 'timeRange'; value: any; label: string }> = [];

  if (correlationId) {
    activeFilters.push({
      type: 'correlationId',
      value: correlationId,
      label: `Correlation ID: ${correlationId}`,
    });
  }

  if (timeRange.preset !== 'last10min') {
    const formatTimeRange = (range: typeof timeRange): string => {
      if (range.preset === 'last5min') return 'Last 5 min';
      if (range.preset === 'last10min') return 'Last 10 min';
      if (range.preset === 'last1hour') return 'Last hour';
      if (range.preset === 'custom' && range.start && range.end) {
        const startDate = new Date(range.start).toLocaleString();
        const endDate = new Date(range.end).toLocaleString();
        return `${startDate} - ${endDate}`;
      }
      return 'Unknown';
    };

    activeFilters.push({
      type: 'timeRange',
      value: timeRange,
      label: `Time: ${formatTimeRange(timeRange)}`,
    });
  }

  if (activeFilters.length === 0) {
    return null;
  }

  return (
    <div className={styles.container}>
      {activeFilters.map((filter, index) => (
        <div
          key={filter.type}
          className={`${styles.pill} ${index === 1 ? styles.pillSecondary : ''}`}
        >
          <span className={styles.pillLabel}>{filter.label}</span>
          <button
            onClick={() => removeFilter(filter.type)}
            aria-label={`Remove ${filter.type} filter`}
            className={styles.removeButton}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};

export default FilterPills;
