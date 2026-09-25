"""Flock.shutdown() stops in-flight agent work before closing MCP."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type(name="ShutdownInput")
class ShutdownInput(BaseModel):
    value: str


@flock_type(name="ShutdownOutput")
class ShutdownOutput(BaseModel):
    value: str


class RecordingMCP:
    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def cleanup(self) -> None:
        self._order.append("mcp:cleanup")


class SleepyEngine(EngineComponent):
    order: Any = None  # shared list (Any keeps identity; list would be copied)

    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        self.order.append("engine:start")
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.order.append("engine:cancelled")
            raise
        return EvalResult(artifacts=[])


def _flock(order: list[str]) -> Flock:
    flock = Flock(no_output=True)
    flock.agent("sleepy").consumes(ShutdownInput).publishes(
        ShutdownOutput
    ).with_engines(SleepyEngine(order=order))
    flock._mcp_manager_instance = RecordingMCP(order)
    return flock


@pytest.mark.asyncio
async def test_shutdown_cancels_running_agent_tasks_before_mcp_cleanup():
    order: list[str] = []
    flock = _flock(order)

    await flock.publish(ShutdownInput(value="x"))
    while "engine:start" not in order:
        await asyncio.sleep(0.01)
    await asyncio.wait_for(flock.shutdown(), 5)

    assert order == ["engine:start", "engine:cancelled", "mcp:cleanup"]
    assert not flock._scheduler.pending_tasks


@pytest.mark.asyncio
async def test_idle_cleanup_path_does_not_cancel_tasks():
    order: list[str] = []
    flock = _flock(order)

    await flock.publish(ShutdownInput(value="x"))
    while "engine:start" not in order:
        await asyncio.sleep(0.01)
    await flock.shutdown(include_components=False)

    assert "engine:cancelled" not in order
    assert flock._scheduler.pending_tasks
    await flock.shutdown()


@pytest.mark.asyncio
async def test_instance_is_usable_after_shutdown():
    order: list[str] = []
    flock = _flock(order)
    await flock.shutdown()

    await flock.publish(ShutdownInput(value="again"))
    while order.count("engine:start") < 1:
        await asyncio.sleep(0.01)
    await flock.shutdown()

    assert order.count("engine:cancelled") == 1
