import React, { useEffect } from 'react';
import './KeyboardShortcutsDialog.css';

interface KeyboardShortcutsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;

interface Shortcut {
  keys: string[];
  description: string;
  category: 'Navigation' | 'Panels' | 'General';
}

const shortcuts: Shortcut[] = [
  // Navigation
  {
    keys: isMac ? ['⌘', 'M'] : ['Ctrl', 'M'],
    description: 'Toggle Agent/Blackboard View',
    category: 'Navigation',
  },
  {
    keys: isMac ? ['⌘', 'F'] : ['Ctrl', 'F'],
    description: 'Focus filter input',
    category: 'Navigation',
  },

  // Panels
  {
    keys: isMac ? ['⌘', 'Shift', 'P'] : ['Ctrl', 'Shift', 'P'],
    description: 'Toggle Publish Panel',
    category: 'Panels',
  },
  {
    keys: isMac ? ['⌘', 'Shift', 'D'] : ['Ctrl', 'Shift', 'D'],
    description: 'Toggle Agent Details',
    category: 'Panels',
  },
  {
    keys: isMac ? ['⌘', 'Shift', 'F'] : ['Ctrl', 'Shift', 'F'],
    description: 'Toggle Filters Panel',
    category: 'Panels',
  },
  {
    keys: isMac ? ['⌘', ','] : ['Ctrl', ','],
    description: 'Toggle Settings Panel',
    category: 'Panels',
  },

  // General
  {
    keys: ['Esc'],
    description: 'Close panels and windows',
    category: 'General',
  },
  {
    keys: isMac ? ['⌘', '/'] : ['Ctrl', '/'],
    description: 'Show this help dialog',
    category: 'General',
  },
];

const KeyboardShortcutsDialog: React.FC<KeyboardShortcutsDialogProps> = ({ isOpen, onClose }) => {
  // Handle ESC key to close dialog
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown, { capture: true });
    return () => {
      window.removeEventListener('keydown', handleKeyDown, { capture: true });
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = [];
    }
    acc[shortcut.category]!.push(shortcut);
    return acc;
  }, {} as Record<string, Shortcut[]>);

  return (
    <div className="keyboard-shortcuts-overlay" onClick={onClose}>
      <div className="keyboard-shortcuts-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="keyboard-shortcuts-header">
          <h2 className="keyboard-shortcuts-title">Keyboard Shortcuts</h2>
          <button
            className="keyboard-shortcuts-close"
            onClick={onClose}
            aria-label="Close keyboard shortcuts"
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

        <div className="keyboard-shortcuts-content">
          {Object.entries(groupedShortcuts).map(([category, categoryShortcuts]) => (
            <div key={category} className="keyboard-shortcuts-category">
              <h3 className="keyboard-shortcuts-category-title">{category}</h3>
              <div className="keyboard-shortcuts-list">
                {categoryShortcuts.map((shortcut, index) => (
                  <div key={index} className="keyboard-shortcut-item">
                    <div className="keyboard-shortcut-keys">
                      {shortcut.keys.map((key, keyIndex) => (
                        <React.Fragment key={keyIndex}>
                          <kbd className="keyboard-key">{key}</kbd>
                          {keyIndex < shortcut.keys.length - 1 && (
                            <span className="keyboard-key-separator">+</span>
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                    <div className="keyboard-shortcut-description">{shortcut.description}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="keyboard-shortcuts-footer">
          <p className="keyboard-shortcuts-hint">
            Press <kbd className="keyboard-key">Esc</kbd> or click outside to close
          </p>
        </div>
      </div>
    </div>
  );
};

export default KeyboardShortcutsDialog;
