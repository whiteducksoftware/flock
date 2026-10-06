"""End-to-end tracing export: real exporters, no mocks.

``FLOCK_AUTO_TRACE`` configures OpenTelemetry at import time and the global
tracer provider can be set only once per process, so the workflow runs in a
fresh interpreter. The test hosts a real OTLP/gRPC receiver - the path Jaeger,
Grafana and Azure Monitor collectors use now that the legacy Jaeger exporter
packages are gone - and checks that the same workflow reaches OTLP, the DuckDB
trace store and the log lines' trace ids.
"""

import os
import re
import subprocess
import sys
import textwrap
import threading
from concurrent import futures

import duckdb
import grpc
import pytest
from opentelemetry.proto.collector.trace.v1 import (
    trace_service_pb2,
    trace_service_pb2_grpc,
)


WORKFLOW_SCRIPT = textwrap.dedent(
    """
    import asyncio

    from pydantic import BaseModel

    from flock import Flock, flock_type
    from flock.components.agent import EngineComponent
    from flock.logging.logging import get_logger
    from flock.utils.runtime import EvalResult

    log = get_logger("tracing_e2e")


    @flock_type
    class E2EQuestion(BaseModel):
        text: str


    @flock_type
    class E2EAnswer(BaseModel):
        text: str


    class EchoEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            question = E2EQuestion(**inputs.artifacts[0].payload)
            return EvalResult.from_object(E2EAnswer(text=question.text.upper()), agent=agent)


    async def main():
        flock = Flock(no_output=True)
        flock.agent("echo").consumes(E2EQuestion).publishes(E2EAnswer).with_engines(EchoEngine())
        async with flock.traced_run("e2e_tracing_workflow"):
            await flock.publish(E2EQuestion(text="is tracing alive?"))
            await flock.run_until_idle()
            log.warning("E2E_LOG_INSIDE_WORKFLOW")


    asyncio.run(main())
    """
)


class _TraceCollector(trace_service_pb2_grpc.TraceServiceServicer):
    """Minimal OTLP/gRPC trace receiver."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, str, str]] = []  # (service, name, trace_id)
        self._lock = threading.Lock()

    def Export(self, request, context):  # noqa: N802 - gRPC method name
        with self._lock:
            for resource_spans in request.resource_spans:
                service = next(
                    (
                        attr.value.string_value
                        for attr in resource_spans.resource.attributes
                        if attr.key == "service.name"
                    ),
                    "",
                )
                for scope_spans in resource_spans.scope_spans:
                    for span in scope_spans.spans:
                        self.spans.append((service, span.name, span.trace_id.hex()))
        return trace_service_pb2.ExportTraceServiceResponse()


@pytest.fixture
def otlp_collector():
    collector = _TraceCollector()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(collector, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield collector, f"http://127.0.0.1:{port}"
    finally:
        server.stop(grace=None)


def test_auto_trace_exports_workflow_to_otlp_duckdb_and_logs(otlp_collector, tmp_path):
    collector, endpoint = otlp_collector
    (tmp_path / "workflow.py").write_text(WORKFLOW_SCRIPT)
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "FLOCK_DISABLE_TELEMETRY_AUTOSETUP"
    }
    env.update(
        FLOCK_AUTO_TRACE="true",
        FLOCK_TRACE_FILE="true",
        OTEL_EXPORTER_OTLP_ENDPOINT=endpoint,
        NO_COLOR="1",
    )

    completed = subprocess.run(
        [sys.executable, "workflow.py"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output

    # 1. OTLP: the workflow root span and the agent's work arrive over the wire.
    names = {name for _, name, _ in collector.spans}
    assert "e2e_tracing_workflow" in names, sorted(names)
    assert "Flock.publish" in names, sorted(names)
    assert any(name.startswith("Agent.") for name in names), sorted(names)
    assert {service for service, _, _ in collector.spans} == {"flock-auto-trace"}
    workflow_trace_id = next(
        trace_id
        for _, name, trace_id in collector.spans
        if name == "e2e_tracing_workflow"
    )

    # 2. DuckDB: the same spans, same trace, stored locally.
    with duckdb.connect(
        str(tmp_path / ".flock" / "traces.duckdb"), read_only=True
    ) as db:
        stored = {
            row[0]
            for row in db.execute(
                "SELECT name FROM spans WHERE trace_id = ?", [workflow_trace_id]
            ).fetchall()
        }
    assert {"e2e_tracing_workflow", "Flock.publish"} <= stored, sorted(stored)

    # 3. Logging: a log line inside the workflow carries that trace id.
    log_line = next(
        (line for line in output.splitlines() if "E2E_LOG_INSIDE_WORKFLOW" in line),
        None,
    )
    assert log_line is not None, output
    assert re.search(rf"trace_id: {workflow_trace_id}\b", log_line), log_line
