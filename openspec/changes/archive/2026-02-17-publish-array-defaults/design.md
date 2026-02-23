# Design: Publish Array Default Hydration

## Context

The dashboard publish form consumes schema from `/api/artifact-types` and initializes field values from `property.default`.

Current contract gap:
- `default_factory` list defaults exist at runtime (`model_fields`)
- but are absent in JSON schema output
- therefore UI cannot prefill list textareas

## Design Overview

Introduce a small schema post-processor in `ControlRoutesComponent`:

- Input: `model_class`, `schema`
- Output: enriched schema with array defaults injected where safe

### Helper responsibilities

1. Read schema `properties`
2. Iterate `model_class.model_fields`
3. For matching property names:
   - require `prop.type == "array"`
   - require `prop.default` missing
   - require field has `default_factory`
4. Evaluate `field.get_default(call_default_factory=True)`
5. Inject only if:
   - value is `list`
   - value is JSON-serializable

### Endpoint integration

Use helper for both artifact type routes in `ControlRoutesComponent`:
- `GET /api/artifact-types`
- `GET /api/artifact_types` (legacy/compat)

## Why backend enrichment (vs frontend fallback)

- Frontend has no access to Python model field metadata/default factories
- Backend already owns artifact type introspection
- One source of truth for all clients

## Testing Strategy

### Backend
- Add endpoint test with real Pydantic model:
  - scalar default + list default_factory
  - assert list schema property now contains `default` array

### Frontend
- Add PublishControl test:
  - artifact type schema includes array `default`
  - selecting type pre-fills textarea with newline-joined list

## Non-Goals

- Generic enrichment for every `default_factory` type
- Modifying required-field semantics beyond existing logic

## Migration/Compatibility

Backward-compatible additive contract change:
- Existing consumers ignoring `default` are unaffected
- Publish UI immediately benefits without API version bump