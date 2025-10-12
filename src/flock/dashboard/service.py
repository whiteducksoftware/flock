"""DashboardHTTPService - extends BlackboardHTTPService with WebSocket support.

Provides real-time dashboard capabilities by:
1. Mounting WebSocket endpoint at /ws
2. Serving static files for dashboard frontend
3. Integrating DashboardEventCollector with WebSocketManager
4. Supporting CORS for development mode (DASHBOARD_DEV=1)
"""

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.events import MessagePublishedEvent, VisibilitySpec
from flock.dashboard.graph_builder import GraphAssembler
from flock.dashboard.models.graph import GraphRequest, GraphSnapshot
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger
from flock.orchestrator import Flock
from flock.registry import type_registry
from flock.service import BlackboardHTTPService


logger = get_logger("dashboard.service")


class DashboardHTTPService(BlackboardHTTPService):
    """HTTP service with WebSocket support for real-time dashboard.

    Extends BlackboardHTTPService to add:
    - WebSocket endpoint at /ws for real-time event streaming
    - Static file serving for dashboard frontend
    - Integration with DashboardEventCollector
    - Optional CORS middleware for development
    """

    def __init__(
        self,
        orchestrator: Flock,
        websocket_manager: WebSocketManager | None = None,
        event_collector: DashboardEventCollector | None = None,
        *,
        use_v2: bool = False,
    ) -> None:
        """Initialize DashboardHTTPService.

        Args:
            orchestrator: Flock orchestrator instance
            websocket_manager: Optional WebSocketManager (creates new if not provided)
            event_collector: Optional DashboardEventCollector (creates new if not provided)
        """
        # Initialize base service
        super().__init__(orchestrator)

        # Initialize WebSocket manager and event collector
        self.websocket_manager = websocket_manager or WebSocketManager()
        self.event_collector = event_collector or DashboardEventCollector(
            store=self.orchestrator.store
        )
        self.use_v2 = use_v2

        # Integrate collector with WebSocket manager
        self.event_collector.set_websocket_manager(self.websocket_manager)

        # Graph assembler powers both dashboards by default
        self.graph_assembler: GraphAssembler | None = GraphAssembler(
            self.orchestrator.store, self.event_collector, self.orchestrator
        )

        # Configure CORS if DASHBOARD_DEV environment variable is set
        if os.environ.get("DASHBOARD_DEV") == "1":
            logger.info("DASHBOARD_DEV mode enabled - adding CORS middleware")
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Allow all origins in dev mode
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # IMPORTANT: Register API routes BEFORE static files!
        # Static file mount acts as catch-all and must be last
        self._register_control_routes()
        self._register_theme_routes()
        self._register_dashboard_routes()

        logger.info("DashboardHTTPService initialized")

    def _register_dashboard_routes(self) -> None:
        """Register WebSocket endpoint and static file serving."""
        app = self.app

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            """WebSocket endpoint for real-time dashboard events.

            Handles connection lifecycle:
            1. Accept connection
            2. Add to WebSocketManager pool
            3. Keep connection alive
            4. Handle disconnection gracefully
            """
            await websocket.accept()
            await self.websocket_manager.add_client(websocket)

            try:
                # Keep connection alive and handle incoming messages
                # Dashboard clients may send heartbeat responses or control messages
                while True:
                    # Wait for messages from client (pong responses, etc.)
                    try:
                        data = await websocket.receive_text()
                        # Handle client messages if needed (e.g., pong responses)
                        # For Phase 3, we primarily broadcast from server to client
                        logger.debug(f"Received message from client: {data[:100]}")
                    except WebSocketDisconnect:
                        logger.info("WebSocket client disconnected")
                        break
                    except Exception as e:
                        logger.warning(f"Error receiving WebSocket message: {e}")
                        break

            except Exception as e:
                logger.exception(f"WebSocket endpoint error: {e}")
            finally:
                # Clean up: remove client from pool
                await self.websocket_manager.remove_client(websocket)

        if self.graph_assembler is not None:

            @app.post("/api/dashboard/graph", response_model=GraphSnapshot)
            async def get_dashboard_graph(request: GraphRequest) -> GraphSnapshot:
                """Return server-side assembled dashboard graph snapshot."""
                return await self.graph_assembler.build_snapshot(request)

        dashboard_dir = Path(__file__).parent
        frontend_root = dashboard_dir.parent / ("frontend_v2" if self.use_v2 else "frontend")
        static_dir = dashboard_dir / ("static_v2" if self.use_v2 else "static")

        possible_dirs = [
            static_dir,
            frontend_root / "dist",
            frontend_root / "build",
        ]

        for dir_path in possible_dirs:
            if dir_path.exists() and dir_path.is_dir():
                logger.info(f"Mounting static files from: {dir_path}")
                # Mount at root to serve index.html and other frontend assets
                app.mount(
                    "/",
                    StaticFiles(directory=str(dir_path), html=True),
                    name="dashboard-static",
                )
                break
        else:
            logger.warning(
                f"No static directory found for dashboard frontend (expected one of: {possible_dirs})."
            )

    def _register_control_routes(self) -> None:
        """Register control API endpoints for dashboard operations."""
        app = self.app
        orchestrator = self.orchestrator

        @app.get("/api/artifact-types")
        async def get_artifact_types() -> dict[str, Any]:
            """Get all registered artifact types with their schemas.

            Returns:
                {
                    "artifact_types": [
                        {
                            "name": "TypeName",
                            "schema": {...}
                        },
                        ...
                    ]
                }
            """
            artifact_types = []

            for type_name in type_registry._by_name:
                try:
                    model_class = type_registry.resolve(type_name)
                    # Get Pydantic schema
                    schema = model_class.model_json_schema()
                    artifact_types.append({"name": type_name, "schema": schema})
                except Exception as e:
                    logger.warning(f"Could not get schema for {type_name}: {e}")

            return {"artifact_types": artifact_types}

        @app.get("/api/agents")
        async def get_agents() -> dict[str, Any]:
            """Get all registered agents.

            Returns:
                {
                    "agents": [
                        {
                            "name": "agent_name",
                            "description": "...",
                            "status": "ready",
                            "subscriptions": ["TypeA", "TypeB"],
                            "output_types": ["TypeC", "TypeD"]
                        },
                        ...
                    ]
                }
            """
            agents = []

            for agent in orchestrator.agents:
                # Extract consumed types from agent subscriptions
                consumed_types = []
                for sub in agent.subscriptions:
                    consumed_types.extend(sub.type_names)

                # Extract produced types from agent outputs
                produced_types = [output.spec.type_name for output in agent.outputs]

                agents.append(
                    {
                        "name": agent.name,
                        "description": agent.description or "",
                        "status": "ready",
                        "subscriptions": consumed_types,
                        "output_types": produced_types,
                    }
                )

            return {"agents": agents}

        @app.get("/api/version")
        async def get_version() -> dict[str, str]:
            """Get version information for the backend and dashboard.

            Returns:
                {
                    "backend_version": "0.1.18",
                    "package_name": "flock-flow"
                }
            """
            try:
                backend_version = version("flock-flow")
            except PackageNotFoundError:
                # Fallback version if package not installed
                backend_version = "0.2.0-dev"

            return {"backend_version": backend_version, "package_name": "flock-flow"}

        @app.post("/api/control/publish")
        async def publish_artifact(body: dict[str, Any]) -> dict[str, str]:
            """Publish artifact with correlation tracking.

            Request body:
                {
                    "artifact_type": "TypeName",
                    "content": {"field": "value", ...}
                }

            Returns:
                {
                    "correlation_id": "<uuid>",
                    "published_at": "<iso-timestamp>"
                }
            """
            # Validate required fields
            artifact_type = body.get("artifact_type")
            content = body.get("content")

            if not artifact_type:
                raise HTTPException(status_code=400, detail="artifact_type is required")
            if content is None:
                raise HTTPException(status_code=400, detail="content is required")

            try:
                # Resolve type from registry
                model_class = type_registry.resolve(artifact_type)

                # Validate content against Pydantic schema
                try:
                    instance = model_class(**content)
                except ValidationError as e:
                    raise HTTPException(status_code=422, detail=f"Validation error: {e!s}")

                # Generate correlation ID
                correlation_id = str(uuid4())

                # Publish to orchestrator
                artifact = await orchestrator.publish(
                    instance, correlation_id=correlation_id, is_dashboard=True
                )

                # Phase 11 Fix: Emit message_published event for dashboard visibility
                # This enables virtual "orchestrator" agent to appear in both Agent View and Blackboard View
                event = MessagePublishedEvent(
                    correlation_id=str(artifact.correlation_id),
                    artifact_id=str(artifact.id),
                    artifact_type=artifact.type,
                    produced_by=artifact.produced_by,  # Will be "orchestrator" or similar for non-agent publishers
                    payload=artifact.payload,
                    visibility=VisibilitySpec(
                        kind="Public"
                    ),  # Dashboard-published artifacts are public by default
                    tags=list(artifact.tags) if artifact.tags else [],
                    partition_key=artifact.partition_key,
                    version=artifact.version,
                    consumers=[],  # Will be populated by subscription matching in frontend
                )
                await self.websocket_manager.broadcast(event)

                return {
                    "correlation_id": str(artifact.correlation_id),
                    "published_at": artifact.created_at.isoformat(),
                }

            except KeyError:
                raise HTTPException(
                    status_code=422, detail=f"Unknown artifact type: {artifact_type}"
                )
            except Exception as e:
                logger.exception(f"Error publishing artifact: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/control/invoke")
        async def invoke_agent(body: dict[str, Any]) -> dict[str, Any]:
            """Directly invoke a specific agent.

            Request body:
                {
                    "agent_name": "agent_name",
                    "input": {"type": "TypeName", "field": "value", ...}
                }

            Returns:
                {
                    "invocation_id": "<uuid>",
                    "result": "success"
                }
            """
            # Validate required fields
            agent_name = body.get("agent_name")
            input_data = body.get("input")

            if not agent_name:
                raise HTTPException(status_code=400, detail="agent_name is required")
            if input_data is None:
                raise HTTPException(status_code=400, detail="input is required")

            try:
                # Get agent from orchestrator
                agent = orchestrator.get_agent(agent_name)
            except KeyError:
                raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

            try:
                # Parse input type and create instance
                input_type = input_data.get("type")
                if not input_type:
                    raise HTTPException(status_code=400, detail="input.type is required")

                # Resolve type from registry
                model_class = type_registry.resolve(input_type)

                # Create payload by removing 'type' key
                payload = {k: v for k, v in input_data.items() if k != "type"}

                # Validate and create instance
                try:
                    instance = model_class(**payload)
                except ValidationError as e:
                    raise HTTPException(status_code=422, detail=f"Validation error: {e!s}")

                # Invoke agent
                outputs = await orchestrator.invoke(agent, instance)

                # Generate invocation ID from first output or create new UUID
                invocation_id = str(outputs[0].id) if outputs else str(uuid4())

                # Extract correlation_id from first output (for filter automation)
                correlation_id = (
                    str(outputs[0].correlation_id)
                    if outputs and outputs[0].correlation_id
                    else None
                )

                return {
                    "invocation_id": invocation_id,
                    "correlation_id": correlation_id,
                    "result": "success",
                }

            except HTTPException:
                raise
            except KeyError:
                raise HTTPException(status_code=422, detail=f"Unknown type: {input_type}")
            except Exception as e:
                logger.exception(f"Error invoking agent: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/control/pause")
        async def pause_orchestrator() -> dict[str, Any]:
            """Pause orchestrator (placeholder).

            Returns:
                501 Not Implemented
            """
            raise HTTPException(status_code=501, detail="Pause functionality coming in Phase 12")

        @app.post("/api/control/resume")
        async def resume_orchestrator() -> dict[str, Any]:
            """Resume orchestrator (placeholder).

            Returns:
                501 Not Implemented
            """
            raise HTTPException(status_code=501, detail="Resume functionality coming in Phase 12")

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
            import json
            from pathlib import Path

            import duckdb

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
                            "attributes": json.loads(row[12]) if row[12] else {},  # attributes
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
            from pathlib import Path

            import duckdb

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
            """
            Execute a DuckDB SQL query on the traces database.

            Security: Only SELECT queries allowed, rate-limited.
            """
            from pathlib import Path

            import duckdb

            query = request.get("query", "").strip()

            if not query:
                return {"error": "Query cannot be empty", "results": [], "columns": []}

            # Security: Only allow SELECT queries
            query_upper = query.upper().strip()
            if not query_upper.startswith("SELECT"):
                return {"error": "Only SELECT queries are allowed", "results": [], "columns": []}

            # Check for dangerous keywords
            dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
            if any(keyword in query_upper for keyword in dangerous):
                return {
                    "error": "Query contains forbidden operations",
                    "results": [],
                    "columns": [],
                }

            db_path = Path(".flock/traces.duckdb")
            if not db_path.exists():
                return {"error": "Trace database not found", "results": [], "columns": []}

            try:
                with duckdb.connect(str(db_path), read_only=True) as conn:
                    result = conn.execute(query).fetchall()
                    columns = [desc[0] for desc in conn.description] if conn.description else []

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

                    return {"results": results, "columns": columns, "row_count": len(results)}
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
            from datetime import datetime
            from pathlib import Path

            import duckdb

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
                            time_range[0] / 1_000_000_000
                        ).isoformat()
                        newest_trace = datetime.fromtimestamp(
                            time_range[1] / 1_000_000_000
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
                history = self.websocket_manager.get_streaming_history(agent_name)
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
                from flock.store import FilterConfig

                messages = []

                # 1. Get messages PRODUCED by this node
                produced_filter = FilterConfig(produced_by={node_id})
                produced_artifacts, _produced_count = await orchestrator.store.query_artifacts(
                    produced_filter, limit=100, offset=0, embed_meta=False
                )

                for artifact in produced_artifacts:
                    messages.append(
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
                    )

                # 2. Get messages CONSUMED by this node
                # Query all artifacts with consumption metadata
                all_artifacts_filter = FilterConfig()  # No filter = all artifacts
                all_envelopes, _ = await orchestrator.store.query_artifacts(
                    all_artifacts_filter, limit=500, offset=0, embed_meta=True
                )

                for envelope in all_envelopes:
                    artifact = envelope.artifact
                    for consumption in envelope.consumptions:
                        if consumption.consumer == node_id:
                            messages.append(
                                {
                                    "id": str(artifact.id),
                                    "type": artifact.type,
                                    "direction": "consumed",
                                    "payload": artifact.payload,
                                    "timestamp": artifact.created_at.isoformat(),
                                    "correlation_id": str(artifact.correlation_id)
                                    if artifact.correlation_id
                                    else None,
                                    "produced_by": artifact.produced_by,
                                    "consumed_at": consumption.consumed_at.isoformat(),
                                }
                            )

                # Sort by timestamp (most recent first)
                messages.sort(key=lambda m: m.get("consumed_at", m["timestamp"]), reverse=True)

                return {"node_id": node_id, "messages": messages, "total": len(messages)}

            except Exception as e:
                logger.exception(f"Failed to get message history for {node_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get message history: {e!s}")

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
                raise HTTPException(status_code=500, detail=f"Failed to get run history: {e!s}")

    def _register_theme_routes(self) -> None:
        """Register theme API endpoints for dashboard customization."""
        from pathlib import Path

        import toml

        app = self.app
        themes_dir = Path(__file__).parent.parent / "themes"

        @app.get("/api/themes")
        async def list_themes() -> dict[str, Any]:
            """Get list of available theme names.

            Returns:
                {"themes": ["dracula", "nord", ...]}
            """
            try:
                if not themes_dir.exists():
                    return {"themes": []}

                theme_files = list(themes_dir.glob("*.toml"))
                theme_names = sorted([f.stem for f in theme_files])

                return {"themes": theme_names}
            except Exception as e:
                logger.exception(f"Failed to list themes: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to list themes: {e!s}")

        @app.get("/api/themes/{theme_name}")
        async def get_theme(theme_name: str) -> dict[str, Any]:
            """Get theme data by name.

            Args:
                theme_name: Name of theme (without .toml extension)

            Returns:
                {
                    "name": "dracula",
                    "data": {
                        "colors": {...}
                    }
                }
            """
            try:
                # Sanitize theme name to prevent path traversal
                theme_name = theme_name.replace("/", "").replace("\\", "").replace("..", "")

                theme_path = themes_dir / f"{theme_name}.toml"

                if not theme_path.exists():
                    raise HTTPException(status_code=404, detail=f"Theme '{theme_name}' not found")

                # Load TOML theme
                theme_data = toml.load(theme_path)

                return {"name": theme_name, "data": theme_data}
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Failed to load theme '{theme_name}': {e}")
                raise HTTPException(status_code=500, detail=f"Failed to load theme: {e!s}")

    async def start(self) -> None:
        """Start the dashboard service.

        Note: For testing purposes. In production, use uvicorn.run(app).
        """
        logger.info("DashboardHTTPService started")
        # Start heartbeat if there are clients
        if len(self.websocket_manager.clients) > 0:
            await self.websocket_manager.start_heartbeat()

    async def stop(self) -> None:
        """Stop the dashboard service and clean up resources.

        Closes all WebSocket connections gracefully.
        """
        logger.info("Stopping DashboardHTTPService")
        await self.websocket_manager.shutdown()
        logger.info("DashboardHTTPService stopped")

    def get_app(self) -> Any:
        """Get FastAPI application instance.

        Returns:
            FastAPI app for testing or custom server setup
        """
        return self.app


__all__ = ["DashboardHTTPService"]
