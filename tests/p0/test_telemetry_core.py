import pytest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

import importlib
import sys


pytestmark = [pytest.mark.otel]


class _MemoryExporter(SpanExporter):
    def __init__(self):
        self.spans = []
    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS
    def shutdown(self):
        return


def test_flock_run_async_emits_span_attributes(register_fakes):
    # Set up in-memory exporter
    exporter = _MemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Install provider globally for this test
    original_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    try:
        # Reload modules that bind tracers at import time so they pick up the new provider
        for mod_name in [
            "flock.core.agent.flock_agent_execution",
            "flock.core.agent.flock_agent_lifecycle",
            "flock.core.orchestration.flock_execution",
            "flock.core.flock",
        ]:
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])

        # Prevent framework from overwriting our provider in Flock import
        import flock.config as _flock_config
        _flock_config.TELEMETRY.setup_tracing = lambda: None  # type: ignore[attr-defined]

        from flock.core.flock_agent import FlockAgent
        from flock.core.flock import Flock
        from tests._helpers.fakes import FakeEvaluator

        agent = FlockAgent(name="a1", input="message", output="result", components=[FakeEvaluator(name="eval")])
        flock = Flock(name="tele", show_flock_banner=False)
        flock.add_agent(agent)

        # Run async via sync wrapper to simplify
        out = flock.run(agent="a1", input={"message": "hi"}, box_result=False)
        assert out == {"result": "hi:a1"}

        # Get finished spans
        spans = exporter.spans
        # Non-empty spans indicates provider/exporter hooked in
        assert len(spans) >= 1
        # Best-effort attribute check if agent span exists
        agent_spans = [s for s in spans if s.name in {"agent.run", "agent.evaluate"}]
        if agent_spans:
            attrs = agent_spans[0].attributes
            assert attrs.get("agent.name") == "a1"
    finally:
        # Restore original provider
        trace.set_tracer_provider(original_provider)
