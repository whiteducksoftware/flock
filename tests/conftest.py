import pytest

from flock.core.registry import get_registry
from flock.core.flock_agent import FlockAgent

from tests._helpers.fakes import FakeEvaluator, FakeRouter


@pytest.fixture(autouse=True)
def registry_clear():
    reg = get_registry()
    reg.clear_all()
    try:
        yield
    finally:
        reg.clear_all()


@pytest.fixture()
def register_fakes():
    reg = get_registry()
    reg.register_component(FakeEvaluator)
    reg.register_component(FakeRouter)
    return reg


@pytest.fixture()
def simple_agent(register_fakes) -> FlockAgent:
    return FlockAgent(
        name="agent1",
        input="message: str",
        output="result: str",
        components=[FakeEvaluator(name="eval")],
    )
import os
os.environ.setdefault("FLOCK_DISABLE_TELEMETRY_AUTOSETUP", "1")
