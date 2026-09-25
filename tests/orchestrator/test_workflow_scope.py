"""Workflow scope: correlation stamping and the mandatory context boundary."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.context_provider import BaseContextProvider, DefaultContextProvider
from flock.core.store import SQLiteBlackboardStore
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type(name="ScopeInput")
class ScopeInput(BaseModel):
    value: str


@flock_type(name="ScopeOutput")
class ScopeOutput(BaseModel):
    value: str
    context_size: int


class ContextEchoEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        return EvalResult.from_object(
            ScopeOutput(
                value=inputs.artifacts[0].payload["value"],
                context_size=len(ctx.artifacts),
            ),
            agent=agent,
        )


class WholeStoreProvider(BaseContextProvider):
    """Custom provider that deliberately queries the entire store."""

    async def get_artifacts(self, request):
        return await request.store.list()


def _flock(store=None, provider=None) -> Flock:
    flock = Flock(no_output=True, store=store)
    builder = (
        flock.agent("echo")
        .consumes(ScopeInput)
        .publishes(ScopeOutput)
        .with_engines(ContextEchoEngine())
    )
    if provider is not None:
        builder.with_context(provider)
    return flock


@pytest.mark.asyncio
async def test_scoped_instance_stamps_workflow_id_on_every_artifact():
    flock = _flock()
    flock._set_workflow_scope("resp_not_a_uuid")

    await flock.publish(ScopeInput(value="x"), correlation_id="other")
    await flock.run_until_idle()

    stored = await flock.store.list()
    assert len(stored) == 2
    assert {a.correlation_id for a in stored} == {"resp_not_a_uuid"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider", [None, DefaultContextProvider(), WholeStoreProvider()]
)
async def test_shared_store_never_leaks_foreign_artifacts_into_context(
    tmp_path, provider
):
    store = SQLiteBlackboardStore(str(tmp_path / "shared.db"))
    await store.ensure_schema()
    try:
        for i in range(3):
            await store.publish(
                Artifact(
                    type="ScopeInput",
                    payload={"value": f"foreign-{i}"},
                    produced_by="external",
                    correlation_id="someone-else",
                )
            )
        flock = _flock(store=store, provider=provider)
        flock._set_workflow_scope("mine")

        await flock.publish(ScopeInput(value="x"))
        await flock.run_until_idle()

        outputs, _ = await store.query_artifacts(limit=100)
        mine = [a for a in outputs if a.type == "ScopeOutput"]
        assert [a.payload["context_size"] for a in mine] == [0]
        assert mine[0].correlation_id == "mine"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_timer_ticks_join_the_workflow_scope():
    @flock_type(name="ScopeTick")
    class ScopeTick(BaseModel):
        n: int = 1

    flock = Flock(no_output=True)
    flock.agent("ticker").schedule(
        every=timedelta(milliseconds=20), max_repeats=1
    ).publishes(ScopeTick).with_engines(TickEngine())
    flock._set_workflow_scope("wf-1")

    await flock.run_until_idle(timeout=1)

    stored = await flock.store.list()
    assert stored
    assert {a.correlation_id for a in stored} == {"wf-1"}


class TickEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        from flock.registry import type_registry

        model = type_registry.resolve("ScopeTick")
        return EvalResult.from_object(model(n=1), agent=agent)
