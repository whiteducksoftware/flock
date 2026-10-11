/**
 * The ⌘K palette: search agents, types and runs, run commands
 * (docs/internal/design-system/README.md, Overlays). A combobox over a
 * grouped listbox: the focus stays in the search, ↑ ↓ move, Enter runs the
 * active result's first action, Shift+Enter its second, Ctrl/⌘+Enter its third.
 */

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { fetchAgents, fetchArtifactTypes, type Agent, type ArtifactType } from '../../services/api';
import { applyThemeByName } from '../../services/themeApplicator';
import { fetchTheme } from '../../services/themeService';
import { useFilterStore } from '../../store/filterStore';
import { useGraphStore } from '../../store/graphStore';
import { useSettingsStore } from '../../store/settingsStore';
import { useUIStore, type VisualizationMode } from '../../store/uiStore';
import { isMac } from '../../utils/keys';
import { withAgent, withCanvas } from '../graph/canvasCommands';
import { Icon } from '../icons/Icon';
import { type PaletteCommands, type PaletteGroup, type PaletteItem, buildItems, search } from './palette';
import styles from './CommandPalette.module.css';

/** The keys of a result's first, second and third action */
const ACTION_KEYS = ['↵', '⇧↵', isMac ? '⌘↵' : 'Ctrl+↵'];

/** The view an agent is on: actions on agents switch to the Flow first */
const toFlow = () => {
  if (useUIStore.getState().mode !== 'agent') useUIStore.getState().setMode('agent');
};

const setMode = (mode: VisualizationMode) => useUIStore.getState().setMode(mode);

/** The palette's commands, bound to the dashboard's stores */
const commandsFor = (onShowShortcuts: () => void): PaletteCommands => ({
  showAgent: (name) => {
    toFlow();
    useUIStore.getState().unfocus();
    withCanvas((canvas) => canvas.show(name));
  },
  // From the Blackboard: once the Flow has the agent on its board (it clears an unfold or focus of an agent it lacks)
  unfoldAgent: (name) => {
    toFlow();
    useUIStore.getState().unfocus();
    withAgent(name, () => useUIStore.getState().unfold(name));
  },
  focusAgent: (name) => {
    toFlow();
    withAgent(name, () => useUIStore.getState().focus(name));
  },
  filterType: (name) => useFilterStore.getState().setArtifactTypes([name]),
  publishType: (name) => {
    useUIStore.getState().setPublishType(name);
    useSettingsStore.getState().setShowControls(true);
  },
  filterRun: (correlationId) => useFilterStore.getState().setCorrelationId(correlationId),
  showLane: (correlationId) => {
    useFilterStore.getState().setCorrelationId(correlationId);
    useUIStore.getState().setBlackboardView('lanes');
    // Its lane shows whether or not it needs a review
    useUIStore.getState().setNeedsReviewOnly(false);
    setMode('blackboard');
  },
  setMode,
  publish: () => {
    useUIStore.getState().setPublishType(null);
    useSettingsStore.getState().setShowControls(true);
  },
  settings: () => useSettingsStore.getState().setShowSettings(true),
  shortcuts: onShowShortcuts,
  addFilter: () => useSettingsStore.getState().setShowFilters(true),
  clearFilters: () => useFilterStore.getState().clearFilters(),
  timeRange: (preset) => useFilterStore.getState().setTimeRange({ preset }),
  zoomIn: () => withCanvas((canvas) => canvas.zoomIn()),
  zoomOut: () => withCanvas((canvas) => canvas.zoomOut()),
  fit: () => withCanvas((canvas) => canvas.fit()),
  layout: (mode) => withCanvas((canvas) => canvas.layout(mode)),
  autoArrange: (on) => useUIStore.getState().setAutoLayoutEnabled(on),
  openDock: (tab) => useUIStore.getState().openDock(tab),
  closeDock: () => useUIStore.getState().closeDock(),
  theme: (name) => {
    // Only the latest choice applies and is stored (null: a newer one won)
    void applyThemeByName(name, document.documentElement, fetchTheme, false)
      .then((applied) => {
        if (applied !== null) useSettingsStore.getState().setTheme(applied);
      })
      .catch((error) => console.error(`Failed to load theme "${name}":`, error));
  },
});

const CommandPalette: React.FC<{ onShowShortcuts: () => void }> = ({ onShowShortcuts }) => {
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [types, setTypes] = useState<ArtifactType[]>([]);
  const ids = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  // Whatever had the focus before the palette opened gets it back
  const [opener] = useState(() => document.activeElement as HTMLElement | null);

  const close = useUIStore((state) => state.closePalette);
  const mode = useUIStore((state) => state.mode);
  const autoArrange = useUIStore((state) => state.autoLayoutEnabled);
  const dockOpen = useUIStore((state) => state.dockOpen);
  const theme = useSettingsStore((state) => state.appearance.theme);
  const runs = useFilterStore((state) => state.availableCorrelationIds);
  // Whether an agent runs comes from the runs going on (the agents list says ready or waiting)
  const inFlight = useGraphStore((state) => state.inFlight);
  const timeRange = useFilterStore((state) => state.timeRange.preset);
  const hasFilters = useFilterStore(
    (state) =>
      Boolean(state.correlationId) ||
      state.selectedArtifactTypes.length > 0 ||
      state.selectedProducers.length > 0 ||
      state.selectedTags.length > 0 ||
      state.selectedVisibility.length > 0,
  );

  useEffect(() => {
    inputRef.current?.focus();
    return () => opener?.focus?.();
  }, [opener]);

  // The agents and types as they are now; without them the commands still work
  useEffect(() => {
    let live = true;
    fetchAgents()
      .then((list) => live && setAgents(list ?? []))
      .catch((error) => console.error('Failed to fetch agents:', error));
    fetchArtifactTypes()
      .then((list) => live && setTypes(list ?? []))
      .catch((error) => console.error('Failed to fetch artifact types:', error));
    return () => {
      live = false;
    };
  }, []);

  const commands = useMemo(() => commandsFor(onShowShortcuts), [onShowShortcuts]);
  const results = useMemo(() => {
    const running = new Set([...inFlight.values()].map((run) => run.agent));
    const items = buildItems({
      agents: agents.map((agent) => ({ name: agent.name, running: running.has(agent.name) })),
      types,
      runs,
      now: Date.now(),
      mode,
      autoArrange,
      dockOpen,
      theme,
      timeRange,
      hasFilters,
      do: commands,
    });
    return search(items, query);
  }, [agents, inFlight, types, runs, mode, autoArrange, dockOpen, theme, timeRange, hasFilters, commands, query]);

  // A new query starts at the top; a shorter list keeps the active one inside it
  useEffect(() => setActiveIndex(0), [query]);
  const index = Math.min(activeIndex, results.length - 1);
  const activeItem = index >= 0 ? results[index] : undefined;
  const optionId = (i: number) => `${ids}-option-${i}`;

  useEffect(() => {
    if (index >= 0) document.getElementById(optionId(index))?.scrollIntoView?.({ block: 'nearest' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  const run = (item: PaletteItem, action: number) => {
    const chosen = item.actions[action];
    if (!chosen) return;
    // The focus goes back first: an overlay the action opens (the composer, the
    // settings) takes it as the place to return to, not the search about to go
    inputRef.current?.blur();
    opener?.focus?.();
    close();
    chosen.run();
  };

  const onInputKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (results.length === 0) return;
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActiveIndex((index + step + results.length) % results.length);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (activeItem) run(activeItem, event.ctrlKey || event.metaKey ? 2 : event.shiftKey ? 1 : 0);
    }
  };

  const onDialogKeyDown = (event: React.KeyboardEvent) => {
    // The palette's own Esc: the board's shortcuts leave it alone
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
      return;
    }
    // Modal: Tab and Shift+Tab go round inside it
    if (event.key === 'Tab' && dialogRef.current) {
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>('input, button:not(:disabled)'),
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  };

  // The results in their groups, each with its index in the whole list
  const groups: { group: PaletteGroup; members: { item: PaletteItem; index: number }[] }[] = [];
  results.forEach((item, i) => {
    const last = groups[groups.length - 1];
    if (last?.group === item.group) last.members.push({ item, index: i });
    else groups.push({ group: item.group, members: [{ item, index: i }] });
  });

  const listId = `${ids}-list`;
  const hintId = `${ids}-hint`;

  return (
    <div className={styles.overlay}>
      <div className={styles.scrim} aria-hidden onClick={close} data-testid="palette-scrim" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search and commands"
        className={styles.dialog}
        onKeyDown={onDialogKeyDown}
      >
        <div className={styles.search}>
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label="Search agents, types and runs, or run a command"
            aria-autocomplete="list"
            aria-expanded={results.length > 0}
            aria-controls={listId}
            aria-activedescendant={activeItem ? optionId(index) : undefined}
            aria-describedby={hintId}
            placeholder="Search agents, types, runs, or run a command"
            spellCheck={false}
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
          />
          <kbd aria-hidden>Esc</kbd>
        </div>

        <div id={listId} role="listbox" aria-label="Results" className={styles.list}>
          {groups.map(({ group, members }) => (
            <div key={group} role="group" aria-labelledby={`${ids}-${group}`}>
              <div id={`${ids}-${group}`} className={styles.groupLabel}>
                {group}
              </div>
              {members.map(({ item, index: i }) => (
                <div
                  key={item.id}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === index}
                  className={styles.option}
                  onMouseMove={() => i !== index && setActiveIndex(i)}
                  // The search keeps the focus
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => run(item, 0)}
                >
                  <span className={`${item.group === 'Commands' ? '' : 'mono'} ${styles.label}`}>{item.label}</span>
                  {item.detail && <span className={styles.detail}>{item.detail}</span>}
                  {item.shortcut && <kbd className={styles.shortcut}>{item.shortcut}</kbd>}
                </div>
              ))}
            </div>
          ))}
          {results.length === 0 && <p className={styles.empty}>Nothing matches “{query}”.</p>}
        </div>

        <div className={styles.footer}>
          {activeItem && activeItem.actions.length > 1 ? (
            <div role="group" aria-label="Actions" className={styles.actions}>
              {activeItem.actions.map((action, i) => (
                <button
                  key={action.label}
                  type="button"
                  className={`btn ghost sm ${styles.action}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => run(activeItem, i)}
                >
                  {action.label}
                  <kbd aria-hidden>{ACTION_KEYS[i]}</kbd>
                </button>
              ))}
            </div>
          ) : (
            <span className={styles.hint}>
              <kbd aria-hidden>↑</kbd>
              <kbd aria-hidden>↓</kbd> move <kbd aria-hidden>↵</kbd> run
            </span>
          )}
          <span id={hintId} className={styles.srOnly}>
            {activeItem && activeItem.actions.length > 1
              ? activeItem.actions.map((action, i) => `${['Enter', 'Shift+Enter', 'Control+Enter'][i]}: ${action.label}`).join(', ')
              : 'Arrow keys move, Enter runs'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
