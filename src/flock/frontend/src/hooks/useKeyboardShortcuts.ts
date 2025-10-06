import { useEffect } from 'react';
import { useUIStore } from '../store/uiStore';
import { useSettingsStore } from '../store/settingsStore';

interface KeyboardShortcutConfig {
  onToggleMode?: () => void;
  onFocusFilter?: () => void;
  onCloseWindows?: () => void;
  onToggleHelp?: () => void;
  onToggleAgentDetails?: () => void;
}

/**
 * Custom hook for managing global keyboard shortcuts
 *
 * Shortcuts:
 * - Ctrl+M (or Cmd+M): Toggle between Agent View and Blackboard View
 * - Ctrl+F (or Cmd+F): Focus the filter input
 * - Ctrl+, (or Cmd+,): Toggle Settings Panel
 * - Ctrl+Shift+F: Toggle Filters Panel
 * - Ctrl+Shift+P: Toggle Publish Panel
 * - Ctrl+Shift+D: Toggle Agent Details
 * - Ctrl+/ (or Cmd+/): Toggle Keyboard Shortcuts Help
 * - Esc: Close all panels and detail windows
 */
export const useKeyboardShortcuts = (config: KeyboardShortcutConfig = {}) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for modifier key (Ctrl on Windows/Linux, Cmd on Mac)
      const modifier = event.ctrlKey || event.metaKey;

      // Ctrl+, or Cmd+,: Toggle Settings Panel
      if (modifier && event.key === ',') {
        event.preventDefault();
        const showSettings = useSettingsStore.getState().ui.showSettings;
        useSettingsStore.getState().setShowSettings(!showSettings);
        return;
      }

      // Ctrl+Shift+F: Toggle Filters Panel
      if (modifier && event.shiftKey && event.key === 'F') {
        event.preventDefault();
        const showFilters = useSettingsStore.getState().ui.showFilters;
        useSettingsStore.getState().setShowFilters(!showFilters);
        return;
      }

      // Ctrl+Shift+P: Toggle Publish/Controls Panel
      if (modifier && event.shiftKey && event.key === 'P') {
        event.preventDefault();
        const showControls = useSettingsStore.getState().ui.showControls;
        useSettingsStore.getState().setShowControls(!showControls);
        return;
      }

      // Ctrl+Shift+D: Toggle Agent Details
      if (modifier && event.shiftKey && event.key === 'D') {
        event.preventDefault();
        if (config.onToggleAgentDetails) {
          config.onToggleAgentDetails();
        }
        return;
      }

      // Ctrl+/ or Cmd+/: Toggle Keyboard Shortcuts Help
      if (modifier && event.key === '/') {
        event.preventDefault();
        if (config.onToggleHelp) {
          config.onToggleHelp();
        }
        return;
      }

      // Ctrl+M or Cmd+M: Toggle mode
      if (modifier && event.key === 'm') {
        event.preventDefault();
        if (config.onToggleMode) {
          config.onToggleMode();
        } else {
          // Default behavior: toggle mode
          const currentMode = useUIStore.getState().mode;
          useUIStore.getState().setMode(currentMode === 'agent' ? 'blackboard' : 'agent');
        }
        return;
      }

      // Ctrl+F or Cmd+F: Focus filter (only if not in an input already)
      if (modifier && event.key === 'f') {
        const activeElement = document.activeElement;
        const isInInput = activeElement?.tagName === 'INPUT' ||
                         activeElement?.tagName === 'TEXTAREA';

        if (!isInInput) {
          event.preventDefault();
          if (config.onFocusFilter) {
            config.onFocusFilter();
          } else {
            // Default behavior: focus correlation ID filter
            const filterInput = document.querySelector<HTMLInputElement>(
              'input[placeholder*="correlation"], input[placeholder*="Correlation"]'
            );
            if (filterInput) {
              filterInput.focus();
              filterInput.select();
            }
          }
        }
        return;
      }

      // Esc: Close windows/dialogs/panels
      if (event.key === 'Escape') {
        if (config.onCloseWindows) {
          config.onCloseWindows();
        } else {
          // Priority: Close panels first, then detail windows
          const { showSettings, showFilters, showControls } = useSettingsStore.getState().ui;
          const detailWindows = useUIStore.getState().detailWindows;

          if (showSettings) {
            event.preventDefault();
            useSettingsStore.getState().setShowSettings(false);
          } else if (showControls) {
            event.preventDefault();
            useSettingsStore.getState().setShowControls(false);
          } else if (showFilters) {
            event.preventDefault();
            useSettingsStore.getState().setShowFilters(false);
          } else if (detailWindows.size > 0) {
            event.preventDefault();
            // Close all detail windows
            detailWindows.clear();
            useUIStore.setState({ detailWindows: new Map() });
          }
        }
        return;
      }
    };

    // Add event listener
    window.addEventListener('keydown', handleKeyDown);

    // Cleanup
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [config]);
};
