## ADDED Requirements

### Requirement: Azure Prompt Shield config uses SecretStr for API key
The `AzurePromptShieldConfig.api_key` field SHALL use `SecretStr | None` instead of `str` to prevent plaintext secret leakage in serialization, logs, and traces. This matches the pattern established in `openclaw/config.py`.

#### Scenario: API key passed as SecretStr
- **WHEN** a user creates `AzurePromptShieldConfig(api_key=SecretStr("my-key"))`
- **THEN** the key is stored as a `SecretStr` and `_build_headers()` resolves it via `.get_secret_value()`

#### Scenario: API key from environment variable
- **WHEN** `api_key` is None and `AZURE_CONTENT_SAFETY_KEY` env var is set
- **THEN** `_build_headers()` reads the env var directly (no SecretStr wrapping needed for runtime-only value)

#### Scenario: No API key available
- **WHEN** `api_key` is None and no env var is set and `use_managed_identity` is False
- **THEN** `_build_headers()` SHALL raise `ValueError`

### Requirement: Error messages reference uv, not pip
All import error messages in the guard component SHALL reference `uv sync --extra azure` as the install command, not `pip install`.

#### Scenario: azure-identity not installed for managed identity
- **WHEN** `_get_managed_identity_token()` is called and `azure-identity` is not installed
- **THEN** the ImportError message SHALL include `uv sync --extra azure`

### Requirement: Test URL assertions use exact match
Test assertions for API endpoint URLs SHALL use exact URL comparison or `startswith`, not substring `in` checks, to satisfy CodeQL static analysis.

#### Scenario: Environment fallback endpoint test
- **WHEN** the test verifies the env fallback endpoint is used
- **THEN** the assertion SHALL compare the exact constructed URL, not a substring
