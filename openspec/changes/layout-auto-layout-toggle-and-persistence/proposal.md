# Proposal: Dashboard Auto-Layout Toggle + Persistence + Pending Label De-overlap

## Intent

Address three dashboard UX issues in one cohesive change:

1. Context-menu layout selections currently revert after redraw/refresh.
2. There is no persisted auto-layout toggle/mode behavior for redraws.
3. Pending join/batch labels can overlap and become unreadable.

## Scope

- Persist node positions when users apply context-menu layouts.
- Add a persisted auto-layout behavior model:
  - toggle (enabled/disabled), default **enabled**,
  - mode sourced from last used layout,
  - default mode **hierarchical-horizontal**.
- Add an explicit context-menu toggle item for auto-layout below existing layout options, separated by a divider.
- Apply selected auto-layout mode automatically only for topology-changing redraws (for example when new nodes appear) while auto-layout is enabled.
- De-overlap pending join/batch edge labels via offset strategy (matching existing edge-label offset principles).
- Add targeted regression tests for frontend and backend behavior.

## Out of Scope

- ELK migration / layout engine replacement (remains in `layout-elk-migration-p2`).
- New layout algorithms beyond existing hierarchical/circular/grid/random modes.
- Broad dashboard UX redesign outside the context-menu + behavior described here.

## Approach

1. Extend persisted settings state with auto-layout toggle + selected mode.
2. Treat manual context-menu layout actions as both:
   - immediate placement action, and
   - mode selection update for future auto-layout redraws.
3. Persist layouted node positions so redraw merges do not snap back to stale IndexedDB values.
4. Trigger auto-layout only on topology-changing redraws when enabled, and debounce burst updates (e.g., 500ms) so live runs do not continuously re-layout on every snapshot.
5. Compute pending edge label offsets (`pending_join`, `pending_batch`) instead of fixed zero offset.

## Risks

- Auto-layout can still cause excessive movement if topology-change detection/debouncing is implemented incorrectly.
- Persisting layout on every menu action may overwrite intentionally dragged ad-hoc positions.
- Pending label offset grouping may need tuning for dense graphs.

## Mitigations

- Gate auto-layout to topology changes (especially new-node additions), skip status-only snapshot refreshes, and debounce burst updates (~500ms).
- Persist only on explicit layout actions (not on every render).
- Reuse existing offset calculation strategy and cap spread.
- Add regression coverage for redraw behavior and pending-label readability.

## Success Criteria

- Layout no longer snaps back after redraw when user applied a layout.
- Auto-layout toggle exists in context menu, defaults enabled, and persists across reloads.
- Last used layout mode drives automatic layout only when topology changes while auto-layout is enabled (not on status-only redraws).
- Pending join/batch labels are legible in multi-edge scenarios (no full label stack on identical coordinates).
