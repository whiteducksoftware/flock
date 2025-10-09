import React from 'react';
import { useMemo } from 'react';
import { useFilterStore, formatTimeRange } from '../../store/filterStore';
import styles from './FilterPills.module.css';

const extractLabelParts = (label: string) => {
  const match = label.match(/^([^:]+):(.*)$/);
  const title = match?.[1]?.trim() ?? label.trim();
  const value = match?.[2]?.trim() ?? '';

  return { title, value };
};

const FilterPills: React.FC = () => {
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const selectedArtifactTypes = useFilterStore((state) => state.selectedArtifactTypes);
  const selectedProducers = useFilterStore((state) => state.selectedProducers);
  const selectedTags = useFilterStore((state) => state.selectedTags);
  const selectedVisibility = useFilterStore((state) => state.selectedVisibility);
  const removeFilter = useFilterStore((state) => state.removeFilter);

  const activeFilters = useMemo(() => {
    const filters = [];
    if (correlationId) {
      filters.push({
        type: 'correlationId' as const,
        value: correlationId,
        label: `Correlation ID: ${correlationId}`,
      });
    }

    filters.push({
      type: 'timeRange' as const,
      value: timeRange,
      label: `Time: ${formatTimeRange(timeRange)}`,
    });

    selectedArtifactTypes.forEach((type) => {
      filters.push({
        type: 'artifactTypes' as const,
        value: type,
        label: `Type: ${type}`,
      });
    });

    selectedProducers.forEach((producer) => {
      filters.push({
        type: 'producers' as const,
        value: producer,
        label: `Producer: ${producer}`,
      });
    });

    selectedTags.forEach((tag) => {
      filters.push({
        type: 'tags' as const,
        value: tag,
        label: `Tag: ${tag}`,
      });
    });

    selectedVisibility.forEach((visibilityKind) => {
      filters.push({
        type: 'visibility' as const,
        value: visibilityKind,
        label: `Visibility: ${visibilityKind}`,
      });
    });

    return filters;
  }, [correlationId, timeRange, selectedArtifactTypes, selectedProducers, selectedTags, selectedVisibility]);

  if (activeFilters.length === 0) {
    return null;
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.container} role="list">
        {activeFilters.map((filter, index) => {
          const labelValue =
            filter.type === 'timeRange' && typeof filter.value !== 'string'
              ? `Time: ${formatTimeRange(filter.value)}`
              : filter.label;

          const { title, value } = extractLabelParts(labelValue);
          const accessibleDescriptor = value ? `${title} ${value}` : title;

          return (
            <div
              key={`${filter.type}-${String(filter.value)}-${index}`}
              className={styles.pill}
              data-filter-type={filter.type}
              role="listitem"
            >
              <span className={styles.pillAccent} aria-hidden="true" />
              <div className={styles.textGroup}>
                <span className={styles.pillTitle}>{title}</span>
                {value && <span className={styles.pillValue}>{value}</span>}
              </div>
              <button
                onClick={() => removeFilter(filter)}
                aria-label={`Remove ${accessibleDescriptor} filter`}
                className={styles.removeButton}
                type="button"
              >
                <span aria-hidden="true" className={styles.removeIcon}>
                  ×
                </span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default FilterPills;
