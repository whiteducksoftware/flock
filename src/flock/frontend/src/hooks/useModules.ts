/**
 * useModules Hook - Module Lifecycle Management
 *
 * Provides ModuleContext to modules and manages lifecycle hooks.
 * Aggregates data from multiple stores into a unified context.
 * Calls module onMount/onUnmount lifecycle hooks when instances change.
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/FRONTEND_ARCHITECTURE.md Section 7.4
 * - Build ModuleContext from store data (events, filters)
 * - Call module onMount lifecycle hooks when instances added
 * - Call module onUnmount lifecycle hooks when instances removed
 * - Provide publish and invoke actions in context
 *
 * UI Optimization Migration (Phase 4.1 - Spec 002):
 * - agents/messages Maps are DEPRECATED (Phase 1 architecture)
 * - Modules should use events array instead
 * - Empty Maps provided for backward compatibility
 */

import { useEffect, useMemo, useRef } from 'react';
import { useModuleStore } from '../store/moduleStore';
import { useGraphStore } from '../store/graphStore';
import { useFilterStore } from '../store/filterStore';
import { moduleRegistry, type ModuleContext } from '../components/modules/ModuleRegistry';

/**
 * Custom hook for module lifecycle management
 *
 * Features:
 * - Builds ModuleContext from graphStore, filterStore
 * - Tracks module instances and calls lifecycle hooks
 * - Calls onMount when new instances are added
 * - Calls onUnmount when instances are removed
 * - Provides publish/invoke actions (placeholder for now)
 *
 * @returns {Object} Hook return value
 * @returns {ModuleContext} context - The module context object
 */
export function useModules() {
  // Subscribe to store state
  const instances = useModuleStore((state) => state.instances);
  const events = useGraphStore((state) => state.events);

  // UI Optimization Migration (Phase 4.1): Provide empty Maps for deprecated fields
  const agents = useMemo(() => new Map(), []);
  const messages = useMemo(() => new Map(), []);
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);
  const artifactTypes = useFilterStore((state) => state.selectedArtifactTypes);
  const producers = useFilterStore((state) => state.selectedProducers);
  const tags = useFilterStore((state) => state.selectedTags);
  const visibility = useFilterStore((state) => state.selectedVisibility);
  const summary = useFilterStore((state) => state.summary);

  // Track previous instances to detect changes
  const prevInstancesRef = useRef<Map<string, any>>(new Map());

  // Build ModuleContext
  const context: ModuleContext = useMemo(
    () => ({
      agents,
      messages,
      events,
      filters: {
        correlationId,
        timeRange,
        artifactTypes,
        producers,
        tags,
        visibility,
      },
      summary,
      publish: (artifact: any) => {
        // Placeholder: In production, this would dispatch to WebSocket
        console.log('[Module Context] Publish artifact:', artifact);
      },
      invoke: (agentName: string, inputs: any[]) => {
        // Placeholder: In production, this would dispatch to WebSocket
        console.log('[Module Context] Invoke agent:', agentName, 'with inputs:', inputs);
      },
    }),
    // Note: agents and messages are stable empty Maps, so excluded from deps
    [events, correlationId, timeRange, artifactTypes, producers, tags, visibility, summary]
  );

  /**
   * Lifecycle effect: Call onMount/onUnmount hooks when instances change
   */
  useEffect(() => {
    const currentInstances = instances;
    const prevInstances = prevInstancesRef.current;

    // Detect added instances (in current but not in previous)
    const addedInstances = new Map<string, any>();
    currentInstances.forEach((instance, id) => {
      if (!prevInstances.has(id)) {
        addedInstances.set(id, instance);
      }
    });

    // Detect removed instances (in previous but not in current)
    const removedInstances = new Map<string, any>();
    prevInstances.forEach((instance, id) => {
      if (!currentInstances.has(id)) {
        removedInstances.set(id, instance);
      }
    });

    // Call onMount for added instances
    addedInstances.forEach((instance) => {
      const module = moduleRegistry.get(instance.type);
      if (module?.onMount) {
        console.log(`[useModules] Calling onMount for module: ${module.name} (${instance.id})`);
        try {
          module.onMount(context);
        } catch (error) {
          console.error(`[useModules] Error in onMount for module ${module.name}:`, error);
        }
      }
    });

    // Call onUnmount for removed instances
    removedInstances.forEach((instance) => {
      const module = moduleRegistry.get(instance.type);
      if (module?.onUnmount) {
        console.log(`[useModules] Calling onUnmount for module: ${module.name} (${instance.id})`);
        try {
          module.onUnmount();
        } catch (error) {
          console.error(`[useModules] Error in onUnmount for module ${module.name}:`, error);
        }
      }
    });

    // Update previous instances ref for next comparison
    prevInstancesRef.current = new Map(currentInstances);

    // Cleanup: Call onUnmount for all instances when hook unmounts
    return () => {
      currentInstances.forEach((instance) => {
        const module = moduleRegistry.get(instance.type);
        if (module?.onUnmount) {
          console.log(`[useModules] Cleanup: Calling onUnmount for module: ${module.name} (${instance.id})`);
          try {
            module.onUnmount();
          } catch (error) {
            console.error(`[useModules] Error in cleanup onUnmount for module ${module.name}:`, error);
          }
        }
      });
    };
  }, [instances, context]);

  return {
    context,
  };
}
