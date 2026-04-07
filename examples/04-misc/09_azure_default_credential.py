"""Azure OpenAI with DefaultAzureCredential.

This focused example shows how to authenticate to Azure OpenAI without storing
API keys in code. `get_default_azure_token_provider()` plugs Azure Identity's
`DefaultAzureCredential` chain into `DSPyEngine`, so the same Flock agent can
use `az login` locally and Managed Identity in Azure.

Usage:
    uv run python examples/04-misc/09_azure_default_credential.py

Prerequisites:
    - Install Azure auth support:
        - uv sync --extra azure
    - Create an Azure OpenAI deployment and set:
        - DEFAULT_MODEL="azure/<deployment-name>"
        - AZURE_API_BASE="https://<resource>.openai.azure.com/"
    - Grant the calling identity an Azure OpenAI role on the target resource:
        - Azure OpenAI: "Cognitive Services OpenAI User"
        - Azure AI Foundry: "Azure AI Developer" or "Azure AI User"
    - Optional environment variables:
        - AZURE_API_VERSION="2024-12-01-preview"
        - AZURE_CLIENT_ID="<user-assigned-managed-identity-client-id>"
        - AZURE_TENANT_ID / AZURE_CLIENT_SECRET for service-principal auth
    - Authenticate with one DefaultAzureCredential source, for example:
        - az login for local development
        - Managed Identity in Azure
        - service-principal environment variables

Scopes:
    The default scope covers Azure OpenAI and Azure AI Foundry model inference.
    For Azure AI Foundry **Agents** pass the dedicated scope constant:

        from flock.engines.auth.azure import AZURE_AI_FOUNDRY_SCOPE
        token_provider = get_default_azure_token_provider(scopes=AZURE_AI_FOUNDRY_SCOPE)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.engines import DSPyEngine
from flock.engines.auth.azure import get_default_azure_token_provider


DEFAULT_API_VERSION = "2024-12-01-preview"


@dataclass(frozen=True)
class AzureSettings:
    """Environment-driven configuration for the Azure example."""

    model: str
    api_base: str
    api_version: str
    managed_identity_client_id: str | None = None


@flock_type
class Question(BaseModel):
    """A question that should be answered clearly."""

    text: str = Field(description="The incoming user question")


@flock_type
class AzureAuthGuide(BaseModel):
    """A structured explanation of the Azure auth setup."""

    summary: str = Field(description="Short explanation of the recommended setup")
    local_development_steps: list[str] = Field(
        description="How to authenticate locally with DefaultAzureCredential"
    )
    production_steps: list[str] = Field(
        description="How to authenticate in Azure with Managed Identity"
    )


def require_env(name: str) -> str:
    """Read a required environment variable or exit with setup guidance."""
    value = os.getenv(name)
    if value:
        return value
    raise SystemExit(
        f"Missing required environment variable {name}. "
        "See the module docstring for setup instructions."
    )


def load_settings() -> AzureSettings:
    """Load Azure configuration for the example from the environment."""
    return AzureSettings(
        model=require_env("DEFAULT_MODEL"),
        api_base=require_env("AZURE_API_BASE"),
        api_version=os.getenv("AZURE_API_VERSION", DEFAULT_API_VERSION),
        managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"),
    )


def build_engine(settings: AzureSettings) -> DSPyEngine:
    """Build a DSPyEngine configured for Azure OpenAI token auth."""
    credential_kwargs: dict[str, str] = {}
    if settings.managed_identity_client_id:
        credential_kwargs["managed_identity_client_id"] = (
            settings.managed_identity_client_id
        )

    try:
        token_provider = get_default_azure_token_provider(**credential_kwargs)
    except ImportError as exc:  # pragma: no cover - exercised manually
        raise SystemExit(
            "Install Azure auth support first with uv sync --extra azure."
        ) from exc

    return DSPyEngine(
        lm_kwargs={
            "api_base": settings.api_base,
            "api_version": settings.api_version,
            "azure_ad_token_provider": token_provider,
        }
    )


def build_flock(settings: AzureSettings) -> Flock:
    """Create a small Flock workflow that uses Azure token authentication."""
    flock = Flock(settings.model)

    (
        flock.agent("advisor")
        .description(
            "Explain how to use Azure DefaultAzureCredential with Flock for "
            "local development and Azure-hosted production deployments."
        )
        .consumes(Question)
        .publishes(AzureAuthGuide)
        .with_engines(build_engine(settings))
    )

    return flock


async def main() -> None:
    """Publish one sample question and run the workflow."""
    settings = load_settings()
    flock = build_flock(settings)

    print("☁️ Azure DefaultAzureCredential Example")
    print("=" * 42)
    print(f"Model: {settings.model}")
    print(f"API base: {settings.api_base}")
    print(f"API version: {settings.api_version}")
    if settings.managed_identity_client_id:
        print(f"Managed identity client ID: {settings.managed_identity_client_id}")
    else:
        print(
            "Managed identity client ID: not set (using the default credential chain)"
        )
    print()

    question = Question(
        text=(
            "How should I use Azure DefaultAzureCredential with Flock in local "
            "development and production?"
        )
    )
    print(f"❓ Question: {question.text}\n")

    await flock.publish(question)
    await flock.run_until_idle()

    guides = await flock.store.get_by_type(AzureAuthGuide)
    if not guides:
        raise SystemExit(
            "No Azure auth guide was produced. Common causes:\n"
            "  1. Missing RBAC role — assign 'Cognitive Services OpenAI User'\n"
            "     (or 'Azure AI Developer' for Foundry) to the calling identity.\n"
            "  2. Incorrect AZURE_API_BASE or DEFAULT_MODEL deployment name.\n"
            "  3. DefaultAzureCredential could not obtain a token — run "
            "'az login' for local dev."
        )

    guide = guides[0]
    print(f"💡 Summary: {guide.summary}\n")
    print("🧪 Local development:")
    for step in guide.local_development_steps:
        print(f"   - {step}")
    print("\n🚀 Production:")
    for step in guide.production_steps:
        print(f"   - {step}")


if __name__ == "__main__":
    asyncio.run(main())
