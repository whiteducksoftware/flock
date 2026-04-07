## 1. SecretStr Migration

- [x] 1.1 Change `api_key: str` to `api_key: SecretStr | None = None` in `AzurePromptShieldConfig` (`src/flock/components/agent/azure_prompt_shield.py:55`)
- [x] 1.2 Update `_build_headers()` to use `self.config.api_key.get_secret_value()` with None check instead of empty string check (`azure_prompt_shield.py:186-187`)
- [x] 1.3 Add `SecretStr` import from pydantic in `azure_prompt_shield.py`

## 2. Error Message Fix

- [x] 2.1 Change `"Install it with: pip install azure-identity"` to `"Install it with: uv sync --extra azure"` in `_get_managed_identity_token()` (`azure_prompt_shield.py:208`)

## 3. CodeQL Fix

- [x] 3.1 Change test assertion at line 508 from `assert "env.cognitiveservices.azure.com" in call_url` to `assert call_url == "https://env.cognitiveservices.azure.com/contentsafety/text:shieldPrompt"` (`tests/test_guard_component.py:508`)

## 4. Test Updates

- [x] 4.1 Update test fixtures and assertions that construct `AzurePromptShieldConfig(api_key="...")` to use `SecretStr("...")` (`tests/test_guard_component.py`)
- [x] 4.2 Run `uv run pytest tests/test_guard_component.py -x` to verify all 40 tests pass

## 5. Documentation

- [x] 5.1 Add GuardComponent framework to docs — document the abstract `GuardComponent` base class, `GuardVerdict`, `GuardComponentConfig` actions (block/warn/annotate), and how to implement custom guards
- [x] 5.2 Add Azure Prompt Shield guard to docs — document `AzurePromptShieldGuard` usage, config options, Entra ID / API key auth, scope constants
- [x] 5.3 Add Azure Entra ID / `lm_kwargs` auth to docs — verified: PR #379 already includes 118 lines in dspy-engine.md, 70 lines in configuration.md, README + AGENTS.md updates. No gaps to fill.

## 6. Verify

- [x] 6.1 Run full test suite `uv run pytest -x -q` to check no regressions — 2255 passed, 60 skipped, 0 failures
- [ ] 6.2 Commit and push to trigger CI (CodeQL + Backend Quality)
