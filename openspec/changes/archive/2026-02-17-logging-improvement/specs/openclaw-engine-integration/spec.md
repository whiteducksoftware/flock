## ADDED Requirements

### Requirement: Fast OpenClaw Orchestration Smoke Example
The repository SHALL include a compact OpenClaw example that validates core orchestration behaviors without long web-research runtime.

#### Scenario: Headless streaming toggle
- GIVEN the fast example is run in headless mode
- WHEN invoked with `--stream off` or `--stream on`
- THEN OpenClaw agents run with the requested streaming mode
- AND the workflow completes without requiring dashboard/manual UI interaction

#### Scenario: Fan-out identity and datetime-safe shaping exercised
- GIVEN the fast example pipeline executes
- WHEN fan-out artifacts and datetime-bearing artifacts flow through OpenClaw stages
- THEN fan-out outputs have unique artifact IDs
- AND OpenClaw prompt shaping does not crash on datetime values in input/context payloads
