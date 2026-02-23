# Proposal: Dashboard Auto-Layout Overlap Hardening (P1)

## Intent

Improve the existing auto-position implementation so dashboard nodes stop overlapping/covering each other during auto-layout, without changing the layout engine yet.

## Scope

- Keep hierarchical layout on the current Dagre-based path.
- Wire existing advanced layout settings into runtime layout execution:
  - `layoutDirection`
  - `nodeSpacing`
  - `rankSpacing`
- Improve node dimension handling so layout uses measured node sizes when available.
- Add a deterministic post-layout de-overlap pass for residual collisions.
- Keep circular/grid/random layouts working.
- Preserve current context-menu UX (`Auto Layout`) and persistence semantics.

## Out of Scope

- ELK.js migration (tracked separately in `layout-elk-migration-p2`).
- Reworking node rendering components.
- New visualization modules.

## Approach

1. Thread settings store values through `GraphCanvas.applyLayout()` into layout service options.
2. Extend layout service options to accept per-node measured dimensions.
3. Use measured dimensions when available; fall back to current defaults.
4. Run a bounded de-overlap pass after initial layout to resolve partial overlaps.
5. Add layout tests focused on overlap prevention and settings wiring.

## Risks

- De-overlap post-pass may increase spread on dense graphs.
- Measured dimensions may be missing during first render.

## Mitigations

- Keep deterministic fallback dimensions.
- Keep de-overlap bounded and predictable (single pass family).
- Validate with representative multi-agent graphs.

## Success Criteria

- Auto-layout no longer produces visible node overlap in common dashboard scenarios.
- Layout direction and spacing settings materially affect auto-layout output.
- No regression in auto-layout runtime behavior for existing examples.
