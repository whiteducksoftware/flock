# openclaw-engine-integration Specification

## Purpose
TBD - created by archiving change openclaw-phase1-tdd. Update Purpose after archive.
## Requirements
### Requirement: OpenClaw Engine Delegation
The system SHALL allow a Flock agent to delegate computation to an OpenClaw-backed engine while preserving existing orchestration semantics (subscriptions, output groups, fan-out behavior, visibility filtering, and workflow control).

#### Scenario: OpenClaw-backed agent produces typed artifact
- **WHEN** an agent configured with OpenClaw consumes an input artifact and publishes one output type
- **THEN** the engine SHALL call the configured OpenClaw gateway in spawn mode
- **AND** the returned payload SHALL be validated against the published Pydantic output model
- **AND** the validated artifact SHALL be published through the normal Flock pipeline

#### Scenario: Existing non-OpenClaw agents remain unaffected
- **WHEN** a workflow mixes OpenClaw-backed agents and existing engine-backed agents
- **THEN** non-OpenClaw agents SHALL execute with unchanged behavior
- **AND** OpenClaw execution SHALL be opt-in only

### Requirement: OpenClaw Configuration and Alias Resolution
The system SHALL provide typed OpenClaw configuration for gateways and aliases, including environment-based loading.

#### Scenario: Load configuration from environment
- **WHEN** `OpenClawConfig.from_env()` is called with valid `OPENCLAW_*` environment variables
- **THEN** the resulting config SHALL include gateway URL and token mappings for discovered aliases
- **AND** missing required fields SHALL produce explicit validation errors

#### Scenario: Resolve agent alias to gateway settings
- **WHEN** `flock.openclaw_agent("alias")` is created
- **THEN** alias resolution SHALL map to one configured gateway and runtime defaults
- **AND** unknown aliases SHALL fail fast with a clear configuration error

### Requirement: Builder DX for OpenClaw Agents
The system SHALL support fluent OpenClaw agent construction aligned with existing Flock builder style.

#### Scenario: OpenClaw builder method returns AgentBuilder-compatible chain
- **WHEN** a caller invokes `flock.openclaw_agent("codie").consumes(X).publishes(Y)`
- **THEN** the call chain SHALL behave like `flock.agent(...)` with respect to chaining and registration
- **AND** the resulting agent SHALL include an OpenClaw engine configuration

#### Scenario: Per-agent runtime overrides are applied
- **WHEN** a caller passes runtime overrides (e.g., timeout, mode) to `openclaw_agent`
- **THEN** those overrides SHALL take precedence over global defaults for that agent

### Requirement: Structured Output Validation with Single Repair Attempt
The system SHALL enforce strict structured output validation for OpenClaw responses.

#### Scenario: Valid JSON response passes directly
- **WHEN** OpenClaw returns valid JSON matching the published schema
- **THEN** the engine SHALL parse and validate without repair
- **AND** exactly one output artifact SHALL be materialized for the output group

#### Scenario: Invalid JSON triggers one repair attempt
- **WHEN** OpenClaw returns malformed or wrapped JSON on first attempt
- **THEN** the engine SHALL perform exactly one repair attempt
- **AND** if repaired output validates, execution SHALL continue
- **AND** if repair still fails, execution SHALL raise a schema/validation error

### Requirement: Deterministic Failure Taxonomy for OpenClaw Phase 1
The system SHALL map OpenClaw failures into deterministic Flock-native execution errors.

#### Scenario: Transport failure is retriable once
- **WHEN** the gateway is unreachable or returns transient transport failures
- **THEN** the engine SHALL retry according to Phase 1 policy
- **AND** failure after retry SHALL surface a transport execution error

#### Scenario: Auth/configuration failure fails fast
- **WHEN** credentials or alias configuration are invalid
- **THEN** the engine SHALL not perform transport retries
- **AND** the engine SHALL raise a configuration/auth error with actionable context

#### Scenario: Timeout failure maps to execution timeout
- **WHEN** spawn execution exceeds configured timeout
- **THEN** the engine SHALL return a timeout-class execution failure mapped to Flock error handling

