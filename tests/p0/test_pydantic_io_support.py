import pytest
from pydantic import BaseModel

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.registry import flock_type
from tests._helpers.fakes import FakeEvaluator


pytestmark = pytest.mark.p0


@flock_type
class InModel(BaseModel):
    message: str


@flock_type
class OutModel(BaseModel):
    result: str


def test_agent_pydantic_io_resolves_specs(register_fakes):
    """Agent accepts Pydantic models for input/output and resolves to spec strings."""
    agent = FlockAgent(
        name="pyd-agent",
        input=InModel,
        output=OutModel,
        components=[FakeEvaluator(name="eval")],
    )

    # The public properties return the resolved string specs
    assert isinstance(agent.input, str)
    assert isinstance(agent.output, str)

    # Basic contract: field names and types appear in the string contract
    assert "message: str" in agent.input
    assert "result: str" in agent.output


def test_flock_run_accepts_pydantic_input_with_pydantic_io(register_fakes):
    """Flock.run accepts a BaseModel instance as input when agent IO uses Pydantic models."""
    agent = FlockAgent(
        name="pyd-agent",
        input=InModel,
        output=OutModel,
        components=[FakeEvaluator(name="eval")],
    )
    flock = Flock(name="pyd-f", show_flock_banner=False)
    flock.add_agent(agent)

    # Pass a BaseModel instance as input
    out = flock.run(agent=agent, input=InModel(message="hi"), box_result=False)
    assert out == {"result": "hi:pyd-agent"}


def test_flock_run_accepts_pydantic_input_with_string_io(register_fakes):
    """Flock.run accepts a BaseModel instance even if the agent IO was defined as strings."""
    class SimpleIn(BaseModel):
        message: str

    agent = FlockAgent(
        name="mix-agent",
        input="message: str",
        output="result: str",
        components=[FakeEvaluator(name="eval")],
    )
    flock = Flock(name="mix-f", show_flock_banner=False)
    flock.add_agent(agent)

    out = flock.run(agent=agent, input=SimpleIn(message="hey"), box_result=False)
    assert out == {"result": "hey:mix-agent"}

