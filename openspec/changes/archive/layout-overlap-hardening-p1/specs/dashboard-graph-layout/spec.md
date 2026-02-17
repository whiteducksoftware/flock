# Delta Spec: Dashboard Graph Layout

## ADDED Requirements

### Requirement: Auto-Layout MUST Honor Dashboard Layout Settings
The dashboard auto-layout flow MUST apply user-configured direction and spacing settings when computing hierarchical layouts.

#### Scenario: Direction setting applied
- GIVEN a graph with multiple connected nodes
- WHEN the user applies hierarchical auto-layout with direction `TB`
- THEN resulting node coordinates follow top-to-bottom rank progression
- AND switching to `LR` changes rank progression to left-to-right

#### Scenario: Spacing settings applied
- GIVEN a graph with multiple connected nodes
- WHEN the user increases `nodeSpacing` or `rankSpacing`
- THEN computed node distances increase accordingly

### Requirement: Auto-Layout MUST Avoid Visible Node Overlap
The dashboard auto-layout result MUST avoid visible overlap between node bounding boxes under normal graph sizes.

#### Scenario: Residual overlap after initial layout
- GIVEN a graph where initial hierarchical placement causes partial overlap
- WHEN auto-layout finishes
- THEN a post-layout collision resolution step separates overlapping nodes
- AND no node visually covers another node

### Requirement: Auto-Layout MUST Use Measured Node Dimensions When Available
Layout computation MUST use measured node dimensions when available, with safe fallback to node-type defaults.

#### Scenario: Dynamic node content size
- GIVEN a node rendered larger than the default template size
- WHEN auto-layout runs
- THEN layout spacing uses the measured size for that node
- AND overlap risk from undersized assumptions is reduced
