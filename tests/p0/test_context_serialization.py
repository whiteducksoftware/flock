import pytest

from flock.core.context.context import FlockContext
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_context_introspection_after_run(register_fakes):
    a = FlockAgent(name="a", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="ctxsnap", show_flock_banner=False)
    flock.add_agent(a)
    ctx = FlockContext()

    _ = flock.run(agent="a", input={"message": "hi"}, context=ctx, box_result=False)

    # Last agent name recorded
    assert ctx.get_last_agent_name() == "a"
    # State present and contains last agent/result vars
    assert isinstance(ctx.state, dict)
    assert ctx.get_variable("flock.current_agent") == "a"
    # get_agent_history and get_most_recent_value work
    hist = ctx.get_agent_history("a")
    assert hist and hist[-1].agent == "a"
    assert ctx.get_most_recent_value("result") is not None
