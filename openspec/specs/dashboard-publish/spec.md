# dashboard-publish Specification

## Purpose
TBD - created by archiving change publish-array-defaults. Update Purpose after archive.
## Requirements
### Requirement: Artifact Type Schema Includes Array Defaults from `default_factory`
The system SHALL return artifact type schemas that include usable defaults for array fields backed by Pydantic `default_factory`.

#### Scenario: Array default via default_factory is exposed
- GIVEN an artifact model with `tags: list[str] = Field(default_factory=lambda: ["a", "b"])`
- WHEN `GET /api/artifact-types` is called
- THEN the response schema for `tags` contains `"default": ["a", "b"]`

#### Scenario: Explicit schema default is preserved
- GIVEN an artifact model where array property already has an explicit schema `default`
- WHEN artifact types are returned
- THEN the explicit `default` is kept unchanged

#### Scenario: Unsupported/non-serializable factory output
- GIVEN an array field default factory that errors or returns non-serializable data
- WHEN artifact types are returned
- THEN the endpoint still succeeds
- AND that property is returned without injected default

### Requirement: Publish UI Prefills Arrays from Schema Defaults
The publish form SHALL prefill array textareas from schema defaults when provided.

#### Scenario: Prefilled multiline array textarea
- GIVEN an artifact type schema where `known_competitors.default = ["CrewAI", "LangGraph", "AutoGen"]`
- WHEN the user selects that artifact type in Publish modal
- THEN the textarea value is:
  - `CrewAI`
  - `LangGraph`
  - `AutoGen`
  (one item per line)

### Requirement: Artifact-Type Route Parity
Both artifact type endpoints SHALL apply the same schema-enrichment behavior.

#### Scenario: Route parity
- GIVEN routes `/api/artifact-types` and `/api/artifact_types`
- WHEN requesting artifact schemas from either route
- THEN array defaults from `default_factory` are present consistently

