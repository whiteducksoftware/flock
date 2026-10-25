"""A run's correlation on its spans, for sessions and threads in observability tools (#681)."""

from __future__ import annotations

import inspect

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel

from flock.core import Flock
from flock.logging import trace_and_logged
from flock.logging.trace_and_logged import (
    _result_correlation,
    run_attributes,
    traced_and_logged,
)
from flock.registry import flock_type


@pytest.fixture
def spans(monkeypatch):
    """Flock's spans go to an in-memory exporter of their own provider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace_and_logged, "tracer", provider.get_tracer("test"))
    yield exporter
    provider.shutdown()


@flock_type
class SessionNote(BaseModel):
    text: str


class Ctx:
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        self.task_id = "task-1"


class Run:
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id


class Worker:
    name = "worker"

    def work(self, ctx, result=None):
        return result

    async def awork(self, ctx=None, result=None):
        return result


def run_of(span) -> tuple:
    return tuple(
        span.attributes.get(key)
        for key in ("correlation_id", "session.id", "gen_ai.conversation.id")
    )


def test_run_attributes_name_the_run_for_both_tools():
    assert run_attributes("run-1") == {
        "session.id": "run-1",
        "gen_ai.conversation.id": "run-1",
    }


def test_a_span_that_knows_its_run_carries_it(spans):
    traced_and_logged(Worker.work)(Worker(), ctx=Ctx("run-1"))

    (span,) = spans.get_finished_spans()
    assert run_of(span) == ("run-1", "run-1", "run-1")


async def test_a_span_learns_its_run_from_what_it_returns(spans):
    await traced_and_logged(Worker.awork)(Worker(), result=[Run("run-2"), Run("run-2")])

    (span,) = spans.get_finished_spans()
    assert run_of(span) == ("run-2", "run-2", "run-2")


def test_the_context_wins_over_the_result(spans):
    traced_and_logged(Worker.work)(Worker(), ctx=Ctx("run-1"), result=Run("run-2"))

    (span,) = spans.get_finished_spans()
    assert run_of(span) == ("run-1", "run-1", "run-1")


def test_only_one_shared_correlation_counts():
    assert _result_correlation(Run("r1")) == "r1"
    assert _result_correlation([Run("r1"), Run("r1")]) == "r1"
    assert _result_correlation([Run("r1"), Run("r2")]) is None
    assert _result_correlation("text") is None
    assert _result_correlation(None) is None


async def test_publish_puts_the_run_it_creates_on_its_span(spans):
    flock = Flock(no_output=True)
    publish = traced_and_logged(inspect.unwrap(Flock.publish))

    artifact = await publish(flock, SessionNote(text="hi"))

    (span,) = [s for s in spans.get_finished_spans() if s.name == "Flock.publish"]
    run = str(artifact.correlation_id)
    assert run_of(span) == (run, run, run)


def test_model_call_spans_join_their_run(monkeypatch):
    import dspy

    from flock.logging import genai_spans
    from tests.test_genai_spans import MESSAGES, FakeLM

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(genai_spans, "tracer", provider.get_tracer("test"))

    with dspy.context(callbacks=[genai_spans.GenAISpans("writer", "run-3")]):
        FakeLM()(messages=MESSAGES)

    (span,) = exporter.get_finished_spans()
    assert run_of(span) == ("run-3", "run-3", "run-3")
