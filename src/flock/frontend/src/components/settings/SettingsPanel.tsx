/**
 * Settings Panel
 *
 * Main settings container with tabbed interface for:
 * - Graph Settings (edge customization)
 * - Appearance Settings (theme, colors)
 * - Advanced Settings (debug, performance)
 */

import React, { useState } from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import GraphSettings from './GraphSettings';
import AppearanceSettings from './AppearanceSettings';
import AdvancedSettings from './AdvancedSettings';
import BuildInfo from '../common/BuildInfo';
import './SettingsPanel.css';

type TabName = 'graph' | 'appearance' | 'advanced';

const SettingsPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabName>('graph');
  const setShowSettings = useSettingsStore((state) => state.setShowSettings);
  const resetToDefaults = useSettingsStore((state) => state.resetToDefaults);

  const handleClose = () => {
    setShowSettings(false);
  };

  const handleReset = () => {
    if (confirm('Reset all settings to defaults? This cannot be undone.')) {
      resetToDefaults();
    }
  };

  return (
    <div className="settings-panel">
      <div className="settings-panel-inner">
        {/* Header */}
        <div className="settings-header">
          <h2 className="settings-title">Settings</h2>
          <button
            onClick={handleClose}
            className="settings-close-button"
            aria-label="Close settings"
            title="Close settings (Esc)"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M15 5L5 15M5 5l10 10"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="settings-tabs">
          <button
            onClick={() => setActiveTab('graph')}
            className={`settings-tab ${activeTab === 'graph' ? 'active' : ''}`}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="4" cy="8" r="2" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="12" cy="4" r="2" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="12" cy="12" r="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M6 8h4M10 5l2 6" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            Graph
          </button>

          <button
            onClick={() => setActiveTab('appearance')}
            className={`settings-tab ${activeTab === 'appearance' ? 'active' : ''}`}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 2v12M2 8h12M4.343 4.343l7.314 7.314M11.657 4.343L4.343 11.657"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            Appearance
          </button>

          <button
            onClick={() => setActiveTab('advanced')}
            className={`settings-tab ${activeTab === 'advanced' ? 'active' : ''}`}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 10.667a2.667 2.667 0 100-5.334 2.667 2.667 0 000 5.334z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M13 8a5 5 0 01-5 5m0-10a5 5 0 015 5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            Advanced
          </button>
        </div>

        {/* Tab Content */}
        <div className="settings-content">
          {activeTab === 'graph' && <GraphSettings />}
          {activeTab === 'appearance' && <AppearanceSettings />}
          {activeTab === 'advanced' && <AdvancedSettings />}
        </div>

        {/* Footer Actions */}
        <div className="settings-footer">
          <div className="settings-footer-left">
            <BuildInfo />
          </div>
          <button onClick={handleReset} className="settings-reset-button">
            Reset to Defaults
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;
