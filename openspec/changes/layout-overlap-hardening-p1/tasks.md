# Tasks: Dashboard Auto-Layout Overlap Hardening (P1)

## 1. Runtime Wiring

- [x] 1.1 Read advanced layout settings in `GraphCanvas` and pass them into hierarchical layout calls
- [x] 1.2 Remove hardcoded spacing assumptions from UI call path
- [x] 1.3 Ensure vertical/horizontal context-menu actions still map cleanly to direction selection

## 2. Layout Service Improvements

- [x] 2.1 Extend `LayoutOptions` with measured-dimension support and minimum clearance
- [x] 2.2 Resolve node dimensions by precedence: measured -> node -> defaults
- [x] 2.3 Implement a robust residual collision/de-overlap pass (deterministic, bounded multi-pass) that meaningfully improves dense graph placement quality
- [x] 2.4 Keep circular/grid/random behavior unchanged

## 3. Validation

- [x] 3.1 Add/extend layout service tests for settings wiring and de-overlap
- [x] 3.2 Run targeted frontend tests for layout behavior
- [x] 3.3 Manual dashboard smoke on representative multi-agent graph

## 4. Review

- [x] 4.1 Request Claude review before merge/push
