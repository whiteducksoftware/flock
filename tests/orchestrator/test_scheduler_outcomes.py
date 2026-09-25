"""Scheduler hardening: task outcomes, empty-input guard and scheduling gate."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.components.orchestrator import OrchestratorComponent
from flock.core import Flock
from flock.orchestrator import AgentTaskOutcome
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type(name="SchedOutcomeInput")
class SchedOutcomeInput(BaseModel):
    value: str


@flock_type(name="SchedOutcomeOutput")
class SchedOutcomeOutput(BaseModel):
    value: str


class RecordingEngine(EngineComponent):
    """Engine that records calls and echoes its input."""

    calls: list[int] = []

    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        self.calls.append(len(inputs.artifacts))
        if not inputs.artifacts:
            return EvalResult(artifacts=[])
        value = inputs.artifacts[0].payload["value"]
        return EvalResult.from_object(SchedOutcomeOutput(value=value), agent=agent)


class DropEverything(OrchestratorComponent):
    """Filters every artifact out, like an unmet activation condition."""

    async def on_before_agent_schedule(self, orchestrator, agent, artifacts):
        return []


class ExplodingProvider:
    """Context provider that fails while the task builds its context."""

    async def __call__(self, request):
        raise RuntimeError("context provider exploded")


def _flock_with_agent(engine: EngineComponent) -> Flock:
    flock = Flock(no_output=True)
    (
        flock.agent("echo")
        .consumes(SchedOutcomeInput)
        .publishes(SchedOutcomeOutput)
        .with_engines(engine)
    )
    return flock


@pytest.mark.asyncio
async def test_fully_deferred_artifacts_do_not_run_agent():
    engine = RecordingEngine(calls=[])
    flock = _flock_with_agent(engine)
    flock.add_component(DropEverything())

    await flock.publish(SchedOutcomeInput(value="x"))
    await flock.run_until_idle()

    assert engine.calls == []


@pytest.mark.asyncio
async def test_failure_outside_agent_run_is_reported_as_outcome():
    flock = _flock_with_agent(RecordingEngine(calls=[]))
    flock.get_agent("echo").context_provider = ExplodingProvider()
    outcomes: list[AgentTaskOutcome] = []
    flock._scheduler.add_task_outcome_listener(outcomes.append)

    await flock.publish(SchedOutcomeInput(value="x"))
    await flock.run_until_idle()

    assert [(o.agent_name, o.outcome, o.exc_type) for o in outcomes] == [
        ("echo", "failed", "RuntimeError")
    ]
    assert not flock._scheduler.pending_tasks


@pytest.mark.asyncio
async def test_completed_outcome_carries_context_task_id():
    seen_task_ids: list[str] = []

    class TaskIdEngine(RecordingEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            seen_task_ids.append(ctx.task_id)
            return await super().evaluate(agent, ctx, inputs, output_group)

    flock = _flock_with_agent(TaskIdEngine(calls=[]))
    outcomes: list[AgentTaskOutcome] = []
    remove = flock._scheduler.add_task_outcome_listener(outcomes.append)

    await flock.publish(SchedOutcomeInput(value="x"))
    await flock.run_until_idle()
    remove()

    assert [o.outcome for o in outcomes] == ["completed"]
    assert outcomes[0].task_id == seen_task_ids[0]


@pytest.mark.asyncio
async def test_closed_gate_schedules_nothing():
    engine = RecordingEngine(calls=[])
    flock = _flock_with_agent(engine)
    flock._scheduler.close_gate()

    await flock.publish(SchedOutcomeInput(value="x"))
    await flock.run_until_idle()

    assert engine.calls == []
    assert not flock._scheduler.pending_tasks


@pytest.mark.asyncio
async def test_cancel_all_cancels_and_reports_outcome():
    started = asyncio.Event()

    class SlowEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            started.set()
            await asyncio.sleep(30)
            return EvalResult(artifacts=[])

    flock = _flock_with_agent(SlowEngine())
    outcomes: list[AgentTaskOutcome] = []
    flock._scheduler.add_task_outcome_listener(outcomes.append)

    await flock.publish(SchedOutcomeInput(value="x"))
    await asyncio.wait_for(started.wait(), 5)
    leftovers = await flock._scheduler.cancel_all(grace=2)
    await asyncio.sleep(0)

    assert leftovers == set()
    assert [o.outcome for o in outcomes] == ["cancelled"]


def test_component_runner_can_still_be_assigned_on_the_scheduler():
    flock = Flock(no_output=True)
    custom = object()

    flock._scheduler._component_runner = custom

    assert flock._scheduler._component_runner is custom
