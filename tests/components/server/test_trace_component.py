"""Comprehensive tests for TracingComponent."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import duckdb
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flock.components.server.models.events import StreamingOutputEvent
from flock.components.server.traces import TracingComponent, TracingComponentConfig
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.store import ArtifactEnvelope, ConsumptionRecord
from flock.core.visibility import PublicVisibility


@pytest.fixture
def orchestrator():
    """Create a test orchestrator."""
    return Flock("openai/gpt-4o")


@pytest.fixture
def app():
    """Create a FastAPI app."""
    return FastAPI()


@pytest.fixture
def temp_db():
    """Create a temporary DuckDB database with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_traces.duckdb"

        # Create database and table
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE spans (
                trace_id VARCHAR NOT NULL,
                span_id VARCHAR PRIMARY KEY,
                parent_id VARCHAR,
                name VARCHAR NOT NULL,
                service VARCHAR,
                operation VARCHAR,
                kind VARCHAR,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                duration_ms DOUBLE NOT NULL,
                status_code VARCHAR NOT NULL,
                status_description VARCHAR,
                attributes JSON,
                events JSON,
                links JSON,
                resource JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert test spans
        test_spans = [
            (
                "trace-001",
                "span-001",
                None,
                "Agent.execute",
                "TestAgent",
                "execute",
                "INTERNAL",
                1000000000,  # start_time in nanoseconds
                1001000000,  # end_time in nanoseconds
                1.0,  # duration_ms
                "OK",
                None,
                '{"key": "value"}',
                "[]",
                "[]",
                '{"service.name": "flock"}',
            ),
            (
                "trace-001",
                "span-002",
                "span-001",
                "Flock.publish",
                "Flock",
                "publish",
                "INTERNAL",
                1001000000,
                1002000000,
                1.0,
                "OK",
                None,
                '{"artifact_type": "TestType"}',
                "[]",
                "[]",
                '{"service.name": "flock"}',
            ),
            (
                "trace-002",
                "span-003",
                None,
                "Agent.execute",
                "AnotherAgent",
                "execute",
                "INTERNAL",
                1003000000,
                1004000000,
                1.0,
                "ERROR",
                "Test error",
                "{}",
                "[]",
                "[]",
                "{}",
            ),
        ]

        for span_data in test_spans:
            conn.execute(
                """
                INSERT INTO spans (
                    trace_id, span_id, parent_id, name, service, operation,
                    kind, start_time, end_time, duration_ms, status_code,
                    status_description, attributes, events, links, resource
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                span_data,
            )

        conn.close()

        yield db_path


class TestTracingComponentConfig:
    """Tests for TracingComponentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TracingComponentConfig()

        assert config.prefix == "/api/plugin/"
        assert config.tags == ["Tracing"]
        assert config.db_path is None

    def test_custom_prefix(self):
        """Test custom prefix."""
        config = TracingComponentConfig(prefix="/api/v1/")

        assert config.prefix == "/api/v1/"

    def test_custom_tags(self):
        """Test custom tags."""
        config = TracingComponentConfig(tags=["Custom", "Traces"])

        assert config.tags == ["Custom", "Traces"]

    def test_custom_db_path_string(self):
        """Test custom db_path as string."""
        config = TracingComponentConfig(db_path="/custom/path/traces.duckdb")

        assert config.db_path == "/custom/path/traces.duckdb"

    def test_custom_db_path_path_object(self):
        """Test custom db_path as Path object."""
        path = Path("/custom/path/traces.duckdb")
        config = TracingComponentConfig(db_path=path)

        assert config.db_path == path


class TestTracingComponent:
    """Tests for TracingComponent."""

    def test_init_defaults(self):
        """Test component initialization with defaults."""
        component = TracingComponent()

        assert component.name == "tracing"
        assert component.priority == 4
        assert component.config.prefix == "/api/plugin/"
        assert component._db_path is None
        assert component._db_path_exists is False

    def test_init_custom_config(self):
        """Test component initialization with custom config."""
        config = TracingComponentConfig(prefix="/custom/", tags=["Custom"])
        component = TracingComponent(config=config)

        assert component.config.prefix == "/custom/"
        assert component.config.tags == ["Custom"]

    def test_configure_with_custom_db_path(self, app, orchestrator, temp_db):
        """Test configure with custom db_path."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)

        assert component._db_path == temp_db
        assert component._db_path_exists is True

    def test_configure_with_default_db_path_exists(self, app, orchestrator, temp_db):
        """Test configure with default db_path that exists."""
        component = TracingComponent()

        # Manually set the path to our temp db
        component._db_path = temp_db
        component.configure(app, orchestrator)

        assert component._db_path_exists is True

    def test_configure_with_nonexistent_db_path(self, app, orchestrator):
        """Test configure with non-existent db_path."""
        from pathlib import Path
        
        # Use OS-agnostic path that works on all platforms
        nonexistent_path = "nonexistent/traces.duckdb"
        config = TracingComponentConfig(db_path=nonexistent_path)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)

        assert component._db_path == Path(nonexistent_path)
        assert component._db_path_exists is False

    def test_configure_string_db_path_conversion(self, app, orchestrator):
        """Test that string db_path is converted to Path object."""
        from pathlib import Path
        
        # Use OS-agnostic path that works on all platforms
        test_path = "test/path/traces.duckdb"
        config = TracingComponentConfig(db_path=test_path)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)

        assert isinstance(component._db_path, Path)
        # Check that the path is converted correctly (OS-agnostic comparison)
        expected_path = Path(test_path)
        assert component._db_path == expected_path
        assert component._db_path.name == "traces.duckdb"
        assert component._db_path.suffix == ".duckdb"

    @pytest.mark.asyncio
    async def test_get_traces_success(self, app, orchestrator, temp_db):
        """Test successful retrieval of traces."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces")

            assert response.status_code == 200
            spans = response.json()
            assert len(spans) == 3
            assert spans[0]["name"] == "Agent.execute"
            assert spans[0]["context"]["trace_id"] == "trace-002"
            assert spans[0]["status"]["status_code"] == "ERROR"

    @pytest.mark.asyncio
    async def test_get_traces_db_not_found(self, app, orchestrator):
        """Test get_traces when database doesn't exist."""
        component = TracingComponent()
        component._db_path_exists = False
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces")

            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_traces_with_parent_id(self, app, orchestrator, temp_db):
        """Test that traces with parent_id include it in response."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces")

            assert response.status_code == 200
            spans = response.json()
            # Find span with parent_id
            child_span = next(s for s in spans if s["name"] == "Flock.publish")
            assert "parent_id" in child_span
            assert child_span["parent_id"] == "span-001"

    @pytest.mark.asyncio
    async def test_get_traces_services_success(self, app, orchestrator, temp_db):
        """Test successful retrieval of unique services."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces/services")

            assert response.status_code == 200
            data = response.json()
            assert "services" in data
            assert "operations" in data
            assert set(data["services"]) == {"AnotherAgent", "Flock", "TestAgent"}
            assert "Agent.execute" in data["operations"]
            assert "Flock.publish" in data["operations"]

    @pytest.mark.asyncio
    async def test_get_traces_services_db_not_found(self, app, orchestrator):
        """Test get_traces_services when database doesn't exist."""
        component = TracingComponent()
        component._db_path_exists = False
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces/services")

            assert response.status_code == 200
            assert response.json() == {"services": [], "operations": []}

    @pytest.mark.asyncio
    async def test_clear_traces_success(self, app, orchestrator, temp_db, mocker):
        """Test successful clearing of traces."""
        # Mock Flock.clear_traces to return success
        mock_clear = mocker.patch(
            "flock.core.orchestrator.Flock.clear_traces",
            return_value={"success": True, "deleted_count": 3, "error": None},
        )

        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post("/api/plugin/traces/clear")

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["deleted_count"] == 3
            assert result["error"] is None
            # Verify mock was called with correct path
            mock_clear.assert_called_once_with(db_path=temp_db)

    @pytest.mark.asyncio
    async def test_clear_traces_db_not_found(self, app, orchestrator):
        """Test clear_traces when database doesn't exist."""
        component = TracingComponent()
        component._db_path_exists = False
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post("/api/plugin/traces/clear")

            assert response.status_code == 200
            assert response.json() == {}

    @pytest.mark.asyncio
    async def test_execute_trace_query_valid_select(self, app, orchestrator, temp_db):
        """Test executing a valid SELECT query."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/plugin/traces/query",
                json={
                    "query": "SELECT name, service FROM spans WHERE service = 'Flock'"
                },
            )

            assert response.status_code == 200
            result = response.json()
            assert "results" in result
            assert result["row_count"] == 1
            assert result["results"][0]["name"] == "Flock.publish"
            assert result["results"][0]["service"] == "Flock"

    @pytest.mark.asyncio
    async def test_execute_trace_query_empty_query(self, app, orchestrator, temp_db):
        """Test executing an empty query."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post("/api/plugin/traces/query", json={"query": ""})

            assert response.status_code == 200
            result = response.json()
            assert result["error"] == "Query cannot be empty"
            assert result["results"] == []

    @pytest.mark.asyncio
    async def test_execute_trace_query_non_select(self, app, orchestrator, temp_db):
        """Test executing a non-SELECT query."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/plugin/traces/query", json={"query": "DELETE FROM spans"}
            )

            assert response.status_code == 200
            result = response.json()
            assert result["error"] == "Only SELECT queries are allowed"

    @pytest.mark.asyncio
    async def test_execute_trace_query_dangerous_keywords(
        self, app, orchestrator, temp_db
    ):
        """Test that queries with dangerous keywords are rejected."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            dangerous_queries = [
                "SELECT * FROM spans; DROP TABLE spans",
                "SELECT * FROM spans WHERE name = 'test' INSERT INTO spans VALUES (...)",
                "SELECT * FROM spans; UPDATE spans SET name = 'hacked'",
                "SELECT * FROM spans; ALTER TABLE spans ADD COLUMN bad TEXT",
                "SELECT * FROM spans; CREATE TABLE malicious (id INT)",
                "SELECT * FROM spans; TRUNCATE TABLE spans",
            ]

            for query in dangerous_queries:
                response = await client.post(
                    "/api/plugin/traces/query", json={"query": query}
                )

                assert response.status_code == 200
                result = response.json()
                assert result["error"] == "Query contains forbidden operations"

    @pytest.mark.asyncio
    async def test_execute_trace_query_db_not_found(self, app, orchestrator):
        """Test query execution when database doesn't exist."""
        component = TracingComponent()
        component._db_path_exists = False
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/plugin/traces/query",
                json={"query": "SELECT * FROM spans"},
            )

            assert response.status_code == 200
            result = response.json()
            assert result["error"] == "Trace database not found"

    @pytest.mark.asyncio
    async def test_execute_trace_query_sql_error(self, app, orchestrator, temp_db):
        """Test query execution with SQL error."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/plugin/traces/query",
                json={"query": "SELECT * FROM nonexistent_table"},
            )

            assert response.status_code == 200
            result = response.json()
            assert "error" in result
            assert result["results"] == []

    @pytest.mark.asyncio
    async def test_get_trace_stats_success(self, app, orchestrator, temp_db):
        """Test successful retrieval of trace statistics."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces/stats")

            assert response.status_code == 200
            stats = response.json()
            # Note: total_spans returns a tuple, so we need to check the structure
            assert stats["total_traces"] == 2
            assert stats["services_count"] == 3
            assert stats["oldest_trace"] is not None
            assert stats["newest_trace"] is not None
            assert stats["database_size_mb"] > 0

    @pytest.mark.asyncio
    async def test_get_trace_stats_db_not_found(self, app, orchestrator):
        """Test get_trace_stats when database doesn't exist."""
        component = TracingComponent()
        component._db_path_exists = False
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/traces/stats")

            assert response.status_code == 200
            stats = response.json()
            assert stats["total_spans"] == 0
            assert stats["total_traces"] == 0
            assert stats["services_count"] == 0
            assert stats["oldest_trace"] is None
            assert stats["newest_trace"] is None
            assert stats["database_size_mb"] == 0

    @pytest.mark.asyncio
    async def test_get_streaming_history_success(self, app, orchestrator):
        """Test successful retrieval of streaming history."""
        # Mock WebSocketManager
        mock_event = StreamingOutputEvent(
            correlation_id="test-correlation",
            timestamp=datetime.now(UTC).isoformat(),
            agent_name="test_agent",
            run_id="test-run-001",
            output_type="llm_token",
            content="test content",
            sequence=0,
            is_final=False,
        )

        component = TracingComponent()
        component.websocket_manager = AsyncMock()
        component.websocket_manager.get_streaming_history.return_value = [mock_event]
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/streaming-history/test_agent")

            assert response.status_code == 200
            data = response.json()
            assert data["agent_name"] == "test_agent"
            assert len(data["events"]) == 1
            assert data["events"][0]["content"] == "test content"

    @pytest.mark.asyncio
    async def test_get_streaming_history_exception(self, app, orchestrator):
        """Test get_streaming_history with exception."""
        component = TracingComponent()
        component.websocket_manager = AsyncMock()
        component.websocket_manager.get_streaming_history.side_effect = Exception(
            "Test error"
        )
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/streaming-history/test_agent")

            assert response.status_code == 500
            assert "Failed to get streaming history" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_message_history_success(self, app, orchestrator):
        """Test successful retrieval of message history."""
        # Create mock artifacts
        artifact1 = Artifact(
            type="TestType",
            payload={"data": "test1"},
            produced_by="test_agent",
            visibility=PublicVisibility(),
        )

        artifact2 = Artifact(
            type="TestType",
            payload={"data": "test2"},
            produced_by="other_agent",
            visibility=PublicVisibility(),
        )

        # Mock the store's query_artifacts method
        orchestrator.store = AsyncMock()

        # Mock second call (all artifacts with consumption metadata)
        orchestrator.store.query_artifacts = AsyncMock()
        orchestrator.store.query_artifacts.side_effect = [
            ([artifact1], 1),  # First call: produced by test_agent
            (
                [  # Second call: all artifacts with consumption metadata
                    ArtifactEnvelope(
                        artifact=artifact2,
                        consumptions=[
                            ConsumptionRecord(
                                artifact_id=artifact2.id,
                                consumer="test_agent",
                                consumed_at=datetime.now(UTC),
                            )
                        ],
                    )
                ],
                1,
            ),
        ]

        component = TracingComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/artifacts/history/test_agent")

            assert response.status_code == 200
            data = response.json()
            assert data["node_id"] == "test_agent"
            assert len(data["messages"]) == 2
            assert data["total"] == 2

            # Check produced message
            produced = next(
                m for m in data["messages"] if m["direction"] == "published"
            )
            assert produced["produced_by"] == "test_agent"

            # Check consumed message
            consumed = next(m for m in data["messages"] if m["direction"] == "consumed")
            assert consumed["produced_by"] == "other_agent"
            assert "consumed_at" in consumed

    @pytest.mark.asyncio
    async def test_get_message_history_exception(self, app, orchestrator):
        """Test get_message_history with exception."""
        orchestrator.store = AsyncMock()
        orchestrator.store.query_artifacts.side_effect = Exception("Test error")

        component = TracingComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/artifacts/history/test_agent")

            assert response.status_code == 500
            assert "Failed to get message histor" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_agent_runs(self, app, orchestrator):
        """Test get_agent_runs returns empty array (future implementation)."""
        component = TracingComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/agents/test_agent/runs")

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "test_agent"
            assert data["runs"] == []
            assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_on_startup_async(self, orchestrator):
        """Test on_startup_async is a no-op."""
        component = TracingComponent()
        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async(self, orchestrator):
        """Test on_shutdown_async is a no-op."""
        component = TracingComponent()
        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies(self):
        """Test get_dependencies returns empty list."""
        component = TracingComponent()
        assert component.get_dependencies() == []

    @pytest.mark.asyncio
    async def test_custom_prefix_in_routes(self, app, orchestrator, temp_db):
        """Test that custom prefix is applied to all routes."""
        config = TracingComponentConfig(prefix="/custom/api/", db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Test traces endpoint with custom prefix
            response = await client.get("/custom/api/traces")
            assert response.status_code == 200

            # Test services endpoint with custom prefix
            response = await client.get("/custom/api/traces/services")
            assert response.status_code == 200

            # Test stats endpoint with custom prefix
            response = await client.get("/custom/api/traces/stats")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_with_bytes_conversion(self, app, orchestrator, temp_db):
        """Test that query results convert bytes to strings."""
        config = TracingComponentConfig(db_path=temp_db)
        component = TracingComponent(config=config)
        component.configure(app, orchestrator)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # This query will return results with various types
            response = await client.post(
                "/api/plugin/traces/query",
                json={"query": "SELECT name, service, duration_ms FROM spans LIMIT 1"},
            )

            assert response.status_code == 200
            result = response.json()
            assert len(result["results"]) > 0
            # Verify data is JSON-serializable
            assert isinstance(result["results"][0]["name"], str)

    @pytest.mark.asyncio
    async def test_message_history_with_correlation_id(self, app, orchestrator):
        """Test message history includes correlation_id when present."""
        artifact = Artifact(
            type="TestType",
            payload={"data": "test"},
            produced_by="test_agent",
            visibility=PublicVisibility(),
        )
        # Manually set correlation_id (normally set during publish)
        artifact.correlation_id = "test-correlation-123"

        orchestrator.store = AsyncMock()
        orchestrator.store.query_artifacts.side_effect = [
            ([artifact], 1),
            ([], 0),
        ]

        component = TracingComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/artifacts/history/test_agent")

            assert response.status_code == 200
            data = response.json()
            assert data["messages"][0]["correlation_id"] == "test-correlation-123"

    @pytest.mark.asyncio
    async def test_message_history_without_correlation_id(self, app, orchestrator):
        """Test message history handles missing correlation_id."""
        artifact = Artifact(
            type="TestType",
            payload={"data": "test"},
            produced_by="test_agent",
            visibility=PublicVisibility(),
        )
        # Ensure no correlation_id
        artifact.correlation_id = None

        orchestrator.store = AsyncMock()
        orchestrator.store.query_artifacts.side_effect = [
            ([artifact], 1),
            ([], 0),
        ]

        component = TracingComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/plugin/artifacts/history/test_agent")

            assert response.status_code == 200
            data = response.json()
            assert data["messages"][0]["correlation_id"] is None

    @pytest.mark.asyncio
    async def test_trace_stats_with_empty_database(self, app, orchestrator):
        """Test trace stats with empty database (no spans)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "empty_traces.duckdb"

            # Create empty database
            conn = duckdb.connect(str(db_path))
            conn.execute("""
                CREATE TABLE spans (
                    trace_id VARCHAR NOT NULL,
                    span_id VARCHAR PRIMARY KEY,
                    parent_id VARCHAR,
                    name VARCHAR NOT NULL,
                    service VARCHAR,
                    operation VARCHAR,
                    kind VARCHAR,
                    start_time BIGINT NOT NULL,
                    end_time BIGINT NOT NULL,
                    duration_ms DOUBLE NOT NULL,
                    status_code VARCHAR NOT NULL,
                    status_description VARCHAR,
                    attributes JSON,
                    events JSON,
                    links JSON,
                    resource JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.close()

            config = TracingComponentConfig(db_path=db_path)
            component = TracingComponent(config=config)
            component.configure(app, orchestrator)
            component.register_routes(app, orchestrator)

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                response = await client.get("/api/plugin/traces/stats")

                assert response.status_code == 200
                stats = response.json()
                assert stats["total_traces"] == 0
                assert stats["services_count"] == 0
                assert stats["oldest_trace"] is None
                assert stats["newest_trace"] is None
