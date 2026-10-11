/**
 * The dashboard's one header row: wordmark, Flow / Blackboard, the scope
 * chips, search, the live status, Publish, settings and shortcuts. It wraps
 * on narrow windows.
 */

import React from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import { useUIStore } from '../../store/uiStore';
import ScopeChips from '../filters/ScopeChips';
import { FlockMark, Icon } from '../icons/Icon';
import LiveStatus from './LiveStatus';
import styles from './AppHeader.module.css';

const VIEWS = [
  { mode: 'agent', label: 'Flow' },
  { mode: 'blackboard', label: 'Blackboard' },
] as const;

const AppHeader: React.FC<{ onShowShortcuts: () => void }> = ({ onShowShortcuts }) => {
  const mode = useUIStore((state) => state.mode);
  const setMode = useUIStore((state) => state.setMode);
  const showControls = useSettingsStore((state) => state.ui.showControls);
  const showSettings = useSettingsStore((state) => state.ui.showSettings);
  const setShowControls = useSettingsStore((state) => state.setShowControls);
  const setShowSettings = useSettingsStore((state) => state.setShowSettings);

  return (
    <header className={styles.header}>
      <span className={styles.wordmark}>
        <FlockMark size={22} />
        <span>flock</span>
      </span>

      <nav aria-label="Views" className={styles.views} title="Switch views (Ctrl+M)">
        {VIEWS.map((view) => (
          <button
            key={view.mode}
            type="button"
            className="seg"
            aria-pressed={mode === view.mode}
            onClick={() => setMode(view.mode)}
          >
            {view.label}
          </button>
        ))}
      </nav>

      <ScopeChips />

      <div className={styles.spacer} />

      <button type="button" className={`chip ${styles.search}`} disabled title="Search arrives with the command palette">
        <span className={styles.searchLabel}>
          <Icon name="search" size={14} />
          <span>Search agents, types, runs</span>
        </span>
        <kbd>⌘K</kbd>
      </button>

      <LiveStatus />

      <button
        type="button"
        className="btn primary"
        aria-pressed={showControls}
        title="Publish an artifact (Ctrl+Shift+P)"
        onClick={() => setShowControls(!showControls)}
      >
        <Icon name="plus" size={14} />
        <span>Publish</span>
      </button>

      <div className={styles.tools}>
        <button
          type="button"
          className="btn icon ghost"
          aria-label="Settings"
          aria-pressed={showSettings}
          title="Settings (Ctrl+,)"
          onClick={() => setShowSettings(!showSettings)}
        >
          <Icon name="settings" />
        </button>
        <button
          type="button"
          className="btn icon ghost"
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts (Ctrl+/)"
          onClick={onShowShortcuts}
        >
          <Icon name="shortcuts" />
        </button>
      </div>
    </header>
  );
};

export default AppHeader;
