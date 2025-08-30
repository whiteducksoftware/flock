import pytest

from flock.core.flock_agent import FlockAgent

from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_agent_serialization_roundtrip(register_fakes):
    agent = FlockAgent(
        name="a1",
        input="message: str",
        output="result: str",
        components=[FakeEvaluator(name="eval")],
    )

    data = agent.to_dict()
    assert data["name"] == "a1"
    assert any(c.get("type") == "FakeEvaluator" for c in data.get("components", []))

    # Current deserializer expects base fields without runtime-only ids
    data = dict(data)
    data.pop("agent_id", None)
    # Align keys with constructor expectations
    if "input_spec" in data:
        data["input"] = data.pop("input_spec")
    if "output_spec" in data:
        data["output"] = data.pop("output_spec")
    agent2 = FlockAgent.from_dict(data)
    assert agent2.name == "a1"
    assert len(agent2.components) == 1
    assert type(agent2.components[0]).__name__ == "FakeEvaluator"
