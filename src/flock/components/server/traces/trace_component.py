"""Trace-relate API routes."""

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from fastapi import HTTPException, Query
from pydantic import Field

from flock.api.thumbnails import compact, image_summaries
from flock.api.websocket import WebSocketManager
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.core.store import FilterConfig
from flock.logging.logging import get_logger


logger = get_logger(__name__)


# Queries as literals: the columns of _span_from_row, in its order
_ALL_SPANS_SQL = """
    SELECT trace_id, span_id, parent_id, name, service, operation,
           kind, start_time, end_time, duration_ms,
           status_code, status_description,
           attributes, events, links, resource
    FROM spans
    ORDER BY start_time DESC
"""

# An agent's latest runs (Agent.execute by agent.name) and the spans below them
_AGENT_SPANS_SQL = """
    WITH RECURSIVE latest AS (
        SELECT trace_id, span_id FROM spans
        WHERE name = 'Agent.execute'
          AND json_extract_string(attributes, '$."agent.name"') = ?
        ORDER BY start_time DESC
        LIMIT ?
    ),
    tree(trace_id, span_id) AS (
        SELECT trace_id, span_id FROM latest
        UNION
        SELECT spans.trace_id, spans.span_id
        FROM spans JOIN tree
          ON spans.trace_id = tree.trace_id
         AND spans.parent_id = tree.span_id
    )
    SELECT trace_id, span_id, parent_id, name, service, operation,
           kind, start_time, end_time, duration_ms,
           status_code, status_description,
           attributes, events, links, resource
    FROM spans
    WHERE (trace_id, span_id) IN (SELECT trace_id, span_id FROM tree)
    ORDER BY start_time
"""


def _span_from_row(row: Sequence[Any]) -> dict[str, Any]:
    """A span in OTEL format from a row of ``_ALL_SPANS_SQL`` or ``_AGENT_SPANS_SQL``."""
    span = {
        "name": row[3],
        "context": {
            "trace_id": row[0],
            "span_id": row[1],
            "trace_flags": 0,
            "trace_state": "",
        },
        "kind": row[6],
        "start_time": row[7],
        "end_time": row[8],
        "status": {"status_code": row[10], "description": row[11]},
        "attributes": json.loads(row[12]) if row[12] else {},
        "events": json.loads(row[13]) if row[13] else [],
        "links": json.loads(row[14]) if row[14] else [],
        "resource": json.loads(row[15]) if row[15] else {},
    }
    if row[2]:
        span["parent_id"] = row[2]
    return span


class TracingComponentConfig(ServerComponentConfig):
    """Configuration class for ThemesService."""

    prefix: str = Field(
        default="/api/plugin/",
        description="Optional prefix for the routes for tracing. (Defaults to '/api/')",
    )
    tags: list[str] = Field(
        default=["Tracing"],
        description="OpenAPI tags for grouping the API-Endpoints of the Component.",
    )
    # FUTURE: Add option for remote tracing DB-Path
    # TODO: Add option for remote tracing DB-Path
    db_path: str | Path | None = Field(
        default=None,
        description="Optional path to the DuckDB Tracing Database. If None (default), local database will be used. MUST BE A PATH FOR A LOCAL DB FILE (More options in the future)",
    )


class TracingComponent(ServerComponent):
    """ServerComponent that handles trace-related API endpoints.

    Features:
    - /api/traces -> Gets open Telemetry Traces
    - /api/traces/services -> Get list of unique services that have been traced.
    - /api/traces/clear -> Clear all traces from DuckDB database
    - /api/traces/stats -> Get statistics about the trace database
    - /api/streaming-history/{agent_name} -> Get historical streaming output
    - /api/artifacts/history/{node_id} -> Get complete message history for a node (both produced and consumed)
    - /api/agents/{agent_id}/runs -> Get run history for an agent
    """

    name: str = "tracing"
    priority: int = Field(
        default=4, description="Registration priority. (Defaults to 4)"
    )
    config: TracingComponentConfig = Field(
        default_factory=TracingComponentConfig, description="Optional Config"
    )
    websocket_manager: WebSocketManager = Field(
        default_factory=WebSocketManager,
        description="Singleton WebSocketManagerInstance",
    )
    _db_path: Path | str | None = None

    @property
    def _db_path_exists(self) -> bool:
        """Whether the trace database is there now; the tracer creates it on its
        first span, which can be after the server started."""
        return self._db_path is not None and Path(self._db_path).exists()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """A connection to the trace database, configured as the tracer's exporter
        connects. DuckDB refuses a second connection to a file in one process with
        another configuration (``read_only=True``), so the dashboard's reads and the
        exporter's writes would fail whenever they meet (#599); with the same
        configuration they share the database.
        """
        return duckdb.connect(str(self._db_path))

    def configure(self, app, orchestrator):
        """Configure the Component.

        Configure duckDB database path if not set: the file the tracer writes
        with FLOCK_TRACE_FILE=true and Flock.clear_traces() clears,
        .flock/traces.duckdb in the working directory.
        """
        if self.config.db_path is not None:
            self._db_path = self.config.db_path

        if self._db_path is None:
            self._db_path = Path(".flock") / "traces.duckdb"

        if isinstance(self._db_path, str):
            # turn it into a path-object
            self._db_path = Path(self._db_path)

        if not self._db_path.exists():
            logger.warning(
                "TracingComponent: Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
            )

    def register_routes(self, app, orchestrator):
        """Register the routes the TracingComponent provides."""

        @app.get(self._join_path(self.config.prefix, "traces"), tags=self.config.tags)
        async def get_traces() -> list[dict[str, Any]]:
            """Get OpenTelemetry traces from DuckDB.

            Returns list of trace spans in OTEL format.

            Returns:
                [
                    {
                        "name": "Agent.execute",
                        "context": {
                            "trace_id": "...",
                            "span_id": "...",
                        },
                        "start_time": 1234,
                        "end_time": 1234,
                        "attributes": {...},
                        "status": {...}
                    }
                ]
            """
            if not self._db_path_exists:
                logger.warning(
                    "TracingComponent: Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
                )
                return []
            try:
                with self._connect() as conn:
                    # Query all spans from DuckDB
                    result = conn.execute(_ALL_SPANS_SQL).fetchall()
                    spans = [_span_from_row(row) for row in result]
                    logger.debug(f"Loaded {len(spans)} spans from DuckDB")
                    return spans

            except Exception as ex:
                logger.exception(f"Error reading traces from DuckDB: {ex!s}")
                return []

        def read_agent_traces(agent_name: str, runs: int) -> list[dict[str, Any]]:
            with self._connect() as conn:
                result = conn.execute(_AGENT_SPANS_SQL, [agent_name, runs]).fetchall()
            return [_span_from_row(row) for row in result]

        # A path parameter, since agent names may contain a slash
        @app.get(
            self._join_path(self.config.prefix, "traces/agents/{agent_name:path}"),
            tags=self.config.tags,
        )
        async def get_agent_traces(
            agent_name: str,
            runs: int = Query(
                5, ge=1, le=50, description="How many of the latest runs"
            ),
        ) -> list[dict[str, Any]]:
            """The agent's latest runs and the spans below them, in the format of /traces.

            A run is an ``Agent.execute`` span whose ``agent.name`` attribute
            names the agent; its spans are read with a recursive query, so the
            trace database is never read whole. The query runs in a thread, off
            the event loop that serves the dashboard's websocket.
            """
            if not self._db_path_exists:
                return []
            try:
                return await asyncio.to_thread(read_agent_traces, agent_name, runs)
            except Exception as ex:
                logger.exception(f"Error reading traces from DuckDB: {ex!s}")
                return []

        @app.get(
            self._join_path(self.config.prefix, "traces/services"),
            tags=self.config.tags,
        )
        async def get_traces_services() -> dict[str, Any]:
            """Get list of unique services that have been traced.

            Returns:
                {
                    "services": ["Flock", "Agent", "DspyEngine", ...]
                    "operations": ["Flock.publish", "Agent.execute", ...]
                }
            """
            if not self._db_path_exists:
                logger.warning(
                    "TracingComponent: Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
                )
                return {"services": [], "operations": []}
            try:
                with self._connect() as conn:
                    # Get unique services
                    services_result = conn.execute(
                        """
                        SELECT DISTINCT service
                        FROM spans
                        WHERE service IS NOT NULL
                        ORDER BY service
                        """
                    ).fetchall()
                    # Get unique operations
                    operations_result = conn.execute(
                        """
                        SELECT DISTINCT name
                        FROM spans
                        WHERE name IS NOT NULL
                        ORDER BY name
                        """
                    ).fetchall()
                    return {
                        "services": [row[0] for row in services_result],
                        "operations": [row[0] for row in operations_result],
                    }
            except Exception as ex:
                logger.exception(
                    f"TracingComponent: Error reading trace services: {ex!s}"
                )
                return {"services": [], "operations": []}

        @app.post(
            self._join_path(self.config.prefix, "traces/clear"), tags=self.config.tags
        )
        async def clear_traces() -> dict[str, Any]:
            """Clear all traces from DuckDB database.

            Returns:
                {
                    "success": true,
                    "deleted_count": 123,
                    "error": null
                }
            """
            if self._db_path_exists:
                # Off the event loop: the clear writes waiting spans first (#601)
                result = await asyncio.to_thread(
                    orchestrator.clear_traces, db_path=self._db_path
                )
                if result["success"]:
                    logger.info(
                        f"TracingComponent: Cleared {result['deleted_count']} trace spans via API"
                    )
                else:
                    logger.error(
                        f"TracingComponent: Failed to clear traces: {result['error']}"
                    )

                return result
            return {}

        @app.get(
            self._join_path(self.config.prefix, "traces/stats"), tags=self.config.tags
        )
        async def get_trace_stats() -> dict[str, Any]:
            """Get statistics about the trace database.

            Returns:
                {
                    "total_spans": 123,
                    "total_traces": 45,
                    "services_count": 5,
                    "oldest_trace": "2025-10-07T12:00:00Z",
                    "newest_trace": "2025-10-07T14:30:00Z",
                    "databse_size_mb": 12.5,
                }
            """
            if not self._db_path_exists:
                logger.warning(
                    "TracingComponent: Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
                )
                return {
                    "total_spans": 0,
                    "total_traces": 0,
                    "services_count": 0,
                    "oldest_trace": None,
                    "newest_trace": None,
                    "database_size_mb": 0,
                }
            try:
                with self._connect() as conn:
                    # Get total spans
                    total_spans = conn.execute("SELECT COUNT(*) FROM spans").fetchone()
                    # Get total unique traces
                    total_traces = conn.execute(
                        "SELECT COUNT(DISTINCT trace_id) FROM spans"
                    ).fetchone()[0]
                    # Get services count
                    services_count = conn.execute(
                        "SELECT COUNT(DISTINCT service) FROM spans WHERE service IS NOT NULL"
                    ).fetchone()[0]
                    # Get time range
                    time_range = conn.execute(
                        """
                        SELECT
                            MIN(start_time) as oldes,
                            MAX(start_time) as newest
                        FROM spans
                        """
                    ).fetchone()
                    oldest_trace = None
                    newest_trace = None
                    if time_range and time_range[0]:
                        # Convert nanoseconds to datetime
                        oldest_trace = datetime.fromtimestamp(
                            time_range[0] / 1_000_000_000, tz=UTC
                        ).isoformat()
                        newest_trace = datetime.fromtimestamp(
                            time_range[1] / 1_000_000_000, tz=UTC
                        ).isoformat()
                    # Get file size
                    size_mb = self._db_path.stat().st_size / (1024 * 1024)
                    return {
                        "total_spans": total_spans,
                        "total_traces": total_traces,
                        "services_count": services_count,
                        "oldest_trace": oldest_trace,
                        "newest_trace": newest_trace,
                        "database_size_mb": round(size_mb, 2),
                    }
            except Exception as ex:
                logger.exception(f"TraceComponent: Error reading trace stats: {ex!s}")
                return {
                    "total_spans": 0,
                    "total_traces": 0,
                    "services_count": 0,
                    "oldest_trace": None,
                    "newest_trace": None,
                    "database_size_mb": 0,
                }

        @app.get(
            self._join_path(self.config.prefix, "streaming-history/{agent_name}"),
            tags=self.config.tags,
        )
        async def get_streaming_history(agent_name: str) -> dict[str, Any]:
            """Get historical streaming output for a specific agent.

            Args:
                agent_name: Name f the agent to get streaming history for
            Returns:
                {
                    "agent_name": "agent_name",
                    "events": [
                        {
                            "correlation_id": "...",
                            "timestamp": "...",
                            "agent_name": "...",
                            "run_id": "...",
                            "output_type": "llm_token",
                            "content": "...",
                            "sequence": 0,
                            "is_final": false
                        }
                    ]
                }
            """
            try:
                history = await self.websocket_manager.get_streaming_history(
                    agent_name=agent_name
                )
                return {
                    "agent_name": agent_name,
                    "events": [event.model_dump() for event in history],
                }
            except Exception as ex:
                logger.exception(
                    f"TracingComponent: Failed to get streaming history for {agent_name}: {ex!s}"
                )
                raise HTTPException(
                    status_code=500, detail=f"Failed to get streaming history: {ex!s}"
                ) from ex

        @app.get(
            self._join_path(self.config.prefix, "artifacts/history/{node_id}"),
            tags=self.config.tags,
        )
        async def get_message_history(node_id: str) -> dict[str, Any]:
            """Get complete message history for a node (both produced and consumed).

            Phase 4.1 Feature Gap Fix: Returns both messages produced by AND consumed by
            the specified node, enabling complete message history view in MessageHistoryTab.

            Args:
                node_id: ID of the node (agent name or message ID)

            Returns:
                {
                    "node_id": "agent_name",
                    "messages": [
                        {
                            "id": "artifact-uuid",
                            "type": "ArtifactType",
                            "direction": "published"|"consumed",
                            "payload": {...},
                            "timestamp": "2025-10-1T..",
                            "correlation_id": "uuid",
                            "produced_by": "producer_name",
                            "consumed_at": "2025-10-1T..." (only for consumed)
                        }
                    ],
                    "total": 123,
                }
            """
            try:
                messages = []
                # 1. Get messages PRODUCED by this node
                produced_filter = FilterConfig(produced_by={node_id})
                (
                    produced_artifacts,
                    _produced_count,
                ) = await orchestrator.store.query_artifacts(
                    produced_filter,
                    limit=100,
                    offset=0,
                    embed_meta=False,
                )
                messages.extend([
                    {
                        "id": str(artifact.id),
                        "type": artifact.type,
                        "direction": "published",
                        "payload": compact(artifact.payload),
                        "_raw": artifact.payload,
                        "timestamp": artifact.created_at.isoformat(),
                        "correlation_id": str(artifact.correlation_id)
                        if artifact.correlation_id
                        else None,
                        "produced_by": artifact.produced_by,
                    }
                    for artifact in produced_artifacts
                ])
                # 2. Get messsages CONSUMED by this node
                # Query all artifacts with consumption metadata
                all_artifacts_filter = FilterConfig()  # No filter = all artifacts
                all_envelopes, _ = await orchestrator.store.query_artifacts(
                    all_artifacts_filter, limit=500, offset=0, embed_meta=True
                )
                messages.extend([
                    {
                        "id": str(envelope.artifact.id),
                        "type": envelope.artifact.type,
                        "direction": "consumed",
                        "payload": compact(envelope.artifact.payload),
                        "_raw": envelope.artifact.payload,
                        "timestamp": envelope.artifact.created_at.isoformat(),
                        "correlation_id": str(envelope.artifact.correlation_id)
                        if envelope.artifact.correlation_id
                        else None,
                        "produced_by": envelope.artifact.produced_by,
                        "consumed_at": consumption.consumed_at.isoformat(),
                    }
                    for envelope in all_envelopes
                    for consumption in envelope.consumptions
                    if consumption.consumer == node_id
                ])
                # Thumbnails decode images: build them off the event loop
                raw_payloads = [message.pop("_raw") for message in messages]
                summaries = await asyncio.to_thread(
                    lambda: [image_summaries(raw) for raw in raw_payloads]
                )
                for message, images in zip(messages, summaries, strict=True):
                    message["images"] = images or None
                # Sort by timestamp (most recent first)
                messages.sort(
                    key=lambda m: m.get("consumed_at", m["timestamp"]),
                    reverse=True,
                )
                return {
                    "node_id": node_id,
                    "messages": messages,
                    "total": len(messages),
                }
            except Exception as ex:
                logger.exception(
                    f"TracingComponent: Failed to get message history for {node_id}: {ex!s}"
                )
                raise HTTPException(
                    status_code=500, detail=f"Failed to get message histor: {ex!s}"
                ) from ex

        @app.get(
            self._join_path(self.config.prefix, "agents/{agent_id}/runs"),
            tags=self.config.tags,
        )
        async def get_agent_runs(agent_id: str) -> dict[str, Any]:
            """Get run history for an agent.

            Phase 4.1 Feature Gap Fix: Returns agent execution history with metrics
            for display in RunStatusTab

            Args:
                agent_id: ID of the agent

            Returns:
                {
                    "agent_id": "agent_name",
                    "runs": [
                        {
                            "run_id": "<uuid>",
                            "correlation_id": "<uuid>",
                            "start_time": "2025-10-11T..",
                            "end_time": "2025-10-11T...",
                            "duration_ms": 1234
                            "status": "completed"|"active"|"error",
                            "metrics": {
                                "tokens_used": 123,
                                "cost_usd": 0.0012,
                                "usage": {"<model>": {"prompt_tokens": .., ..}},
                                "artifacts_produced": 5,
                            },
                            "error_message": "error details" (if status=error)
                        }
                    ],
                    "total": 50,
                }
            """
            try:
                # The dashboard's event collector keeps the runs (and their
                # metrics); without the dashboard there is no run history
                collector = getattr(orchestrator, "_dashboard_collector", None)
                runs = await collector.agent_runs(agent_id) if collector else []
                return {"agent_id": agent_id, "runs": runs, "total": len(runs)}
            except Exception as ex:
                logger.exception(
                    f"TracingComponent: Failed to get run history for {agent_id}: {ex!s}"
                )
                raise HTTPException(
                    status_code=500, detail=f"Failed to get run history: {ex!s}"
                ) from ex

        @app.get(
            self._join_path(self.config.prefix, "runs/active"),
            tags=self.config.tags,
        )
        async def get_active_runs() -> dict[str, Any]:
            """The runs going on now (run_id, agent_name, correlation_id,
            consumed_artifacts, start_time), for a dashboard that connects
            while they go on; empty without the dashboard."""
            collector = getattr(orchestrator, "_dashboard_collector", None)
            return {"runs": await collector.active_runs() if collector else []}

    async def on_shutdown_async(self, orchestrator):
        # No-op
        pass

    async def on_startup_async(self, orchestrator):
        # No-op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
