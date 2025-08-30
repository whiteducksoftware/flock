import pytest

from flock.core.registry import get_registry

from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def tool_one(x):
    return x + 1


def tool_two(x):
    return x * 2


def test_registry_callables_and_components(simple_agent):
    reg = get_registry()

    # Agent registration
    reg.register_agent(simple_agent)
    assert reg.get_agent(simple_agent.name) is simple_agent

    # Callable registration and lookup
    name1 = reg.register_callable(tool_one)
    name2 = reg.register_callable(tool_two)
    assert name1 and name2
    assert reg.get_callable("tool_one")(3) == 4
    assert reg.get_callable("tool_two")(3) == 6

    # Component registration and lookup
    type_name = reg.register_component(FakeEvaluator)
    assert type_name == "FakeEvaluator"
    cls = reg.get_component(type_name)
    assert cls is FakeEvaluator

