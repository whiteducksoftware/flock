# Proposal: Publish UI Array Defaults from Pydantic `default_factory`

**Change:** `publish-array-defaults`  
**Status:** Planning  
**Date:** 2026-02-17

## Problem

In the dashboard "Publish Artifact" modal, scalar defaults (e.g. `str = Field(default="...")`) show correctly, but list defaults defined via `default_factory` do not.

Example:
- `key_differentiators: list[str] = Field(default_factory=lambda: ["..."])`
- `known_competitors: list[str] = Field(default_factory=lambda: ["..."])`

UI behavior today:
- array textareas render empty
- expected defaults are missing

## Root Cause

The frontend initializes array fields from `prop.default` in JSON schema (`PublishControl.tsx`).

Backend endpoint `/api/artifact-types` currently returns `model_class.model_json_schema()` directly.

In Pydantic v2, fields using `default_factory` do **not** emit `default` into JSON schema by default. Therefore list defaults never reach the UI.

## Proposed Solution

Add backend schema enrichment for dashboard artifact type responses:

1. Build schema with `model_json_schema()` (as today)
2. For each model field:
   - if schema property is `type: "array"`
   - and schema has no explicit `default`
   - and field has `default_factory`
   - compute runtime default via `field.get_default(call_default_factory=True)`
3. If computed value is JSON-serializable list, inject as `property.default`

This keeps frontend unchanged while enabling existing default rendering path.

## Scope

### In Scope
- `/api/artifact-types` + `/api/artifact_types` response enrichment
- Array defaults (`list[...]`) sourced from `default_factory`
- Tests for endpoint behavior + UI prefilling behavior

### Out of Scope
- Non-array `default_factory` enrichment (datetime/uuid/object factories)
- General schema transformation framework
- Changes to artifact publish payload semantics

## Why This Approach

- Minimal blast radius (backend-only contract fix)
- Preserves current frontend implementation
- Solves immediate user-facing issue with deterministic behavior
- Avoids exposing dynamic/scalar factories that may be surprising in forms

## Risks & Mitigations

- **Risk:** Some factories may be expensive or have side effects  
  **Mitigation:** Only evaluate for array fields, wrap in try/except, skip on error.

- **Risk:** Non-serializable defaults break response  
  **Mitigation:** Validate JSON serializability before injecting.

## Rollback

Revert schema-enrichment helper and endpoint calls; frontend returns to current behavior (array defaults empty).