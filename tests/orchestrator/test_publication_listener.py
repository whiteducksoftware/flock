"""Publication listeners observe persisted artifacts in store order."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.components.orchestrator import OrchestratorComponent
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type(name="ListenerInput")
class ListenerInput(BaseModel):
    value: str


@flock_type(name="ListenerOutput")
class ListenerOutput(BaseModel):
    value: str


class EchoEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        value = inputs.artifacts[0].payload["value"]
        return EvalResult.from_object(ListenerOutput(value=value), agent=agent)


def _echo_flock() -> Flock:
    flock = Flock(no_output=True)
    (
        flock.agent("echo")
        .consumes(ListenerInput)
        .publishes(ListenerOutput)
        .with_engines(EchoEngine())
    )
    return flock


@pytest.mark.asyncio
async def test_listener_sees_input_and_cascade_in_store_order():
    flock = _echo_flock()
    seen: list[Artifact] = []
    flock._add_publication_listener(seen.append)

    await flock.publish(ListenerInput(value="a"))
    await flock.run_until_idle()

    stored = await flock.store.list()
    assert [a.id for a in seen] == [a.id for a in stored]
    assert [a.type for a in seen] == ["ListenerInput", "ListenerOutput"]


@pytest.mark.asyncio
async def test_listener_sees_persist_only_publications():
    flock = _echo_flock()
    seen: list[Artifact] = []
    flock._add_publication_listener(seen.append)

    await flock.publish(ListenerInput(value="a"), schedule_immediately=False)

    assert [a.type for a in seen] == ["ListenerInput"]


@pytest.mark.asyncio
async def test_listener_sees_artifacts_blocked_by_components():
    class BlockAll(OrchestratorComponent):
        async def on_artifact_published(self, orchestrator, artifact):
            return None

    flock = _echo_flock()
    flock.add_component(BlockAll())
    seen: list[Artifact] = []
    flock._add_publication_listener(seen.append)

    await flock.publish(ListenerInput(value="a"))
    await flock.run_until_idle()

    assert [a.type for a in seen] == ["ListenerInput"]


@pytest.mark.asyncio
async def test_failing_listener_does_not_break_publishing():
    flock = _echo_flock()

    def explode(_artifact: Artifact) -> None:
        raise RuntimeError("listener bug")

    flock._add_publication_listener(explode)

    await flock.publish(ListenerInput(value="a"))
    await flock.run_until_idle()

    assert len(await flock.store.list()) == 2


@pytest.mark.asyncio
async def test_removed_listener_is_not_called():
    flock = _echo_flock()
    seen: list[Artifact] = []
    remove = flock._add_publication_listener(seen.append)
    remove()

    await flock.publish(ListenerInput(value="a"))
    await flock.run_until_idle()

    assert seen == []
