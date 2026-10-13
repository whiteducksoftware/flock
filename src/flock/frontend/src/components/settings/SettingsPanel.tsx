/**
 * The settings sheet (docs/internal/design-system/README.md, Where everything
 * went): Graph, Appearance and Advanced as tabs, on the right of the board.
 * Ctrl+, and the header's settings button open it, Esc closes it.
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import { resetToDefaultTheme } from '../../services/themeApplicator';
import { useSettingsStore } from '../../store/settingsStore';
import BuildInfo from '../common/BuildInfo';
import { nextTab } from '../graph/tabKeys';
import { Icon } from '../icons/Icon';
import AdvancedSettings from './AdvancedSettings';
import AppearanceSettings from './AppearanceSettings';
import GraphSettings from './GraphSettings';
import styles from './SettingsPanel.module.css';
import './settingsFields.css';

const TABS = [
  { key: 'graph', label: 'Graph' },
  { key: 'appearance', label: 'Appearance' },
  { key: 'advanced', label: 'Advanced' },
] as const;

type TabName = (typeof TABS)[number]['key'];

const SettingsPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabName>('graph');
  const setShowSettings = useSettingsStore((state) => state.setShowSettings);
  const resetToDefaults = useSettingsStore((state) => state.resetToDefaults);
  const ids = useId();
  const sheet = useRef<HTMLElement>(null);
  // Whatever had the focus before the sheet opened gets it back
  const [opener] = useState(() => document.activeElement as HTMLElement | null);

  // The sheet takes the focus on its open tab
  useEffect(() => {
    sheet.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
    return () => opener?.focus?.();
  }, [opener]);

  const handleReset = () => {
    if (confirm('Reset all settings to defaults? This cannot be undone.')) {
      resetToDefaults();
      resetToDefaultTheme(); // the store's default theme, applied
    }
  };

  const tabId = (key: TabName) => `${ids}-tab-${key}`;

  return (
    <aside ref={sheet} role="dialog" aria-labelledby={`${ids}-title`} className={styles.sheet}>
      <header className={styles.header}>
        <h2 id={`${ids}-title`} className={styles.title}>
          Settings
        </h2>
        <button
          type="button"
          className="btn icon ghost"
          aria-label="Close settings"
          title="Close settings (Esc)"
          onClick={() => setShowSettings(false)}
        >
          <Icon name="close" />
        </button>
      </header>

      <div role="tablist" aria-label="Settings" className={styles.tabs}>
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            id={tabId(key)}
            type="button"
            role="tab"
            aria-selected={activeTab === key}
            aria-controls={`${ids}-panel`}
            tabIndex={activeTab === key ? 0 : -1}
            className={styles.tab}
            onClick={() => setActiveTab(key)}
            onKeyDown={(event) => {
              const next = nextTab(
                TABS.map((tab) => tab.key),
                activeTab,
                event.key,
              );
              if (!next) return;
              event.preventDefault();
              setActiveTab(next);
              document.getElementById(tabId(next))?.focus();
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div id={`${ids}-panel`} role="tabpanel" aria-labelledby={tabId(activeTab)} className={styles.content}>
        {activeTab === 'graph' && <GraphSettings />}
        {activeTab === 'appearance' && <AppearanceSettings />}
        {activeTab === 'advanced' && <AdvancedSettings />}
      </div>

      <footer className={styles.footer}>
        <BuildInfo />
        <button type="button" className="btn sm" onClick={handleReset}>
          Reset to defaults
        </button>
      </footer>
    </aside>
  );
};

export default SettingsPanel;
