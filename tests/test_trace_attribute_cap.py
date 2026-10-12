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
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 100)
    value = json.dumps({"text": "x" * 500})

    cut = json.loads(capped(value))

    assert cut["truncated"] is True
    assert cut["bytes"] == len(value.encode())
    assert value.startswith(cut["preview"])
    assert len(cut["preview"].encode()) <= 100


def test_a_value_under_the_cap_stays_as_it_is(monkeypatch):
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 100)

    assert capped('{"a": 1}') == '{"a": 1}'


def test_the_cut_never_splits_a_character(monkeypatch):
    monkeypatch.setattr(_trace_filter_config, "max_attribute_bytes", 7)

    cut = json.loads(capped("ä" * 20))  # two bytes each

    assert cut["preview"] == "äää"


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


def test_artifacts_are_traced_as_their_type_and_id():
    artifact = Artifact(
        type="app.Reply", payload={"text": "x" * 10_000}, produced_by="support"
    )

    assert _serialize_value(artifact) == {
        "artifact": "app.Reply",
        "id": str(artifact.id),
    }
    assert _serialize_value([artifact]) == [
        {"artifact": "app.Reply", "id": str(artifact.id)}
    ]


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
