# Delta Spec: Dashboard Graph Layout

## ADDED Requirements

### Requirement: Manual Layout Actions MUST Persist Across Redraws
When a user applies a layout from the context menu, resulting node positions MUST remain stable across subsequent dashboard redraw/refresh cycles.

#### Scenario: Horizontal layout does not snap back
- GIVEN a graph in agent view
- WHEN the user applies `Hierarchical (Horizontal)` from the context menu
- AND the graph is redrawn from a new backend snapshot
- THEN node positions remain in the applied horizontal arrangement
- AND do not revert to older saved/backend positions

### Requirement: Dashboard MUST Provide Persisted Auto-Layout Toggle and Mode with Topology-Gated Triggering
The dashboard MUST expose a persisted auto-layout toggle and persisted auto-layout mode used only for topology-changing redraws (not status-only snapshot refreshes).

#### Scenario: Default auto-layout state
- GIVEN a first-time dashboard session (no prior saved settings)
- WHEN settings are initialized
- THEN `autoLayoutEnabled` is `true`
- AND `autoLayoutMode` is `hierarchical-horizontal`

#### Scenario: Toggle placement and persistence
- GIVEN the graph context menu is open
- WHEN the user inspects the layout section
- THEN an auto-layout toggle item is shown below layout options separated by a divider
- AND changing the toggle persists across page reloads

#### Scenario: Last selected layout mode drives topology-change redraw behavior
- GIVEN auto-layout is enabled
- AND the user most recently selected `Circular` layout
- WHEN the graph redraws from updated snapshot data that includes a topology change (for example, new nodes)
- THEN circular auto-layout is applied automatically

#### Scenario: Status-only redraw does not trigger auto-layout
- GIVEN auto-layout is enabled
- AND the current graph topology is unchanged
- WHEN the graph redraws from a snapshot that only updates runtime/status counters
- THEN no automatic re-layout is applied

#### Scenario: Topology burst redraws are debounced
- GIVEN auto-layout is enabled
- AND multiple topology-changing snapshots arrive in rapid succession
- WHEN redraw processing settles after the debounce window
- THEN the graph applies at most one auto-layout pass for that burst using the latest snapshot

#### Scenario: Auto-layout disabled
- GIVEN auto-layout is disabled
- WHEN the graph redraws from updated snapshot data (including topology changes)
- THEN no automatic re-layout is applied

### Requirement: Pending Join/Batch Labels MUST Avoid Full Overlap
Pending logic edges (`pending_join`, `pending_batch`) MUST distribute label positions so multiple labels between the same source and target remain readable.

#### Scenario: Multiple pending join edges between same nodes
- GIVEN multiple `pending_join` edges between one producer and one consumer
- WHEN graph edges are assembled
- THEN each pending join edge receives a non-identical `labelOffset`
- AND labels are not fully stacked at one Y coordinate

#### Scenario: Multiple pending batch edges between same nodes
- GIVEN multiple `pending_batch` edges between one producer and one consumer
- WHEN graph edges are assembled
- THEN each pending batch edge receives a non-identical `labelOffset`
- AND labels are not fully stacked at one Y coordinate
