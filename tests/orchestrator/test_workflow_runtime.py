"""WorkflowRuntime teardown order and quiescence helpers."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.components.orchestrator import OrchestratorComponent
from flock.core import Flock
from flock.orchestrator.workflow_runtime import WorkflowRuntime
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type(name="RuntimeInput")
class RuntimeInput(BaseModel):
    value: str


@flock_type(name="RuntimeOutput")
class RuntimeOutput(BaseModel):
    value: str


class SleepyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        order.append("engine:start")
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            order.append("engine:cancelled")
            raise
        return EvalResult(artifacts=[])


order: list[str] = []


class ShutdownRecorder(OrchestratorComponent):
    async def on_shutdown(self, orchestrator):
        order.append("components:shutdown")


class RecordingMCP:
    async def cleanup(self) -> None:
        order.append("mcp:cleanup")


@pytest.mark.asyncio
async def test_close_cancels_tasks_before_mcp_cleanup_and_blocks_new_work():
    order.clear()
    flock = Flock(no_output=True)
    flock.agent("sleepy").consumes(RuntimeInput).publishes(RuntimeOutput).with_engines(
        SleepyEngine()
    )
    flock.add_component(ShutdownRecorder())
    flock._mcp_manager_instance = RecordingMCP()
    runtime = WorkflowRuntime(flock, "wf")
    seen = []
    runtime.install(on_publish=seen.append, on_task_outcome=lambda _o: None)

    await runtime.start(RuntimeInput(value="x"))
    while "engine:start" not in order:
        await asyncio.sleep(0.01)
    assert not runtime.is_quiescent()

    await runtime.close(grace=2)
    await runtime.close(grace=2)  # idempotent

    assert order == [
        "engine:start",
        "components:shutdown",
        "engine:cancelled",
        "mcp:cleanup",
    ]
    assert runtime.describe()["leftover_tasks"] == 0
    assert flock._scheduler.accepting is False
    assert [a.correlation_id for a in seen] == ["wf"]
