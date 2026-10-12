/**
 * What the ⌘K palette offers: agents, types, runs and commands, each with its
 * actions (Enter runs the first), and how a query ranks them
 * (docs/internal/design-system/README.md, Overlays).
 */

import type { ArtifactType } from '../../services/api';
import { POPULAR_THEMES } from '../../services/themeService';
import { BUILT_IN_THEMES } from '../../services/themeApplicator';
import type { CorrelationIdMetadata, TimeRangePreset } from '../../types/filters';
import type { AutoLayoutMode, DockTab, VisualizationMode } from '../../store/uiStore';
import { modKey } from '../../utils/keys';
import { shortTypeName } from '../../utils/typeName';
import { formatAgo } from '../graph/card/cardModel';
import { LAYOUTS } from '../graph/CanvasDock';
import { fieldCount, isDecisionType, isSystemType } from '../publish/typeGroups';

export type PaletteGroup = 'Agents' | 'Types' | 'Runs' | 'Commands';

export interface PaletteAction {
  label: string;
  run: () => void;
}

export interface PaletteItem {
  id: string;
  group: PaletteGroup;
  label: string;
  /** A second, fainter text: what an agent is doing, a run's size and age */
  detail?: string;
  /** A shortcut that does the same outside the palette */
  shortcut?: string;
  /** Matched like the label, not shown: a full correlation ID or type name */
  keywords?: string[];
  /** Enter runs the first, Shift+Enter the second, Ctrl/⌘+Enter the third */
  actions: [PaletteAction, ...PaletteAction[]];
}

/** Everything the palette does, as callbacks (the component binds them to the stores). */
export interface PaletteCommands {
  showAgent: (name: string) => void;
  unfoldAgent: (name: string) => void;
  focusAgent: (name: string) => void;
  filterType: (name: string) => void;
  publishType: (name: string) => void;
  /** A run by its correlation ID, with when it started (the time range has to hold it) */
  filterRun: (correlationId: string, firstSeen: number) => void;
  showLane: (correlationId: string, firstSeen: number) => void;
  setMode: (mode: VisualizationMode) => void;
  publish: () => void;
  settings: () => void;
  shortcuts: () => void;
  addFilter: () => void;
  clearFilters: () => void;
  timeRange: (preset: TimeRangePreset) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  layout: (mode: AutoLayoutMode) => void;
  autoArrange: (on: boolean) => void;
  openDock: (tab: DockTab) => void;
  closeDock: () => void;
  theme: (name: string) => void;
}

export interface PaletteContext {
  /** The agents, and whether a run of theirs goes on now */
  agents: { name: string; running?: boolean }[];
  types: ArtifactType[];
  runs: CorrelationIdMetadata[];
  now: number;
  mode: VisualizationMode;
  autoArrange: boolean;
  dockOpen: boolean;
  theme: string;
  timeRange: TimeRangePreset;
  hasFilters: boolean;
  do: PaletteCommands;
}

const TIME_RANGES: { preset: TimeRangePreset; label: string }[] = [
  { preset: 'last5min', label: 'Last 5 min' },
  { preset: 'last10min', label: 'Last 10 min' },
  { preset: 'last1hour', label: 'Last hour' },
  { preset: 'all', label: 'All time' },
];

const DOCK_TABS: { tab: DockTab; label: string }[] = [
  { tab: 'traces', label: 'Traces' },
  { tab: 'history', label: 'History' },
  { tab: 'metrics', label: 'Metrics' },
  { tab: 'settings', label: 'Tracing settings' },
];

const THEME_LABELS: Record<string, string> = { graphite: 'Graphite', paper: 'Paper' };

const command = (
  id: string,
  label: string,
  run: () => void,
  extra: Partial<Pick<PaletteItem, 'shortcut' | 'keywords' | 'detail'>> = {},
): PaletteItem => ({ id: `command:${id}`, group: 'Commands', label, actions: [{ label: 'Run', run }], ...extra });

/** The commands that apply now: the other view, not the current theme or time range. */
function commands(ctx: PaletteContext): PaletteItem[] {
  const act = ctx.do;
  const items: PaletteItem[] = [];
  if (ctx.mode === 'agent') {
    items.push(command('blackboard', 'Switch to Blackboard', () => act.setMode('blackboard'), { shortcut: modKey('M') }));
  } else {
    items.push(command('flow', 'Switch to Flow', () => act.setMode('agent'), { shortcut: modKey('M') }));
  }
  items.push(
    command('publish', 'Publish an artifact', act.publish, { shortcut: modKey('Shift+P') }),
    command('filter', 'Add a filter', act.addFilter, { shortcut: modKey('Shift+F') }),
  );
  if (ctx.hasFilters) items.push(command('clear-filters', 'Clear filters', act.clearFilters));
  TIME_RANGES.filter((range) => range.preset !== ctx.timeRange).forEach((range) =>
    items.push(command(`time:${range.preset}`, `Time range: ${range.label}`, () => act.timeRange(range.preset))),
  );

  // The canvas dock: only the Flow has a canvas
  if (ctx.mode === 'agent') {
    items.push(
      command('zoom-in', 'Zoom in', act.zoomIn),
      command('zoom-out', 'Zoom out', act.zoomOut),
      command('fit', 'Fit to screen', act.fit),
      ...LAYOUTS.map((layout) =>
        command(`layout:${layout.mode}`, `Layout: ${layout.label}`, () => act.layout(layout.mode), {
          keywords: ['arrange'],
        }),
      ),
      command(
        'auto-arrange',
        ctx.autoArrange ? 'Turn auto-arrange off' : 'Turn auto-arrange on',
        () => act.autoArrange(!ctx.autoArrange),
        { keywords: ['layout'] },
      ),
    );
  }

  // The timeline dock
  DOCK_TABS.forEach(({ tab, label }) =>
    items.push(command(`dock:${tab}`, `Open ${label}`, () => act.openDock(tab), { keywords: ['timeline dock'] })),
  );
  if (ctx.dockOpen) items.push(command('dock:close', 'Collapse the timeline dock', act.closeDock));

  items.push(
    command('settings', 'Settings', act.settings, { shortcut: modKey(',') }),
    command('shortcuts', 'Keyboard shortcuts', act.shortcuts, { shortcut: modKey('/') }),
  );

  // Themes: the built-in ones, the popular terminal themes, the rest in the settings
  [...BUILT_IN_THEMES, ...POPULAR_THEMES]
    .filter((name) => name !== ctx.theme)
    .forEach((name) =>
      items.push(
        command(`theme:${name}`, `Theme: ${THEME_LABELS[name] ?? name}`, () => act.theme(name), {
          keywords: ['appearance', 'color'],
        }),
      ),
    );
  items.push(command('themes', 'More themes…', act.settings, { keywords: ['theme', 'appearance'] }));
  return items;
}

/** Everything the palette can offer now, in its groups' order. */
export function buildItems(ctx: PaletteContext): PaletteItem[] {
  const act = ctx.do;
  const agents: PaletteItem[] = ctx.agents.map((agent) => ({
    id: `agent:${agent.name}`,
    group: 'Agents',
    label: agent.name,
    detail: agent.running ? 'running' : undefined,
    actions: [
      { label: 'Show', run: () => act.showAgent(agent.name) },
      { label: 'Unfold', run: () => act.unfoldAgent(agent.name) },
      { label: 'Focus', run: () => act.focusAgent(agent.name) },
    ],
  }));

  // System types last, as in the composer
  const types: PaletteItem[] = [
    ...ctx.types.filter((type) => !isSystemType(type.name)),
    ...ctx.types.filter((type) => isSystemType(type.name)),
  ].map((type) => {
    const fields = fieldCount(type);
    return {
      id: `type:${type.name}`,
      group: 'Types',
      label: shortTypeName(type.name),
      detail: isDecisionType(type.name) ? 'decision' : `${fields} ${fields === 1 ? 'field' : 'fields'}`,
      keywords: [type.name],
      actions: [
        { label: 'Filter by type', run: () => act.filterType(type.name) },
        { label: 'Publish this type', run: () => act.publishType(type.name) },
      ],
    };
  });

  // Newest first
  const runs: PaletteItem[] = [...ctx.runs]
    .sort((a, b) => b.first_seen - a.first_seen)
    .map((run) => ({
      id: `run:${run.correlation_id}`,
      group: 'Runs',
      label: run.correlation_id.slice(0, 8),
      detail: `${run.artifact_count} ${run.artifact_count === 1 ? 'artifact' : 'artifacts'} · ${formatAgo(
        (ctx.now - run.first_seen) / 1000,
      )}`,
      keywords: [run.correlation_id],
      actions: [
        { label: 'Filter by run', run: () => act.filterRun(run.correlation_id, run.first_seen) },
        { label: 'Show its lane', run: () => act.showLane(run.correlation_id, run.first_seen) },
      ],
    }));

  return [...agents, ...types, ...runs, ...commands(ctx)];
}

/** The words of a label: split at spaces, punctuation, underscores and camelCase. */
const words = (text: string): string[] =>
  text
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .split(/[^a-z0-9…]+/)
    .filter(Boolean);

const isSubsequence = (text: string, query: string): boolean => {
  let at = 0;
  for (const char of text) if (char === query[at]) at += 1;
  return at === query.length;
};

/**
 * How one query word matches a text: 0 prefix, 1 word start, 2 substring,
 * 3 the initials of its words ("stb": Switch to Blackboard; labels only).
 */
function wordScore(text: string, query: string, initials: boolean): number | null {
  const lower = text.toLowerCase();
  if (lower.startsWith(query)) return 0;
  if (words(text).some((word) => word.startsWith(query))) return 1;
  if (lower.includes(query)) return 2;
  if (initials && query.length > 1 && isSubsequence(words(text).map((word) => word[0]).join(''), query)) return 3;
  return null;
}

/**
 * How well a query matches a label (or one of its keywords): lower is better,
 * null is no match. Every word of the query has to match; the worst one counts.
 */
export function matchScore(label: string, query: string, keywords: string[] = []): number | null {
  const parts = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 0;
  // The whole query as a prefix of the label or a keyword is the best match
  const whole = query.toLowerCase().trim();
  if ([label, ...keywords].some((text) => text.toLowerCase().startsWith(whole))) return 0;
  let worst = 0;
  for (const part of parts) {
    const scores = [label, ...keywords]
      .map((text, index) => wordScore(text, part, index === 0))
      .filter((score): score is number => score !== null);
    if (scores.length === 0) return null;
    worst = Math.max(worst, Math.min(...scores));
  }
  return Math.max(worst, 1);
}

const GROUPS: PaletteGroup[] = ['Agents', 'Types', 'Runs', 'Commands'];
/** How many of a group show; a query narrows them anyway */
const LIMITS: Record<PaletteGroup, number> = { Agents: 8, Types: 8, Runs: 5, Commands: 60 };

/**
 * The items for a query: matches ranked within their group, the group with
 * the best match first; without a query every group in its order.
 */
export function search(items: PaletteItem[], query: string): PaletteItem[] {
  const ranked = items
    .map((item, index) => ({ item, index, score: matchScore(item.label, query, item.keywords) }))
    .filter((entry): entry is { item: PaletteItem; index: number; score: number } => entry.score !== null);
  const groups = GROUPS.map((group) => {
    const members = ranked
      .filter((entry) => entry.item.group === group)
      .sort((a, b) => a.score - b.score || a.index - b.index)
      .slice(0, LIMITS[group]);
    return { group, members, best: members[0]?.score ?? Infinity };
  });
  if (query.trim()) groups.sort((a, b) => a.best - b.best); // stable: ties keep the order
  return groups.flatMap((group) => group.members.map((entry) => entry.item));
}
