# Delta Spec: OpenClaw Multi-Output Envelope

## ADDED Requirements

### Requirement: Multi-Output Groups SHALL Use Single-Call Envelope Contract
For output groups with multiple output declarations, OpenClaw engine MUST request and parse one JSON envelope response in a single `/v1/responses` call.

#### Scenario: Multi-output envelope success
- GIVEN an output group with `publishes(TypeA, TypeB)`
- WHEN OpenClaw returns one JSON envelope with both slots
- THEN the engine validates each slot by declaration
- AND materializes one artifact stream per output declaration

### Requirement: Slot Value Shape SHALL Follow Declaration Cardinality
Each envelope slot MUST match the declaration shape:
- non-fan-out declaration => object
- fan-out declaration => array with declaration cardinality constraints

#### Scenario: Non-fan-out slot is object
- GIVEN declaration `TypeA` without fan-out
- WHEN envelope value for `TypeA` is an object
- THEN the engine validates and materializes one `TypeA` artifact

#### Scenario: Fan-out slot is array
- GIVEN declaration `TypeB` with `fan_out=(2, 4)`
- WHEN envelope value for `TypeB` is an array of 3 valid objects
- THEN the engine validates and materializes 3 `TypeB` artifacts

### Requirement: Envelope Slot Matching SHALL Be Strict
Envelope slot matching MUST be strict in v1.

#### Scenario: Unknown slot key
- GIVEN envelope contains undeclared slot `TypeZ`
- WHEN engine validates envelope
- THEN execution fails with explicit contract error

#### Scenario: Missing declared slot
- GIVEN declaration includes `TypeA` and `TypeB`
- WHEN envelope omits `TypeB`
- THEN execution fails with explicit contract error

### Requirement: Slot Name Collisions SHALL Fail Fast
If multiple declarations resolve to the same slot key, execution MUST fail fast until explicit aliasing support is introduced.

#### Scenario: Duplicate slot key collision
- GIVEN two output declarations that resolve to the same slot name
- WHEN engine prepares envelope contract
- THEN engine fails with actionable configuration/contract error

## MODIFIED Requirements

### Requirement: Multi-Output-Type Group Contract
OpenClaw engine execution SHALL support output groups containing multiple output declarations via envelope contract, instead of unconditional fail-fast rejection.

#### Scenario: Multiple output declarations in one group
- GIVEN an output group with more than one output declaration
- WHEN OpenClaw engine evaluates the group
- THEN it requests one envelope response with declared slots
- AND materializes validated artifacts for each declaration

#### Scenario: Envelope violation remains fail-fast
- GIVEN a multi-output group and invalid envelope shape/content
- WHEN retries are exhausted
- THEN engine fails with explicit contract violation error
