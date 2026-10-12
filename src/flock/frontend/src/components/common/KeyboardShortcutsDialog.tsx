/**
 * The keyboard shortcuts (Ctrl+/ or the header's keyboard button): a modal
 * on the tokens with the keys of the board, the panels, the publish composer
 * and the palette (docs/internal/design-system/README.md, Accessibility).
 */

import React, { useEffect, useId, useRef } from 'react';
import { isMac } from '../../utils/keys';
import { Icon } from '../icons/Icon';
import styles from './KeyboardShortcutsDialog.module.css';

interface KeyboardShortcutsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const MOD = isMac ? '⌘' : 'Ctrl';

const GROUPS: { title: string; shortcuts: { keys: string[]; description: string }[] }[] = [
  {
    title: 'Board',
    shortcuts: [
      { keys: [MOD, 'M'], description: 'Switch between Flow and Blackboard' },
      { keys: [MOD, 'K'], description: 'Search agents, types and runs, or run a command' },
      { keys: ['Space'], description: 'Unfold or fold the selected node' },
      { keys: [MOD, 'Shift', 'D'], description: 'Unfold or fold the selected node' },
      { keys: ['Enter'], description: 'Put the selected node in focus' },
      { keys: ['Esc'], description: 'Leave focus, close a panel, else fold' },
    ],
  },
  {
    title: 'Panels',
    shortcuts: [
      { keys: [MOD, 'Shift', 'P'], description: 'Open or close the publish composer' },
      { keys: [MOD, 'Shift', 'F'], description: 'Open or close the filters' },
      { keys: [MOD, ','], description: 'Open or close the settings' },
      { keys: [MOD, '/'], description: 'Show or hide these shortcuts' },
    ],
  },
  {
    title: 'Publish composer',
    shortcuts: [
      { keys: [MOD, 'Enter'], description: 'Publish' },
      { keys: ['↑', '↓'], description: 'Move through the types' },
    ],
  },
  {
    title: 'Palette',
    shortcuts: [
      { keys: ['↑', '↓'], description: 'Move through the results' },
      { keys: ['Enter'], description: 'Run the first action of a result' },
      { keys: ['Shift', 'Enter'], description: 'Run the second action of a result' },
      { keys: [MOD, 'Enter'], description: 'Run the third action of a result' },
    ],
  },
];

const KeyboardShortcutsDialog: React.FC<KeyboardShortcutsDialogProps> = ({ isOpen, onClose }) => {
  const ids = useId();
  const close = useRef<HTMLButtonElement>(null);

  // Open: the focus goes in; closed: back where it was
  useEffect(() => {
    if (!isOpen) return;
    const opener = document.activeElement as HTMLElement | null;
    close.current?.focus();
    return () => opener?.focus?.();
  }, [isOpen]);

  if (!isOpen) return null;

  const onKeyDown = (event: React.KeyboardEvent) => {
    // Esc and Ctrl+/ close it (a modal: the board's shortcuts stay behind it)
    if (event.key === 'Escape' || (event.key === '/' && (event.ctrlKey || event.metaKey))) {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    // The close button is the one stop: Tab stays on it
    if (event.key === 'Tab') {
      event.preventDefault();
      close.current?.focus();
    }
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.scrim} aria-hidden onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${ids}-title`}
        className={styles.dialog}
        onKeyDown={onKeyDown}
      >
        <header className={styles.header}>
          <h2 id={`${ids}-title`} className={styles.title}>
            Keyboard shortcuts
          </h2>
          <button ref={close} type="button" className="btn icon ghost" aria-label="Close keyboard shortcuts" onClick={onClose}>
            <Icon name="close" />
          </button>
        </header>
        <div className={styles.groups}>
          {GROUPS.map((group) => (
            <section key={group.title} className={styles.group} aria-labelledby={`${ids}-${group.title}`}>
              <h3 id={`${ids}-${group.title}`} className={styles.groupTitle}>
                {group.title}
              </h3>
              <dl className={styles.list}>
                {group.shortcuts.map((shortcut) => (
                  <div key={`${shortcut.keys.join('+')}-${shortcut.description}`} className={styles.row}>
                    <dt className={styles.keys}>
                      {shortcut.keys.map((key) => (
                        <kbd key={key}>{key}</kbd>
                      ))}
                    </dt>
                    <dd className={styles.description}>{shortcut.description}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
};

export default KeyboardShortcutsDialog;
