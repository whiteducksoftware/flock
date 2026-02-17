# Delta Spec: OpenClaw Serialization Safety Hotfix

## MODIFIED Requirements

### Requirement: OpenClaw Engine SHALL Include Context History When Available
The OpenClaw engine MUST include relevant context history from `ctx.artifacts` in request payloads/prompts when context is enabled and available.

#### Scenario: Context artifacts include non-JSON-native values
- GIVEN context artifacts containing values such as `datetime`
- WHEN the engine builds OpenClaw request payload text
- THEN context serialization does not raise JSON serialization errors
- AND values are converted to JSON-safe representations

### Requirement: OpenClaw Engine Delegation Preserves Context + Batch Semantics
OpenClaw engine delegation SHALL preserve orchestration semantics including context-aware and batch-aware execution behavior.

#### Scenario: Input payload includes non-JSON-native values
- GIVEN an input artifact payload with non-JSON-native values
- WHEN OpenClaw request shaping runs
- THEN payload composition succeeds without serialization crashes
- AND resulting request remains parseable by the OpenClaw endpoint