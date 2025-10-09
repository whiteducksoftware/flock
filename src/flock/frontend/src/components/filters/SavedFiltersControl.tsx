import React, { useEffect, useRef, useState } from 'react';
import { indexedDBService } from '../../services/indexeddb';
import { useFilterStore } from '../../store/filterStore';
import styles from './SavedFiltersControl.module.css';

const SavedFiltersControl: React.FC = () => {
  const savedFilters = useFilterStore((state) => state.savedFilters);
  const setSavedFilters = useFilterStore((state) => state.setSavedFilters);
  const addSavedFilter = useFilterStore((state) => state.addSavedFilter);
  const removeSavedFilter = useFilterStore((state) => state.removeSavedFilter);
  const getFilterSnapshot = useFilterStore((state) => state.getFilterSnapshot);
  const applyFilterSnapshot = useFilterStore((state) => state.applyFilterSnapshot);

  const [selectedId, setSelectedId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const renderCountRef = useRef(0);
  renderCountRef.current += 1;
  if (import.meta.env.DEV) {
    console.debug('[SavedFilters] render', {
      renderCount: renderCountRef.current,
      savedCount: savedFilters.length,
      loading,
      selectedId
    });
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        if (import.meta.env.DEV) {
          console.debug('[SavedFilters] initializing IndexedDB');
        }
        await indexedDBService.initialize();
        const presets = await indexedDBService.getAllFilterPresets();
        if (import.meta.env.DEV) {
          console.debug('[SavedFilters] loaded presets', { count: presets.length });
        }
        if (!mounted) return;
        setSavedFilters(presets);
        if (presets.length > 0) {
          setSelectedId(presets[0]?.filter_id ?? '');
        } else {
          setSelectedId('');
        }
        setError(null);
      } catch (err) {
        console.error('[SavedFilters] Failed to load presets', err);
        if (mounted) {
          setError('Unable to load saved presets');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    })();
    return () => {
      mounted = false;
    };
  }, [setSavedFilters]);

  const handleSavePreset = async () => {
    const name = window.prompt('Save current filters as preset. Enter a name:');
    if (!name || !name.trim()) {
      return;
    }

    try {
      const record = {
        filter_id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `filter-${Date.now()}`,
        name: name.trim(),
        created_at: Date.now(),
        filters: getFilterSnapshot(),
      };
      await indexedDBService.saveFilterPreset(record);
      addSavedFilter(record);
      setSelectedId(record.filter_id);
      setError(null);
    } catch (err) {
      console.error('[SavedFilters] Failed to save preset', err);
      setError('Failed to save preset');
    }
  };

  const handleApplyPreset = () => {
    if (!selectedId) return;
    const preset = savedFilters.find((filter) => filter.filter_id === selectedId);
    if (!preset) return;
    applyFilterSnapshot(preset.filters);
  };

  const handleDeletePreset = async () => {
    if (!selectedId) return;
    try {
      await indexedDBService.deleteFilterPreset(selectedId);
      removeSavedFilter(selectedId);
      const remaining = savedFilters.filter((filter) => filter.filter_id !== selectedId);
      setSelectedId(remaining[0]?.filter_id ?? '');
      setError(null);
    } catch (err) {
      console.error('[SavedFilters] Failed to delete preset', err);
      setError('Failed to delete preset');
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.controlsRow}>
        <button
          type="button"
          className={styles.saveButton}
          onClick={handleSavePreset}
          disabled={loading}
        >
          Save Current
        </button>

        <select
          className={styles.select}
          value={selectedId}
          onChange={(event) => setSelectedId(event.target.value)}
          disabled={loading || savedFilters.length === 0}
          aria-label="Saved filter presets"
        >
          {savedFilters.length === 0 && <option value="">No presets</option>}
          {savedFilters.map((preset) => (
            <option key={preset.filter_id} value={preset.filter_id}>
              {preset.name}
            </option>
          ))}
        </select>

        <button
          type="button"
          className={styles.applyButton}
          onClick={handleApplyPreset}
          disabled={!selectedId}
        >
          Apply
        </button>

        <button
          type="button"
          className={styles.deleteButton}
          onClick={handleDeletePreset}
          disabled={!selectedId}
        >
          Delete
        </button>
      </div>
      {error && <div className={styles.error}>{error}</div>}
    </div>
  );
};

export default SavedFiltersControl;
