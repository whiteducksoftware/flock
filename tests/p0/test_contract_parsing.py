import pytest

from flock.core.flock_agent import FlockAgent
from flock.core.context.context import FlockContext


pytestmark = pytest.mark.p0


def test_next_input_for_parses_single_key():
    agent = FlockAgent(name="a1", input="message", output="result: str")
    ctx = FlockContext()
    ctx.set_variable("message", "hello")
    assert ctx.next_input_for(agent) == "hello"


def test_next_input_for_multiple_keys():
    agent = FlockAgent(name="a1", input="a, b", output="result: str")
    ctx = FlockContext()
    ctx.set_variable("a", 1)
    ctx.set_variable("b", "two")
    assert ctx.next_input_for(agent) == {"a": 1, "b": "two"}
