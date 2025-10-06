import { useEffect, useRef, useCallback } from 'react';
import { useModuleStore } from '../store/moduleStore';
import { indexedDBService } from '../services/indexeddb';
import type { ModuleInstance } from '../types/modules';

/**
 * Hook to persist module instances to IndexedDB
 *
 * Features:
 * - Loads all module instances on mount
 * - Saves instances when added/updated (with debouncing for drag/resize)
 * - Deletes instances when removed
 * - Debounce: 300ms (same as node position persistence)
 */
export const useModulePersistence = () => {
  const instances = useModuleStore((state) => state.instances);
  const addModule = useModuleStore((state) => state.addModule);

  // Track previous instances to detect changes
  const previousInstancesRef = useRef<Map<string, ModuleInstance>>(new Map());

  // Debounce timer for saves
  const saveTimerRef = useRef<{ [key: string]: number }>({});

  // Load module instances on mount
  useEffect(() => {
    const loadModuleInstances = async () => {
      try {
        const savedInstances = await indexedDBService.getAllModuleInstances();

        // Restore each module instance to the store
        savedInstances.forEach((record) => {
          const instance: ModuleInstance = {
            id: record.instance_id,
            type: record.type,
            position: record.position,
            size: record.size,
            visible: record.visible,
          };
          addModule(instance);
        });

        console.log(`[ModulePersistence] Restored ${savedInstances.length} module instances`);
      } catch (error) {
        console.error('[ModulePersistence] Failed to load module instances:', error);
      }
    };

    loadModuleInstances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount

  // Save module instances when they change (debounced)
  const saveModuleInstance = useCallback(async (instance: ModuleInstance) => {
    // Clear existing timer for this instance
    if (saveTimerRef.current[instance.id]) {
      clearTimeout(saveTimerRef.current[instance.id]);
    }

    // Debounce: wait 300ms before saving (handles rapid drag/resize updates)
    saveTimerRef.current[instance.id] = setTimeout(async () => {
      try {
        const now = new Date().toISOString();
        const record = {
          instance_id: instance.id,
          type: instance.type,
          position: instance.position,
          size: instance.size,
          visible: instance.visible,
          created_at: now, // Will be overwritten if updating existing
          updated_at: now,
        };

        await indexedDBService.saveModuleInstance(record);
        console.log(`[ModulePersistence] Saved instance: ${instance.id}`);
      } catch (error) {
        console.error(`[ModulePersistence] Failed to save instance ${instance.id}:`, error);
      }

      delete saveTimerRef.current[instance.id];
    }, 300);
  }, []);

  // Delete module instance from IndexedDB
  const deleteModuleInstance = useCallback(async (instanceId: string) => {
    // Clear any pending save timer
    if (saveTimerRef.current[instanceId]) {
      clearTimeout(saveTimerRef.current[instanceId]);
      delete saveTimerRef.current[instanceId];
    }

    try {
      await indexedDBService.deleteModuleInstance(instanceId);
      console.log(`[ModulePersistence] Deleted instance: ${instanceId}`);
    } catch (error) {
      console.error(`[ModulePersistence] Failed to delete instance ${instanceId}:`, error);
    }
  }, []);

  // Detect changes in module instances
  useEffect(() => {
    const currentIds = new Set(instances.keys());
    const previousIds = new Set(previousInstancesRef.current.keys());

    // Detect added instances
    currentIds.forEach((id) => {
      if (!previousIds.has(id)) {
        const instance = instances.get(id);
        if (instance) {
          console.log(`[ModulePersistence] Detected new instance: ${id}`);
          saveModuleInstance(instance);
        }
      }
    });

    // Detect updated instances
    instances.forEach((instance, id) => {
      const previous = previousInstancesRef.current.get(id);
      if (previous) {
        // Check if position, size, or visibility changed
        const positionChanged =
          previous.position.x !== instance.position.x ||
          previous.position.y !== instance.position.y;
        const sizeChanged =
          previous.size.width !== instance.size.width ||
          previous.size.height !== instance.size.height;
        const visibilityChanged = previous.visible !== instance.visible;

        if (positionChanged || sizeChanged || visibilityChanged) {
          console.log(`[ModulePersistence] Detected update to instance: ${id}`);
          saveModuleInstance(instance);
        }
      }
    });

    // Detect removed instances
    previousIds.forEach((id) => {
      if (!currentIds.has(id)) {
        console.log(`[ModulePersistence] Detected removed instance: ${id}`);
        deleteModuleInstance(id);
      }
    });

    // Update ref for next comparison
    previousInstancesRef.current = new Map(instances);
  }, [instances, saveModuleInstance, deleteModuleInstance]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      Object.values(saveTimerRef.current).forEach(clearTimeout);
    };
  }, []);
};
