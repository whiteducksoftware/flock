import pytest
from box import Box

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


def make_agent(name: str) -> FlockAgent:
    return FlockAgent(name=name, input="message", output="result", components=[FakeEvaluator(name="eval")])


def test_run_defaults_single_agent_without_agent_param(register_fakes):
    flock = Flock(name="v1", show_flock_banner=False)
    a1 = make_agent("a1")
    flock.add_agent(a1)
    out = flock.run(input={"message": "hi"}, box_result=False)
    assert out == {"result": "hi:a1"}


def test_run_unknown_start_agent_raises(register_fakes):
    flock = Flock(name="v2", show_flock_banner=False)
    a1 = make_agent("a1")
    flock.add_agent(a1)
    with pytest.raises(ValueError):
        flock.run(agent="does-not-exist", input={"message": "hi"})


def test_run_with_agents_param_adds(register_fakes):
    flock = Flock(name="v3", show_flock_banner=False)
    a1 = make_agent("a1")
    # pass via 'agents' param instead of add_agent
    out = flock.run(agent="a1", input={"message": "hi"}, agents=[a1], box_result=False)
    assert out == {"result": "hi:a1"}
    # ensure persisted internally
    assert "a1" in flock.agents


def test_run_with_agent_instance(register_fakes):
    flock = Flock(name="v4", show_flock_banner=False)
    a1 = make_agent("a1")
    flock.add_agent(a1)
    # pass the instance instead of name
    out = flock.run(agent=a1, input={"message": "hi"}, box_result=False)
    assert out == {"result": "hi:a1"}


def test_run_box_result_is_box(register_fakes):
    flock = Flock(name="v5", show_flock_banner=False)
    a1 = make_agent("a1")
    flock.add_agent(a1)
    out = flock.run(agent="a1", input={"message": "hi"}, box_result=True)
    assert isinstance(out, Box)
    assert out == {"result": "hi:a1"}

