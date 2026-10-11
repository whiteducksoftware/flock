"""Active runs for a dashboard that connects while runs go on (#608)."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.components.agent import EngineComponent
from flock.components.server.traces.trace_component import TracingComponent
from flock.core import Flock
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type(name="ActiveRunTicket")
class ActiveRunTicket(BaseModel):
    text: str


@flock_type(name="ActiveRunReply")
class ActiveRunReply(BaseModel):
    text: str


RELEASE: dict[str, asyncio.Event] = {}


class WaitingEngine(EngineComponent):
    """Works until the test releases it."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        await RELEASE["writer"].wait()
        return EvalResult.from_object(ActiveRunReply(text="done"), agent=agent)


def _app(flock: Flock) -> FastAPI:
    app = FastAPI()
    TracingComponent().register_routes(app, flock)
    return app


async def _active(app: FastAPI) -> list[dict]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/plugin/runs/active")
    assert response.status_code == 200
    return response.json()["runs"]


async def test_lists_the_runs_going_on_and_drops_them_when_they_end():
    RELEASE["writer"] = asyncio.Event()
    flock = Flock(no_output=True)
    flock.agent("writer").consumes(ActiveRunTicket).publishes(
        ActiveRunReply
    ).with_engines(WaitingEngine())
    collector = DashboardEventCollector(store=flock.store)
    flock._dashboard_collector = collector  # as serve(dashboard=True) does
    for agent in flock.agents:
        agent._add_utilities([collector])
    app = _app(flock)

    ticket = await flock.publish(ActiveRunTicket(text="hi"))
    running = asyncio.create_task(flock.run_until_idle())
    for _ in range(200):
        if await _active(app):
            break
        await asyncio.sleep(0.01)

    (run,) = await _active(app)
    assert run["agent_name"] == "writer"
    assert run["correlation_id"] == str(ticket.correlation_id)
    assert run["consumed_artifacts"] == [str(ticket.id)]
    assert run["run_id"]
    assert run["start_time"]

    RELEASE["writer"].set()
    await running
    assert await _active(app) == []


async def test_knows_no_runs_without_the_dashboard():
    assert await _active(_app(Flock(no_output=True))) == []
