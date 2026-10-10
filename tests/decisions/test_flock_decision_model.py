"""A flock-wide default decision model: Flock(decision_model=...)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.decisions import Choice, FakeDecider
from flock.decisions.engine import DecisionEngine
from flock.registry import flock_type


@flock_type
class Request(BaseModel):
    text: str


class Lane(Choice):
    """Which lane?"""

    fast = "Fast lane"
    slow = "Slow lane"


def provider_of(flock: Flock, name: str):
    agent = next(a for a in flock.agents if a.name == name)
    (engine,) = [e for e in agent.engines if isinstance(e, DecisionEngine)]
    return engine.provider


def test_deciders_use_the_flock_decision_model():
    decider = FakeDecider({"fast": 0.9, "slow": 0.1})
    flock = Flock(decision_model=decider)

    flock.agent("a").consumes(Request).decides(Lane)
    flock.agent("b").consumes(Request).decides(Lane, threshold=0.8)

    assert flock.decision_model is decider
    assert provider_of(flock, "a") is decider
    assert provider_of(flock, "b") is decider


def test_model_on_decides_wins():
    explicit = FakeDecider({"fast": 0.9, "slow": 0.1}, label="explicit")
    flock = Flock(decision_model=FakeDecider({"fast": 0.1, "slow": 0.9}))

    flock.agent("a").consumes(Request).decides(Lane, model=explicit)

    assert provider_of(flock, "a") is explicit


def test_flock_decision_model_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("DEFAULT_DECISION_MODEL", "local/from-env")
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    flock = Flock(decision_model="jev/jev-latest")

    flock.agent("a").consumes(Request).decides(Lane)

    assert provider_of(flock, "a").label == "jev/jev-latest"


def test_without_any_model_the_error_names_every_option(monkeypatch):
    monkeypatch.delenv("DEFAULT_DECISION_MODEL", raising=False)
    flock = Flock()

    with pytest.raises(ValueError, match=r"decision_model=.*DEFAULT_DECISION_MODEL"):
        flock.agent("a").consumes(Request).decides(Lane)


async def test_decisions_flow_with_the_flock_model():
    flock = Flock(decision_model=FakeDecider({"fast": 0.9, "slow": 0.1}))
    flock.agent("a").consumes(Request).decides(Lane)

    await flock.publish(Request(text="urgent"))
    await flock.run_until_idle()

    decisions = [a for a in await flock.store.list() if a.type.startswith("Decision[")]
    assert [d.payload["choice"] for d in decisions] == ["fast"]
