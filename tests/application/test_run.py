"""FlockApplication.run: outcomes, contract, admission, isolation."""

from __future__ import annotations

import asyncio
import gc
import weakref
from datetime import timedelta

import pytest

from flock.application import (
    CapacityExceeded,
    CompletionPolicy,
    ContractError,
    FailureCode,
    FlockApplication,
    InvalidWorkflowInput,
    SessionRequired,
    WorkflowContext,
    WorkflowFailedError,
    WorkflowIdConflict,
    WorkflowStatus,
)
from flock.components.orchestrator import OrchestratorComponent
from flock.core import Flock
from flock.core.conditions import Until
from flock.core.subscription import BatchSpec, JoinSpec
from flock.core.visibility import PrivateVisibility, TenantVisibility

from .conftest import (
    AppDigest,
    AppIdea,
    AppNote,
    AppPing,
    AppPong,
    AppSummary,
    AppTicket,
    AppTriage,
    engine,
    summarize,
    triage,
)


def two_stage_flock() -> Flock:
    flock = Flock(no_output=True)
    flock.agent("triage").consumes(AppTicket).publishes(AppTriage).with_engines(
        engine(triage)
    )
    flock.agent("summarizer").consumes(AppTriage).publishes(AppSummary).with_engines(
        engine(summarize)
    )
    return flock


def app_for(factory=two_stage_flock, **kwargs) -> FlockApplication:
    kwargs.setdefault("input_type", AppTicket)
    kwargs.setdefault("output_types", (AppSummary,))
    kwargs.setdefault("required_output_types", (AppSummary,))
    return FlockApplication(factory, **kwargs)


def ctx(workflow_id: str = "wf-1", **kwargs) -> WorkflowContext:
    return WorkflowContext(workflow_id=workflow_id, **kwargs)


@pytest.mark.asyncio
async def test_multi_stage_workflow_succeeds_with_only_public_outputs():
    app = app_for()

    result = await app.run(AppTicket(text="down"), context=ctx())

    assert result.status is WorkflowStatus.SUCCEEDED
    assert result.values(AppSummary) == [AppSummary(text="summary:triaged:down")]
    # the intermediate AppTriage and the input are internal
    assert [event.artifact.type for event in result.outputs] == ["AppSummary"]
    assert result.outputs[0].artifact.correlation_id == "wf-1"
    result.raise_for_status()


@pytest.mark.asyncio
async def test_mapping_input_is_validated():
    app = app_for()

    result = await app.run({"text": "dict"}, context=ctx())
    assert result.ok

    with pytest.raises(InvalidWorkflowInput):
        await app.run({"wrong": 1}, context=ctx("wf-2"))


@pytest.mark.asyncio
async def test_agent_failure_is_failed_without_raw_exception_text():
    app = app_for()

    result = await app.run(AppTicket(text="private-value", fail=True), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.AGENT_FAILED
    assert result.failure.agent == "triage"
    assert "private-value" not in result.failure.message
    with pytest.raises(WorkflowFailedError):
        result.raise_for_status()


@pytest.mark.asyncio
async def test_missing_required_output_fails():
    def only_triage() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("triage").consumes(AppTicket).publishes(AppTriage).with_engines(
            engine(triage)
        )
        flock.agent("never").consumes(AppNote).publishes(AppSummary).with_engines(
            engine(summarize)
        )
        return flock

    app = app_for(only_triage)

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.REQUIRED_OUTPUT_MISSING
    assert result.diagnostics["missing_outputs"] == ["AppSummary"]


@pytest.mark.asyncio
async def test_timeout_cancels_running_engine():
    cancelled = asyncio.Event()

    async def slow(agent, ctx, inputs):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return []

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("slow").consumes(AppTicket).publishes(AppSummary).with_engines(
            engine(slow)
        )
        return flock

    app = app_for(factory)

    result = await app.run(AppTicket(text="x"), context=ctx(), timeout=0.2)

    assert result.status is WorkflowStatus.TIMED_OUT
    assert cancelled.is_set()
    assert app.active_workflows == 0


@pytest.mark.asyncio
async def test_iteration_limit_is_a_failure():
    async def ping(agent, ctx, inputs):
        return [AppPong(n=inputs.artifacts[0].payload["n"] + 1)]

    async def pong(agent, ctx, inputs):
        return [AppPing(n=inputs.artifacts[0].payload["n"] + 1)]

    def factory() -> Flock:
        flock = Flock(no_output=True, max_agent_iterations=3)
        flock.agent("ping").consumes(AppPing).publishes(AppPong).with_engines(
            engine(ping)
        )
        flock.agent("pong").consumes(AppPong).publishes(AppPing).with_engines(
            engine(pong)
        )
        return flock

    app = FlockApplication(factory, input_type=AppPing, output_types=(AppPong,))

    result = await app.run(AppPing(), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.ITERATION_LIMIT_EXCEEDED
    assert len(result.values(AppPong)) == 3


@pytest.mark.asyncio
async def test_fan_out_outputs_arrive_in_publication_order():
    async def ideas(agent, ctx, inputs):
        return [AppIdea(n=i) for i in range(3)]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("ideas").consumes(AppTicket).publishes(
            AppIdea, fan_out=3
        ).with_engines(engine(ideas))
        return flock

    app = FlockApplication(factory, input_type=AppTicket, output_types=(AppIdea,))

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.ok
    assert [idea.n for idea in result.values(AppIdea)] == [0, 1, 2]
    assert [event.sequence for event in result.outputs] == [0, 1, 2]


@pytest.mark.asyncio
async def test_partial_batch_is_flushed_once_the_cascade_is_quiescent():
    async def ideas(agent, ctx, inputs):
        return [AppIdea(n=i) for i in range(3)]

    async def digest(agent, ctx, inputs):
        return [AppDigest(count=len(inputs.artifacts))]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("ideas").consumes(AppTicket).publishes(
            AppIdea, fan_out=3
        ).with_engines(engine(ideas))
        flock.agent("digest").consumes(
            AppIdea, batch=BatchSpec(size=10, timeout=timedelta(hours=1))
        ).publishes(AppDigest).with_engines(engine(digest))
        return flock

    app = FlockApplication(
        factory,
        input_type=AppTicket,
        output_types=(AppDigest,),
        required_output_types=(AppDigest,),
    )

    result = await app.run(AppTicket(text="x"), context=ctx(), timeout=5)

    assert result.ok
    assert result.values(AppDigest) == [AppDigest(count=3)]
    assert result.diagnostics["partial_batches_flushed"] == 1


@pytest.mark.asyncio
async def test_incomplete_join_does_not_wait_and_is_reported():
    async def note(agent, ctx, inputs):
        return [AppNote(key="k")]

    async def joined(agent, ctx, inputs):
        return [AppSummary(text="joined")]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("note").consumes(AppTicket).publishes(AppNote).with_engines(
            engine(note)
        )
        flock.agent("joiner").consumes(
            AppNote,
            AppIdea,
            join=JoinSpec(by=lambda item: "k", within=timedelta(hours=1)),
        ).publishes(AppSummary).with_engines(engine(joined))
        return flock

    app = app_for(factory)

    result = await app.run(AppTicket(text="x"), context=ctx(), timeout=5)

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.REQUIRED_OUTPUT_MISSING
    assert result.diagnostics["incomplete_joins"] == 1


@pytest.mark.asyncio
async def test_access_policy_hides_private_and_foreign_tenant_outputs():
    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("triage").consumes(AppTicket).publishes(
            AppTriage, visibility=PrivateVisibility(agents={"summarizer"})
        ).with_engines(engine(triage))
        flock.agent("summarizer").consumes(AppTriage).publishes(
            AppSummary, visibility=TenantVisibility(tenant_id="customer-a")
        ).with_engines(engine(summarize))
        return flock

    app = FlockApplication(
        factory, input_type=AppTicket, output_types=(AppTriage, AppSummary)
    )

    own = await app.run(
        AppTicket(text="x"), context=ctx("a", principal_id="customer-a")
    )
    other = await app.run(
        AppTicket(text="x"), context=ctx("b", principal_id="customer-b")
    )

    assert [e.artifact.type for e in own.outputs] == ["AppSummary"]
    assert other.outputs == ()


@pytest.mark.asyncio
async def test_until_stop_cancels_remaining_work():
    started_slow = asyncio.Event()

    async def fast(agent, ctx, inputs):
        return [AppSummary(text="fast")]

    async def slow(agent, ctx, inputs):
        started_slow.set()
        await asyncio.sleep(30)
        return [AppDigest(count=0)]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("fast").consumes(AppTicket).publishes(AppSummary).with_engines(
            engine(fast)
        )
        flock.agent("slow").consumes(AppTicket).publishes(AppDigest).with_engines(
            engine(slow)
        )
        return flock

    app = app_for(factory, completion=CompletionPolicy(until=Until.exists(AppSummary)))

    result = await asyncio.wait_for(
        app.run(AppTicket(text="x"), context=ctx(), timeout=10), 5
    )

    assert result.ok
    assert result.condition_met is True
    assert started_slow.is_set()


@pytest.mark.asyncio
async def test_unmet_until_condition_fails():
    app = app_for(completion=CompletionPolicy(until=Until.exists(AppDigest)))

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.CONDITION_NOT_MET
    assert result.condition_met is False


@pytest.mark.asyncio
async def test_output_limit_fails_without_dropping_silently():
    async def ideas(agent, ctx, inputs):
        return [AppIdea(n=i) for i in range(3)]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("ideas").consumes(AppTicket).publishes(
            AppIdea, fan_out=3
        ).with_engines(engine(ideas))
        return flock

    app = FlockApplication(
        factory, input_type=AppTicket, output_types=(AppIdea,), max_outputs=2
    )

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.OUTPUT_LIMIT_EXCEEDED
    assert len(result.outputs) == 2


@pytest.mark.asyncio
async def test_duplicate_and_recent_ids_are_rejected_until_retention_expires():
    now = [1000.0]
    app = app_for(id_retention=timedelta(seconds=60), clock=lambda: now[0])

    first = await app.run(AppTicket(text="x"), context=ctx("same"))
    assert first.ok
    with pytest.raises(WorkflowIdConflict):
        await app.run(AppTicket(text="x"), context=ctx("same", principal_id="other"))

    now[0] += 61
    assert (await app.run(AppTicket(text="x"), context=ctx("same"))).ok


@pytest.mark.asyncio
async def test_active_duplicate_id_is_rejected():
    app = app_for()

    async with app.stream(AppTicket(text="x", delay=0.3), context=ctx("dup")):
        with pytest.raises(WorkflowIdConflict):
            await app.run(AppTicket(text="y"), context=ctx("dup"))


@pytest.mark.asyncio
async def test_capacity_rejection_keeps_id_reusable():
    app = app_for(max_active_workflows=1)

    async with app.stream(AppTicket(text="x", delay=0.3), context=ctx("busy")):
        with pytest.raises(CapacityExceeded):
            await app.run(AppTicket(text="y"), context=ctx("retry-me"))

    assert (await app.run(AppTicket(text="y"), context=ctx("retry-me"))).ok


@pytest.mark.asyncio
async def test_conversation_turns_serialize_per_session_but_not_across():
    order: list[str] = []

    async def record(agent, ctx, inputs):
        text = inputs.artifacts[0].payload["text"]
        order.append(f"start:{text}")
        await asyncio.sleep(0.1)
        order.append(f"end:{text}")
        return [AppSummary(text=text)]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("record").consumes(AppTicket).publishes(AppSummary).with_engines(
            engine(record)
        )
        return flock

    app = app_for(factory, history="conversation")
    with pytest.raises(SessionRequired):
        await app.run(AppTicket(text="x"), context=ctx("no-session"))

    same = [
        app.run(
            AppTicket(text=f"s{i}"),
            context=ctx(f"t{i}", principal_id="p", session_id="c1"),
        )
        for i in range(2)
    ]
    other = app.run(
        AppTicket(text="o"), context=ctx("t-other", principal_id="p", session_id="c2")
    )
    results = await asyncio.gather(*same, other)

    assert all(r.ok for r in results)
    assert order.index("end:s0") < order.index("start:s1")
    assert order.index("start:o") < order.index("end:s0")


@pytest.mark.asyncio
async def test_concurrent_workflows_are_independent():
    app = app_for()

    slow_task = asyncio.create_task(
        app.run(
            AppTicket(text="slow", delay=0.3), context=ctx("slow", principal_id="a")
        )
    )
    fast = await app.run(AppTicket(text="fast"), context=ctx("fast", principal_id="b"))
    slow = await slow_task

    assert fast.ok and slow.ok
    assert fast.values(AppSummary) == [AppSummary(text="summary:triaged:fast")]
    assert slow.values(AppSummary) == [AppSummary(text="summary:triaged:slow")]


@pytest.mark.asyncio
async def test_factory_receives_context_and_may_be_async():
    seen: list[WorkflowContext] = []

    async def factory(context: WorkflowContext) -> Flock:
        seen.append(context)
        return two_stage_flock()

    app = app_for(factory)
    context = ctx("wf-ctx", principal_id="p", attributes={"call_id": "c-1"})

    assert (await app.run(AppTicket(text="x"), context=context)).ok
    assert seen[-1] is context


@pytest.mark.asyncio
async def test_factory_failure_is_reported_after_admission():
    calls = {"n": 0}

    def factory() -> Flock:
        calls["n"] += 1
        if calls["n"] > 1:  # first call is the contract probe
            raise RuntimeError("boom")
        return two_stage_flock()

    app = app_for(factory)

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.FACTORY_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factory", "kwargs", "message"),
    [
        (lambda: Flock(), {}, "no_output=True"),
        (two_stage_flock, {"input_type": AppIdea}, "no agent consumes"),
        (
            two_stage_flock,
            {"output_types": (AppDigest,), "required_output_types": ()},
            "no agent publishes",
        ),
    ],
)
async def test_contract_errors_are_raised_by_start(factory, kwargs, message):
    app = app_for(factory, **kwargs)

    with pytest.raises(ContractError, match=message):
        await app.start()


@pytest.mark.asyncio
@pytest.mark.parametrize("input_type", [AppTicket, AppIdea])
async def test_contract_probe_instance_is_shut_down(input_type):
    shutdowns: list[dict] = []

    def factory() -> Flock:
        flock = two_stage_flock()
        original = flock.shutdown

        async def spy(**kwargs):
            shutdowns.append(kwargs)
            await original(**kwargs)

        flock.shutdown = spy
        return flock

    app = app_for(factory, input_type=input_type)
    if input_type is AppTicket:
        await app.start()
    else:
        with pytest.raises(ContractError):
            await app.start()

    assert shutdowns == [{"include_components": False}]


@pytest.mark.asyncio
async def test_reused_instance_is_rejected():
    shared = two_stage_flock()
    app = app_for(lambda: shared)
    await app.start()  # the contract probe consumes the instance

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.code is FailureCode.FACTORY_ERROR


@pytest.mark.asyncio
async def test_components_shut_down_once_and_instance_is_released():
    shutdowns: list[str] = []
    instances: list[weakref.ref] = []

    class Tracker(OrchestratorComponent):
        async def on_shutdown(self, orchestrator):
            shutdowns.append("down")

    def factory() -> Flock:
        flock = two_stage_flock()
        flock.add_component(Tracker())
        instances.append(weakref.ref(flock))
        return flock

    app = app_for(factory)
    await app.start()
    result = await app.run(AppTicket(text="x"), context=ctx())
    gc.collect()

    assert result.ok
    assert shutdowns == ["down"]
    assert instances[-1]() is None


@pytest.mark.asyncio
async def test_shutdown_drains_then_cancels():
    app = app_for()
    await app.start()

    quick = asyncio.create_task(
        app.run(AppTicket(text="q", delay=0.05), context=ctx("q"))
    )
    slow = asyncio.create_task(app.run(AppTicket(text="s", delay=30), context=ctx("s")))
    await asyncio.sleep(0.01)
    await app.shutdown(grace=0.5)

    assert (await quick).ok
    assert (await slow).status is WorkflowStatus.CANCELLED
    assert not app.accepting


def _scheduled_flock() -> Flock:
    async def beat(agent, ctx, inputs):
        return [AppDigest(count=1)]

    flock = Flock(no_output=True)
    flock.agent("triage").consumes(AppTicket).publishes(AppTriage).with_engines(
        engine(triage)
    )
    flock.agent("heartbeat").schedule(every=timedelta(milliseconds=20)).publishes(
        AppDigest
    ).with_engines(engine(beat))
    return flock


@pytest.mark.asyncio
async def test_scheduled_agents_need_an_explicit_until():
    app = FlockApplication(
        _scheduled_flock, input_type=AppTicket, output_types=(AppDigest,)
    )

    with pytest.raises(ContractError, match="open-ended"):
        await app.start()


@pytest.mark.asyncio
async def test_scheduled_agents_stop_at_until_and_timers_are_cleaned_up():
    app = FlockApplication(
        _scheduled_flock,
        input_type=AppTicket,
        output_types=(AppDigest,),
        completion=CompletionPolicy(until=Until.artifact_count(AppDigest).at_least(2)),
    )

    result = await asyncio.wait_for(
        app.run(AppTicket(text="x"), context=ctx(), timeout=10), 5
    )

    assert result.ok
    assert len(result.values(AppDigest)) >= 2
    assert app.active_workflows == 0


@pytest.mark.asyncio
async def test_on_error_continue_finishes_other_branches_but_still_fails():
    async def boom(agent, ctx, inputs):
        raise RuntimeError("branch failed")

    async def fine(agent, ctx, inputs):
        await asyncio.sleep(0.05)
        return [AppSummary(text="other branch")]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("boom").consumes(AppTicket).publishes(AppDigest).with_engines(
            engine(boom)
        )
        flock.agent("fine").consumes(AppTicket).publishes(AppSummary).with_engines(
            engine(fine)
        )
        return flock

    stop_app = app_for(factory)
    continue_app = app_for(factory, completion=CompletionPolicy(on_error="continue"))

    stopped = await stop_app.run(AppTicket(text="x"), context=ctx("stop"))
    continued = await continue_app.run(AppTicket(text="x"), context=ctx("continue"))

    assert stopped.failure.code is FailureCode.AGENT_FAILED
    assert continued.failure.code is FailureCode.AGENT_FAILED
    assert continued.values(AppSummary) == [AppSummary(text="other branch")]


@pytest.mark.asyncio
async def test_until_drain_lets_remaining_work_finish():
    async def fast(agent, ctx, inputs):
        return [AppSummary(text="fast")]

    async def later(agent, ctx, inputs):
        await asyncio.sleep(0.1)
        return [AppDigest(count=1)]

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("fast").consumes(AppTicket).publishes(AppSummary).with_engines(
            engine(fast)
        )
        flock.agent("later").consumes(AppTicket).publishes(AppDigest).with_engines(
            engine(later)
        )
        return flock

    app = FlockApplication(
        factory,
        input_type=AppTicket,
        output_types=(AppSummary, AppDigest),
        completion=CompletionPolicy(
            until=Until.exists(AppSummary), on_condition="drain"
        ),
    )

    result = await app.run(AppTicket(text="x"), context=ctx())

    assert result.ok and result.condition_met
    assert result.values(AppDigest) == [AppDigest(count=1)]


@pytest.mark.asyncio
async def test_task_failures_during_teardown_do_not_change_the_outcome():
    async def fast(agent, ctx, inputs):
        return [AppSummary(text="fast")]

    async def stubborn(agent, ctx, inputs):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise RuntimeError("converted cancellation") from None
        return []

    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("fast").consumes(AppTicket).publishes(AppSummary).with_engines(
            engine(fast)
        )
        flock.agent("stubborn").consumes(AppTicket).publishes(AppDigest).with_engines(
            engine(stubborn)
        )
        return flock

    app = app_for(factory, completion=CompletionPolicy(until=Until.exists(AppSummary)))

    result = await app.run(AppTicket(text="x"), context=ctx(), timeout=10)

    assert result.status is WorkflowStatus.SUCCEEDED
    # the WorkflowError published while tearing down is recorded, not counted
    assert result.diagnostics["late_publications"] >= 1


def test_task_outcomes_after_freeze_are_only_diagnostics():
    from flock.application.application import _Workflow
    from flock.orchestrator import AgentTaskOutcome

    workflow = _Workflow(app_for(), AppTicket(text="x"), ctx(), deadline=0.0)
    workflow.frozen = True

    workflow.on_task_outcome(AgentTaskOutcome("a", "t", "failed", "RuntimeError"))

    assert workflow.failure is None
    assert workflow.late_task_failures == 1
