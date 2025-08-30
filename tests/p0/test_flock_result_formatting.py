import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_flock_result_boxed_vs_raw(register_fakes):
    agent = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="fmt", show_flock_banner=False)
    flock.add_agent(agent)

    raw = flock.run(agent="a1", input={"message": "hi"}, box_result=False)
    assert isinstance(raw, dict)
    boxed = flock.run(agent="a1", input={"message": "hi"}, box_result=True)
    # Box behaves like a mapping with equality to dict
    assert boxed == {"result": "hi:a1"}

