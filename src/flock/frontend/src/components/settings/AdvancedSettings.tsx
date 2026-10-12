/**
 * Settings › Advanced: the Flow's layout spacing, clearing the dashboard's
 * data, and the versions. The direction of a layout is the canvas dock's
 * layout menu; debug and performance mode were read nowhere and are gone.
 */

import React, { useEffect, useState } from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import { clearDashboardData } from '../../utils/clearDashboardData';

const AdvancedSettings: React.FC = () => {
  const nodeSpacing = useSettingsStore((state) => state.advanced.nodeSpacing);
  const rankSpacing = useSettingsStore((state) => state.advanced.rankSpacing);

  const setNodeSpacing = useSettingsStore((state) => state.setNodeSpacing);
  const setRankSpacing = useSettingsStore((state) => state.setRankSpacing);

  // Another dashboard tab keeps the data open while it is cleared
  const [clearBlocked, setClearBlocked] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  // Version information state
  const [backendVersion, setBackendVersion] = useState<string>('Loading...');
  const dashboardVersion = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'dev';

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
        <h3 className="settings-section-title">Layout of the Flow</h3>

        <div className="settings-field">
          <label htmlFor="node-spacing" className="settings-label">
            Node spacing: {nodeSpacing}px
          </label>
          <p className="settings-description">
            Space between agents of one rank; the board lays itself out again
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
            Rank spacing: {rankSpacing}px
          </label>
          <p className="settings-description">
            Space between ranks of the hierarchical layouts
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
        <h3 className="settings-section-title">Data</h3>

        <div className="settings-field">
          <p className="settings-description">
            Forget the graph, filters, windows, layouts and presets this browser keeps. The blackboard is not touched.
          </p>
          <button
            type="button"
            className="btn sm"
            onClick={() => {
              if (confirm('Clear all dashboard data? This will remove all graph data and session data.')) {
                setClearError(null);
                clearDashboardData(undefined, () => setClearBlocked(true)).catch((error: unknown) => {
                  setClearBlocked(false);
                  setClearError(error instanceof Error ? error.message : String(error));
                });
              }
            }}
          >
            Clear all dashboard data
          </button>
          {clearBlocked && (
            <p role="status" className="settings-description">
              Close the other dashboard tabs to finish clearing.
            </p>
          )}
          {clearError && (
            <p role="alert" className="settings-description settings-error">
              The dashboard data could not be cleared: {clearError}
            </p>
          )}
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Versions</h3>
        <dl className="settings-versions">
          <dt>Dashboard</dt>
          <dd className="mono">{dashboardVersion}</dd>
          <dt>Flock</dt>
          <dd className="mono">{backendVersion}</dd>
          <dt>React Flow</dt>
          <dd className="mono">12.8.6</dd>
        </dl>
      </div>
    </div>
  );
};

export default AdvancedSettings;
