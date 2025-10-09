import React from 'react';
import { useFilterStore } from '../../store/filterStore';
import styles from './FilterPills.module.css';

const FilterPills: React.FC = () => {
  const activeFilters = useFilterStore((state) => state.getActiveFilters());
  const removeFilter = useFilterStore((state) => state.removeFilter);

  if (activeFilters.length === 0) {
    return null;
  }

  return (
    <div className={styles.container}>
      {activeFilters.map((filter, index) => (
        <div
          key={`${filter.type}-${String(filter.value)}-${index}`}
          className={`${styles.pill} ${index % 2 === 1 ? styles.pillSecondary : ''}`}
        >
          <span className={styles.pillLabel}>{filter.label}</span>
          <button
            onClick={() => removeFilter(filter)}
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
