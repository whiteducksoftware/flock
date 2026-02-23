# Delta Spec: OpenClaw Fan-Out Identity Hotfix

## MODIFIED Requirements

### Requirement: OpenClaw Engine SHALL Materialize Fan-Out Outputs
When an OpenClaw-backed agent declares fan-out for an output type, the engine MUST materialize one artifact per returned item.

#### Scenario: Streaming fan-out preserves artifact cardinality
- GIVEN a fan-out output declaration and streaming-enabled execution
- WHEN the OpenClaw response returns multiple valid fan-out items
- THEN all items are materialized as artifacts
- AND fan-out output does not collapse to a single artifact

### Requirement: Fan-Out Requests SHALL Use Array Schema Contract
For fan-out output declarations, the engine MUST request a JSON array of typed objects rather than a single object.

#### Scenario: Fan-out artifacts have distinct identities
- GIVEN fan-out output materialization from one OpenClaw response
- WHEN artifacts are persisted to the blackboard
- THEN each materialized fan-out artifact has a unique artifact identity
- AND downstream scheduling can process each item independently