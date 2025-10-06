/**
 * Appearance Settings Tab
 *
 * Visual customization options:
 * - Theme selection (300+ terminal themes)
 * - Agent node colors (idle, active, error)
 * - Node shadow intensity
 * - Status pulse animation
 * - Compact view mode
 */

import React from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import ThemeSelector from './ThemeSelector';

const AppearanceSettings: React.FC = () => {
  const agentIdleColor = useSettingsStore((state) => state.appearance.agentIdleColor);
  const agentActiveColor = useSettingsStore((state) => state.appearance.agentActiveColor);
  const agentErrorColor = useSettingsStore((state) => state.appearance.agentErrorColor);
  const nodeShadow = useSettingsStore((state) => state.appearance.nodeShadow);
  const showStatusPulse = useSettingsStore((state) => state.appearance.showStatusPulse);
  const compactNodeView = useSettingsStore((state) => state.appearance.compactNodeView);

  const setAgentIdleColor = useSettingsStore((state) => state.setAgentIdleColor);
  const setAgentActiveColor = useSettingsStore((state) => state.setAgentActiveColor);
  const setAgentErrorColor = useSettingsStore((state) => state.setAgentErrorColor);
  const setNodeShadow = useSettingsStore((state) => state.setNodeShadow);
  const setShowStatusPulse = useSettingsStore((state) => state.setShowStatusPulse);
  const setCompactNodeView = useSettingsStore((state) => state.setCompactNodeView);

  return (
    <div>
      <div className="settings-section">
        <h3 className="settings-section-title">Theme</h3>

        <p className="settings-description" style={{ marginBottom: 'var(--space-component-md)' }}>
          Choose from 300+ terminal color themes. Themes are loaded from the backend and applied in real-time.
        </p>

        <ThemeSelector />
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Agent Colors</h3>

        <div className="settings-field">
          <label htmlFor="idle-color" className="settings-label">
            Idle Agent Color
          </label>
          <p className="settings-description">
            Border and indicator color for idle agents
          </p>
          <div style={{ display: 'flex', gap: 'var(--gap-sm)', alignItems: 'center' }}>
            <input
              id="idle-color"
              type="color"
              value={agentIdleColor}
              onChange={(e) => setAgentIdleColor(e.target.value)}
              style={{ width: '60px', height: '36px', cursor: 'pointer' }}
            />
            <input
              type="text"
              value={agentIdleColor}
              onChange={(e) => setAgentIdleColor(e.target.value)}
              className="settings-input"
              placeholder="#60a5fa"
            />
          </div>
        </div>

        <div className="settings-field">
          <label htmlFor="active-color" className="settings-label">
            Active Agent Color
          </label>
          <p className="settings-description">
            Border and indicator color for running agents (thick border)
          </p>
          <div style={{ display: 'flex', gap: 'var(--gap-sm)', alignItems: 'center' }}>
            <input
              id="active-color"
              type="color"
              value={agentActiveColor}
              onChange={(e) => setAgentActiveColor(e.target.value)}
              style={{ width: '60px', height: '36px', cursor: 'pointer' }}
            />
            <input
              type="text"
              value={agentActiveColor}
              onChange={(e) => setAgentActiveColor(e.target.value)}
              className="settings-input"
              placeholder="#10b981"
            />
          </div>
        </div>

        <div className="settings-field">
          <label htmlFor="error-color" className="settings-label">
            Error Agent Color
          </label>
          <p className="settings-description">
            Border and indicator color for agents in error state
          </p>
          <div style={{ display: 'flex', gap: 'var(--gap-sm)', alignItems: 'center' }}>
            <input
              id="error-color"
              type="color"
              value={agentErrorColor}
              onChange={(e) => setAgentErrorColor(e.target.value)}
              style={{ width: '60px', height: '36px', cursor: 'pointer' }}
            />
            <input
              type="text"
              value={agentErrorColor}
              onChange={(e) => setAgentErrorColor(e.target.value)}
              className="settings-input"
              placeholder="#ef4444"
            />
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Node Appearance</h3>

        <div className="settings-field">
          <label htmlFor="node-shadow" className="settings-label">
            Node Shadow
          </label>
          <p className="settings-description">
            Shadow intensity for node elevation effect
          </p>
          <select
            id="node-shadow"
            value={nodeShadow}
            onChange={(e) => setNodeShadow(e.target.value as typeof nodeShadow)}
            className="settings-select"
          >
            <option value="none">None</option>
            <option value="small">Small</option>
            <option value="medium">Medium (Default)</option>
            <option value="large">Large</option>
          </select>
        </div>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="status-pulse"
              type="checkbox"
              checked={showStatusPulse}
              onChange={(e) => setShowStatusPulse(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="status-pulse" className="settings-checkbox-label">
              Show status pulse animation
            </label>
          </div>
          <p className="settings-description">
            Animate status indicator for running agents
          </p>
        </div>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="compact-view"
              type="checkbox"
              checked={compactNodeView}
              onChange={(e) => setCompactNodeView(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="compact-view" className="settings-checkbox-label">
              Compact node view
            </label>
          </div>
          <p className="settings-description">
            Reduce node size and spacing (useful for large graphs)
          </p>
        </div>
      </div>
    </div>
  );
};

export default AppearanceSettings;
