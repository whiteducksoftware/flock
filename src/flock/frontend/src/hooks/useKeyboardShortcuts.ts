import { useEffect } from 'react';
import { useGraphStore } from '../store/graphStore';
import { useUIStore } from '../store/uiStore';
import { useSettingsStore } from '../store/settingsStore';

interface KeyboardShortcutConfig {
  onToggleMode?: () => void;
  onFocusFilter?: () => void;
  onCloseWindows?: () => void;
  onToggleHelp?: () => void;
}

/** The node Space and Ctrl+Shift+D act on: the focused agent, else the selected one, else the unfolded one. */
const unfoldTarget = (): string | null => {
  const { nodes } = useGraphStore.getState();
  const isAgent = (id: string | null | undefined) => nodes.some((node) => node.id === id && node.type === 'agent');
  const focused = document.activeElement?.closest('.react-flow__node[data-id]')?.getAttribute('data-id');
  if (isAgent(focused)) return focused!;
  const selected = nodes.find((node) => node.selected && node.type === 'agent');
  return selected?.id ?? useUIStore.getState().unfoldedNodeId;
};

/** Focus where Space means something else: typing, pressing a button, a tab, a dialog. */
const SPACE_TAKEN = 'input, textarea, select, button, a[href], [contenteditable="true"], [role="tab"], [role="dialog"]';

/**
 * Custom hook for managing global keyboard shortcuts
 *
 * Shortcuts:
 * - Ctrl+M (or Cmd+M): Toggle between the Flow and Blackboard views
 * - Ctrl+F (or Cmd+F): Open the filters on the correlation search
 * - Ctrl+, (or Cmd+,): Toggle Settings Panel
 * - Ctrl+Shift+F: Toggle Filters Panel
 * - Ctrl+Shift+P: Toggle Publish Panel
 * - Space, Ctrl+Shift+D: Unfold or fold the selected node
 * - Ctrl+/ (or Cmd+/): Toggle Keyboard Shortcuts Help
 * - Esc: Close a panel, else fold the unfolded node, else close the artifact windows
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

      // Ctrl+Shift+D: Unfold or fold the selected node
      if (modifier && event.shiftKey && event.key === 'D') {
        event.preventDefault();
        const target = unfoldTarget();
        if (target) useUIStore.getState().toggleUnfold(target);
        return;
      }

      // Space: Unfold or fold the selected node, unless the focus has a use for it
      if (event.key === ' ' && !modifier && !event.altKey) {
        if (document.activeElement?.closest(SPACE_TAKEN)) return;
        const target = unfoldTarget();
        if (!target) return;
        event.preventDefault();
        useUIStore.getState().toggleUnfold(target);
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
            // Default behavior: focus the correlation search of the filters
            const focusCorrelation = (): boolean => {
              // The one in the filters; other panels have correlation fields too
              const filterInput = document.querySelector<HTMLInputElement>(
                '[role="dialog"][aria-label="Filters"] input[placeholder*="orrelation"]'
              );
              filterInput?.focus();
              filterInput?.select();
              return filterInput !== null;
            };
            if (!focusCorrelation()) {
              // The filters are closed: open them, then focus once they render
              useSettingsStore.getState().setShowFilters(true);
              window.setTimeout(focusCorrelation, 0);
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
          // Priority: Close panels first, then the unfolded node, then artifact windows
          const { showSettings, showFilters, showControls } = useSettingsStore.getState().ui;
          const { detailWindows, unfoldedNodeId } = useUIStore.getState();

          if (showSettings) {
            event.preventDefault();
            useSettingsStore.getState().setShowSettings(false);
          } else if (showControls) {
            event.preventDefault();
            useSettingsStore.getState().setShowControls(false);
          } else if (showFilters) {
            event.preventDefault();
            useSettingsStore.getState().setShowFilters(false);
          } else if (unfoldedNodeId) {
            event.preventDefault();
            useUIStore.getState().fold();
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
