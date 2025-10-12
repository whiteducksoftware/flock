import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { ModuleInstance } from '../types/modules';

interface ModuleState {
  // Module instances
  instances: Map<string, ModuleInstance>;

  // Actions
  addModule: (module: ModuleInstance) => void;
  updateModule: (id: string, updates: Partial<Omit<ModuleInstance, 'id' | 'type'>>) => void;
  removeModule: (id: string) => void;
  toggleVisibility: (id: string) => void;
}

export const useModuleStore = create<ModuleState>()(
  devtools(
    persist<ModuleState>(
      (set) => ({
        instances: new Map(),

        addModule: (module: ModuleInstance) =>
          set((state) => {
            const instances = new Map(state.instances);
            instances.set(module.id, module);
            return { instances };
          }),

        updateModule: (id: string, updates: Partial<Omit<ModuleInstance, 'id' | 'type'>>) =>
          set((state) => {
            const instances = new Map(state.instances);
            const existing = instances.get(id);
            if (existing) {
              instances.set(id, { ...existing, ...updates });
            }
            return { instances };
          }),

        removeModule: (id: string) =>
          set((state) => {
            const instances = new Map(state.instances);
            instances.delete(id);
            return { instances };
          }),

        toggleVisibility: (id: string) =>
          set((state) => {
            const instances = new Map(state.instances);
            const existing = instances.get(id);
            if (existing) {
              instances.set(id, { ...existing, visible: !existing.visible });
            }
            return { instances };
          }),
      }),
      {
        name: 'flock-module-state',
        partialize: (state) => ({
          instances: Array.from(state.instances.entries()),
        }) as any,
        merge: (persistedState: any, currentState: any) => {
          // Convert instances array back to Map
          if (persistedState?.instances && Array.isArray(persistedState.instances)) {
            persistedState.instances = new Map(persistedState.instances);
          }
          return {
            ...currentState,
            ...persistedState,
          };
        },
      }
    ),
    { name: 'moduleStore' }
  )
);
