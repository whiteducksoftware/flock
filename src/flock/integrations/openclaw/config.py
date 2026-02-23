"""Configuration models for OpenClaw integration."""

from __future__ import annotations

import os
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class OpenClawDefaults(BaseModel):
    """Default runtime options for OpenClaw-backed agents.

    Phase 1 is intentionally spawn-only for deterministic behavior.
    """

    # TODO(phase2): widen to Literal["spawn", "session"] once session mode lands.
    mode: Literal["spawn"] = Field(
        default="spawn",
        description="Execution mode (Phase 1: spawn-only).",
    )
    timeout: int = Field(default=120, ge=1, description="Request timeout in seconds.")
    retries: int = Field(
        default=1, ge=0, description="Retry count for transient failures."
    )
    response_mode: Literal["json_schema", "prompt_only"] = Field(
        default="json_schema",
        description="How output contract is communicated to the OpenClaw agent.",
    )


class GatewayConfig(BaseModel):
    """Gateway definition for a named OpenClaw alias.

    If ``token_env`` is set and ``token`` is not provided, the token is
    automatically resolved from the environment variable at construction time.
    """

    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1, description="OpenClaw gateway URL.")
    token_env: str | None = Field(
        default=None,
        description="Environment variable name containing gateway auth token.",
    )
    token: SecretStr | None = Field(
        default=None,
        description="Resolved token value (typically from environment).",
    )
    agent_id: str = Field(
        default="main",
        min_length=1,
        description="Target OpenClaw agent id for HTTP API requests.",
    )

    def model_post_init(self, __context: object) -> None:
        """Resolve token from environment if token_env is set but token is not."""
        if self.token is None and self.token_env is not None:
            resolved = os.getenv(self.token_env)
            if resolved:
                self.token = SecretStr(resolved)


class OpenClawConfig(BaseModel):
    """Top-level OpenClaw integration configuration."""

    model_config = ConfigDict(extra="forbid")

    gateways: dict[str, GatewayConfig] = Field(
        default_factory=dict,
        description="Alias -> gateway configuration mapping.",
    )
    defaults: OpenClawDefaults = Field(default_factory=OpenClawDefaults)

    @classmethod
    def from_env(cls) -> OpenClawConfig:
        """Load OpenClaw gateway config from OPENCLAW_<ALIAS>_* variables.

        Expected pair per alias:
          - OPENCLAW_<ALIAS>_URL
          - OPENCLAW_<ALIAS>_TOKEN

        Example:
          OPENCLAW_CODEX_URL=http://localhost:19789
          OPENCLAW_CODEX_TOKEN=...
        """

        gateways: dict[str, GatewayConfig] = {}
        pattern = re.compile(r"^OPENCLAW_([A-Z0-9_]+)_URL$")

        for env_name, url in os.environ.items():
            match = pattern.match(env_name)
            if not match:
                continue

            alias_raw = match.group(1)
            alias = alias_raw.lower()
            token_key = f"OPENCLAW_{alias_raw}_TOKEN"
            token = os.getenv(token_key)

            if not token:
                raise ValueError(
                    f"Missing required token environment variable: {token_key}"
                )

            gateways[alias] = GatewayConfig(
                url=url,
                token_env=token_key,
                token=token,
            )

        if not gateways:
            raise ValueError(
                "No OpenClaw gateways discovered from environment variables"
            )

        return cls(gateways=gateways)

    def get_gateway(self, alias: str) -> GatewayConfig:
        """Resolve a configured gateway by alias."""
        if alias not in self.gateways:
            raise ValueError(f"Unknown OpenClaw gateway alias: {alias}")
        return self.gateways[alias]
