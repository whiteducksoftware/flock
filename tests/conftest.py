"""Global pytest fixtures for Flock tests."""

import os

import pytest

from flock.core.flock_agent import FlockAgent
from flock.core.registry import get_registry
from tests._helpers.fakes import FakeEvaluator, FakeRouter

# Ensure telemetry auto-setup is disabled in tests
os.environ.setdefault("FLOCK_DISABLE_TELEMETRY_AUTOSETUP", "1")


@pytest.fixture(autouse=True)
def registry_clear():
    """Clear the global registry before and after each test."""
    reg = get_registry()
    reg.clear_all()
    try:
        yield
    finally:
        reg.clear_all()


@pytest.fixture()
def register_fakes():
    """Register deterministic fake components for use in tests."""
    reg = get_registry()
    reg.register_component(FakeEvaluator)
    reg.register_component(FakeRouter)
    return reg


@pytest.fixture()
def simple_agent(register_fakes) -> FlockAgent:
    """Return a simple agent with FakeEvaluator configured."""
    return FlockAgent(
        name="agent1",
        input="message: str",
        output="result: str",
        components=[FakeEvaluator(name="eval")],
    )
