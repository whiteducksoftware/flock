"""TDD tests for OpenClaw agent builder integration (Phase 1)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

import flock.core as flock_core
from flock import Flock
from flock.integrations.openclaw import GatewayConfig, OpenClawConfig
from flock.registry import flock_type


@flock_type(name="OpenClawBuilderInput")
class OpenClawBuilderInput(BaseModel):
    prompt: str = Field(description="Input payload")


@flock_type(name="OpenClawBuilderOutput")
class OpenClawBuilderOutput(BaseModel):
    result: str = Field(description="Output payload")


def _config() -> OpenClawConfig:
    return OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token="token-codie",
                token_env="OPENCLAW_CODIE_TOKEN",
            )
        }
    )


def test_flock_accepts_openclaw_config_argument() -> None:
    """Flock constructor should accept an OpenClawConfig object."""
    flock = Flock(openclaw=_config())

    assert flock.openclaw is not None
    assert "codie" in flock.openclaw.gateways


def test_openclaw_agent_builder_is_chainable_and_registers_agent() -> None:
    """openclaw_agent should behave like standard fluent builder."""
    flock = Flock(openclaw=_config())

    (
        flock.openclaw_agent("codie")
        .description("OpenClaw builder contract test")
        .consumes(OpenClawBuilderInput)
        .publishes(OpenClawBuilderOutput)
    )

    agent = flock.get_agent("codie")
    assert agent.name == "codie"
    assert len(agent.output_groups) == 1
    assert agent.output_groups[0].outputs[0].spec.type_name == "OpenClawBuilderOutput"
    assert "openclaw" in agent.labels


def test_openclaw_agent_unknown_alias_raises_value_error() -> None:
    """Unknown OpenClaw alias should fail fast with ValueError."""
    flock = Flock(openclaw=_config())

    with pytest.raises(ValueError, match="Unknown OpenClaw gateway alias: unknown"):
        flock.openclaw_agent("unknown")


def test_core_dunder_all_includes_openclaw_exports() -> None:
    """OpenClaw types re-exported from flock.core should be in __all__."""
    for symbol in ("GatewayConfig", "OpenClawConfig", "OpenClawDefaults"):
        assert symbol in flock_core.__all__


def test_openclaw_agent_supports_per_agent_timeout_override() -> None:
    """Builder should support per-agent runtime overrides in constructor call."""
    flock = Flock(openclaw=_config())

    (
        flock.openclaw_agent("codie", timeout=300)
        .consumes(OpenClawBuilderInput)
        .publishes(OpenClawBuilderOutput)
    )

    agent = flock.get_agent("codie")
    assert len(agent.engines) == 1
    engine = agent.engines[0]
    assert getattr(engine, "timeout", None) == 300


def test_openclaw_agent_supports_instructions_override() -> None:
    """Builder should pass through engine-level instructions override."""
    flock = Flock(openclaw=_config())

    (
        flock.openclaw_agent("codie", instructions="Use terse style")
        .consumes(OpenClawBuilderInput)
        .publishes(OpenClawBuilderOutput)
    )

    agent = flock.get_agent("codie")
    assert len(agent.engines) == 1
    engine = agent.engines[0]
    assert getattr(engine, "instructions", None) == "Use terse style"
