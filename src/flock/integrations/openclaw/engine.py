"""OpenClaw engine component (Phase 1 scaffold)."""

from __future__ import annotations

from typing import Literal

from flock.components.agent import EngineComponent
from flock.integrations.openclaw.config import GatewayConfig
from flock.utils.runtime import EvalResult


class OpenClawEngine(EngineComponent):
    """Engine delegating execution to an OpenClaw gateway.

    Phase 1 scope in this step: configuration + builder wiring.
    Transport/evaluate behavior is implemented in later tasks.
    """

    alias: str
    gateway: GatewayConfig
    mode: Literal["spawn"] = "spawn"
    timeout: int = 120
    retries: int = 1
    response_mode: Literal["json_schema"] = "json_schema"

    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        raise RuntimeError(
            "OpenClawEngine.evaluate is not implemented yet (Phase 1 transport pending)."
        )
