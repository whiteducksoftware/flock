import asyncio
import sys
from collections import OrderedDict, defaultdict
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.dashboard.events import StreamingOutputEvent
from flock.engines.dspy.streaming_executor import DSPyStreamingExecutor
from flock.engines.streaming.sinks import RichSink, WebSocketSink


def _make_executor() -> DSPyStreamingExecutor:
    return DSPyStreamingExecutor(
        status_output_field="_status",
        stream_vertical_overflow="crop",
        theme="afterglow",
        no_output=True,
    )


def test_payload_kwargs_variants() -> None:
    executor = _make_executor()

    rich_payload = {"description": "Describe", "task": "do something"}
    assert executor._payload_kwargs(payload=rich_payload, description="ignored") is rich_payload

    legacy_payload = {"input": "story", "context": ["a"]}
    result = executor._payload_kwargs(payload=legacy_payload, description="desc")
    assert result == {"description": "desc", "input": "story", "context": ["a"]}

    fallback = executor._payload_kwargs(payload="raw", description="desc")
    assert fallback == {"description": "desc", "input": "raw", "context": []}


def test_artifact_type_label_deduplicates() -> None:
    executor = _make_executor()

    spec_a = SimpleNamespace(type_name="Report")
    spec_b = SimpleNamespace(type_name="Summary")
    spec_dup = SimpleNamespace(type_name="Report")
    output = SimpleNamespace(spec=spec_a)
    output_b = SimpleNamespace(spec=spec_b)
    output_dup = SimpleNamespace(spec=spec_dup)

    agent = SimpleNamespace(outputs=[output, output_b, output_dup])

    assert executor._artifact_type_label(agent, output_group=None) == "Report, Summary"
    assert executor._artifact_type_label(SimpleNamespace(outputs=[]), None) == "output"


def test_normalize_value_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = _make_executor()

    class FakePrediction:
        pass

    class FakeStatus:
        def __init__(self, message: str) -> None:
            self.message = message

    class FakeStream:
        def __init__(self, chunk: str, signature_field_name: str | None = None) -> None:
            self.chunk = chunk
            self.signature_field_name = signature_field_name

    class FakeModelResponse:
        def __init__(self, token: str, signature_field_name: str | None = None) -> None:
            delta = SimpleNamespace(content=token)
            choice = SimpleNamespace(delta=delta)
            self.choices = [choice]
            self.signature_field_name = signature_field_name

    fake_streaming = SimpleNamespace(
        StreamListener=None,
        StatusMessage=FakeStatus,
        StreamResponse=FakeStream,
    )
    fake_dspy = SimpleNamespace(streaming=fake_streaming, Prediction=FakePrediction)

    fake_litellm = ModuleType("litellm")
    fake_litellm.ModelResponseStream = FakeModelResponse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    kind, text, field, final = executor._normalize_value(
        FakeStatus("Loading"), fake_dspy
    )
    assert (kind, text, field, final) == ("status", "Loading", None, None)

    kind, text, field, final = executor._normalize_value(
        FakeStream("chunk", signature_field_name="output"), fake_dspy
    )
    assert (kind, text, field, final) == ("token", "chunk", "output", None)

    kind, text, field, final = executor._normalize_value(
        FakeModelResponse("model-token", signature_field_name="output"), fake_dspy
    )
    assert (kind, text, field, final) == ("token", "model-token", "output", None)

    prediction = FakePrediction()
    kind, text, field, final = executor._normalize_value(prediction, fake_dspy)
    assert (kind, text, field, final) == ("prediction", None, None, prediction)

    kind, text, field, final = executor._normalize_value(object(), fake_dspy)
    assert (kind, text, field, final) == ("unknown", None, None, None)


@pytest.mark.asyncio
async def test_websocket_sink_emits_events_in_order() -> None:
    executor = _make_executor()

    correlation_id = uuid4()
    ctx = SimpleNamespace(correlation_id=correlation_id, task_id="task-1")
    agent = SimpleNamespace(name="agent-1")
    artifact_id = uuid4()

    events: list[StreamingOutputEvent] = []

    async def broadcast(event: StreamingOutputEvent) -> None:
        events.append(event)

    def event_factory(output_type: str, content: str, sequence: int, is_final: bool) -> StreamingOutputEvent:
        return executor._build_event(  # type: ignore[attr-defined]
            ctx=ctx,
            agent=agent,
            artifact_id=artifact_id,
            artifact_type="Report",
            output_type=output_type,
            content=content,
            sequence=sequence,
            is_final=is_final,
        )

    sink = WebSocketSink(ws_broadcast=broadcast, event_factory=event_factory)

    await sink.on_status("Processing")
    await sink.on_token("token-1", None)
    await sink.on_final(object(), tokens_emitted=1)
    await sink.flush()

    assert [e.sequence for e in events] == [0, 1, 2, 3]
    assert events[0].content == "Processing\n"
    assert events[1].output_type == "llm_token" and events[1].content == "token-1"
    assert events[2].content == "\nAmount of output tokens: 1"
    assert events[2].is_final is True
    assert events[3].content == "--- End of output ---"
    assert events[3].is_final is True
    assert all(e.agent_name == "agent-1" for e in events)
    assert all(e.artifact_type == "Report" for e in events)


class DummyModel(BaseModel):
    foo: str


class DummyPrediction:
    def __init__(self, output: str, detail: DummyModel) -> None:
        self.output = output
        self.detail = detail


@pytest.mark.asyncio
async def test_rich_sink_updates_display_and_finalizes() -> None:
    display_data = OrderedDict(
        [
            ("id", "temp"),
            ("type", "Report"),
            ("payload", OrderedDict({"output": "", "detail": ""})),
            ("produced_by", "agent"),
            ("correlation_id", None),
            ("partition_key", None),
            ("tags", "set()"),
            ("visibility", OrderedDict([("kind", "Public")])),
            ("created_at", "streaming..."),
            ("version", 1),
            ("status", "_status"),
        ]
    )
    stream_buffers = defaultdict(list)

    refresh_calls: list[int] = []

    def refresh() -> None:
        refresh_calls.append(1)

    sink = RichSink(
        display_data=display_data,
        stream_buffers=stream_buffers,
        status_field="_status",
        signature_order=["description", "output", "detail"],
        formatter=None,
        theme_dict=None,
        styles=None,
        agent_label=None,
        refresh_panel=refresh,
        timestamp_factory=lambda: "2025-10-19T00:00:00Z",
    )

    await sink.on_status("Booting")
    assert display_data["status"] == "Booting\n"

    await sink.on_token("hello", "output")
    assert display_data["payload"]["_streaming"] == "hello"

    prediction = DummyPrediction("final", DummyModel(foo="bar"))
    await sink.on_final(prediction, tokens_emitted=1)
    await sink.flush()

    assert display_data["payload"]["output"] == "final"
    assert display_data["payload"]["detail"] == {"foo": "bar"}
    assert display_data["created_at"] == "2025-10-19T00:00:00Z"
    assert "status" not in display_data
    assert sink.final_display_data[1] is display_data
    assert refresh_calls  # at least one refresh was triggered
