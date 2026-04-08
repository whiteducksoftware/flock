from __future__ import annotations

import builtins
import sys
from types import ModuleType

import pytest

from flock.engines.auth.azure import (
    AZURE_AI_FOUNDRY_SCOPE,
    AZURE_COGNITIVE_SERVICES_SCOPE,
    get_default_azure_token_provider,
)


def _install_fake_azure_identity(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Install a fake ``azure.identity`` module for helper tests."""
    captured: dict[str, object] = {}
    azure_module = ModuleType("azure")
    identity_module = ModuleType("azure.identity")

    class FakeDefaultAzureCredential:
        def __init__(self, **kwargs):
            captured["credential_kwargs"] = kwargs

    def fake_get_bearer_token_provider(credential, *scopes):
        captured["credential"] = credential
        captured["scopes"] = scopes

        def provider() -> str:
            return "fake-token"

        return provider

    identity_module.DefaultAzureCredential = FakeDefaultAzureCredential
    identity_module.get_bearer_token_provider = fake_get_bearer_token_provider
    azure_module.identity = identity_module

    monkeypatch.setitem(sys.modules, "azure", azure_module)
    monkeypatch.setitem(sys.modules, "azure.identity", identity_module)
    return captured


def test_get_default_azure_token_provider_uses_default_scope(monkeypatch):
    """The helper should build a provider with the default Azure scope."""
    captured = _install_fake_azure_identity(monkeypatch)

    provider = get_default_azure_token_provider(
        managed_identity_client_id="00000000-0000-0000-0000-000000000000"
    )

    assert callable(provider)
    assert provider() == "fake-token"
    assert captured["credential_kwargs"] == {
        "managed_identity_client_id": "00000000-0000-0000-0000-000000000000"
    }
    assert captured["scopes"] == ("https://cognitiveservices.azure.com/.default",)


def test_scope_constants_have_expected_values():
    """Public scope constants should match the Azure documentation."""
    assert AZURE_COGNITIVE_SERVICES_SCOPE == (
        "https://cognitiveservices.azure.com/.default",
    )
    assert AZURE_AI_FOUNDRY_SCOPE == ("https://ai.azure.com/.default",)


def test_get_default_azure_token_provider_with_foundry_scope(monkeypatch):
    """The helper should correctly pass the Foundry Agents scope."""
    captured = _install_fake_azure_identity(monkeypatch)

    provider = get_default_azure_token_provider(scopes=AZURE_AI_FOUNDRY_SCOPE)

    assert callable(provider)
    assert captured["scopes"] == ("https://ai.azure.com/.default",)


def test_get_default_azure_token_provider_supports_custom_scopes(monkeypatch):
    """The helper should forward custom scopes and credential kwargs."""
    captured = _install_fake_azure_identity(monkeypatch)

    provider = get_default_azure_token_provider(
        scopes=("scope-a", "scope-b"),
        exclude_environment_credential=True,
    )

    assert callable(provider)
    assert provider() == "fake-token"
    assert captured["credential_kwargs"] == {"exclude_environment_credential": True}
    assert captured["scopes"] == ("scope-a", "scope-b")


def test_get_default_azure_token_provider_requires_optional_dependency(monkeypatch):
    """The helper should raise install guidance when azure-identity is missing."""
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"azure", "azure.identity"} or name.startswith("azure."):
            raise ImportError("missing azure.identity")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "azure", raising=False)
    monkeypatch.delitem(sys.modules, "azure.identity", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match="uv sync --extra azure"):
        get_default_azure_token_provider()
