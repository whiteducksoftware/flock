/**
 * useModules Hook - Module Lifecycle Management
 *
 * Provides ModuleContext to modules and manages lifecycle hooks.
 * Aggregates data from multiple stores into a unified context.
 * Calls module onMount/onUnmount lifecycle hooks when instances change.
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/FRONTEND_ARCHITECTURE.md Section 7.4
 * - Build ModuleContext from store data (agents, messages, events, filters)
 * - Call module onMount lifecycle hooks when instances added
 * - Call module onUnmount lifecycle hooks when instances removed
 * - Provide publish and invoke actions in context
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
  const agents = useGraphStore((state) => state.agents);
  const messages = useGraphStore((state) => state.messages);
  const events = useGraphStore((state) => state.events);
  const correlationId = useFilterStore((state) => state.correlationId);
  const timeRange = useFilterStore((state) => state.timeRange);

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
      },
      publish: (artifact: any) => {
        // Placeholder: In production, this would dispatch to WebSocket
        console.log('[Module Context] Publish artifact:', artifact);
      },
      invoke: (agentName: string, inputs: any[]) => {
        // Placeholder: In production, this would dispatch to WebSocket
        console.log('[Module Context] Invoke agent:', agentName, 'with inputs:', inputs);
      },
    }),
    [agents, messages, events, correlationId, timeRange]
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
