import copy
import pytest

from flock.core.flock_agent import FlockAgent

from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def _normalize_agent_dict(d: dict) -> dict:
    data = copy.deepcopy(d)
    # Remove non-deterministic/runtime fields
    data.pop("agent_id", None)
    # Order-insensitive normalization of components
    comps = data.get("components", [])
    for c in comps:
        # No runtime fields expected beyond these
        c.setdefault("config", {})
        # Ensure config doesn't include nulls
        if "model" in c.get("config", {}) and c["config"]["model"] is None:
            c["config"].pop("model")
    return data


def test_agent_to_dict_snapshot(register_fakes):
    agent = FlockAgent(
        name="snap",
        input="message",
        output="result",
        components=[FakeEvaluator(name="eval")],
    )

    data = _normalize_agent_dict(agent.to_dict())

    expected = {
        "name": "snap",
        "input_spec": "message",
        "output_spec": "result",
        "config": {
            "write_to_file": False,
            "wait_for_input": False,
            "handoff_strategy": "static",
        },
        "components": [
            {
                "name": "eval",
                "config": {"enabled": True},
                "type": "FakeEvaluator",
            }
        ],
    }

    assert data == expected


def test_agent_to_dict_with_router_snapshot(register_fakes):
    from tests._helpers.fakes import FakeRouter

    agent = FlockAgent(
        name="snap2",
        input="message",
        output="result",
        components=[FakeEvaluator(name="eval"), FakeRouter(name="router")],
    )

    data = _normalize_agent_dict(agent.to_dict())

    # Order-independent check for components
    types = sorted([c["type"] for c in data.get("components", [])])
    assert types == ["FakeEvaluator", "FakeRouter"]
