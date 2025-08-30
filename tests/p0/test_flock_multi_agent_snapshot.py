import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator, FakeRouter


pytestmark = pytest.mark.p0


def test_flock_two_agents_with_router_snapshot(register_fakes):
    a1 = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval1"), FakeRouter(name="router")])
    a2 = FlockAgent(name="a2", input="message", output="result", components=[FakeEvaluator(name="eval2")])

    flock = Flock(name="multi", show_flock_banner=False)
    flock.add_agent(a1)
    flock.add_agent(a2)

    data = flock.to_dict()
    assert data["name"] == "multi"
    assert set(data["agents"].keys()) == {"a1", "a2"}
    # Ensure router presence on a1
    comps_a1 = data["agents"]["a1"].get("components", [])
    types_a1 = {c.get("type") for c in comps_a1}
    assert "FakeRouter" in types_a1 and "FakeEvaluator" in types_a1
    # a2 has just evaluator
    comps_a2 = data["agents"]["a2"].get("components", [])
    types_a2 = {c.get("type") for c in comps_a2}
    assert types_a2 == {"FakeEvaluator"}

