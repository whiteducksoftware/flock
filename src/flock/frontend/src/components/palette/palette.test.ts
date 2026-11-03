import { describe, expect, it, vi } from 'vitest';
import type { ArtifactType } from '../../services/api';
import { type PaletteContext, type PaletteItem, buildItems, matchScore, search } from './palette';

const type = (name: string, fields: string[] = ['a']): ArtifactType => ({
  name,
  schema: { type: 'object', properties: Object.fromEntries(fields.map((field) => [field, { type: 'string' }])) },
});

const context = (overrides: Partial<PaletteContext> = {}): PaletteContext => ({
  agents: [
    { name: 'triage', running: false },
    { name: 'billing_team', running: true },
  ],
  types: [
    type('app.SupportTicket', ['ticket_id', 'title']),
    type('Decision[app.Route]'),
    type('flock.models.system_artifacts.WorkflowError'),
  ],
  runs: [
    { correlation_id: '4e7b1c2d-0000-4000-8000-000000000000', first_seen: 1_000, artifact_count: 5, run_count: 3 },
    { correlation_id: 'b20c9a8e-0000-4000-8000-000000000000', first_seen: 61_000, artifact_count: 2, run_count: 1 },
  ],
  now: 121_000,
  mode: 'agent',
  blackboardView: 'lanes',
  autoArrange: true,
  dockOpen: false,
  theme: 'graphite',
  timeRange: 'last10min',
  hasFilters: false,
  do: {
    showAgent: vi.fn(),
    unfoldAgent: vi.fn(),
    focusAgent: vi.fn(),
    filterType: vi.fn(),
    publishType: vi.fn(),
    filterRun: vi.fn(),
    showLane: vi.fn(),
    setMode: vi.fn(),
    setBlackboardView: vi.fn(),
    publish: vi.fn(),
    settings: vi.fn(),
    shortcuts: vi.fn(),
    addFilter: vi.fn(),
    clearFilters: vi.fn(),
    timeRange: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    fit: vi.fn(),
    layout: vi.fn(),
    autoArrange: vi.fn(),
    openDock: vi.fn(),
    closeDock: vi.fn(),
    theme: vi.fn(),
  },
  ...overrides,
});

const labels = (items: PaletteItem[]) => items.map((item) => item.label);
const find = (items: PaletteItem[], label: string) => items.find((item) => item.label === label)!;

describe('matchScore', () => {
  it('ranks a prefix before a word start, a substring and initials', () => {
    expect(matchScore('Fit to screen', 'fit')).toBe(0);
    expect(matchScore('Switch to Blackboard', 'black')).toBe(1);
    expect(matchScore('SupportTicket', 'ticket')).toBe(1); // camelCase word
    expect(matchScore('billing_team', 'team')).toBe(1);
    expect(matchScore('Collapse the timeline dock', 'imeli')).toBe(2);
    expect(matchScore('Switch to Blackboard', 'stb')).toBe(3); // the words' initials
    // Not any scattered letters: "tri" is in neither theme
    expect(matchScore('Theme: solarized-dark', 'tri')).toBeNull();
    expect(matchScore('Time range: Last 5 min', 'tri')).toBeNull();
    expect(matchScore('Fit to screen', 'zoom')).toBeNull();
  });

  it('needs every word of the query', () => {
    expect(matchScore('Layout: grid', 'lay grid')).toBe(1);
    expect(matchScore('Layout: grid', 'lay circ')).toBeNull();
  });

  it('matches the keywords too', () => {
    expect(matchScore('4e7b1c2d', '4e7b1c2d-0000', ['4e7b1c2d-0000-4000-8000-000000000000'])).toBe(0);
    expect(matchScore('Theme: Graphite', 'dark', ['dark'])).toBe(0);
  });
});

describe('buildItems', () => {
  it('lists the agents, types (system types last), runs (newest first) and commands', () => {
    const items = buildItems(context());

    expect(labels(items.filter((item) => item.group === 'Agents'))).toEqual(['triage', 'billing_team']);
    expect(labels(items.filter((item) => item.group === 'Types'))).toEqual([
      'SupportTicket',
      'Decision[Route]',
      'WorkflowError',
    ]);
    expect(labels(items.filter((item) => item.group === 'Runs'))).toEqual(['b20c9a8e', '4e7b1c2d']);
    expect(find(items, 'b20c9a8e').detail).toBe('2 artifacts · 1 m ago');
    expect(find(items, 'SupportTicket').detail).toBe('2 fields');
    expect(find(items, 'billing_team').detail).toBe('running');
    expect(find(items, 'triage').detail).toBeUndefined();
  });

  it('gives agents, types and runs their actions, Enter first', () => {
    const ctx = context();
    const items = buildItems(ctx);

    const triage = find(items, 'triage');
    expect(triage.actions.map((action) => action.label)).toEqual(['Show', 'Unfold', 'Focus']);
    triage.actions[1]!.run();
    expect(ctx.do.unfoldAgent).toHaveBeenCalledWith('triage');

    const ticket = find(items, 'SupportTicket');
    expect(ticket.actions.map((action) => action.label)).toEqual(['Filter by type', 'Publish this type']);
    ticket.actions[1]!.run();
    expect(ctx.do.publishType).toHaveBeenCalledWith('app.SupportTicket');

    const run = find(items, '4e7b1c2d');
    expect(run.actions.map((action) => action.label)).toEqual(['Filter by run', 'Show its lane']);
    run.actions[0]!.run();
    expect(ctx.do.filterRun).toHaveBeenCalledWith('4e7b1c2d-0000-4000-8000-000000000000', 1_000);
  });

  it('has a command for every action of the header and both docks', () => {
    const items = buildItems(context());
    const commands = labels(items.filter((item) => item.group === 'Commands'));

    expect(commands).toEqual(
      expect.arrayContaining([
        // Header
        'Switch to Blackboard',
        'Publish an artifact',
        'Add a filter',
        'Time range: Last 5 min',
        'Time range: Last hour',
        'Time range: All time',
        'Settings',
        'Keyboard shortcuts',
        // Canvas dock
        'Zoom in',
        'Zoom out',
        'Fit to screen',
        'Layout: Hierarchical, left to right',
        'Layout: Hierarchical, top down',
        'Layout: Circular',
        'Layout: Grid',
        'Layout: Random',
        'Turn auto-arrange off',
        // Timeline dock
        'Open Traces',
        'Open History',
        'Open Metrics',
        'Open Tracing settings',
        // Themes
        'Theme: Paper',
        'Theme: dracula',
        'More themes…',
      ]),
    );
    // What does not apply now is not offered
    expect(commands).not.toContain('Switch to Flow');
    expect(commands).not.toContain('Theme: Graphite');
    expect(commands).not.toContain('Time range: Last 10 min');
    expect(commands).not.toContain('Clear filters');
    expect(commands).not.toContain('Collapse the timeline dock');
  });

  it('follows the state: the other view, filters to clear, the dock to collapse, no canvas on the Blackboard', () => {
    const items = buildItems(context({ mode: 'blackboard', hasFilters: true, dockOpen: true, autoArrange: false }));
    const commands = labels(items.filter((item) => item.group === 'Commands'));

    expect(commands).toContain('Switch to Flow');
    expect(commands).toContain('Clear filters');
    expect(commands).toContain('Collapse the timeline dock');
    expect(commands).not.toContain('Fit to screen');
    expect(commands).not.toContain('Layout: Grid');
    expect(commands).not.toContain('Turn auto-arrange on');
  });

  it('offers the Blackboard\'s other view, and the canvas commands on its graph', () => {
    const lanes = labels(buildItems(context({ mode: 'blackboard', blackboardView: 'lanes' })));
    expect(lanes).toContain('Show as graph');
    expect(lanes).not.toContain('Show as lanes');
    expect(lanes).not.toContain('Fit to screen');

    const ctx = context({ mode: 'blackboard', blackboardView: 'graph' });
    const graph = buildItems(ctx);
    expect(labels(graph)).toEqual(expect.arrayContaining(['Show as lanes', 'Fit to screen', 'Layout: Grid', 'Turn auto-arrange off']));
    expect(labels(graph)).not.toContain('Show as graph');
    find(graph, 'Show as lanes').actions[0]!.run();
    expect(ctx.do.setBlackboardView).toHaveBeenCalledWith('lanes');

    // On the Flow there is no Blackboard view to choose
    expect(labels(buildItems(context()))).not.toContain('Show as graph');
  });

  it('runs a command', () => {
    const ctx = context();
    const items = buildItems(ctx);

    find(items, 'Layout: Grid').actions[0]!.run();
    find(items, 'Time range: Last hour').actions[0]!.run();
    find(items, 'Open History').actions[0]!.run();
    find(items, 'Theme: Paper').actions[0]!.run();
    find(items, 'Turn auto-arrange off').actions[0]!.run();

    expect(ctx.do.layout).toHaveBeenCalledWith('grid');
    expect(ctx.do.timeRange).toHaveBeenCalledWith('last1hour');
    expect(ctx.do.openDock).toHaveBeenCalledWith('history');
    expect(ctx.do.theme).toHaveBeenCalledWith('paper');
    expect(ctx.do.autoArrange).toHaveBeenCalledWith(false);
  });
});

describe('search', () => {
  it('shows every group without a query, a few runs only', () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      correlation_id: `${String(i).padStart(8, '0')}-0000`,
      first_seen: i,
      artifact_count: 1,
      run_count: 1,
    }));
    const results = search(buildItems(context({ runs: many })), '');

    expect(results.filter((item) => item.group === 'Runs')).toHaveLength(5);
    expect(results[0]!.group).toBe('Agents');
  });

  it('ranks within a group, and the group with the best match first', () => {
    const results = search(buildItems(context()), 'tri');

    // "triage" is a prefix match (agents), WorkflowError has no "tri"
    expect(labels(results)[0]).toBe('triage');
    expect(labels(results)).not.toContain('WorkflowError');
  });

  it('finds a run by the start of its correlation ID', () => {
    const results = search(buildItems(context()), '4e7b');

    expect(labels(results)).toEqual(['4e7b1c2d']);
  });

  it('finds commands by their words', () => {
    expect(labels(search(buildItems(context()), 'lay grid'))).toEqual(['Layout: Grid']);
    expect(labels(search(buildItems(context()), 'blackboard'))[0]).toBe('Switch to Blackboard');
  });
});
