import pytest

from flock.core.flock_agent import FlockAgent
from flock.core.context.context import FlockContext


pytestmark = pytest.mark.p0


def desc0():
    return "d0"


def desc1(ctx: FlockContext):
    return f"d1:{'ok' if isinstance(ctx, FlockContext) else 'no'}"


def bad(a, b):
    return "wrong"


def test_description_resolves_0_and_1_arg():
    a = FlockAgent(name="ai", input="message", output="result")
    a.description = desc0
    assert a.description == "d0"
    a.description = desc1
    # ensure context is passed
    a.context = FlockContext()
    assert a.description == "d1:ok"


def test_description_invalid_callable_raises():
    a = FlockAgent(name="ai2", input="message", output="result")
    a.description = bad  # invalid signature for adapt()
    with pytest.raises(TypeError):
        _ = a.description

