/**
 * Advanced Settings Tab
 *
 * Power-user settings:
 * - Layout direction (top-bottom vs left-right) for manual layout
 * - Node and rank spacing for manual layout algorithm
 * - Debug mode (show node IDs, verbose logging)
 * - Performance mode (disable animations/effects)
 */

import React, { useEffect, useState } from 'react';
import { useSettingsStore } from '../../store/settingsStore';

const AdvancedSettings: React.FC = () => {
  const layoutDirection = useSettingsStore((state) => state.advanced.layoutDirection);
  const nodeSpacing = useSettingsStore((state) => state.advanced.nodeSpacing);
  const rankSpacing = useSettingsStore((state) => state.advanced.rankSpacing);
  const debugMode = useSettingsStore((state) => state.advanced.debugMode);
  const performanceMode = useSettingsStore((state) => state.advanced.performanceMode);

  const setLayoutDirection = useSettingsStore((state) => state.setLayoutDirection);
  const setNodeSpacing = useSettingsStore((state) => state.setNodeSpacing);
  const setRankSpacing = useSettingsStore((state) => state.setRankSpacing);
  const setDebugMode = useSettingsStore((state) => state.setDebugMode);
  const setPerformanceMode = useSettingsStore((state) => state.setPerformanceMode);

  // Version information state
  const [backendVersion, setBackendVersion] = useState<string>('Loading...');
  const dashboardVersion = '0.1.1'; // From package.json

  // Fetch version information from backend
  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const response = await fetch('/api/version');
        if (response.ok) {
          const data = await response.json();
          setBackendVersion(data.backend_version || 'Unknown');
        } else {
          setBackendVersion('Error fetching version');
        }
      } catch (error) {
        console.error('Failed to fetch version:', error);
        setBackendVersion('Error fetching version');
      }
    };

    fetchVersion();
  }, []);

  return (
    <div>
      <div className="settings-section">
        <h3 className="settings-section-title">Graph Layout</h3>

        <div className="settings-field">
          <label htmlFor="layout-direction" className="settings-label">
            Layout Direction
          </label>
          <p className="settings-description">
            Direction for manual layout algorithm (right-click → Auto Layout)
          </p>
          <select
            id="layout-direction"
            value={layoutDirection}
            onChange={(e) => setLayoutDirection(e.target.value as typeof layoutDirection)}
            className="settings-select"
          >
            <option value="LR">Left to Right (Default)</option>
            <option value="TB">Top to Bottom</option>
          </select>
        </div>

        <div className="settings-field">
          <label htmlFor="node-spacing" className="settings-label">
            Node Spacing: {nodeSpacing}px
          </label>
          <p className="settings-description">
            Horizontal space between nodes when using manual layout (affects edge label visibility)
          </p>
          <input
            id="node-spacing"
            type="range"
            min="25"
            max="150"
            step="5"
            value={nodeSpacing}
            onChange={(e) => setNodeSpacing(parseFloat(e.target.value))}
            className="settings-input"
          />
        </div>

        <div className="settings-field">
          <label htmlFor="rank-spacing" className="settings-label">
            Rank Spacing: {rankSpacing}px
          </label>
          <p className="settings-description">
            Vertical space between graph layers when using manual layout
          </p>
          <input
            id="rank-spacing"
            type="range"
            min="50"
            max="300"
            step="10"
            value={rankSpacing}
            onChange={(e) => setRankSpacing(parseFloat(e.target.value))}
            className="settings-input"
          />
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Developer Options</h3>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="debug-mode"
              type="checkbox"
              checked={debugMode}
              onChange={(e) => setDebugMode(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="debug-mode" className="settings-checkbox-label">
              Debug mode
            </label>
          </div>
          <p className="settings-description">
            Show node IDs, detailed message counts, and verbose console logging
          </p>
        </div>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="performance-mode"
              type="checkbox"
              checked={performanceMode}
              onChange={(e) => setPerformanceMode(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="performance-mode" className="settings-checkbox-label">
              Performance mode
            </label>
          </div>
          <p className="settings-description">
            Disable animations, shadows, and blur effects for better performance
          </p>
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Information</h3>

        <div className="settings-field">
          <p className="settings-description" style={{ marginBottom: 'var(--spacing-2)' }}>
            <strong>Dashboard Version:</strong> {dashboardVersion}
          </p>
          <p className="settings-description" style={{ marginBottom: 'var(--spacing-2)' }}>
            <strong>Backend Version:</strong> {backendVersion}
          </p>
          <p className="settings-description" style={{ marginBottom: 'var(--spacing-2)' }}>
            <strong>React Flow Version:</strong> 12.8.6
          </p>
          <p className="settings-description">
            <strong>Local Storage Used:</strong> {localStorage.length} keys
          </p>
        </div>
      </div>
    </div>
  );
};

export default AdvancedSettings;
