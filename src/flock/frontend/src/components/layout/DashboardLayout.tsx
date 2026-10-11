import React, { useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import GraphCanvas from '../graph/GraphCanvas';
import DetailWindowContainer from '../details/DetailWindowContainer';
import PublishControl from '../controls/PublishControl';
import ModuleWindow from '../modules/ModuleWindow';
import SettingsPanel from '../settings/SettingsPanel';
import KeyboardShortcutsDialog from '../common/KeyboardShortcutsDialog';
import { useModuleStore } from '../../store/moduleStore';
import { useSettingsStore } from '../../store/settingsStore';
import { useModulePersistence } from '../../hooks/useModulePersistence';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import BoardStates from '../graph/BoardStates';
import AppHeader from './AppHeader';
import './DashboardLayout.css';

const DashboardLayout: React.FC = () => {
  const moduleInstances = useModuleStore((state) => state.instances);

  // UI visibility from settings store
  const showControls = useSettingsStore((state) => state.ui.showControls);
  const showSettings = useSettingsStore((state) => state.ui.showSettings);
  const setShowControls = useSettingsStore((state) => state.setShowControls);

  // Keyboard shortcuts help dialog
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);

  // Enable module window persistence
  useModulePersistence();

  // The dashboard's keyboard shortcuts, registered once
  useKeyboardShortcuts({
    onToggleHelp: () => setShowKeyboardShortcuts((prev) => !prev),
  });

  return (
    <div className="dashboard-layout">
      <AppHeader onShowShortcuts={() => setShowKeyboardShortcuts(true)} />

      <div className="dashboard-main">
        <main className="graph-container">
          <ReactFlowProvider>
            <GraphCanvas />
          </ReactFlowProvider>
          <BoardStates onPublish={() => setShowControls(true)} />
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
