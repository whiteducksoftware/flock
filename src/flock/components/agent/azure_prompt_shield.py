"""Azure AI Content Safety – Prompt Shields guard component.

Calls the Azure Prompt Shields REST API to detect direct jailbreak
attacks in user prompts and indirect injection in context documents.

The stable ``azure-ai-contentsafety`` Python SDK (1.0.0) does not
expose a dedicated ``shield_prompt`` method, so this implementation
calls the REST API directly via ``httpx``.

Authentication:
    * **API key** – set ``api_key`` in config or the
      ``AZURE_CONTENT_SAFETY_KEY`` environment variable.
    * **Managed Identity** – leave ``api_key`` empty and set
      ``use_managed_identity=True``; requires ``azure-identity``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import Field, SecretStr

from flock.components.agent.guard import (
    GuardComponent,
    GuardComponentConfig,
    GuardVerdict,
)
from flock.logging.logging import get_logger


logger = get_logger(__name__)

_API_VERSION = "2024-09-01"
_SHIELD_PATH = "/contentsafety/text:shieldPrompt"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class AzurePromptShieldConfig(GuardComponentConfig):
    """Configuration for the Azure Prompt Shield guard."""

    endpoint: str = Field(
        default="",
        description=(
            "Azure Content Safety endpoint URL "
            "(e.g. https://<resource>.cognitiveservices.azure.com). "
            "Falls back to AZURE_CONTENT_SAFETY_ENDPOINT env var."
        ),
    )
    api_key: SecretStr | None = Field(
        default=None,
        description=(
            "API key for Azure Content Safety. "
            "Falls back to AZURE_CONTENT_SAFETY_KEY env var."
        ),
    )
    use_managed_identity: bool = Field(
        default=False,
        description="Use Azure Managed Identity instead of API key.",
    )
    max_document_length: int = Field(
        default=10_000,
        description="Maximum character length per document sent to the API.",
    )
    timeout: float = Field(
        default=10.0,
        description="HTTP request timeout in seconds.",
    )


# ---------------------------------------------------------------------------
# Guard implementation
# ---------------------------------------------------------------------------


class AzurePromptShieldGuard(GuardComponent):
    """Guard component backed by Azure AI Content Safety Prompt Shields.

    Detects direct jailbreak attacks in user prompts and indirect
    prompt injection in context documents via the Azure REST API.

    Example::

        guard = AzurePromptShieldGuard(
            priority=-10,
            config=AzurePromptShieldConfig(
                on_input_flagged="block",
                scan_context_artifacts=True,
            ),
        )
    """

    name: str = "azure_prompt_shield"
    config: AzurePromptShieldConfig = Field(
        default_factory=AzurePromptShieldConfig,
    )

    # ------------------------------------------------------------------
    # Scanner interface
    # ------------------------------------------------------------------

    async def scan_input(
        self,
        text: str,
        documents: list[str] | None = None,
        **kwargs: Any,
    ) -> GuardVerdict:
        """Call the Prompt Shields API for the given prompt and documents."""
        result = await self._call_shield_api(text, documents or [])

        user_attack: bool = result.get("userPromptAnalysis", {}).get(
            "attackDetected", False
        )
        doc_analyses = result.get("documentsAnalysis", [])
        doc_attacks: list[bool] = [d.get("attackDetected", False) for d in doc_analyses]

        if user_attack or any(doc_attacks):
            return GuardVerdict(
                safe=False,
                reason="Prompt attack detected",
                details={
                    "user_attack": user_attack,
                    "doc_attacks": doc_attacks,
                },
                provider=self.name,
            )
        return GuardVerdict(safe=True, provider=self.name)

    # ------------------------------------------------------------------
    # REST API call
    # ------------------------------------------------------------------

    async def _call_shield_api(
        self, user_prompt: str, documents: list[str]
    ) -> dict[str, Any]:
        """POST to the Azure Prompt Shields endpoint."""
        endpoint = self.config.endpoint or os.environ.get(
            "AZURE_CONTENT_SAFETY_ENDPOINT", ""
        )
        if not endpoint:
            raise ValueError(
                "Azure Content Safety endpoint not configured. "
                "Set 'endpoint' in AzurePromptShieldConfig or the "
                "AZURE_CONTENT_SAFETY_ENDPOINT environment variable."
            )
        endpoint = endpoint.rstrip("/")

        headers = await self._build_headers()

        # Truncate documents to max length
        max_len = self.config.max_document_length
        truncated_docs = [doc[:max_len] for doc in documents]

        url = f"{endpoint}{_SHIELD_PATH}"
        params = {"api-version": _API_VERSION}
        body = {
            "userPrompt": user_prompt,
            "documents": truncated_docs,
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with authentication."""
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if self.config.use_managed_identity:
            token = await self._get_managed_identity_token()
            headers["Authorization"] = f"Bearer {token}"
        else:
            api_key = (
                self.config.api_key.get_secret_value()
                if self.config.api_key
                else os.environ.get("AZURE_CONTENT_SAFETY_KEY", "")
            )
            if not api_key:
                raise ValueError(
                    "Azure Content Safety API key not configured. "
                    "Set 'api_key' in AzurePromptShieldConfig or the "
                    "AZURE_CONTENT_SAFETY_KEY environment variable, "
                    "or enable use_managed_identity."
                )
            headers["Ocp-Apim-Subscription-Key"] = api_key

        return headers

    @staticmethod
    async def _get_managed_identity_token() -> str:
        """Obtain an access token using Azure Managed Identity."""
        try:
            from azure.identity.aio import DefaultAzureCredential
        except ImportError as exc:
            raise ImportError(
                "azure-identity is required for Managed Identity auth. "
                "Install it with: uv sync --extra azure"
            ) from exc

        async with DefaultAzureCredential() as credential:
            token = await credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            return token.token


__all__ = [
    "AzurePromptShieldConfig",
    "AzurePromptShieldGuard",
]
