import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.registry import get_registry
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def desc_callable():
    return "A description"


def input_callable():
    return "message"


def output_callable():
    return "result"


def tool_add(x):
    return x + 1


def test_agent_serialization_with_callables_and_tools(register_fakes):
    reg = get_registry()
    # Register callables so path strings can be resolved for serialization
    reg.register_callable(desc_callable)
    reg.register_callable(input_callable)
    reg.register_callable(output_callable)
    reg.register_callable(tool_add)

    agent = FlockAgent(
        name="withc",
        description=desc_callable,
        input=input_callable,
        output=output_callable,
        components=[FakeEvaluator(name="eval")],
        tools=[tool_add],
    )

    flock = Flock(name="aflock", show_flock_banner=False)
    flock.add_agent(agent)

    agent_dict = agent.to_dict()
    assert agent_dict.get("description_callable") == "desc_callable"
    assert agent_dict.get("input_callable") == "input_callable"
    assert agent_dict.get("output_callable") == "output_callable"
    assert agent_dict.get("tools") == ["tool_add"]

    data = flock.to_dict()
    # FlockSerializer should include callable definitions under components
    comps = data.get("components", {})
    assert "tool_add" in comps

