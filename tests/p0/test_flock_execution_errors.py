import pytest

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from tests._helpers.fakes import FakeRouter
from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.context.context import FlockContext


pytestmark = pytest.mark.p0


class RaisingEval(EvaluationComponent):
    name: str = "raiser"

    def set_model(self, model: str, temperature: float = 0.0, max_tokens: int = 4096) -> None:
        return

    async def evaluate_core(self, agent, inputs, context: FlockContext | None = None, tools=None, mcp_tools=None):
        raise RuntimeError("boom")


def test_run_returns_error_dict_on_exception(register_fakes):
    a = FlockAgent(name="a", input="message", output="result", components=[RaisingEval(), FakeRouter(name="router")])
    flock = Flock(name="errflock", show_flock_banner=False)
    flock.add_agent(a)

    out = flock.run(agent="a", input={"message": "x"}, box_result=False)
    assert isinstance(out, dict)
    assert "error" in out and "run_id" in out and out["start_agent"] == "a"


def test_run_returns_box_on_exception_when_box_result(register_fakes):
    a = FlockAgent(name="a", input="message", output="result", components=[RaisingEval(), FakeRouter(name="router")])
    flock = Flock(name="errflock2", show_flock_banner=False)
    flock.add_agent(a)

    out = flock.run(agent="a", input={"message": "x"}, box_result=True)
    # Box equality with dict still works
    assert "error" in out and "run_id" in out

