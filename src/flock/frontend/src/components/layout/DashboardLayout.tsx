import React, { useCallback, useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import GraphCanvas from '../graph/GraphCanvas';
import Blackboard from '../blackboard/Blackboard';
import PublishComposer from '../publish/PublishComposer';
import SettingsPanel from '../settings/SettingsPanel';
import KeyboardShortcutsDialog from '../common/KeyboardShortcutsDialog';
import Toast from '../common/Toast';
import CommandPalette from '../palette/CommandPalette';
import { useSettingsStore } from '../../store/settingsStore';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useBoardData } from '../../hooks/useBoardData';
import BoardStates from '../graph/BoardStates';
import TimelineDock from '../timeline/TimelineDock';
import { useUIStore } from '../../store/uiStore';
import AppHeader from './AppHeader';
import './DashboardLayout.css';

const DashboardLayout: React.FC = () => {
  const dockOpen = useUIStore((state) => state.dockOpen);
  const mode = useUIStore((state) => state.mode);

  // The board's data, for the view and the filters
  useBoardData();

  // UI visibility from settings store
  const showControls = useSettingsStore((state) => state.ui.showControls);
  const showSettings = useSettingsStore((state) => state.ui.showSettings);
  const setShowControls = useSettingsStore((state) => state.setShowControls);

  // Keyboard shortcuts help dialog
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const showShortcuts = useCallback(() => setShowKeyboardShortcuts(true), []);
  const paletteOpen = useUIStore((state) => state.paletteOpen);

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
            {/* The Flow is a graph; the Blackboard lays its runs out as lanes */}
            {mode === 'agent' ? (
              <ReactFlowProvider>
                <GraphCanvas />
              </ReactFlowProvider>
            ) : (
              <Blackboard />
            )}
            <BoardStates onPublish={() => setShowControls(true)} />
            {/* Bottom center of the board, so above the timeline dock */}
            <Toast />
          </div>
          <TimelineDock />
        </main>
      </div>

      {/* Publish composer: a modal over the board */}
      {showControls && <PublishComposer />}

      {/* Settings Panel - Slides in from right */}
      {showSettings && <SettingsPanel />}

      {/* The ⌘K palette: search and commands */}
      {paletteOpen && <CommandPalette onShowShortcuts={showShortcuts} />}

      {/* Keyboard Shortcuts Dialog */}
      <KeyboardShortcutsDialog
        isOpen={showKeyboardShortcuts}
        onClose={() => setShowKeyboardShortcuts(false)}
      />
    </div>
  );
};

export default DashboardLayout;
