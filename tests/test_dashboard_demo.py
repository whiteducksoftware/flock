"""The dashboard demo (examples/04-misc/10_dashboard_triage_demo.py) produces
the states it promises, without API keys."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from flock.decisions import UNSURE, Decision
from flock.models.system_artifacts import WorkflowError
from flock.registry import type_registry


DEMO = (
    Path(__file__).parents[1] / "examples" / "04-misc" / "10_dashboard_triage_demo.py"
)


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("dashboard_triage_demo", DEMO)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


async def test_the_demo_runs_every_state_without_api_keys(demo):
    flock = demo.build_flock(token_seconds=0, decide_seconds=0, digest_every=None)

    for number in range(1, 11):  # every ticket of the catalog, and one more
        await flock.publish(demo.ticket(number))
    for number in (2, 4):  # follow-ups for two tickets: their joins complete
        await flock.publish(
            demo.CustomerFollowUp(ticket_id=f"T-{number:04d}", note="Any news?")
        )
    await flock.run_until_idle()

    by_type: dict[str, list] = {}
    for artifact in await flock.store.list():
        by_type.setdefault(artifact.type, []).append(artifact)

    def of(model) -> list:
        return by_type.get(type_registry.name_for(model), [])

    routes = [a.payload["choice"] for a in of(Decision.of(demo.Route))]
    replies = of(demo.TeamReply)
    assert sorted(set(routes)) == sorted({"billing", "shipping", "tech", UNSURE})
    assert {a.payload["team"] for a in replies} == {
        "billing_team",
        "shipping_team",
        "tech_support",
        "supervisor",
    }
    assert len(replies) == 10  # every ticket gets an answer
    assert of(demo.Page)  # urgent tech tickets page on-call
    assert {a.payload["ticket_id"] for a in of(demo.Resolution)} == {"T-0002", "T-0004"}
    assert [a.payload["replies"] for a in of(demo.TeamReport)] == [5, 5]
    assert len(of(demo.CrmRecord)) < len(replies)  # the CRM fails now and then
    assert of(WorkflowError)


def test_the_demo_has_a_scheduled_agent(demo):
    flock = demo.build_flock()

    (digest,) = [agent for agent in flock.agents if agent.name == "digest"]
    assert digest.schedule_spec is not None
