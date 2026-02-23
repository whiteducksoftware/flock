# openclaw-engine-context-parity Specification

## Purpose
TBD - created by archiving change openclaw-context-batch-parity. Update Purpose after archive.
## Requirements
### Requirement: OpenClaw Engine SHALL Include Context History When Available
The OpenClaw engine MUST include relevant context history from `ctx.artifacts` in request payloads/prompts when context is enabled and available.

#### Scenario: Context artifacts included
- GIVEN an OpenClaw-backed agent with non-empty `ctx.artifacts`
- WHEN the engine builds the request payload
- THEN context artifacts are serialized into the request contract
- AND the task prompt explicitly indicates context is provided

#### Scenario: No context artifacts
- GIVEN `ctx.artifacts` is empty
- WHEN the engine builds the request payload
- THEN no context section is injected

### Requirement: OpenClaw Engine SHALL Handle Batch Mode Explicitly
The OpenClaw engine MUST detect `ctx.is_batch` and shape request instructions/payload accordingly.

#### Scenario: Batch mode request shaping
- GIVEN `ctx.is_batch = true`
- WHEN request payload is built
- THEN prompt instructions indicate batched processing semantics
- AND input payload formatting is batch-aware

#### Scenario: Non-batch mode unchanged
- GIVEN `ctx.is_batch = false`
- WHEN request payload is built
- THEN existing single-execution behavior remains unchanged

### Requirement: OpenClaw Engine SHALL Honor Output Group Description
When `publishes(..., description=...)` is set, OpenClaw request instructions MUST include that description as output guidance.

#### Scenario: Group description present
- GIVEN an output declaration with `group_description`
- WHEN the OpenClaw request is built
- THEN the description is included in task guidance

### Requirement: OpenClaw Engine SHALL Support Instructions Override
OpenClaw engine configuration MUST allow explicit `instructions` override that takes precedence over `agent.description`.

#### Scenario: Engine instructions override
- GIVEN engine config includes `instructions="X"`
- WHEN request payload is built
- THEN `instructions` uses "X"
- AND `agent.description` is not used as primary instructions

### Requirement: OpenClaw Response Mode Knob SHALL Be Live or Removed
`response_mode` configuration MUST either influence request behavior or be removed from public configuration/builder surface.

#### Scenario: Live response_mode behavior
- GIVEN `response_mode` is configured
- WHEN request payload is built
- THEN request shaping differs according to configured mode

#### Scenario: Removed dead knob
- GIVEN `response_mode` is not implemented as behavior
- WHEN integration config is validated
- THEN dead configuration path is removed from public API

### Requirement: OpenClaw Engine Delegation Preserves Context + Batch Semantics
OpenClaw engine delegation SHALL preserve orchestration semantics including context-aware and batch-aware execution behavior.

#### Scenario: Context + batch parity with native behavior
- GIVEN equivalent pipeline conditions for OpenClaw and native agents (context present, batch trigger)
- WHEN both execute
- THEN OpenClaw request shaping reflects the same operational semantics (context usage + batch intent)
- AND resulting artifacts remain schema-valid and publish through normal pipeline flow

