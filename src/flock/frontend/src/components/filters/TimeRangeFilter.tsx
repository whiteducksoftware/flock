import React from 'react';
import { useFilterStore } from '../../store/filterStore';
import { TimeRangePreset } from '../../types/filters';
import styles from './TimeRangeFilter.module.css';

const TimeRangeFilter: React.FC = () => {
  const timeRange = useFilterStore((state) => state.timeRange);
  const setTimeRange = useFilterStore((state) => state.setTimeRange);

  const handlePresetClick = (preset: TimeRangePreset) => {
    if (preset === 'custom') {
      // Initialize custom range with last hour
      const end = Date.now();
      const start = end - 3600000; // 1 hour ago
      setTimeRange({ preset: 'custom', start, end });
    } else {
      setTimeRange({ preset });
    }
  };

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const start = new Date(e.target.value).getTime();
    setTimeRange({
      preset: 'custom',
      start,
      end: timeRange.end || Date.now(),
    });
  };

  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const end = new Date(e.target.value).getTime();
    setTimeRange({
      preset: 'custom',
      start: timeRange.start || Date.now() - 3600000,
      end,
    });
  };

  const formatDateTimeLocal = (timestamp: number): string => {
    return new Date(timestamp).toISOString().slice(0, 16);
  };

  const presets: { preset: TimeRangePreset; label: string }[] = [
    { preset: 'all', label: 'All' },
    { preset: 'last5min', label: 'Last 5 min' },
    { preset: 'last10min', label: 'Last 10 min' },
    { preset: 'last1hour', label: 'Last hour' },
    { preset: 'custom', label: 'Custom' },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.presetButtons}>
        {presets.map(({ preset, label }) => (
          <button
            key={preset}
            onClick={() => handlePresetClick(preset)}
            className={[
              styles.presetButton,
              preset === 'all' ? styles.presetButtonAll : '',
              timeRange.preset === preset ? styles.active : '',
            ].filter(Boolean).join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {timeRange.preset === 'custom' && (
        <div className={styles.customRange}>
          <div className={styles.dateInputGroup}>
            <label
              htmlFor="start-time"
              className={styles.dateLabel}
            >
              Start
            </label>
            <input
              id="start-time"
              type="datetime-local"
              value={
                timeRange.start ? formatDateTimeLocal(timeRange.start) : ''
              }
              onChange={handleStartChange}
              className={styles.dateInput}
            />
          </div>

          <div className={styles.dateInputGroup}>
            <label
              htmlFor="end-time"
              className={styles.dateLabel}
            >
              End
            </label>
            <input
              id="end-time"
              type="datetime-local"
              value={timeRange.end ? formatDateTimeLocal(timeRange.end) : ''}
              onChange={handleEndChange}
              className={styles.dateInput}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default TimeRangeFilter;
