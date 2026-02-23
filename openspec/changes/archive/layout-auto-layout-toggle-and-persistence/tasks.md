# Tasks: Dashboard Auto-Layout Toggle + Persistence + Pending Label De-overlap

## 1. Planning + Approval Gates

- [x] 1.1 (`flock-repo-75m.1`) Finalize OpenSpec artifacts for this change (`proposal.md`, `design.md`, delta spec, tasks)
- [x] 1.2 (`flock-repo-75m.2`) Request Claude review of planning artifacts before implementation
- [x] 1.3 (`flock-repo-75m.4`) Wait for explicit Pyro go-ahead before any implementation work

## 2. Fix: Layout Snap-Back on Redraw

- [x] 2.1 (`flock-repo-75m.5`) Persist node positions when context-menu layout actions are applied
- [x] 2.2 (`flock-repo-75m.8`) Add frontend regression coverage for “layout does not revert on redraw/refresh”

## 3. Feature: Persisted Auto-Layout Toggle + Mode

- [x] 3.1 (`flock-repo-75m.6`) Extend persisted settings with `autoLayoutEnabled` (default true)
- [x] 3.2 (`flock-repo-75m.6`) Extend persisted settings with `autoLayoutMode` (default `hierarchical-horizontal`)
- [x] 3.3 (`flock-repo-75m.6`) Add context-menu divider + auto-layout toggle item below layout options
- [x] 3.4 (`flock-repo-75m.6`) Update “last used layout mode” whenever a layout option is selected
- [x] 3.5 (`flock-repo-75m.6`) Apply auto-layout only on topology-changing redraws (especially new-node additions) when enabled, using persisted mode
- [x] 3.6 (`flock-repo-75m.6`) Debounce topology-triggered auto-layout bursts (target ~500ms) to prevent continuous relayout during live runs
- [x] 3.7 (`flock-repo-75m.8`) Add frontend tests for enable/disable behavior, mode persistence, no relayout on status-only refresh, and burst-debounce behavior

## 4. Fix: Pending Join/Batch Label Overlap

- [x] 4.1 (`flock-repo-75m.7`) Compute label offsets for `pending_join` edges by source/target grouping
- [x] 4.2 (`flock-repo-75m.7`) Compute label offsets for `pending_batch` edges by source/target grouping
- [x] 4.3 (`flock-repo-75m.8`) Add backend tests for pending-edge label offset distribution

## 5. Validation + Review

- [x] 5.1 (`flock-repo-75m.8`) Run targeted frontend/backend tests for this change
- [x] 5.2 (`flock-repo-75m.9`) Run manual dashboard smoke on competitive-intelligence-style graph
- [x] 5.3 (`flock-repo-75m.9`) Request Claude implementation review before merge/push
