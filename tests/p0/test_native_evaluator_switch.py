import asyncio
import os
import pytest

from flock.components.evaluation.declarative_evaluation_component import (
    DeclarativeEvaluationComponent,
    DeclarativeEvaluationConfig,
)


class _DummyAgent:
    name = "dummy"
    model = None


@pytest.mark.p0
def test_declarative_eval_uses_native_when_flag_set(monkeypatch):
    # Ensure env flag enables native path
    monkeypatch.setenv("FLOCK_USE_NATIVE_EVALUATOR", "1")

    comp = DeclarativeEvaluationComponent(
        name="e", config=DeclarativeEvaluationConfig(use_native=False, program_type="predict")
    )
    out = asyncio.run(comp.evaluate_core(_DummyAgent(), {"q": "hi"}, context=None, tools=None, mcp_tools=None))
    assert out["q"] == "hi"


@pytest.mark.p0
def test_declarative_eval_uses_native_when_config_set(monkeypatch):
    monkeypatch.delenv("FLOCK_USE_NATIVE_EVALUATOR", raising=False)

    comp = DeclarativeEvaluationComponent(
        name="e", config=DeclarativeEvaluationConfig(use_native=True, program_type="predict")
    )
    out = asyncio.run(comp.evaluate_core(_DummyAgent(), {"a": 1}, context=None, tools=None, mcp_tools=None))
    assert out == {"a": 1}

