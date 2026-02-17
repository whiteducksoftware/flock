# Design: Dashboard Auto-Layout Overlap Hardening (P1)

## Summary

P1 hardens the current Dagre-based auto-layout by improving input fidelity (actual dimensions) and adding a residual collision resolver.

## Architecture Changes

### 1) GraphCanvas settings wiring

- Source current settings from `useSettingsStore`.
- Pass settings into `applyHierarchicalLayout(...)` instead of hardcoding direction in menu handlers.
- Keep existing menu entries (vertical/horizontal) but map them to explicit direction overrides where appropriate.

### 2) Layout options extension

Extend `LayoutOptions` with optional measured dimension map:

- `dimensionsByNodeId?: Record<string, { width: number; height: number }>`
- `minClearance?: number`

Resolution precedence:
1. `dimensionsByNodeId[node.id]`
2. node-level measured dimensions (if attached)
3. existing type defaults (agent/message)

### 3) Residual collision resolver

After primary Dagre positioning:
- detect axis-aligned bounding-box intersections with clearance,
- apply deterministic offsets (rank-aware push and local reflow where needed),
- run bounded multi-pass refinement to resolve dense-cluster collisions without runaway drift.

Goal is a quality-focused overlap resolver for Dagre output (still deterministic and bounded, not physics-simulated).

### 4) Auto-fit behavior

Keep current explicit auto-fit action as-is.
Potential optional follow-up (outside strict P1 scope): auto-fit right after auto-layout behind a small UX toggle.

## Testing Strategy

- Unit tests in layout service:
  - settings values are honored,
  - measured dimensions override defaults,
  - overlap cleanup reduces/eliminates collisions.
- Integration smoke:
  - context-menu auto-layout produces non-overlapping placement on representative graph snapshots.

## Rollout

- No config migration required.
- Keep Dagre as current engine.
- P2 (ELK migration) will build on this with engine abstraction.
