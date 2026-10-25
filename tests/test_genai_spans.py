"""A span per model call in the OpenTelemetry GenAI semantic conventions (#680)."""

from __future__ import annotations

import json

import dspy
import pytest
from litellm import ModelResponse
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from pydantic import BaseModel

from flock.core import Flock
from flock.logging import genai_spans
from flock.logging.genai_spans import (
    GenAISpans,
    input_messages,
    output_messages,
    provider_name,
)
from flock.logging.trace_and_logged import _trace_filter_config
from flock.registry import flock_type


@pytest.fixture
def spans(monkeypatch):
    """GenAI spans go to an in-memory exporter of their own provider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(genai_spans, "tracer", provider.get_tracer("test"))
    monkeypatch.delenv(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", raising=False
    )
    yield exporter
    provider.shutdown()


@pytest.fixture
def trace_filter():
    """Restore the global trace filter after a test changes it."""
    ignored = set(_trace_filter_config.ignore_operations)
    cap = _trace_filter_config.max_attribute_bytes
    yield _trace_filter_config
    _trace_filter_config.ignore_operations = ignored
    _trace_filter_config.max_attribute_bytes = cap


class FakeLM(dspy.BaseLM):
    """An LM that answers without a network call, with token usage."""

    def __init__(self, model: str = "azure/gpt-x", fail: bool = False):
        super().__init__(model=model, temperature=0.2, max_tokens=300)
        self.fail = fail

    def _response(self) -> ModelResponse:
        if self.fail:
            raise RuntimeError("rate limited")
        return ModelResponse(
            id="resp-1",
            model="gpt-x-2026-10-01",
            choices=[
                {
                    "message": {"role": "assistant", "content": "hello"},
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
        )

    def forward(self, prompt=None, messages=None, **kwargs):
        return self._response()

    async def aforward(self, prompt=None, messages=None, **kwargs):
        return self._response()


MESSAGES = [{"role": "user", "content": "Say hello"}]


def test_a_model_call_becomes_a_chat_span_with_model_tokens_and_agent(spans):
    with dspy.context(callbacks=[GenAISpans("writer")]):
        FakeLM()(messages=MESSAGES)

    (span,) = spans.get_finished_spans()
    assert span.name == "LM.chat"
    assert span.kind == SpanKind.CLIENT
    assert dict(span.attributes) == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "azure.ai.openai",
        "gen_ai.request.model": "azure/gpt-x",
        "gen_ai.agent.name": "writer",
        "gen_ai.request.temperature": 0.2,
        "gen_ai.request.max_tokens": 300,
        "gen_ai.response.model": "gpt-x-2026-10-01",
        "gen_ai.usage.input_tokens": 12,
        "gen_ai.usage.output_tokens": 3,
        "gen_ai.response.id": "resp-1",
        "gen_ai.response.finish_reasons": ("stop",),
    }


async def test_async_calls_get_a_span_under_the_current_span(spans):
    parent_tracer = genai_spans.tracer
    with parent_tracer.start_as_current_span("DSPyEngine.evaluate") as parent:
        with dspy.context(callbacks=[GenAISpans("writer")]):
            await FakeLM().acall(messages=MESSAGES)

    chat = next(s for s in spans.get_finished_spans() if s.name == "LM.chat")
    assert chat.parent.span_id == parent.get_span_context().span_id
    assert chat.attributes["gen_ai.usage.output_tokens"] == 3


def test_message_content_only_on_request(spans, monkeypatch):
    with dspy.context(callbacks=[GenAISpans("writer")]):
        FakeLM()(messages=MESSAGES)
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
    with dspy.context(callbacks=[GenAISpans("writer")]):
        FakeLM()(messages=MESSAGES)

    without, with_content = spans.get_finished_spans()
    assert "gen_ai.input.messages" not in without.attributes
    assert json.loads(with_content.attributes["gen_ai.input.messages"]) == [
        {"role": "user", "parts": [{"type": "text", "content": "Say hello"}]}
    ]
    assert json.loads(with_content.attributes["gen_ai.output.messages"]) == [
        {
            "role": "assistant",
            "parts": [{"type": "text", "content": "hello"}],
            "finish_reason": "stop",
        }
    ]


def test_messages_follow_the_conventions_schema():
    messages = [
        {"role": "system", "content": "Be brief."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is on it?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/a.png"},
                },
            ],
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {"name": "lookup", "arguments": '{"q": "a"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "a cat"},
    ]

    assert input_messages(messages) == [
        {"role": "system", "parts": [{"type": "text", "content": "Be brief."}]},
        {
            "role": "user",
            "parts": [
                {"type": "text", "content": "What is on it?"},
                {
                    "type": "uri",
                    "modality": "image",
                    "uri": "https://example.com/a.png",
                },
            ],
        },
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool_call",
                    "id": "call-1",
                    "name": "lookup",
                    "arguments": '{"q": "a"}',
                }
            ],
        },
        {
            "role": "tool",
            "parts": [
                {"type": "tool_call_response", "id": "call-1", "response": "a cat"}
            ],
        },
    ]
    assert input_messages(None, "Say hi") == [
        {"role": "user", "parts": [{"type": "text", "content": "Say hi"}]}
    ]
    outputs = [{"text": "Done.", "reasoning_content": "Short."}]
    assert output_messages(outputs) == [
        {
            "role": "assistant",
            "parts": [
                {"type": "reasoning", "content": "Short."},
                {"type": "text", "content": "Done."},
            ],
        }
    ]


def test_responses_api_usage_is_read_too(spans):
    lm = type(
        "ResponsesLM", (), {"model": "openai/gpt-x", "kwargs": {}, "history": []}
    )()
    outputs = [{"text": "hi"}]
    callback = GenAISpans("writer")

    callback.on_lm_start("call-1", lm, {"messages": MESSAGES})
    lm.history.append({
        "outputs": outputs,
        "usage": {"input_tokens": 9, "output_tokens": 4},
    })
    callback.on_lm_end("call-1", outputs)

    (span,) = spans.get_finished_spans()
    assert span.attributes["gen_ai.usage.input_tokens"] == 9
    assert span.attributes["gen_ai.usage.output_tokens"] == 4


def test_message_content_is_capped(spans, monkeypatch, trace_filter):
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
    trace_filter.max_attribute_bytes = 120
    with dspy.context(callbacks=[GenAISpans("writer")]):
        FakeLM()(messages=[{"role": "user", "content": "x" * 1000}])

    (span,) = spans.get_finished_spans()
    stored = span.attributes["gen_ai.input.messages"]
    assert len(stored.encode()) <= 120
    assert json.loads(stored)["truncated"] is True


def test_a_failed_call_ends_its_span_as_an_error(spans):
    with dspy.context(callbacks=[GenAISpans("writer")]), pytest.raises(RuntimeError):
        FakeLM(fail=True)(messages=MESSAGES)

    (span,) = spans.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["error.type"] == "RuntimeError"
    assert "gen_ai.usage.input_tokens" not in span.attributes
    assert [event.name for event in span.events] == ["exception"]


def test_the_trace_filter_can_switch_the_spans_off(spans, trace_filter):
    trace_filter.ignore_operations = {"LM.chat"}
    with dspy.context(callbacks=[GenAISpans("writer")]):
        FakeLM()(messages=MESSAGES)

    assert spans.get_finished_spans() == ()


def test_without_history_the_span_has_no_tokens(spans):
    with dspy.context(callbacks=[GenAISpans("writer")], disable_history=True):
        FakeLM()(messages=MESSAGES)

    (span,) = spans.get_finished_spans()
    assert span.attributes["gen_ai.request.model"] == "azure/gpt-x"
    assert "gen_ai.usage.input_tokens" not in span.attributes


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("azure/gpt-x", "azure.ai.openai"),
        ("openai/gpt-4.1", "openai"),
        ("anthropic/claude-x", "anthropic"),
        ("ollama/llama3", "ollama"),
        ("gpt-4.1", "openai"),
    ],
)
def test_provider_names_follow_the_conventions(model, provider):
    assert provider_name(model) == provider


def test_the_engine_adds_the_callback_only_while_auto_tracing(monkeypatch):
    from flock.engines.dspy_engine import DSPyEngine
    from flock.logging import auto_trace

    mine = object()
    monkeypatch.setattr(auto_trace, "ENABLE_AUTO_TRACE", True)
    with dspy.context(callbacks=[mine]):
        on = DSPyEngine._lm_callbacks(dspy, "writer")
    monkeypatch.setattr(auto_trace, "ENABLE_AUTO_TRACE", False)
    with dspy.context(callbacks=[mine]):
        off = DSPyEngine._lm_callbacks(dspy, "writer")

    assert on[0] is mine
    assert isinstance(on[1], GenAISpans)
    assert on[1].agent_name == "writer"
    assert off == [mine]


@flock_type
class SpanTicket(BaseModel):
    text: str


@flock_type
class SpanReply(BaseModel):
    text: str


async def test_an_agent_run_records_a_span_for_its_model_call(spans, monkeypatch):
    from flock.engines.dspy_engine import DSPyEngine
    from flock.logging import auto_trace

    monkeypatch.setattr(auto_trace, "ENABLE_AUTO_TRACE", True)

    async def answer(self, dspy_mod, program, *, description, payload):
        # The engine's program would call its LM here; the fake one stands in
        await FakeLM().acall(messages=MESSAGES)
        return dspy.Prediction(span_reply=SpanReply(text="hello"))

    monkeypatch.setattr(
        "flock.engines.dspy.streaming_executor.DSPyStreamingExecutor.execute_standard",
        answer,
    )
    flock = Flock("azure/gpt-x", no_output=True)
    flock.agent("writer").consumes(SpanTicket).publishes(SpanReply).with_engines(
        DSPyEngine(model="azure/gpt-x", stream=False)
    )

    await flock.publish(SpanTicket(text="hi"))
    await flock.run_until_idle()

    (span,) = [s for s in spans.get_finished_spans() if s.name == "LM.chat"]
    assert span.attributes["gen_ai.agent.name"] == "writer"
    assert span.attributes["gen_ai.usage.input_tokens"] == 12


def test_responses_api_tool_calls_keep_their_call_id_name_and_arguments():
    flat = {
        "id": "fc-1",
        "call_id": "call-9",
        "name": "lookup",
        "arguments": '{"q": "a"}',
    }

    assert output_messages([{"text": None, "tool_calls": [flat]}]) == [
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool_call",
                    "id": "call-9",
                    "name": "lookup",
                    "arguments": '{"q": "a"}',
                }
            ],
        }
    ]


def test_an_agent_invoked_inside_another_records_its_calls_once(spans, monkeypatch):
    from flock.engines.dspy_engine import DSPyEngine
    from flock.logging import auto_trace

    monkeypatch.setattr(auto_trace, "ENABLE_AUTO_TRACE", True)
    mine = object()
    with dspy.context(callbacks=[*DSPyEngine._lm_callbacks(dspy, "outer"), mine]):
        FakeLM()(messages=MESSAGES)
        inner = DSPyEngine._lm_callbacks(dspy, "inner")
        with dspy.context(callbacks=inner):
            FakeLM()(messages=MESSAGES)

    assert next(c for c in inner if isinstance(c, GenAISpans)).agent_name == "inner"
    assert sum(isinstance(c, GenAISpans) for c in inner) == 1
    assert mine in inner
    agents = [s.attributes["gen_ai.agent.name"] for s in spans.get_finished_spans()]
    assert agents == ["outer", "inner"]
