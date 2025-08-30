import pytest

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


pytestmark = pytest.mark.p0


def test_next_input_context_and_dot_keys():
    ctx = FlockContext()
    agent = FlockAgent(name="a1", input="a1.value, c", output="result")

    # state values
    ctx.set_variable("a1.value", 42)
    ctx.set_variable("c", "see")

    resolved = ctx.next_input_for(agent)
    assert resolved["a1.value"] == 42
    assert resolved["c"] == "see"
