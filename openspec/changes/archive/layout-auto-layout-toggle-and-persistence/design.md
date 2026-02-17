# Design: Dashboard Auto-Layout Toggle + Persistence + Pending Label De-overlap

## Summary

This change unifies manual layout persistence, redraw-time auto-layout behavior, and pending-edge label readability.

It builds on current Dagre-based layout behavior and P1 hardening, without introducing ELK/fallback complexity.

## Architecture Changes

### 1) Persisted auto-layout settings

Extend dashboard settings state (`settingsStore`) with:

- `autoLayoutEnabled: boolean` (default `true`)
- `autoLayoutMode: 'hierarchical-horizontal' | 'hierarchical-vertical' | 'circular' | 'grid' | 'random'` (default `hierarchical-horizontal`)

Because settings store already uses `zustand/persist`, these values persist automatically to localStorage.

### 2) Context-menu behavior updates

In `GraphCanvas` context menu:

- Keep current layout submenu actions.
- Add a divider below layout options.
- Add toggle item: `Auto Layout: On/Off`.

Behavior:
- Choosing any layout action updates `autoLayoutMode` to that layout type.
- Layout action immediately applies layout and persists resulting positions.
- Toggle controls whether redraw-time auto-layout runs.

### 3) Fix snap-back on redraw

Current issue: layout action updates in-memory node positions but does not persist them to IndexedDB, so later refresh can reapply stale saved positions.

Fix:
- On explicit layout action, persist each resulting node position via existing position persistence path.
- Keep merge priority behavior unchanged (`saved > current > backend > random`), but ensure `saved` reflects latest intentional layout.

### 4) Topology-gated redraw-time auto-layout

When graph snapshot refreshes:

- If `autoLayoutEnabled` is `false`, skip auto-layout.
- If only runtime/status counters change (no topology change), skip auto-layout.
- If graph topology changes (especially new node additions), schedule auto-layout using `autoLayoutMode`.
- Debounce topology-triggered auto-layout (target: ~500ms) so rapid fan-out bursts produce one layout pass instead of repeated jumpy relayouts.
- Use the same settings/dimension-aware layout pipeline and avoid recursive refresh/layout loops.

This preserves the “last selected layout style” behavior while preventing constant movement during live updates.

### 5) Pending edge label offsets

Backend graph assembly currently emits pending edges with `labelOffset=0.0`, causing label stacking.

Fix:
- Group `pending_join` and `pending_batch` edges by `(source, target)` pair.
- Reuse offset distribution strategy used for existing edge types.
- Populate computed `labelOffset` in pending edge data.

## Testing Strategy

### Frontend

- Layout persistence regression:
  - apply horizontal layout,
  - refresh snapshot,
  - positions remain in horizontal arrangement.
- Auto-layout toggle/mode/topology trigger:
  - default enabled + horizontal mode,
  - toggle off prevents topology-triggered auto-layout,
  - selecting circular updates mode and topology-triggered redraw applies circular when enabled,
  - status-only snapshot refresh (same topology) does not trigger re-layout,
  - rapid node-addition bursts are debounced to a single layout pass.

### Backend

- Pending edge label offset tests:
  - multi-edge pending join between same source/target receives non-identical offsets,
  - multi-edge pending batch between same source/target receives non-identical offsets.

### Manual smoke

- Competitive intelligence dashboard scenario:
  - verify layout persistence across live redraws,
  - verify pending purple/orange labels are readable under fan-out/join/batch pressure.

## Rollout

- No migration script required.
- Defaults enforce requested behavior immediately (`enabled + horizontal`).
- ELK migration remains deferred in `layout-elk-migration-p2`.
