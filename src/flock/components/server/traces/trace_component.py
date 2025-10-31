"""Trace-relate API routes."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from fastapi import HTTPException
from pydantic import Field

from flock.api.websocket import WebSocketManager
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.core.store import FilterConfig
from flock.logging.logging import get_logger


logger = get_logger(__name__)


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
    - /api/traces/query -> Execute a DuckDB query on the traces database.
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
    _db_path_exists: bool = False

    def configure(self, app, orchestrator):
        """Configure the Component.

        Configure duckDB database path if not set.
        """
        if self.config.db_path is not None:
            self._db_path = self.config.db_path

        if self._db_path is None:
            self._db_path = (
                Path(__file__).parent.parent.parent.parent.parent
                / ".flock/traces.duckdb"
            )

        if isinstance(self._db_path, str):
            # turn it into a path-object
            self._db_path = Path(self._db_path)

        if not self._db_path.exists():
            logger.warning(
                "TracingComponent: Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
            )
            self._db_path_exists = False
        else:
            self._db_path_exists = True

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
                with duckdb.connect(str(self._db_path), read_only=True) as conn:
                    # Query all spans from DuckDB
                    result = conn.execute("""
                                          SELECT
                                            trace_id, span_id, parent_id, name, service, operation,
                                            kind, start_time, end_time, duration_ms,
                                            status_code, status_description,
                                            attributes, events, links, resource
                                          FROM spans
                                          ORDER BY start_time DESC
                                          """).fetchall()
                    spans = []
                    for row in result:
                        # Reconstruct OTEL span format from DuckDB row
                        span = {
                            "name": row[3],
                            "context": {
                                "trace_id": row[0],  # trace_id
                                "span_id": row[1],  # span_id
                                "trace_flags": 0,
                                "trace_state": "",
                            },
                            "kind": row[6],  # kind
                            "start_time": row[7],  # start_time
                            "end_time": row[8],  # end_time
                            "status": {
                                "status_code": row[10],  # status_code
                                "description": row[11],  # status_description
                            },
                            "attributes": json.loads(row[12])
                            if row[12]
                            else {},  # attributes
                            "events": json.loads(row[13]) if row[13] else [],  # events
                            "links": json.loads(row[14]) if row[14] else [],  # links
                            "resource": json.loads(row[15])
                            if row[15]
                            else {},  # resource
                        }
                        # add parent_id if exists
                        if row[2]:
                            span["parent_id"] = row[2]
                        spans.append(span)
                    logger.debug(f"Loaded {len(spans)} spans from DuckDB")
                    return spans

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
                with duckdb.connect(str(self._db_path), read_only=True) as conn:
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
                result = orchestrator.clear_traces(db_path=self._db_path)
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

        @app.post(
            self._join_path(self.config.prefix, "traces/query"), tags=self.config.tags
        )
        async def execute_trace_query(request: dict[str, Any]) -> dict[str, Any]:
            """Execute a DuckDB SQL query on the traces database.

            Security: Only SELECT queries allowed, rate-limited
            """
            query = request.get("query", "").strip()
            if not query:
                return {
                    "error": "Query cannot be empty",
                    "results": [],
                    "columns": [],
                }
            # Security: Only allow SELECT queries
            query_upper = query.upper().strip()
            if not query_upper.startswith("SELECT"):
                return {
                    "error": "Only SELECT queries are allowed",
                    "results": [],
                    "columns": [],
                }
            # Check for dangerous keywords
            dangerous = [
                "DROP",
                "DELETE",
                "INSERT",
                "UPDATE",
                "ALTER",
                "CREATE",
                "TRUNCATE",
            ]
            if any(keyword in query_upper for keyword in dangerous):
                return {
                    "error": "Query contains forbidden operations",
                    "results": [],
                    "columns": [],
                }
            if not self._db_path_exists:
                logger.warning(
                    "TracingComponent: Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
                )
                return {
                    "error": "Trace database not found",
                    "results": [],
                    "columns": [],
                }
            try:
                with duckdb.connect(str(self._db_path), read_only=True) as conn:
                    result = conn.execute(query).fetchall()
                    columns = (
                        [desc[0] for desc in conn.description]
                        if conn.description
                        else []
                    )
                    # Convert to JSON-serializable format
                    results = []
                    for row in result:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            val = row[i]
                            # Convert bytes to string, handle other types
                            if isinstance(val, bytes):
                                row_dict[col] = val.decode("utf-8")
                            else:
                                row_dict[col] = val
                        results.append(row_dict)
                    return {
                        "results": results,
                        "columsn": columns,
                        "row_count": len(results),
                    }
            except Exception as ex:
                logger.exception(f"TracingComponent: DuckDB query error: {ex!s}")
                return {"error": str(ex), "results": [], "columns": []}

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
                with duckdb.connect(str(self._db_path), read_only=True) as conn:
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
                        "payload": artifact.payload,
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
                        "payload": envelope.artifact.payload,
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
                            "start_time": "2025-10-11T..",
                            "end_time": "2025-10-11T...",
                            "duration_ms": 1234
                            "status": "completed"|"active"|"error",
                            "metrics": {
                                "tokens_used": 123,
                                "cost_usd": 0.0012,
                                "artifacts_produced": 5,
                            },
                            "error_message": "error details" (if status=error)
                        }
                    ],
                    "total": 50,
                }
            """
            try:
                # TODO: Implement run history tracking in orchestrator
                # For now, return empty array with proper structure
                # This unblocks frontend development and can be enhanced later
                runs = []

                # FUTURE: Query run history from orchestrator or store
                # Example implementation when run tracking is added:
                # runs = await orchestrator.get_agent_run_history(agent_id, limit=50)
                return {"agent_id": agent_id, "runs": runs, "total": len(runs)}
            except Exception as ex:
                logger.exception(
                    f"TracingComponent: Failed to get run history for {agent_id}: {ex!s}"
                )
                raise HTTPException(
                    status_code=500, detail=f"Failed to get run history: {ex!s}"
                ) from ex

    async def on_shutdown_async(self, orchestrator):
        # No-op
        pass

    async def on_startup_async(self, orchestrator):
        # No-op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
