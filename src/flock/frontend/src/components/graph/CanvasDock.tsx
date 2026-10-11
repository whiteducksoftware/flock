/**
 * Zoom, fit and the layout modes on the board, where they can be seen
 * (docs/internal/design-system/README.md, Where everything went).
 */

import React, { useEffect, useRef, useState } from 'react';
import { useReactFlow, useStore } from '@xyflow/react';
import type { AutoLayoutMode } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import { motionMs } from './animatePositions';
import styles from './CanvasDock.module.css';

export const LAYOUTS: { mode: AutoLayoutMode; label: string; short: string }[] = [
  { mode: 'hierarchical-horizontal', label: 'Hierarchical, left to right', short: 'Hierarchical' },
  { mode: 'hierarchical-vertical', label: 'Hierarchical, top down', short: 'Hierarchical' },
  { mode: 'circular', label: 'Circular', short: 'Circular' },
  { mode: 'grid', label: 'Grid', short: 'Grid' },
  { mode: 'random', label: 'Random', short: 'Random' },
];

interface CanvasDockProps {
  layout: AutoLayoutMode;
  autoArrange: boolean;
  /** Lays the board out in this mode, and keeps it as the board's layout */
  onLayout: (mode: AutoLayoutMode) => void;
  onAutoArrange: (on: boolean) => void;
}

const CanvasDock: React.FC<CanvasDockProps> = ({ layout, autoArrange, onLayout, onAutoArrange }) => {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const zoom = useStore((state) => state.transform[2]);
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const current = LAYOUTS.find((entry) => entry.mode === layout) ?? LAYOUTS[0]!;

  // The open menu takes the focus on its current mode
  useEffect(() => {
    if (open) menu.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus();
  }, [open]);

  // A click elsewhere closes it
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node) && !button.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const closeMenu = () => {
    setOpen(false);
    button.current?.focus();
  };

  const onMenuKey = (event: React.KeyboardEvent) => {
    const items = [...(menu.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? [])];
    const index = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === 'Escape') {
      // The menu's own Esc: the board's shortcuts leave it alone
      event.preventDefault();
      closeMenu();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      items[(index + step + items.length) % items.length]?.focus();
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      items[event.key === 'Home' ? 0 : items.length - 1]?.focus();
    }
  };

  return (
    <div role="toolbar" aria-label="Canvas" className={`nodrag nopan ${styles.dock}`}>
      <button type="button" className="btn icon ghost" aria-label="Zoom out" onClick={() => zoomOut({ duration: motionMs(200) })}>
        <Icon name="minus" size={15} />
      </button>
      <span className={`mono num ${styles.zoom}`} aria-label="Zoom level">
        {Math.round(zoom * 100)}%
      </span>
      <button type="button" className="btn icon ghost" aria-label="Zoom in" onClick={() => zoomIn({ duration: motionMs(200) })}>
        <Icon name="plus" size={15} />
      </button>
      <span className={styles.divider} />
      <button
        type="button"
        className="btn icon ghost"
        aria-label="Fit to screen"
        onClick={() => fitView({ padding: 0.1, duration: motionMs(300) })}
      >
        <Icon name="fit" size={15} />
      </button>
      <div className={styles.layout}>
        <button
          ref={button}
          type="button"
          className={`btn ghost ${styles.text}`}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={`Layout: ${current.label}`}
          title="Layout"
          onClick={() => setOpen((was) => !was)}
        >
          <Icon name="layout" size={15} />
          <span>{current.short}</span>
          <Icon name="chevronDown" size={13} />
        </button>
        {open && (
          <div ref={menu} role="menu" aria-label="Layout" className={styles.menu} onKeyDown={onMenuKey}>
            {LAYOUTS.map((entry) => (
              <button
                key={entry.mode}
                type="button"
                role="menuitemradio"
                aria-checked={entry.mode === layout}
                tabIndex={entry.mode === layout ? 0 : -1}
                className={styles.item}
                onClick={() => {
                  onLayout(entry.mode);
                  closeMenu();
                }}
              >
                <span className={styles.check} aria-hidden>
                  {entry.mode === layout && <Icon name="check" size={13} />}
                </span>
                {entry.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={autoArrange}
        className={`btn ghost ${styles.text}`}
        title="Lay the board out when agents or edges appear"
        onClick={() => onAutoArrange(!autoArrange)}
      >
        <span className={styles.switch} aria-hidden />
        <span>Auto-arrange</span>
      </button>
    </div>
  );
};

export default CanvasDock;
