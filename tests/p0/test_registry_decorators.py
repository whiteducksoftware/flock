import pytest

from flock.core.registry import get_registry
from flock.core.registry.decorators import flock_component, flock_tool, flock_type
from flock.core.component.agent_component_base import AgentComponent, AgentComponentConfig


pytestmark = pytest.mark.p0


def test_flock_component_decorator_registers_class():
    reg = get_registry()

    class MyCfg(AgentComponentConfig):
        pass

    @flock_component(name="DecoComp", config_class=MyCfg)
    class DecoComp(AgentComponent):
        name: str = "deco"

    # Component by name
    cls = reg.get_component("DecoComp")
    assert cls is DecoComp
    # Config mapping present
    assert reg.get_component_class_for_config(MyCfg) is DecoComp


def test_flock_tool_decorator_registers_callable():
    reg = get_registry()

    @flock_tool
    def foo(x):
        return x + 2

    assert reg.get_callable("foo")(5) == 7


def test_flock_type_decorator_registers_type():
    reg = get_registry()

    @flock_type(name="Fancy")
    class Fancy:
        pass

    assert reg.get_type("Fancy") is Fancy

