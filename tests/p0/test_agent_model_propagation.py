import pytest

from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def test_agent_set_model_propagates_to_evaluator(register_fakes):
    agent = FlockAgent(
        name="m1",
        input="message",
        output="result",
        components=[FakeEvaluator(name="eval")],
    )
    agent.set_model("unit/model")
    assert agent.model == "unit/model"
    assert agent.evaluator.config.model == "unit/model"

