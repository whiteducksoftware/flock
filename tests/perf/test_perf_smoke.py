import time
import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.perf


def test_simple_agent_runs_fast(register_fakes):
    agent = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
    flock = Flock(name="perf", show_flock_banner=False)
    flock.add_agent(agent)

    n = 300
    t0 = time.perf_counter()
    for _ in range(n):
        out = flock.run(agent="a1", input={"message": "x"}, box_result=False)
        assert out == {"result": "x:a1"}
    elapsed = time.perf_counter() - t0
    # Generous threshold to avoid flakiness on CI; adjust as needed
    assert elapsed < 2.0

