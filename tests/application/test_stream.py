"""WorkflowStream: incremental outputs, cancellation and ownership."""

from __future__ import annotations

import asyncio

import pytest

from flock.application import FlockApplication, WorkflowContext, WorkflowStatus
from flock.core import Flock

from .conftest import AppSummary, AppTicket, AppTriage, engine, summarize, triage


def slow_second_stage_flock(release: asyncio.Event, cancelled: asyncio.Event) -> Flock:
    async def wait_then_summarize(agent, ctx, inputs):
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return await summarize(agent, ctx, inputs)

    flock = Flock(no_output=True)
    flock.agent("triage").consumes(AppTicket).publishes(AppTriage).with_engines(
        engine(triage)
    )
    flock.agent("summarizer").consumes(AppTriage).publishes(AppSummary).with_engines(
        engine(wait_then_summarize)
    )
    return flock


def make_app(release: asyncio.Event, cancelled: asyncio.Event) -> FlockApplication:
    return FlockApplication(
        lambda: slow_second_stage_flock(release, cancelled),
        input_type=AppTicket,
        output_types=(AppTriage, AppSummary),
    )


@pytest.mark.asyncio
async def test_outputs_arrive_before_the_cascade_completes():
    release, cancelled = asyncio.Event(), asyncio.Event()
    app = make_app(release, cancelled)

    async with app.stream(AppTicket(text="x"), context=WorkflowContext("wf")) as wf:
        iterator = aiter(wf)
        first = await asyncio.wait_for(anext(iterator), 5)
        assert first.artifact.type == "AppTriage"
        release.set()
        rest = [event async for event in iterator]
        result = await wf.result()

    assert [e.artifact.type for e in rest] == ["AppSummary"]
    assert result.ok
    assert [e.sequence for e in result.outputs] == [0, 1]


@pytest.mark.asyncio
async def test_leaving_the_block_early_cancels_and_tears_down():
    release, cancelled = asyncio.Event(), asyncio.Event()
    app = make_app(release, cancelled)

    async with app.stream(AppTicket(text="x"), context=WorkflowContext("wf")) as wf:
        async for _event in wf:
            break

    result = await wf.result()
    assert result.status is WorkflowStatus.CANCELLED
    assert cancelled.is_set()
    assert app.active_workflows == 0


@pytest.mark.asyncio
async def test_explicit_cancel():
    release, cancelled = asyncio.Event(), asyncio.Event()
    app = make_app(release, cancelled)

    async with app.stream(AppTicket(text="x"), context=WorkflowContext("wf")) as wf:
        await asyncio.sleep(0.05)
        wf.cancel()
        result = await wf.result()

    assert result.status is WorkflowStatus.CANCELLED
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_caller_cancellation_tears_down_then_propagates():
    release, cancelled = asyncio.Event(), asyncio.Event()
    app = make_app(release, cancelled)

    task = asyncio.create_task(
        app.run(AppTicket(text="x"), context=WorkflowContext("wf"))
    )
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
    assert app.active_workflows == 0


@pytest.mark.asyncio
async def test_slow_consumer_never_blocks_agents():
    app = FlockApplication(
        lambda: _two_stage(),
        input_type=AppTicket,
        output_types=(AppTriage, AppSummary),
    )

    async with app.stream(AppTicket(text="x"), context=WorkflowContext("wf")) as wf:
        result = await wf.result()  # never iterated while running
        events = [event async for event in wf]

    assert result.ok
    assert [e.artifact.type for e in events] == ["AppTriage", "AppSummary"]


def _two_stage() -> Flock:
    flock = Flock(no_output=True)
    flock.agent("triage").consumes(AppTicket).publishes(AppTriage).with_engines(
        engine(triage)
    )
    flock.agent("summarizer").consumes(AppTriage).publishes(AppSummary).with_engines(
        engine(summarize)
    )
    return flock
