import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_CURRENT_AGENT, FLOCK_RUN_ID

from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.integration


def test_run_records_history_and_context_vars(register_fakes):
    agent = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    ctx = FlockContext()

    flock = Flock(name="ctx", show_flock_banner=False)
    flock.add_agent(agent)
    out = flock.run(agent="a1", input={"message": "hi"}, context=ctx, box_result=False)
    assert out == {"result": "hi:a1"}

    # Context has run_id and last current agent set
    assert ctx.run_id
    assert ctx.get_variable(FLOCK_RUN_ID) == ctx.run_id
    assert ctx.get_variable(FLOCK_CURRENT_AGENT) == "a1"

    # History contains at least one record for a1
    assert any(rec.agent == "a1" for rec in ctx.history)

