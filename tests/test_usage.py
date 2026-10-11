"""Token usage and cost per agent run (#571)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from pydantic import BaseModel

from flock.components.agent import AgentComponent, EngineComponent
from flock.core import Flock
from flock.decisions import Choice, FakeDecider
from flock.decisions.providers import DecisionProvider
from flock.registry import flock_type
from flock.utils.runtime import EvalResult
from flock.utils.usage import ModelPrice, record_usage, run_metrics


@flock_type
class UsageTicket(BaseModel):
    text: str


@flock_type
class UsageReply(BaseModel):
    text: str


class UsageRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class UsageUrgent(Choice):
    """How soon does the customer need an answer?"""

    today = "Today"
    later = "Later"


class RunMetrics(AgentComponent):
    """Keeps the metrics of every finished run."""

    seen: Any = None

    async def on_terminate(self, agent, ctx):
        self.seen.append(dict(ctx.state.get("metrics", {})))


class SpendingEngine(EngineComponent):
    """Reports the usage an LLM call would have reported."""

    usage: Any = None

    async def evaluate(self, agent, ctx, inputs, output_group):
        return EvalResult.from_object(
            UsageReply(text="done"), agent=agent, metrics={"usage": self.usage}
        )


class CountingDecider(DecisionProvider):
    """A provider that reports input tokens, like the HTTP decision providers."""

    def __init__(self, inner: FakeDecider, tokens: int, label: str) -> None:
        self.inner = inner
        self.tokens = tokens
        self.label = label
        self.requests = 0

    async def decide_many(self, state, questions, images=()):
        self.requests += 1
        answers = await self.inner.decide_many(state, questions, images)
        # Every answer of one request carries the request's tokens
        return {
            name: replace(answer, input_tokens=self.tokens)
            for name, answer in answers.items()
        }


def test_usage_adds_up_per_model():
    metrics: dict = {}
    record_usage(metrics, "openai/gpt-4.1", 1000, 500)
    record_usage(metrics, "openai/gpt-4.1", 200, 100)
    record_usage(metrics, "azure/decision-1", 300)

    assert metrics["usage"] == {
        "openai/gpt-4.1": {"prompt_tokens": 1200, "completion_tokens": 600},
        "azure/decision-1": {"prompt_tokens": 300, "completion_tokens": 0},
    }


def test_runs_are_priced_from_configured_prices_and_litellm():
    usage = {
        "openai/gpt-4.1": {"prompt_tokens": 1000, "completion_tokens": 500},
        "azure/decision-1": {"prompt_tokens": 2_000_000, "completion_tokens": 0},
    }

    summary = run_metrics(usage, {"azure/decision-1": ModelPrice(input=0.5)})

    assert summary["prompt_tokens"] == 2_001_000
    assert summary["completion_tokens"] == 500
    assert summary["tokens_used"] == 2_001_500
    # LiteLLM prices gpt-4.1 (0.002 + 0.004); the decision model costs 1.0
    assert summary["cost_usd"] == pytest.approx(1.006)
    assert summary["unpriced_models"] == []


def test_a_model_without_a_price_leaves_the_cost_open():
    summary = run_metrics({"local/my-model": {"prompt_tokens": 10}}, {})

    assert summary["tokens_used"] == 10
    assert summary["cost_usd"] is None
    assert summary["unpriced_models"] == ["local/my-model"]


async def test_a_run_reports_its_tokens_and_cost():
    seen: list = []
    flock = Flock(
        no_output=True, model_prices={"azure/gpt-x": (2.0, 8.0)}
    )  # per million tokens
    flock.agent("writer").consumes(UsageTicket).publishes(UsageReply).with_engines(
        SpendingEngine(
            usage={"azure/gpt-x": {"prompt_tokens": 1000, "completion_tokens": 250}}
        )
    ).with_utilities(RunMetrics(seen=seen))

    await flock.publish(UsageTicket(text="hi"))
    await flock.run_until_idle()

    (metrics,) = seen
    assert metrics["tokens_used"] == 1250
    assert metrics["cost_usd"] == pytest.approx(0.004)  # 0.002 + 0.002
    assert metrics["usage"] == {
        "azure/gpt-x": {"prompt_tokens": 1000, "completion_tokens": 250}
    }


async def test_decision_runs_count_each_request_once():
    seen: list = []
    decider = CountingDecider(
        FakeDecider({
            "UsageRoute": {"billing": 0.9, "tech": 0.1},
            "UsageUrgent": {"today": 0.9, "later": 0.1},
        }),
        tokens=120,
        label="azure/decision-1",
    )
    flock = Flock(no_output=True, model_prices={"azure/decision-1": (0.5, 0.0)})
    flock.agent("triage").consumes(UsageTicket).decides(
        UsageRoute, UsageUrgent, model=decider
    ).with_utilities(RunMetrics(seen=seen))

    await flock.publish(UsageTicket(text="charged twice"))
    await flock.run_until_idle()

    (metrics,) = seen
    assert decider.requests == 1  # both questions in one request
    assert metrics["usage"] == {
        "azure/decision-1": {"prompt_tokens": 120, "completion_tokens": 0}
    }
    assert metrics["cost_usd"] == pytest.approx(120 * 0.5 / 1_000_000)


async def test_escalation_tiers_are_counted_too():
    seen: list = []
    fast = CountingDecider(
        FakeDecider({"billing": 0.6, "tech": 0.4}), tokens=100, label="fast"
    )
    strong = CountingDecider(
        FakeDecider({"billing": 0.95, "tech": 0.05}), tokens=400, label="strong"
    )
    flock = Flock(no_output=True)
    flock.agent("triage").consumes(UsageTicket).decides(
        UsageRoute, model=fast, escalate=[strong], threshold=0.8
    ).with_utilities(RunMetrics(seen=seen))

    await flock.publish(UsageTicket(text="crash, then a charge"))
    await flock.run_until_idle()

    (metrics,) = seen
    assert metrics["usage"] == {
        "fast": {"prompt_tokens": 100, "completion_tokens": 0},
        "strong": {"prompt_tokens": 400, "completion_tokens": 0},
    }
    assert metrics["cost_usd"] is None  # no price for these labels
    assert metrics["unpriced_models"] == ["fast", "strong"]


async def test_llm_runs_report_the_usage_dspy_tracks(monkeypatch):
    import dspy

    from flock.engines.dspy_engine import DSPyEngine

    tracking: list = []

    async def answer(self, dspy_mod, program, *, description, payload):
        tracking.append(dspy.settings.track_usage)
        prediction = dspy.Prediction(usage_reply=UsageReply(text="done"))
        prediction.set_lm_usage({
            "openai/gpt-4.1": {"prompt_tokens": 1000, "completion_tokens": 500}
        })
        return prediction

    monkeypatch.setattr(
        "flock.engines.dspy.streaming_executor.DSPyStreamingExecutor.execute_standard",
        answer,
    )
    seen: list = []
    flock = Flock("openai/gpt-4.1", no_output=True)
    flock.agent("writer").consumes(UsageTicket).publishes(UsageReply).with_engines(
        DSPyEngine(model="openai/gpt-4.1", stream=False)
    ).with_utilities(RunMetrics(seen=seen))

    await flock.publish(UsageTicket(text="hi"))
    await flock.run_until_idle()

    assert tracking == [True]
    (metrics,) = seen
    assert metrics["usage"] == {
        "openai/gpt-4.1": {"prompt_tokens": 1000, "completion_tokens": 500}
    }
    assert metrics["cost_usd"] == pytest.approx(0.006)  # LiteLLM's gpt-4.1 prices


async def test_a_run_puts_its_tokens_and_cost_on_its_trace(monkeypatch):
    from opentelemetry import trace

    attributes: dict = {}

    class Span(trace.NonRecordingSpan):
        """A span like any other, that keeps the attributes set on it."""

        def set_attribute(self, key, value):
            attributes[key] = value

    span = Span(trace.INVALID_SPAN_CONTEXT)
    monkeypatch.setattr("flock.core.agent.trace.get_current_span", lambda *a: span)
    flock = Flock(no_output=True, model_prices={"azure/gpt-x": (2.0, 8.0)})
    flock.agent("writer").consumes(UsageTicket).publishes(UsageReply).with_engines(
        SpendingEngine(
            usage={"azure/gpt-x": {"prompt_tokens": 1000, "completion_tokens": 250}}
        )
    )

    await flock.publish(UsageTicket(text="hi"))
    await flock.run_until_idle()

    assert attributes["flock.usage.tokens"] == 1250
    assert attributes["flock.usage.cost_usd"] == pytest.approx(0.004)


async def test_the_runs_endpoint_reports_each_run_with_its_tokens_and_cost():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from flock.api.collector import DashboardEventCollector
    from flock.components.server.traces.trace_component import TracingComponent

    flock = Flock(no_output=True, model_prices={"azure/gpt-x": (2.0, 8.0)})
    flock.agent("writer").consumes(UsageTicket).publishes(UsageReply).with_engines(
        SpendingEngine(
            usage={"azure/gpt-x": {"prompt_tokens": 1000, "completion_tokens": 250}}
        )
    )
    collector = DashboardEventCollector(store=flock.store)
    flock._dashboard_collector = collector  # as serve(dashboard=True) does
    for agent in flock.agents:
        agent._add_utilities([collector])
    app = FastAPI()
    TracingComponent().register_routes(app, flock)

    await flock.publish(UsageTicket(text="hi"))
    await flock.run_until_idle()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        data = (await client.get("/api/plugin/agents/writer/runs")).json()

    assert data["total"] == 1
    (run,) = data["runs"]
    assert run["status"] == "completed"
    assert run["start_time"] and run["end_time"]
    assert run["duration_ms"] >= 0
    assert run["metrics"]["tokens_used"] == 1250
    assert run["metrics"]["cost_usd"] == pytest.approx(0.004)
    assert run["metrics"]["artifacts_produced"] == 1
