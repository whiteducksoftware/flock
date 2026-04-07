## Why

PR #382 adds a GuardComponent framework for pluggable input/output safety guards, contributed by GitHub Copilot agent. The architecture is sound and the 40 tests pass, but the PR has a failing CodeQL check and several inconsistencies with Flock's existing patterns that block merge. These are all polish fixes (~15 minutes of work) on top of solid generated code.

## What Changes

- Fix CodeQL "incomplete URL substring sanitization" finding in test assertions
- Change `api_key: str` to `SecretStr` in `AzurePromptShieldConfig` to match existing Flock pattern (see `openclaw/config.py`)
- Fix error message: `pip install azure-identity` → `uv sync --extra azure`
- Update tests to work with `SecretStr` and stricter URL assertions

## Capabilities

### New Capabilities

_None — this change fixes an existing PR, not introducing new capabilities._

### Modified Capabilities

_None — no spec-level behavior changes, only implementation fixes._

## Impact

- `src/flock/components/agent/azure_prompt_shield.py` — SecretStr for api_key, error message fix
- `tests/test_guard_component.py` — URL assertion fix, SecretStr test updates
- CI: CodeQL check should go green after URL assertion fix
- CI: Backend Quality should trigger on the new push event
