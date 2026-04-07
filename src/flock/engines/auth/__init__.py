"""Authentication helpers for cloud provider LM integration."""

from flock.engines.auth.azure import (
    AZURE_AI_FOUNDRY_SCOPE,
    AZURE_COGNITIVE_SERVICES_SCOPE,
    get_default_azure_token_provider,
)


__all__ = [
    "AZURE_AI_FOUNDRY_SCOPE",
    "AZURE_COGNITIVE_SERVICES_SCOPE",
    "get_default_azure_token_provider",
]
