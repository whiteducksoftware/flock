import React from 'react';
import type { Message } from '../../types/graph';
import type { TimeRange, ArtifactSummary } from '../../types/filters';

// UI Optimization Migration (Phase 4.1 - Spec 002): ModuleContext uses OLD Phase 1 architecture
// TODO: Update module system to use GraphNode[] instead of Maps
export interface ModuleContext {
  // Data access (DEPRECATED - Phase 1 architecture, use events array instead)
  agents: Map<string, any>; // OLD: was Map<string, Agent>
  messages: Map<string, Message>;
  events: Message[];

  // Filter state
  filters: {
    correlationId: string | null;
    timeRange: TimeRange;
    artifactTypes: string[];
    producers: string[];
    tags: string[];
    visibility: string[];
  };

  summary: ArtifactSummary | null;

  // Actions
  publish: (artifact: any) => void;
  invoke: (agentName: string, inputs: any[]) => void;
}

export interface ModuleDefinition {
  id: string;
  name: string;
  description: string;
  icon?: string;
  component: React.ComponentType<{ context: ModuleContext }>;
  onMount?: (context: ModuleContext) => void;
  onUnmount?: () => void;
}

export interface ModuleRegistry {
  register: (module: ModuleDefinition) => void;
  unregister: (moduleId: string) => void;
  getAll: () => ModuleDefinition[];
  get: (moduleId: string) => ModuleDefinition | undefined;
}

class ModuleRegistryImpl implements ModuleRegistry {
  private static instance: ModuleRegistryImpl;
  private modules: Map<string, ModuleDefinition> = new Map();

  private constructor() {}

  public static getInstance(): ModuleRegistryImpl {
    if (!ModuleRegistryImpl.instance) {
      ModuleRegistryImpl.instance = new ModuleRegistryImpl();
    }
    return ModuleRegistryImpl.instance;
  }

  public register(module: ModuleDefinition): void {
    if (this.modules.has(module.id)) {
      console.warn(`Module with id "${module.id}" is already registered. Skipping registration.`);
      return;
    }
    this.modules.set(module.id, module);
    console.log(`Module "${module.name}" (${module.id}) registered successfully.`);
  }

  public unregister(moduleId: string): void {
    if (this.modules.has(moduleId)) {
      const module = this.modules.get(moduleId);
      this.modules.delete(moduleId);
      console.log(`Module "${module?.name}" (${moduleId}) unregistered successfully.`);
    }
  }

  public getAll(): ModuleDefinition[] {
    return Array.from(this.modules.values());
  }

  public get(moduleId: string): ModuleDefinition | undefined {
    return this.modules.get(moduleId);
  }

  // For testing purposes - reset the singleton instance
  public static resetInstance(): void {
    if (ModuleRegistryImpl.instance) {
      ModuleRegistryImpl.instance.modules.clear();
    }
  }
}

export const moduleRegistry = ModuleRegistryImpl.getInstance();
