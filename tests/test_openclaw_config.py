"""TDD tests for OpenClaw Phase 1 configuration.

These tests intentionally define the desired contract before implementation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flock.integrations.openclaw import (
    GatewayConfig,
    OpenClawConfig,
    OpenClawDefaults,
)


def test_openclaw_defaults_match_phase1_contract() -> None:
    """OpenClawDefaults should encode the locked Phase 1 defaults."""
    defaults = OpenClawDefaults()

    assert defaults.mode == "spawn"
    assert defaults.timeout == 120
    assert defaults.retries == 1
    assert defaults.response_mode == "json_schema"


def test_openclaw_defaults_accepts_prompt_only_response_mode() -> None:
    """response_mode should support prompt_only mode for prompt-embedded schema contract."""
    defaults = OpenClawDefaults(response_mode="prompt_only")

    assert defaults.response_mode == "prompt_only"


def test_openclaw_config_accepts_typed_gateway_config() -> None:
    """Config should support typed gateway definitions."""
    config = OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token_env="OPENCLAW_CODIE_TOKEN",
            )
        }
    )

    assert "codie" in config.gateways
    assert config.gateways["codie"].url == "http://localhost:19789"
    assert config.gateways["codie"].token_env == "OPENCLAW_CODIE_TOKEN"
    assert config.gateways["codie"].agent_id == "main"


def test_openclaw_config_accepts_dict_gateway_config() -> None:
    """Config should accept dict form for ergonomic DX."""
    config = OpenClawConfig(
        gateways={
            "codie": {
                "url": "http://localhost:19789",
                "token_env": "OPENCLAW_CODIE_TOKEN",
                "agent_id": "beta",
            }
        }
    )

    assert config.gateways["codie"].url == "http://localhost:19789"
    assert config.gateways["codie"].token_env == "OPENCLAW_CODIE_TOKEN"
    assert config.gateways["codie"].agent_id == "beta"


@pytest.mark.parametrize(
    "invalid_mode", ["session", "foo", ""]
)  # spawn-only in Phase 1
def test_openclaw_defaults_rejects_invalid_mode(invalid_mode: str) -> None:
    """Phase 1 should reject non-spawn mode at config level."""
    with pytest.raises(ValidationError):
        OpenClawDefaults(mode=invalid_mode)


def test_openclaw_config_from_env_discovers_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env should discover OPENCLAW_<ALIAS>_URL and token pairs."""
    monkeypatch.setenv("OPENCLAW_CODIE_URL", "http://localhost:19789")
    monkeypatch.setenv("OPENCLAW_CODIE_TOKEN", "token-codie")
    monkeypatch.setenv("OPENCLAW_CLAUDE_URL", "http://localhost:18789")
    monkeypatch.setenv("OPENCLAW_CLAUDE_TOKEN", "token-claude")

    config = OpenClawConfig.from_env()

    assert set(config.gateways.keys()) == {"codie", "claude"}
    assert config.gateways["codie"].url == "http://localhost:19789"
    assert config.gateways["codie"].token.get_secret_value() == "token-codie"
    assert config.gateways["codie"].agent_id == "main"
    assert config.gateways["claude"].url == "http://localhost:18789"
    assert config.gateways["claude"].token.get_secret_value() == "token-claude"
    assert config.gateways["claude"].agent_id == "main"


def test_openclaw_config_from_env_fails_on_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env should fail fast when URL exists but TOKEN is missing."""
    monkeypatch.setenv("OPENCLAW_CODIE_URL", "http://localhost:19789")
    monkeypatch.delenv("OPENCLAW_CODIE_TOKEN", raising=False)

    with pytest.raises(ValueError, match="OPENCLAW_CODIE_TOKEN"):
        OpenClawConfig.from_env()


def test_openclaw_config_from_env_fails_when_no_gateways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env should fail explicitly when no OpenClaw env variables are configured."""
    monkeypatch.delenv("OPENCLAW_CODIE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_CODIE_TOKEN", raising=False)
    monkeypatch.delenv("OPENCLAW_CLAUDE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_CLAUDE_TOKEN", raising=False)

    with pytest.raises(ValueError, match="No OpenClaw gateways"):
        OpenClawConfig.from_env()


def test_gateway_config_resolves_token_from_env_automatically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GatewayConfig should auto-resolve token from token_env if token is not set."""
    monkeypatch.setenv("MY_TOKEN", "secret-123")

    gw = GatewayConfig(url="http://localhost:19789", token_env="MY_TOKEN")

    assert gw.token.get_secret_value() == "secret-123"


def test_gateway_config_explicit_token_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit token should take precedence over token_env resolution."""
    monkeypatch.setenv("MY_TOKEN", "from-env")

    gw = GatewayConfig(
        url="http://localhost:19789", token_env="MY_TOKEN", token="explicit"
    )

    assert gw.token.get_secret_value() == "explicit"


def test_gateway_config_accepts_custom_agent_id() -> None:
    """GatewayConfig should allow setting a custom agent_id in explicit config."""
    gw = GatewayConfig(url="http://localhost:19789", token="abc", agent_id="beta")

    assert gw.agent_id == "beta"
