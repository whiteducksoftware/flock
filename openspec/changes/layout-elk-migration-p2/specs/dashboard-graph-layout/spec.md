# Delta Spec: Dashboard Graph Layout

## ADDED Requirements

### Requirement: Hierarchical Auto-Layout MUST Use ELK
The dashboard hierarchical auto-layout path MUST use ELK for node placement after migration.

#### Scenario: Hierarchical vertical layout
- GIVEN a graph with connected nodes
- WHEN the user applies hierarchical vertical auto-layout
- THEN ELK computes node placement
- AND the dashboard renders the resulting layout through the existing layout contract

#### Scenario: Hierarchical horizontal layout
- GIVEN a graph with connected nodes
- WHEN the user applies hierarchical horizontal auto-layout
- THEN ELK computes node placement
- AND the dashboard renders the resulting layout through the existing layout contract

### Requirement: ELK Integration MUST Preserve Dashboard Semantics
ELK-backed layout MUST preserve direction and spacing semantics exposed by dashboard controls.

#### Scenario: Direction parity
- GIVEN hierarchical layout direction is `TB` or `LR`
- WHEN ELK layout runs
- THEN resulting rank progression matches the selected direction

#### Scenario: Spacing parity
- GIVEN node/rank spacing controls are changed
- WHEN ELK layout runs
- THEN resulting layout spacing responds consistently to those controls

### Requirement: ELK Migration MUST Improve Dense-Graph Placement Quality
Hierarchical auto-layout quality on dense graphs MUST be improved relative to the prior Dagre path.

#### Scenario: Dense graph overlap/crossing quality
- GIVEN a representative dense dashboard graph
- WHEN hierarchical auto-layout is applied
- THEN visible node overlap does not increase versus baseline
- AND edge crossing quality is equal or better by agreed fixture checks
