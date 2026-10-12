import { useEffect } from 'react';
import { useGraphStore } from '../store/graphStore';
import { useUIStore } from '../store/uiStore';
import { useSettingsStore } from '../store/settingsStore';

interface KeyboardShortcutConfig {
  onToggleMode?: () => void;
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
const SPACE_TAKEN =
  'input, textarea, select, button, a[href], [contenteditable="true"], [role="button"], [role="tab"], [role="dialog"]';

/**
 * Custom hook for managing global keyboard shortcuts
 *
 * Shortcuts:
 * - Ctrl+K (or Cmd+K): Open or close the palette (search and commands); Ctrl+F is the browser's find
 * - Ctrl+M (or Cmd+M): Toggle between the Flow and Blackboard views
 * - Ctrl+, (or Cmd+,): Toggle Settings Panel
 * - Ctrl+Shift+F: Toggle Filters Panel
 * - Ctrl+Shift+P: Open or close the publish composer
 * - Space, Ctrl+Shift+D: Unfold or fold the selected node
 * - Enter: Put the focused node (else the selected one) in focus
 * - Ctrl+/ (or Cmd+/): Toggle Keyboard Shortcuts Help
 * - Esc: Close a panel, else leave focus mode, else collapse the timeline dock, else fold the unfolded node, else close the artifact windows
 */
export const useKeyboardShortcuts = (config: KeyboardShortcutConfig = {}) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for modifier key (Ctrl on Windows/Linux, Cmd on Mac)
      const modifier = event.ctrlKey || event.metaKey;

      // Ctrl+K or Cmd+K: Open or close the palette (not over another modal dialog)
      if (modifier && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'k') {
        const { paletteOpen, openPalette, closePalette } = useUIStore.getState();
        if (!paletteOpen && document.querySelector('[aria-modal="true"]')) return;
        event.preventDefault();
        if (paletteOpen) closePalette();
        else openPalette();
        return;
      }

      // A modal dialog has the keyboard: only Esc reaches the board's shortcuts
      // (it closes the dialog), nothing behind the dialog opens or takes the focus
      if (event.key !== 'Escape' && document.querySelector('[aria-modal="true"]')) return;

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

      // Ctrl+Shift+P: Open or close the publish composer
      if (modifier && event.shiftKey && event.key === 'P') {
        event.preventDefault();
        const showControls = useSettingsStore.getState().ui.showControls;
        useSettingsStore.getState().setShowControls(!showControls);
        return;
      }

      // Ctrl+Shift+D: Unfold or fold the selected node (not behind a node in focus)
      if (modifier && event.shiftKey && event.key === 'D') {
        event.preventDefault();
        if (useUIStore.getState().focusedNodeId) return;
        const target = unfoldTarget();
        if (target) useUIStore.getState().toggleUnfold(target);
        return;
      }

      // Space: Unfold or fold the selected node, unless the focus has a use for it
      if (event.key === ' ' && !modifier && !event.altKey) {
        if (document.activeElement?.closest(SPACE_TAKEN) || useUIStore.getState().focusedNodeId) return;
        const target = unfoldTarget();
        if (!target) return;
        event.preventDefault();
        useUIStore.getState().toggleUnfold(target);
        return;
      }

      // Enter: put the focused node (else the selected one) in focus, unless the focus has a use for it
      if (event.key === 'Enter' && !modifier && !event.altKey && !event.shiftKey) {
        if (document.activeElement?.closest(SPACE_TAKEN) || useUIStore.getState().focusedNodeId) return;
        const target = unfoldTarget();
        if (!target) return;
        event.preventDefault();
        useUIStore.getState().focus(target);
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

      // Esc: Close windows/dialogs/panels, unless a dialog already handled it
      if (event.key === 'Escape') {
        if (event.defaultPrevented) return;
        if (config.onCloseWindows) {
          config.onCloseWindows();
        } else {
          // Priority: panels, then focus mode, the timeline dock, what the view unfolded
          // (an agent on the Flow, an artifact card on the Blackboard)
          const { showSettings, showFilters, showControls } = useSettingsStore.getState().ui;
          const { mode, unfoldedNodeId, unfoldedArtifactId, focusedNodeId, dockOpen } = useUIStore.getState();

          if (showSettings) {
            event.preventDefault();
            useSettingsStore.getState().setShowSettings(false);
          } else if (showControls) {
            event.preventDefault();
            useSettingsStore.getState().setShowControls(false);
          } else if (showFilters) {
            event.preventDefault();
            useSettingsStore.getState().setShowFilters(false);
          } else if (focusedNodeId) {
            event.preventDefault();
            useUIStore.getState().unfocus();
          } else if (dockOpen) {
            event.preventDefault();
            useUIStore.getState().closeDock();
          } else if (mode === 'blackboard' && unfoldedArtifactId) {
            event.preventDefault();
            useUIStore.getState().foldArtifact();
          } else if (mode === 'agent' && unfoldedNodeId) {
            event.preventDefault();
            useUIStore.getState().fold();
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
