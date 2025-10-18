"""Trace-related API routes for dashboard."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException

from flock.core import Flock
from flock.core.store import FilterConfig
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger


logger = get_logger("dashboard.routes.traces")


def register_trace_routes(
    app: FastAPI,
    orchestrator: Flock,
    websocket_manager: WebSocketManager,
    event_collector: DashboardEventCollector,
) -> None:
    """Register trace-related API endpoints.

    Args:
        app: FastAPI application instance
        orchestrator: Flock orchestrator instance
        websocket_manager: WebSocket manager for real-time updates
        event_collector: Dashboard event collector
    """

    @app.get("/api/traces")
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
                        ...
                    },
                    "start_time": 1234567890,
                    "end_time": 1234567891,
                    "attributes": {...},
                    "status": {...}
                },
                ...
            ]
        """
        db_path = Path(".flock/traces.duckdb")

        if not db_path.exists():
            logger.warning(
                "Trace database not found. Make sure FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true"
            )
            return []

        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
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
                        "name": row[3],  # name
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
                        "resource": json.loads(row[15]) if row[15] else {},  # resource
                    }

                    # Add parent_id if exists
                    if row[2]:  # parent_id
                        span["parent_id"] = row[2]

                    spans.append(span)

            logger.debug(f"Loaded {len(spans)} spans from DuckDB")
            return spans

        except Exception as e:
            logger.exception(f"Error reading traces from DuckDB: {e}")
            return []

    @app.get("/api/traces/services")
    async def get_trace_services() -> dict[str, Any]:
        """Get list of unique services that have been traced.

        Returns:
            {
                "services": ["Flock", "Agent", "DSPyEngine", ...],
                "operations": ["Flock.publish", "Agent.execute", ...]
            }
        """
        db_path = Path(".flock/traces.duckdb")

        if not db_path.exists():
            return {"services": [], "operations": []}

        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                # Get unique services
                services_result = conn.execute("""
                    SELECT DISTINCT service
                    FROM spans
                    WHERE service IS NOT NULL
                    ORDER BY service
                """).fetchall()

                # Get unique operations
                operations_result = conn.execute("""
                    SELECT DISTINCT name
                    FROM spans
                    WHERE name IS NOT NULL
                    ORDER BY name
                """).fetchall()

                return {
                    "services": [row[0] for row in services_result],
                    "operations": [row[0] for row in operations_result],
                }

        except Exception as e:
            logger.exception(f"Error reading trace services: {e}")
            return {"services": [], "operations": []}

    @app.post("/api/traces/clear")
    async def clear_traces() -> dict[str, Any]:
        """Clear all traces from DuckDB database.

        Returns:
            {
                "success": true,
                "deleted_count": 123,
                "error": null
            }
        """
        result = Flock.clear_traces()
        if result["success"]:
            logger.info(f"Cleared {result['deleted_count']} trace spans via API")
        else:
            logger.error(f"Failed to clear traces: {result['error']}")

        return result

    @app.post("/api/traces/query")
    async def execute_trace_query(request: dict[str, Any]) -> dict[str, Any]:
        """Execute a DuckDB SQL query on the traces database.

        Security: Only SELECT queries allowed, rate-limited.
        """
        query = request.get("query", "").strip()

        if not query:
            return {"error": "Query cannot be empty", "results": [], "columns": []}

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

        db_path = Path(".flock/traces.duckdb")
        if not db_path.exists():
            return {
                "error": "Trace database not found",
                "results": [],
                "columns": [],
            }

        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                result = conn.execute(query).fetchall()
                columns = (
                    [desc[0] for desc in conn.description] if conn.description else []
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
                    "columns": columns,
                    "row_count": len(results),
                }
        except Exception as e:
            logger.exception(f"DuckDB query error: {e}")
            return {"error": str(e), "results": [], "columns": []}

    @app.get("/api/traces/stats")
    async def get_trace_stats() -> dict[str, Any]:
        """Get statistics about the trace database.

        Returns:
            {
                "total_spans": 123,
                "total_traces": 45,
                "services_count": 5,
                "oldest_trace": "2025-10-07T12:00:00Z",
                "newest_trace": "2025-10-07T14:30:00Z",
                "database_size_mb": 12.5
            }
        """
        db_path = Path(".flock/traces.duckdb")

        if not db_path.exists():
            return {
                "total_spans": 0,
                "total_traces": 0,
                "services_count": 0,
                "oldest_trace": None,
                "newest_trace": None,
                "database_size_mb": 0,
            }

        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                # Get total spans
                total_spans = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]

                # Get total unique traces
                total_traces = conn.execute(
                    "SELECT COUNT(DISTINCT trace_id) FROM spans"
                ).fetchone()[0]

                # Get services count
                services_count = conn.execute(
                    "SELECT COUNT(DISTINCT service) FROM spans WHERE service IS NOT NULL"
                ).fetchone()[0]

                # Get time range
                time_range = conn.execute("""
                    SELECT
                        MIN(start_time) as oldest,
                        MAX(start_time) as newest
                    FROM spans
                """).fetchone()

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
            size_mb = db_path.stat().st_size / (1024 * 1024)

            return {
                "total_spans": total_spans,
                "total_traces": total_traces,
                "services_count": services_count,
                "oldest_trace": oldest_trace,
                "newest_trace": newest_trace,
                "database_size_mb": round(size_mb, 2),
            }

        except Exception as e:
            logger.exception(f"Error reading trace stats: {e}")
            return {
                "total_spans": 0,
                "total_traces": 0,
                "services_count": 0,
                "oldest_trace": None,
                "newest_trace": None,
                "database_size_mb": 0,
            }

    @app.get("/api/streaming-history/{agent_name}")
    async def get_streaming_history(agent_name: str) -> dict[str, Any]:
        """Get historical streaming output for a specific agent.

        Args:
            agent_name: Name of the agent to get streaming history for

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
                    },
                    ...
                ]
            }
        """
        try:
            history = websocket_manager.get_streaming_history(agent_name)
            return {
                "agent_name": agent_name,
                "events": [event.model_dump() for event in history],
            }
        except Exception as e:
            logger.exception(f"Failed to get streaming history for {agent_name}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get streaming history: {e!s}"
            )

    @app.get("/api/artifacts/history/{node_id}")
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
                        "timestamp": "2025-10-11T...",
                        "correlation_id": "uuid",
                        "produced_by": "producer_name",
                        "consumed_at": "2025-10-11T..." (only for consumed)
                    },
                    ...
                ],
                "total": 123
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
                produced_filter, limit=100, offset=0, embed_meta=False
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

            # 2. Get messages CONSUMED by this node
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
                key=lambda m: m.get("consumed_at", m["timestamp"]), reverse=True
            )

            return {
                "node_id": node_id,
                "messages": messages,
                "total": len(messages),
            }

        except Exception as e:
            logger.exception(f"Failed to get message history for {node_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get message history: {e!s}"
            )

    @app.get("/api/agents/{agent_id}/runs")
    async def get_agent_runs(agent_id: str) -> dict[str, Any]:
        """Get run history for an agent.

        Phase 4.1 Feature Gap Fix: Returns agent execution history with metrics
        for display in RunStatusTab.

        Args:
            agent_id: ID of the agent

        Returns:
            {
                "agent_id": "agent_name",
                "runs": [
                    {
                        "run_id": "uuid",
                        "start_time": "2025-10-11T...",
                        "end_time": "2025-10-11T...",
                        "duration_ms": 1234,
                        "status": "completed"|"active"|"error",
                        "metrics": {
                            "tokens_used": 123,
                            "cost_usd": 0.0012,
                            "artifacts_produced": 5
                        },
                        "error_message": "error details" (if status=error)
                    },
                    ...
                ],
                "total": 50
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

        except Exception as e:
            logger.exception(f"Failed to get run history for {agent_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get run history: {e!s}"
            )
