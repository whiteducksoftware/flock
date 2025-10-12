/**
 * usePersistence Hook - Node Position Persistence
 *
 * Provides position persistence for graph nodes using IndexedDB.
 * Manages loading and saving of node positions with debouncing.
 * Handles separate layouts for Agent View and Blackboard View.
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/FRONTEND_ARCHITECTURE.md
 * - Debounce: 300ms delay on drag stop
 * - Performance: Position save <50ms (after debounce)
 * - Separate layouts for Agent View vs Blackboard View
 */

import { useEffect, useCallback, useRef } from 'react';
import { useGraphStore } from '../store/graphStore';
import { useUIStore, VisualizationMode } from '../store/uiStore';
import { indexedDBService } from '../services/indexeddb';

interface Position {
  x: number;
  y: number;
}

/**
 * Custom debounce implementation
 * Creates a debounced function that delays invoking func until after delay milliseconds
 */
function debounce<T extends (...args: any[]) => void>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      func(...args);
      timeoutId = null;
    }, delay);
  };
}

/**
 * React hook for node position persistence
 *
 * Features:
 * - Loads node positions from IndexedDB on mount
 * - Applies loaded positions to graphStore
 * - Returns debounced saveNodePosition function (300ms delay)
 * - Handles mode switching (reloads positions for new mode)
 *
 * @returns {Object} Hook return value
 * @returns {Function} saveNodePosition - Debounced function to save node position
 */
export function usePersistence() {
  const mode = useUIStore((state) => state.mode);

  // Use ref to maintain debounced function identity across renders
  const debouncedSaveRef = useRef<((nodeId: string, mode: VisualizationMode, position: Position) => void) | null>(null);

  // Initialize debounced save function once
  if (!debouncedSaveRef.current) {
    debouncedSaveRef.current = debounce(
      async (nodeId: string, mode: VisualizationMode, position: Position) => {
        try {
          console.log(`[usePersistence] Saving position for ${nodeId} in ${mode} view:`, position);
          const layoutRecord = {
            node_id: nodeId,
            x: position.x,
            y: position.y,
            last_updated: new Date().toISOString(),
          };

          if (mode === 'agent') {
            await indexedDBService.saveAgentViewLayout(layoutRecord);
            console.log(`[usePersistence] ✓ Saved to agent view layout`);
          } else {
            await indexedDBService.saveBlackboardViewLayout(layoutRecord);
            console.log(`[usePersistence] ✓ Saved to blackboard view layout`);
          }
        } catch (error) {
          console.error(`[usePersistence] Failed to save node position for ${nodeId}:`, error);
        }
      },
      300 // 300ms debounce delay as per specification
    );
  }

  /**
   * Load node positions from IndexedDB for current mode
   * Note: Deliberately excludes updateNodePosition from dependencies to prevent infinite loops
   * The function is stable from zustand, so we can safely use it without re-creating the callback
   */
  const loadNodePositions = useCallback(async (currentMode: VisualizationMode) => {
    try {
      let layouts: Array<{ node_id: string; x: number; y: number; last_updated: string }> = [];

      if (currentMode === 'agent') {
        layouts = await indexedDBService.getAllAgentViewLayouts();
      } else {
        layouts = await indexedDBService.getAllBlackboardViewLayouts();
      }

      // Apply loaded positions to graph store
      // Use graphStore directly to avoid dependency on updateNodePosition selector
      layouts.forEach((layout) => {
        useGraphStore.getState().updateNodePosition(layout.node_id, { x: layout.x, y: layout.y });
      });

      console.log(`[usePersistence] Loaded ${layouts.length} node positions for ${currentMode} view`);
    } catch (error) {
      console.error(`[usePersistence] Failed to load node positions for ${currentMode} view:`, error);
    }
  }, []); // Empty deps - function is now stable!

  /**
   * Load positions on mount and when mode changes
   */
  useEffect(() => {
    loadNodePositions(mode);
  }, [mode, loadNodePositions]);

  /**
   * Public API: Save node position with debouncing
   */
  const saveNodePosition = useCallback(
    (nodeId: string, position: Position) => {
      if (debouncedSaveRef.current) {
        debouncedSaveRef.current(nodeId, mode, position);
      }
    },
    [mode]
  );

  return {
    saveNodePosition,
  };
}
