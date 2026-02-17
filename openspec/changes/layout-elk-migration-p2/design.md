# Design: Dashboard Hierarchical Layout Migration to ELK (P2)

## Summary

P2 introduces a pluggable hierarchical layout engine and migrates the dashboard hierarchical path to ELK.

## Engine Abstraction

Define a small interface:

- Input: nodes, edges, layout options (direction/spacing/center/clearance)
- Output: positioned nodes + graph dimensions (`LayoutResult`)

Implementations during migration:
- `dagreHierarchicalEngine` (existing logic, refactor baseline)
- `elkHierarchicalEngine` (target implementation)

Post-migration runtime path uses ELK for hierarchical layouts.

## ELK Integration

### Option mapping

Map UI semantics into ELK options:
- Direction: `TB/LR` equivalents
- Spacing: node-to-node and rank/layer separation
- Margins/padding aligned with current dashboard behavior

### Position translation

Normalize ELK output coordinates into top-left node positions expected by React Flow.

### Execution model

Adapt hierarchical layout call path for ELK execution while preserving the existing `LayoutResult` contract consumed by GraphCanvas.

## UX and Config

- No user-facing engine selector is introduced in P2.
- Existing auto-layout context-menu entries remain unchanged.
- Hierarchical entries execute the ELK-backed path after migration.

## Testing Strategy

- Unit tests for option mapping and contract compatibility.
- Fixture tests for overlap/crossing quality proxies.
- Runtime smoke checks on representative examples and dense graphs.

## Rollout Plan

1. Land abstraction + ELK engine integration.
2. Switch hierarchical runtime path to ELK.
3. Validate quality/perf against representative scenarios.
