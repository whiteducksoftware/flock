"""Span attributes stay small: a cap per value, artifacts as type and ID (#601)."""

import json

import pytest

from flock.core.artifacts import Artifact
from flock.logging import auto_trace
from flock.logging.trace_and_logged import (
    _extract_span_attributes,
    _serialize_value,
    _trace_filter_config,
    capped,
)


def test_a_value_over_the_cap_is_cut_and_says_how_large_it_was(monkeypatch):
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 200)
    value = json.dumps({"text": "x" * 500})

    attribute = capped(value)
    cut = json.loads(attribute)

    assert cut["truncated"] is True
    assert cut["bytes"] == len(value.encode())
    assert value.startswith(cut["preview"])
    assert len(attribute.encode()) <= 200


def test_a_value_under_the_cap_stays_as_it_is(monkeypatch):
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 100)

    assert capped('{"a": 1}') == '{"a": 1}'


@pytest.mark.parametrize(
    "text",
    ['"' * 5000, "\\\\" * 3000, "ä" * 4000, "🦆" * 2000],
    ids=["quotes", "backslashes", "umlauts", "emoji"],
)
def test_the_whole_attribute_stays_within_the_cap(monkeypatch, text):
    """Escaping and the marker count too; the cut never splits a character."""
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 4096)
    value = json.dumps(text) if text.startswith('"') else text

    attribute = capped(value)
    cut = json.loads(attribute)

    assert len(attribute.encode()) <= 4096
    assert value.startswith(cut["preview"])
    assert "\ufffd" not in cut["preview"]
    # Most of the room holds the value
    assert len(json.dumps(cut["preview"], ensure_ascii=False).encode()) > 4096 * 0.9


def test_no_cap_with_zero(monkeypatch):
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 0)
    value = "x" * 100_000

    assert capped(value) == value


@pytest.mark.parametrize(
    ("value", "cap"),
    [("8192", 8192), ("0", 0), ("", 4096), ("lots", 4096), ("-5", 4096)],
)
def test_the_cap_comes_from_the_environment(monkeypatch, value, cap):
    monkeypatch.setenv("FLOCK_TRACE_MAX_ATTRIBUTE_BYTES", value)

    assert auto_trace._max_attribute_bytes_from_env() == cap


def test_artifacts_are_traced_as_their_type_id_producer_and_payload():
    """Compact, and still readable for artifacts that never reach the blackboard
    (invoke(..., publish_outputs=False), outputs a filter dropped)."""
    artifact = Artifact(type="app.Reply", payload={"text": "hi"}, produced_by="support")
    compact = {
        "artifact": "app.Reply",
        "id": str(artifact.id),
        "produced_by": "support",
        "payload": {"text": "hi"},
    }

    assert _serialize_value(artifact) == compact
    assert _serialize_value([artifact]) == [compact]


def test_inputs_are_capped(monkeypatch):
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 50)

    def work(text):
        return text

    attributes, _ = _extract_span_attributes(work, ("y" * 1000,), {})

    assert json.loads(attributes["input.text"])["truncated"] is True


async def test_outputs_are_capped(monkeypatch):
    from flock.logging import trace_and_logged
    from flock.logging.trace_and_logged import traced_and_logged

    recorded: dict[str, object] = {}

    class Span:
        def set_attribute(self, key, value):
            recorded[key] = value

        def set_status(self, status):
            pass

    class Tracer:
        def start_as_current_span(self, name):
            import contextlib

            return contextlib.nullcontext(Span())

    monkeypatch.setattr(trace_and_logged, "tracer", Tracer())
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 50)
    monkeypatch.setattr(_trace_filter_config, "services", None)
    monkeypatch.setattr(_trace_filter_config, "ignore_operations", set())

    @traced_and_logged
    async def write():
        return "z" * 1000

    assert await write() == "z" * 1000
    assert json.loads(recorded["output.value"])["truncated"] is True
