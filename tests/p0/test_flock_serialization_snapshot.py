import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_flock_to_dict_minimal(register_fakes):
    a1 = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="snapflock", show_flock_banner=False)
    flock.add_agent(a1)

    data = flock.to_dict()

    # Basic structure
    assert data["name"] == "snapflock"
    assert "agents" in data and "a1" in data["agents"]
    # Agent entry should include components with FakeEvaluator type
    agent_entry = data["agents"]["a1"]
    assert any(c.get("type") == "FakeEvaluator" for c in agent_entry.get("components", []))
    # Dependencies and metadata present
    assert "dependencies" in data
    assert data.get("metadata", {}).get("path_type") in {"relative", "absolute"}
