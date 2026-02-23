# openclaw-engine-fanout Specification

## Purpose
TBD - created by archiving change openclaw-fanout-parity. Update Purpose after archive.
## Requirements
### Requirement: OpenClaw Engine SHALL Materialize Fan-Out Outputs
When an OpenClaw-backed agent declares fan-out for an output type, the engine MUST materialize one artifact per returned item.

#### Scenario: Fixed fan-out produces exact number of artifacts
- GIVEN an agent output declaration `publishes(CompetitorProfile, fan_out=3)`
- WHEN the OpenClaw response contains 3 valid `CompetitorProfile` objects
- THEN the engine materializes exactly 3 `CompetitorProfile` artifacts

#### Scenario: Dynamic fan-out produces in-range number of artifacts
- GIVEN an agent output declaration `publishes(CompetitorProfile, fan_out=(3, 8))`
- WHEN the OpenClaw response contains 5 valid `CompetitorProfile` objects
- THEN the engine materializes exactly 5 `CompetitorProfile` artifacts

### Requirement: Fan-Out Requests SHALL Use Array Schema Contract
For fan-out output declarations, the engine MUST request a JSON array of typed objects rather than a single object.

#### Scenario: Fixed fan-out request contract
- GIVEN `fan_out=3`
- WHEN the engine builds the OpenResponses payload
- THEN the schema contract describes an array of item schema `CompetitorProfile`
- AND prompt instructions state that exactly 3 items are required

#### Scenario: Dynamic fan-out request contract
- GIVEN `fan_out=(3, 8)`
- WHEN the engine builds the OpenResponses payload
- THEN the schema contract describes an array of item schema `CompetitorProfile`
- AND prompt instructions state that between 3 and 8 items are required

### Requirement: Fan-Out Count Violations SHALL Be Explicit
The OpenClaw engine MUST fail explicitly when it cannot satisfy required fan-out minimums after configured retries.

#### Scenario: Fixed fan-out under/over count
- GIVEN `fan_out=3`
- WHEN the response yields a count other than 3
- THEN the engine raises a runtime contract error after retry policy is exhausted

#### Scenario: Dynamic fan-out below minimum
- GIVEN `fan_out=(3, 8)`
- WHEN the response yields fewer than 3 items
- THEN the engine raises a runtime contract error after retry policy is exhausted

#### Scenario: Dynamic fan-out above maximum
- GIVEN `fan_out=(3, 8)`
- WHEN the response yields more than 8 items
- THEN the engine enforces maximum bound (truncate to 8) and records a warning

### Requirement: Non-Fan-Out Behavior SHALL Remain Backward Compatible
For output declarations without fan-out, the OpenClaw engine MUST continue to accept a single JSON object and materialize one artifact.

#### Scenario: Legacy single output
- GIVEN `publishes(Draft)` without fan-out
- WHEN the response contains one valid `Draft` object
- THEN the engine materializes exactly one `Draft` artifact

### Requirement: Unsupported Multi-Output-Type Group SHALL Fail Fast
OpenClaw engine execution MUST reject output groups containing multiple output type declarations unless a dedicated multi-type envelope contract is implemented.

#### Scenario: Multiple output declarations in one group
- GIVEN an output group with more than one output declaration
- WHEN OpenClaw engine evaluates the group
- THEN it fails fast with an explicit unsupported-contract error message

