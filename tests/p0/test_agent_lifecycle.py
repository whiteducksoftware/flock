import pytest

from tests._helpers.fakes import FakeEvaluator, HookRecorder
from flock.core.flock_agent import FlockAgent


pytestmark = pytest.mark.p0


def test_agent_lifecycle_order(register_fakes):
    agent = FlockAgent(
        name="a1",
        input="message: str",
        output="result: str",
        components=[HookRecorder(name="hooks"), FakeEvaluator(name="eval")],
    )

    # Ensure context exists so hooks can record order
    from flock.core.context.context import FlockContext
    agent.context = FlockContext()
    out = agent.run({"message": "hi"})
    assert out["result"].startswith("hi:")

    # Order markers captured by HookRecorder into context.state['order']
    order = agent.context.get_variable("order") if agent.context else None
    assert order is not None and set(["on_initialize","on_pre_evaluate","on_post_evaluate","terminate"]).issubset(order)

    # Ensure relative order is correct
    assert order.index("on_initialize") < order.index("on_pre_evaluate") < order.index("on_post_evaluate") < order.index("terminate")
