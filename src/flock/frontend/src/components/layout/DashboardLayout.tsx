import React, { useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import GraphCanvas from '../graph/GraphCanvas';
import DetailWindowContainer from '../details/DetailWindowContainer';
import PublishControl from '../controls/PublishControl';
import SettingsPanel from '../settings/SettingsPanel';
import KeyboardShortcutsDialog from '../common/KeyboardShortcutsDialog';
import { useSettingsStore } from '../../store/settingsStore';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import BoardStates from '../graph/BoardStates';
import TimelineDock from '../timeline/TimelineDock';
import { useUIStore } from '../../store/uiStore';
import AppHeader from './AppHeader';
import './DashboardLayout.css';

const DashboardLayout: React.FC = () => {
  const dockOpen = useUIStore((state) => state.dockOpen);

  // UI visibility from settings store
  const showControls = useSettingsStore((state) => state.ui.showControls);
  const showSettings = useSettingsStore((state) => state.ui.showSettings);
  const setShowControls = useSettingsStore((state) => state.setShowControls);

  // Keyboard shortcuts help dialog
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);

  // The dashboard's keyboard shortcuts, registered once
  useKeyboardShortcuts({
    onToggleHelp: () => setShowKeyboardShortcuts((prev) => !prev),
  });

  return (
    <div className="dashboard-layout">
      <AppHeader onShowShortcuts={() => setShowKeyboardShortcuts(true)} />

      <div className="dashboard-main">
        <main className="graph-container">
          {/* With the timeline dock expanded the board keeps a strip of chips */}
          <div className={`board-area${dockOpen ? ' docked' : ''}`}>
            <ReactFlowProvider>
              <GraphCanvas />
            </ReactFlowProvider>
            <BoardStates onPublish={() => setShowControls(true)} />
          </div>
          <TimelineDock />
        </main>
      </div>

      {/* Detail Windows */}
      <DetailWindowContainer />

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
