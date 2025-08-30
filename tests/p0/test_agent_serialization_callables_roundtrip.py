import pytest

from flock.core.flock_agent import FlockAgent
from flock.core.registry import get_registry
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def d():
    return "desc"


def i():
    return "message"


def o():
    return "result"


def tool(x):
    return x * 2


def test_agent_from_dict_restores_callables_and_tools(register_fakes):
    reg = get_registry()
    # Register callables
    for fn in (d, i, o, tool):
        reg.register_callable(fn)

    a = FlockAgent(
        name="A",
        description=d,
        input=i,
        output=o,
        tools=[tool],
        components=[FakeEvaluator(name="eval")],
    )
    data = a.to_dict()
    # Align with our from_dict expectations (normalize)
    data = dict(data)
    data.pop("agent_id", None)
    # from_dict should recreate the agent with callables resolved
    a2 = FlockAgent.from_dict(data)
    assert a2.name == "A"
    # Callables restored by name
    assert a2.description_spec is not None and callable(a2.description_spec)
    assert a2.input_spec is not None and callable(a2.input_spec)
    assert a2.output_spec is not None and callable(a2.output_spec)
    # Tools restored as callables on the agent
    assert a2.tools and callable(a2.tools[0])

