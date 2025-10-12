import React, { useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import GraphCanvas from '../graph/GraphCanvas';
import DetailWindowContainer from '../details/DetailWindowContainer';
import FilterFlyout from '../filters/FilterFlyout';
import FilterPills from '../filters/FilterPills';
import PublishControl from '../controls/PublishControl';
import ModuleWindow from '../modules/ModuleWindow';
import SettingsPanel from '../settings/SettingsPanel';
import KeyboardShortcutsDialog from '../common/KeyboardShortcutsDialog';
import { useUIStore } from '../../store/uiStore';
import { useModuleStore } from '../../store/moduleStore';
import { useGraphStore } from '../../store/graphStore';
import { useFilterStore } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import { useModulePersistence } from '../../hooks/useModulePersistence';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import Header from './Header';
import './DashboardLayout.css';

const DashboardLayout: React.FC = () => {
  const mode = useUIStore((state) => state.mode);
  const setMode = useUIStore((state) => state.setMode);
  const moduleInstances = useModuleStore((state) => state.instances);
  const detailWindows = useUIStore((state) => state.detailWindows);

  // UI visibility from settings store
  const showFilters = useSettingsStore((state) => state.ui.showFilters);
  const showControls = useSettingsStore((state) => state.ui.showControls);
  const showSettings = useSettingsStore((state) => state.ui.showSettings);
  const setShowFilters = useSettingsStore((state) => state.setShowFilters);
  const setShowControls = useSettingsStore((state) => state.setShowControls);
  const setShowSettings = useSettingsStore((state) => state.setShowSettings);

  // Keyboard shortcuts help dialog
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);

  // Enable module window persistence
  useModulePersistence();

  const handleToggleAgentDetails = () => {
    const detailWindows = useUIStore.getState().detailWindows;

    // Check if any detail windows are open
    if (detailWindows.size > 0) {
      // Close all detail windows
      detailWindows.forEach((_, nodeId) => {
        useUIStore.getState().closeDetailWindow(nodeId);
      });
    } else {
      // UI Optimization Migration (Phase 4.1): Read agent nodes from state.nodes
      const nodes = useGraphStore.getState().nodes;
      const agentNodes = nodes.filter((node) => node.type === 'agent');

      // Open detail windows for all agents
      agentNodes.forEach((node) => {
        useUIStore.getState().openDetailWindow(node.id);
      });
    }
  };

  // Enable keyboard shortcuts with help dialog toggle
  useKeyboardShortcuts({
    onToggleHelp: () => setShowKeyboardShortcuts((prev) => !prev),
    onToggleAgentDetails: handleToggleAgentDetails,
  });

  const handleClearStore = () => {
    if (confirm('Clear all dashboard data? This will remove all graph data and session data.')) {
      // UI Optimization Migration (Phase 4.1): Clear NEW Phase 2 state only
      useGraphStore.setState({
        events: [],
        nodes: [],
        edges: [],
        statistics: null,
        agentStatus: new Map(),
        streamingTokens: new Map(),
      });

      // Clear UI store
      useUIStore.setState({ mode: 'agent' });

      // Clear filter store
      useFilterStore.setState({
        correlationId: undefined,
        timeRange: undefined,
      });

      // Clear module store
      useModuleStore.getState().instances.clear();

      // Clear IndexedDB
      indexedDB.databases().then((dbs) => {
        dbs.forEach((db) => {
          if (db.name) indexedDB.deleteDatabase(db.name);
        });
      });

      // Clear localStorage
      localStorage.clear();

      // Reload page
      window.location.reload();
    }
  };

  return (
    <div className="dashboard-layout">
      {/* Header */}
      <header className="dashboard-header">
        <h1 className="dashboard-title">🦆🐓  Flock  🐤🐧</h1>

        <div className="view-toggle-container">
          <span className="view-toggle-label">View:</span>
          <div className="view-toggle-group">
            <button
              type="button"
              onClick={() => setMode('agent')}
              className={`view-toggle-button ${mode === 'agent' ? 'active' : ''}`}
            >
              Agent View
            </button>
            <button
              type="button"
              onClick={() => setMode('blackboard')}
              className={`view-toggle-button ${mode === 'blackboard' ? 'active' : ''}`}
            >
              Blackboard View
            </button>
          </div>
        </div>

        <div className="dashboard-actions">
          {/* Publish - Primary action, first in order */}
          <button
            type="button"
            onClick={() => setShowControls(!showControls)}
            className={`controls-toggle primary ${showControls ? 'active' : ''}`}
            title="Publish artifacts to the blackboard (Ctrl+Shift+P)"
            aria-pressed={showControls ? 'true' : 'false'}
            aria-label={showControls ? 'Publish panel open' : 'Publish panel closed'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 2.667v10.666M2.667 8h10.666"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>Publish</span>
          </button>

          {/* Agent Details */}
          <button
            type="button"
            onClick={handleToggleAgentDetails}
            className={`controls-toggle ${detailWindows.size > 0 ? 'active' : ''}`}
            title={`${detailWindows.size > 0 ? 'Close' : 'Show'} agent detail windows (Ctrl+Shift+D)`}
            aria-pressed={detailWindows.size > 0 ? 'true' : 'false'}
            aria-label={detailWindows.size > 0 ? 'Agent details shown' : 'Agent details hidden'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M2 4.667h12M2 8h12M2 11.333h12"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>Agent Details</span>
          </button>

          {/* Settings */}
          <button
            type="button"
            onClick={() => setShowSettings(!showSettings)}
            className={`controls-toggle ${showSettings ? 'active' : ''}`}
            title={`${showSettings ? 'Hide' : 'Show'} settings panel (Ctrl+,)`}
            aria-pressed={showSettings ? 'true' : 'false'}
            aria-label={showSettings ? 'Settings shown' : 'Settings hidden'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 10a2 2 0 100-4 2 2 0 000 4z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M13.333 8c0-.367-.2-.7-.533-.867l-.933-.467a.933.933 0 01-.467-.8v-.133c0-.334.133-.6.467-.8l.933-.467c.333-.166.533-.5.533-.866 0-.367-.2-.7-.533-.867L11.867 2.4a.933.933 0 01-.467-.8V1.333c0-.366-.233-.666-.6-.666H9.2c-.366 0-.666.3-.666.666V1.6c0 .334-.267.634-.6.8l-.934.467c-.333.166-.7.166-1 0l-.933-.467a.933.933 0 00-.8 0L2.533 3.067c-.333.166-.533.5-.533.866 0 .367.2.7.533.867l.933.467c.334.2.467.466.467.8v.133c0 .334-.133.6-.467.8l-.933.467c-.333.166-.533.5-.533.866 0 .367.2.7.533.867l.934.533c.333.2.6.5.6.8v.267c0 .366.3.666.666.666h1.6c.367 0 .667-.3.667-.666v-.267c0-.3.267-.6.6-.8l.933-.533c.334-.167.7-.167 1 0l.934.533c.333.2.6.5.6.8v.267c0 .366.3.666.666.666H9.2c.367 0 .667-.3.667-.666v-.267c0-.3.266-.6.6-.8l.933-.533c.333-.167.533-.5.533-.867z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
            <span>Settings</span>
          </button>

          <button
            type="button"
            onClick={() => setShowKeyboardShortcuts(true)}
            className="icon-button help-button"
            title="Keyboard shortcuts (Ctrl+/)"
            aria-label="Show keyboard shortcuts"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle
                cx="8"
                cy="8"
                r="6.5"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M8 11.5v-.5M8 8.5v-2a1.5 1.5 0 10-1.5-1.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <circle cx="8" cy="11.5" r="0.5" fill="currentColor" />
            </svg>
          </button>

          <button
            type="button"
            onClick={handleClearStore}
            className="icon-button clear-button"
            title="Clear all dashboard data"
            aria-label="Clear all dashboard data"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M2 4h12M5.333 4V2.667a1.333 1.333 0 011.334-1.334h2.666a1.333 1.333 0 011.334 1.334V4m2 0v9.333a1.333 1.333 0 01-1.334 1.334H4.667a1.333 1.333 0 01-1.334-1.334V4h9.334z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          <Header />
        </div>
      </header>

      <div className="filter-pills-bar">
        <FilterPills />
      </div>

      {/* Filter Flyout */}
      {showFilters && <FilterFlyout onClose={() => setShowFilters(false)} />}

      {/* Main Content */}
      <div className="dashboard-main">
        {/* Graph Canvas */}
        <main className="graph-container">
          <ReactFlowProvider>
            <GraphCanvas />
          </ReactFlowProvider>
        </main>
      </div>

      {/* Detail Windows */}
      <DetailWindowContainer />

      {/* Module Windows */}
      {Array.from(moduleInstances.values()).map((instance) => (
        <ModuleWindow key={instance.id} instanceId={instance.id} />
      ))}

      {/* Publish Control Panel - Slides in from right */}
      {showControls && <PublishControl />}

      {/* Settings Panel - Slides in from right */}
      {showSettings && <SettingsPanel />}

      {/* Keyboard Shortcuts Dialog */}
      <KeyboardShortcutsDialog
        isOpen={showKeyboardShortcuts}
        onClose={() => setShowKeyboardShortcuts(false)}
      />
    </div>
  );
};

export default DashboardLayout;
