import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SavedFiltersControl from './SavedFiltersControl';
import { useFilterStore } from '../../store/filterStore';
import { indexedDBService } from '../../services/indexeddb';
import type { SavedFilterMeta, FilterSnapshot } from '../../types/filters';

vi.mock('../../store/filterStore');
vi.mock('../../services/indexeddb', () => ({
  indexedDBService: {
    initialize: vi.fn(),
    getAllFilterPresets: vi.fn(),
    saveFilterPreset: vi.fn(),
    deleteFilterPreset: vi.fn(),
  },
}));

const baseSnapshot: FilterSnapshot = {
  correlationId: null,
  timeRange: { preset: 'last10min' },
  artifactTypes: [],
  producers: [],
  tags: [],
  visibility: [],
};

const createMockState = (overrides: Record<string, unknown> = {}) => ({
  savedFilters: [] as SavedFilterMeta[],
  setSavedFilters: vi.fn(),
  addSavedFilter: vi.fn(),
  removeSavedFilter: vi.fn(),
  getFilterSnapshot: vi.fn(() => baseSnapshot),
  applyFilterSnapshot: vi.fn(),
  getActiveFilters: () => [],
  ...overrides,
});

type MockFilterState = ReturnType<typeof createMockState>;

let state: MockFilterState;
type MockedFn = ReturnType<typeof vi.fn>;
const mockedUseFilterStore = useFilterStore as unknown as MockedFn;

const getIndexedDBMocks = () => indexedDBService as unknown as {
  initialize: ReturnType<typeof vi.fn>;
  getAllFilterPresets: ReturnType<typeof vi.fn>;
  saveFilterPreset: ReturnType<typeof vi.fn>;
  deleteFilterPreset: ReturnType<typeof vi.fn>;
};

describe('SavedFiltersControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state = createMockState();
    mockedUseFilterStore.mockReset();
    mockedUseFilterStore.mockImplementation((selector: any) => selector(state as any));

    const indexedDb = getIndexedDBMocks();
    indexedDb.initialize.mockResolvedValue(undefined);
    indexedDb.getAllFilterPresets.mockResolvedValue([]);
    indexedDb.saveFilterPreset.mockResolvedValue(undefined);
    indexedDb.deleteFilterPreset.mockResolvedValue(undefined);
  });

  it('loads saved presets on mount', async () => {
    const presets: SavedFilterMeta[] = [
      {
        filter_id: 'preset-1',
        name: 'Recent Ops',
        created_at: Date.now(),
        filters: baseSnapshot,
      },
    ];

    const indexedDb = getIndexedDBMocks();
    indexedDb.getAllFilterPresets.mockResolvedValueOnce(presets);

    render(<SavedFiltersControl />);

    await waitFor(() => {
      expect(state.setSavedFilters).toHaveBeenCalledWith(presets);
    });
  });

  it('saves current snapshot when Save Current is clicked', async () => {
    const indexedDb = getIndexedDBMocks();
    indexedDb.getAllFilterPresets.mockResolvedValueOnce([]);

    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('My Filters');
    const uuidSpy = vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('123e4567-e89b-12d3-a456-426614174000');

    render(<SavedFiltersControl />);

    const saveButton = await screen.findByRole('button', { name: /save current/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(indexedDb.saveFilterPreset).toHaveBeenCalledTimes(1);
      expect(state.addSavedFilter).toHaveBeenCalledTimes(1);
    });

    const savedRecord = indexedDb.saveFilterPreset.mock.calls[0]?.[0];
    expect(savedRecord).toBeDefined();
    if (savedRecord) {
      expect(savedRecord.filter_id).toBe('123e4567-e89b-12d3-a456-426614174000');
      expect(savedRecord.name).toBe('My Filters');
      expect(savedRecord.filters).toEqual(baseSnapshot);
    }

    promptSpy.mockRestore();
    uuidSpy.mockRestore();
  });

  it('applies selected preset when Apply is clicked', async () => {
    const preset: SavedFilterMeta = {
      filter_id: 'preset-apply',
      name: 'Important',
      created_at: Date.now(),
      filters: { ...baseSnapshot, artifactTypes: ['Plan'] },
    };
    state = createMockState({ savedFilters: [preset] });
    mockedUseFilterStore.mockImplementation((selector: any) => selector(state as any));

    const indexedDb = getIndexedDBMocks();
    indexedDb.getAllFilterPresets.mockResolvedValueOnce([preset]);

    render(<SavedFiltersControl />);

    const applyButton = await screen.findByRole('button', { name: /apply/i });
    fireEvent.click(applyButton);

    expect(state.applyFilterSnapshot).toHaveBeenCalledWith(preset.filters);
  });

  it('deletes preset and updates store when Delete is clicked', async () => {
    const preset: SavedFilterMeta = {
      filter_id: 'preset-delete',
      name: 'Old preset',
      created_at: Date.now(),
      filters: baseSnapshot,
    };
    state = createMockState({ savedFilters: [preset] });
    mockedUseFilterStore.mockImplementation((selector: any) => selector(state as any));

    const indexedDb = getIndexedDBMocks();
    indexedDb.getAllFilterPresets.mockResolvedValueOnce([preset]);

    render(<SavedFiltersControl />);

    const deleteButton = await screen.findByRole('button', { name: /delete/i });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(indexedDb.deleteFilterPreset).toHaveBeenCalledWith('preset-delete');
      expect(state.removeSavedFilter).toHaveBeenCalledWith('preset-delete');
    });
  });
});
