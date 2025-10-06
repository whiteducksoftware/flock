import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
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
    (set) => ({
      instances: new Map(),

      addModule: (module) =>
        set((state) => {
          const instances = new Map(state.instances);
          instances.set(module.id, module);
          return { instances };
        }),

      updateModule: (id, updates) =>
        set((state) => {
          const instances = new Map(state.instances);
          const existing = instances.get(id);
          if (existing) {
            instances.set(id, { ...existing, ...updates });
          }
          return { instances };
        }),

      removeModule: (id) =>
        set((state) => {
          const instances = new Map(state.instances);
          instances.delete(id);
          return { instances };
        }),

      toggleVisibility: (id) =>
        set((state) => {
          const instances = new Map(state.instances);
          const existing = instances.get(id);
          if (existing) {
            instances.set(id, { ...existing, visible: !existing.visible });
          }
          return { instances };
        }),
    }),
    { name: 'moduleStore' }
  )
);
