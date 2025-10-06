import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useModulePersistence } from './useModulePersistence';
import { useModuleStore } from '../store/moduleStore';
import { indexedDBService } from '../services/indexeddb';
import type { ModuleInstance } from '../types/modules';

// Mock IndexedDB service
vi.mock('../services/indexeddb', () => ({
  indexedDBService: {
    getAllModuleInstances: vi.fn(),
    saveModuleInstance: vi.fn(),
    deleteModuleInstance: vi.fn(),
  },
}));

describe('useModulePersistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset module store
    useModuleStore.setState({ instances: new Map() });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Module Loading', () => {
    it('should load saved module instances on mount', async () => {
      const savedInstances = [
        {
          instance_id: 'module-1',
          type: 'eventLog',
          position: { x: 100, y: 200 },
          size: { width: 600, height: 400 },
          visible: true,
          created_at: '2025-10-03T00:00:00Z',
          updated_at: '2025-10-03T00:00:00Z',
        },
        {
          instance_id: 'module-2',
          type: 'eventLog',
          position: { x: 300, y: 400 },
          size: { width: 800, height: 600 },
          visible: true,
          created_at: '2025-10-03T00:00:00Z',
          updated_at: '2025-10-03T00:00:00Z',
        },
      ];

      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue(savedInstances);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        const instances = useModuleStore.getState().instances;
        expect(instances.size).toBe(2);
        expect(instances.get('module-1')).toEqual({
          id: 'module-1',
          type: 'eventLog',
          position: { x: 100, y: 200 },
          size: { width: 600, height: 400 },
          visible: true,
        });
        expect(instances.get('module-2')).toEqual({
          id: 'module-2',
          type: 'eventLog',
          position: { x: 300, y: 400 },
          size: { width: 800, height: 600 },
          visible: true,
        });
      });
    });

    it('should handle empty module instances on mount', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalledOnce();
      });

      const instances = useModuleStore.getState().instances;
      expect(instances.size).toBe(0);
    });

    it('should handle errors when loading instances', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(indexedDBService.getAllModuleInstances).mockRejectedValue(
        new Error('Database error')
      );

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith(
          '[ModulePersistence] Failed to load module instances:',
          expect.any(Error)
        );
      });

      consoleErrorSpy.mockRestore();
    });
  });

  describe('Module Saving', () => {
    it('should save new module instance when added', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const newInstance: ModuleInstance = {
        id: 'new-module',
        type: 'eventLog',
        position: { x: 150, y: 250 },
        size: { width: 700, height: 500 },
        visible: true,
      };

      useModuleStore.getState().addModule(newInstance);

      // Wait for debounced save (300ms + buffer)
      await new Promise((resolve) => setTimeout(resolve, 400));

      await waitFor(() => {
        expect(indexedDBService.saveModuleInstance).toHaveBeenCalledWith(
          expect.objectContaining({
            instance_id: 'new-module',
            type: 'eventLog',
            position: { x: 150, y: 250 },
            size: { width: 700, height: 500 },
            visible: true,
          })
        );
      });
    });

    it('should debounce saves when position changes rapidly', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'drag-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);

      // Wait for initial add to save
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Rapidly update position (simulating drag)
      useModuleStore.getState().updateModule('drag-module', { position: { x: 110, y: 110 } });
      await new Promise((resolve) => setTimeout(resolve, 100));

      useModuleStore.getState().updateModule('drag-module', { position: { x: 120, y: 120 } });
      await new Promise((resolve) => setTimeout(resolve, 100));

      useModuleStore.getState().updateModule('drag-module', { position: { x: 130, y: 130 } });

      // Wait for debounced save
      await new Promise((resolve) => setTimeout(resolve, 400));

      await waitFor(() => {
        // Should have saved at least twice: initial add + final position
        expect(indexedDBService.saveModuleInstance).toHaveBeenCalled();
        expect(indexedDBService.saveModuleInstance).toHaveBeenLastCalledWith(
          expect.objectContaining({
            position: { x: 130, y: 130 },
          })
        );
      });
    });

    it('should save when size changes', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'resize-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Update size
      useModuleStore.getState().updateModule('resize-module', {
        size: { width: 800, height: 600 },
      });

      await new Promise((resolve) => setTimeout(resolve, 400));

      await waitFor(() => {
        expect(indexedDBService.saveModuleInstance).toHaveBeenCalledWith(
          expect.objectContaining({
            size: { width: 800, height: 600 },
          })
        );
      });
    });

    it('should save when visibility changes', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'toggle-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Toggle visibility
      useModuleStore.getState().toggleVisibility('toggle-module');

      await new Promise((resolve) => setTimeout(resolve, 400));

      await waitFor(() => {
        expect(indexedDBService.saveModuleInstance).toHaveBeenCalledWith(
          expect.objectContaining({
            visible: false,
          })
        );
      });
    });

    it('should handle save errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);
      vi.mocked(indexedDBService.saveModuleInstance).mockRejectedValue(
        new Error('Save failed')
      );

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'error-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);
      await new Promise((resolve) => setTimeout(resolve, 400));

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith(
          expect.stringContaining('Failed to save instance'),
          expect.any(Error)
        );
      });

      consoleErrorSpy.mockRestore();
    });
  });

  describe('Module Deletion', () => {
    it('should delete module instance when removed', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'delete-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Remove the instance
      useModuleStore.getState().removeModule('delete-module');

      await waitFor(() => {
        expect(indexedDBService.deleteModuleInstance).toHaveBeenCalledWith('delete-module');
      });
    });

    it('should cancel pending save when module is deleted', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'cancel-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);

      // Wait for initial add to save
      await new Promise((resolve) => setTimeout(resolve, 400));

      const initialCallCount = vi.mocked(indexedDBService.saveModuleInstance).mock.calls.length;

      // Update position (triggers debounced save)
      useModuleStore.getState().updateModule('cancel-module', { position: { x: 200, y: 200 } });

      // Remove before debounce timer fires (100ms < 300ms debounce)
      await new Promise((resolve) => setTimeout(resolve, 100));
      useModuleStore.getState().removeModule('cancel-module');

      // Wait for potential saves
      await new Promise((resolve) => setTimeout(resolve, 400));

      await waitFor(() => {
        expect(indexedDBService.deleteModuleInstance).toHaveBeenCalledWith('cancel-module');
      });

      // save should not have been called again after the update (timer was cancelled)
      const finalCallCount = vi.mocked(indexedDBService.saveModuleInstance).mock.calls.length;
      expect(finalCallCount).toBe(initialCallCount);
    });

    it('should handle delete errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);
      vi.mocked(indexedDBService.deleteModuleInstance).mockRejectedValue(
        new Error('Delete failed')
      );

      renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'error-delete-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);
      await new Promise((resolve) => setTimeout(resolve, 400));

      useModuleStore.getState().removeModule('error-delete-module');

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith(
          expect.stringContaining('Failed to delete instance'),
          expect.any(Error)
        );
      });

      consoleErrorSpy.mockRestore();
    });
  });

  describe('Timer Cleanup', () => {
    it('should cleanup timers on unmount', async () => {
      vi.mocked(indexedDBService.getAllModuleInstances).mockResolvedValue([]);

      const { unmount } = renderHook(() => useModulePersistence());

      await waitFor(() => {
        expect(indexedDBService.getAllModuleInstances).toHaveBeenCalled();
      });

      const instance: ModuleInstance = {
        id: 'cleanup-module',
        type: 'eventLog',
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
        visible: true,
      };

      useModuleStore.getState().addModule(instance);

      // Wait for initial add to potentially save
      await new Promise((resolve) => setTimeout(resolve, 400));

      const callCountBeforeUpdate = vi.mocked(indexedDBService.saveModuleInstance).mock.calls.length;

      // Update position (triggers debounced save)
      useModuleStore.getState().updateModule('cleanup-module', { position: { x: 200, y: 200 } });

      // Unmount before timer fires (100ms < 300ms debounce)
      await new Promise((resolve) => setTimeout(resolve, 100));
      unmount();

      // Wait for potential timer - save should not be called after unmount
      await new Promise((resolve) => setTimeout(resolve, 400));

      // The update should NOT have saved because we unmounted before debounce completed
      const finalCallCount = vi.mocked(indexedDBService.saveModuleInstance).mock.calls.length;
      expect(finalCallCount).toBe(callCountBeforeUpdate);
    });
  });
});
