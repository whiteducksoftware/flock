import types
import sys
import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.registry import get_registry

from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_flock_error_missing_start_agent_returns_error_dict(register_fakes):
    a1 = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    a2 = FlockAgent(name="a2", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="err", show_flock_banner=False)
    flock.add_agent(a1)
    flock.add_agent(a2)

    with pytest.raises(ValueError):
        flock.run(input={"message": "hi"}, box_result=False)


def test_flock_error_no_agents_present():
    flock = Flock(name="err2", show_flock_banner=False)
    with pytest.raises(ValueError):
        flock.run(input={"message": "hi"}, box_result=False)


def test_agent_without_evaluator_raises_runtime_error():
    agent = FlockAgent(name="noeval", input="x", output="y", components=[])
    with pytest.raises(RuntimeError):
        agent.run({"x": "y"})


def test_registry_ambiguous_callable_error():
    # Create two dummy modules with same function name
    mod_a = types.ModuleType("tmp_mod_a")
    mod_b = types.ModuleType("tmp_mod_b")

    def dup(x):
        return x

    def dup2(x):
        return x

    mod_a.dup = dup
    mod_b.dup = dup2
    sys.modules["tmp_mod_a"] = mod_a
    sys.modules["tmp_mod_b"] = mod_b

    reg = get_registry()
    reg.register_callable(mod_a.dup, name="tmp_mod_a.dup")
    reg.register_callable(mod_b.dup, name="tmp_mod_b.dup")

    with pytest.raises(KeyError):
        reg.get_callable("dup")


def test_agent_deserialize_skips_invalid_component(register_fakes):
    # Create minimal data with an invalid component type
    data = {
        "name": "A",
        "input": "message",
        "output": "result",
        "components": [
            {"name": "bad", "type": "DefinitelyUnknownComponent"}
        ],
    }
    agent = FlockAgent.from_dict(data)
    assert agent.name == "A"
    # Invalid component should not be present
    assert len(agent.components) == 0
