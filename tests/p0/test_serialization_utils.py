import pytest

from flock.core.serialization.serialization_utils import (
    deserialize_component,
    deserialize_item,
)
from flock.core.registry import get_registry

from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_deserialize_component_known(register_fakes):
    data = {"type": "FakeEvaluator", "name": "eval", "config": {"enabled": True}}
    comp = deserialize_component(data, expected_base_type=object)
    assert comp is not None
    assert type(comp).__name__ == "FakeEvaluator"


def test_deserialize_component_unknown_returns_none(register_fakes):
    data = {"type": "DefinitelyUnknownComponent", "name": "x"}
    comp = deserialize_component(data, expected_base_type=object)
    assert comp is None


def test_deserialize_callable_ref(register_fakes):
    def tool_one(x):
        return x + 1

    reg = get_registry()
    reg.register_callable(tool_one)  # ensures lookup by simple name works

    ref = {"__callable_ref__": "tool_one"}
    fn = deserialize_item(ref)
    assert callable(fn)
    assert fn(3) == 4


def test_deserialize_type_ref_builtin():
    t = deserialize_item({"__type_ref__": "builtins.int"})
    assert t is int


def test_deserialize_unknown_callable_returns_none():
    fn = deserialize_item({"__callable_ref__": "does_not_exist"})
    assert fn is None


def test_deserialize_unknown_component_returns_none():
    comp = deserialize_component({"type": "Nope"}, expected_base_type=object)
    assert comp is None
