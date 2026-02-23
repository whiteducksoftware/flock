# Proposal: Dashboard Hierarchical Layout Migration to ELK (P2)

## Intent

Migrate hierarchical auto-layout from Dagre to ELK.js to improve placement quality on dense/complex graphs.

## Scope

- Add a hierarchical layout engine abstraction for clean structure.
- Implement ELK-backed hierarchical layout path.
- Replace Dagre hierarchical execution path with ELK in dashboard auto-layout.
- Map existing dashboard layout controls (direction + spacing) to ELK options.
- Keep circular/grid/random layouts unchanged.

## Out of Scope

- Replacing non-hierarchical algorithms.
- Broad redesign of graph/node rendering.
- User-facing layout engine selector UI.
- Runtime fallback to Dagre on ELK failure.

## Approach

1. Introduce a thin layout engine interface for hierarchical layout.
2. Add ELK engine implementation with compatible `LayoutResult` output.
3. Wire GraphCanvas hierarchical actions to ELK-backed path.
4. Validate quality and performance on representative real workflows.

## Risks

- ELK may increase computation latency on larger graphs.
- Option-mapping mismatch could produce spacing behavior differences vs current Dagre output.
- Async integration complexity relative to current sync assumptions.

## Mitigations

- Add deterministic fixtures and quality/perf regression checks.
- Keep option mapping explicit and covered by tests.
- Keep migration scoped to hierarchical layouts only.

## Success Criteria

- ELK hierarchical layout produces visibly better placement on dense graphs (fewer overlaps/crossings).
- Existing dashboard direction/spacing controls remain effective and predictable.
- No regression in dashboard auto-layout UX for core examples.
