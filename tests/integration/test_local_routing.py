import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent

from tests._helpers.fakes import FakeEvaluator, FakeRouter


pytestmark = pytest.mark.integration


def test_local_routing_chain(register_fakes):
    a1 = FlockAgent(name="a1", input="message: str", output="result: str", components=[FakeEvaluator(name="eval1"), FakeRouter(name="router")])
    a2 = FlockAgent(name="a2", input="message: str", output="result: str", components=[FakeEvaluator(name="eval2")])

    flock = Flock(name="chain", show_flock_banner=False)
    flock.add_agent(a1)
    flock.add_agent(a2)

    # Provide next agent via context variable through inputs to router
    out = flock.run(agent="a1", input={"message": "hi", "next_agent": "a2"})
    assert out == {"result": "hi:a2"}

