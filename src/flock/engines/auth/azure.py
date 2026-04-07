"""Azure authentication helpers for LM integrations.

Provides :func:`get_default_azure_token_provider` for Azure Entra ID auth and
pre-defined scope constants for common Azure AI services:

* :data:`AZURE_COGNITIVE_SERVICES_SCOPE` — Azure OpenAI and Azure AI Foundry
  model inference endpoints (the default).
* :data:`AZURE_AI_FOUNDRY_SCOPE` — Azure AI Foundry **Agents** API.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flock.logging.logging import get_logger


logger = get_logger(__name__)

AZURE_COGNITIVE_SERVICES_SCOPE: tuple[str, ...] = (
    "https://cognitiveservices.azure.com/.default",
)
"""Token scope for Azure OpenAI and Azure AI Foundry model inference.

This is the correct scope for:
- Azure OpenAI endpoints (``*.openai.azure.com``)
- Azure AI Foundry model inference (``*.api.<region>.cognitive.microsoft.com``)
- Azure AI Foundry Anthropic models (``*.services.ai.azure.com/anthropic``)
"""

AZURE_AI_FOUNDRY_SCOPE: tuple[str, ...] = ("https://ai.azure.com/.default",)
"""Token scope for the Azure AI Foundry **Agents** API.

Use this scope when authenticating to Foundry Agent endpoints
(``*.services.ai.azure.com/api/projects/...``).  For standard model inference
through Foundry, use :data:`AZURE_COGNITIVE_SERVICES_SCOPE` instead.
"""

_DEFAULT_AZURE_SCOPES = AZURE_COGNITIVE_SERVICES_SCOPE


def get_default_azure_token_provider(
    *,
    scopes: tuple[str, ...] = _DEFAULT_AZURE_SCOPES,
    **credential_kwargs: Any,
) -> Callable[..., str]:
    """Create an Azure bearer token provider backed by ``DefaultAzureCredential``.

    Parameters
    ----------
    scopes:
        Token audience scope(s).  Defaults to
        :data:`AZURE_COGNITIVE_SERVICES_SCOPE` which covers Azure OpenAI and
        Foundry model inference.  Pass :data:`AZURE_AI_FOUNDRY_SCOPE` for the
        Foundry Agents API.
    **credential_kwargs:
        Forwarded to ``DefaultAzureCredential(...)``.  Common options include
        ``managed_identity_client_id`` and ``exclude_environment_credential``.
    """
    try:
        from azure.identity import (  # type: ignore[import-not-found]
            DefaultAzureCredential,
            get_bearer_token_provider,
        )
    except ImportError as exc:
        logger.info(
            "azure-identity is not installed; Azure token provider helper is unavailable."
        )
        raise ImportError(
            "Azure auth helpers require the optional 'azure-identity' dependency. "
            "Install with: uv sync --extra azure"
        ) from exc

    logger.debug("Creating Azure DefaultAzureCredential token provider.")
    credential = DefaultAzureCredential(**credential_kwargs)
    token_provider = get_bearer_token_provider(credential, *scopes)
    logger.debug("Azure bearer token provider created.")
    return token_provider  # type: ignore[no-any-return]


__all__ = [
    "AZURE_AI_FOUNDRY_SCOPE",
    "AZURE_COGNITIVE_SERVICES_SCOPE",
    "get_default_azure_token_provider",
]
