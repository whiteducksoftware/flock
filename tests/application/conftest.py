"""Deterministic engines and models for FlockApplication tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type(name="AppTicket")
class AppTicket(BaseModel):
    text: str
    delay: float = 0.0
    fail: bool = False


@flock_type(name="AppTriage")
class AppTriage(BaseModel):
    text: str


@flock_type(name="AppSummary")
class AppSummary(BaseModel):
    text: str


@flock_type(name="AppIdea")
class AppIdea(BaseModel):
    n: int


@flock_type(name="AppDigest")
class AppDigest(BaseModel):
    count: int


@flock_type(name="AppNote")
class AppNote(BaseModel):
    key: str


@flock_type(name="AppPing")
class AppPing(BaseModel):
    n: int = 0


@flock_type(name="AppPong")
class AppPong(BaseModel):
    n: int = 0


Behavior = Callable[[Any, Any, EvalInputs], Awaitable[list[BaseModel]]]


class FnEngine(EngineComponent):
    """Engine whose behavior is a plain async function (no LLM)."""

    fn: Any = None

    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        produced = await self.fn(agent, ctx, inputs)
        if not produced:
            return EvalResult(artifacts=[])
        return EvalResult.from_objects(*produced, agent=agent)


def engine(fn: Behavior) -> FnEngine:
    return FnEngine(fn=fn)


async def triage(agent, ctx, inputs):
    ticket = AppTicket(**inputs.artifacts[0].payload)
    if ticket.delay:
        await asyncio.sleep(ticket.delay)
    if ticket.fail:
        raise RuntimeError(f"secret input leaked: {ticket.text}")
    return [AppTriage(text=f"triaged:{ticket.text}")]


async def summarize(agent, ctx, inputs):
    triaged = AppTriage(**inputs.artifacts[0].payload)
    return [AppSummary(text=f"summary:{triaged.text}")]
