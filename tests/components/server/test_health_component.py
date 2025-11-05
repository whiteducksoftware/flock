"""Comprehensive tests for HealthAndMetricsComponent."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flock.components.server.health import (
    HealthAndMetricsComponent,
    HealthComponentConfig,
    HealthResponse,
)
from flock.core.orchestrator import Flock


@pytest.fixture
def orchestrator():
    """Create a test orchestrator."""
    return Flock("openai/gpt-4o")


@pytest.fixture
def app():
    """Create a FastAPI app."""
    return FastAPI()


class TestHealthComponentConfig:
    """Tests for HealthComponentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = HealthComponentConfig()

        assert config.enabled is True
        assert config.prefix is None
        assert config.tags == ["Health & Metrics"]

    def test_custom_prefix(self):
        """Test custom prefix."""
        config = HealthComponentConfig(prefix="/api/v1")

        assert config.prefix == "/api/v1"

    def test_custom_tags(self):
        """Test custom tags."""
        config = HealthComponentConfig(tags=["Custom", "Health"])

        assert config.tags == ["Custom", "Health"]


class TestHealthAndMetricsComponent:
    """Tests for HealthAndMetricsComponent."""

    def test_init_defaults(self):
        """Test component initialization with defaults."""
        component = HealthAndMetricsComponent()

        assert component.name == "health"
        assert component.priority == 0  # Should be first
        assert component.config.enabled is True

    def test_init_custom_config(self):
        """Test component initialization with custom config."""
        config = HealthComponentConfig(prefix="/custom", tags=["Custom"])
        component = HealthAndMetricsComponent(config=config)

        assert component.config.prefix == "/custom"
        assert component.config.tags == ["Custom"]

    def test_configure_no_op(self, app, orchestrator):
        """Test that configure is a no-op."""
        component = HealthAndMetricsComponent()

        # Should not raise or modify anything
        component.configure(app, orchestrator)

    @pytest.mark.asyncio
    async def test_health_endpoint_no_prefix(self, app, orchestrator):
        """Test health endpoint without prefix."""
        component = HealthAndMetricsComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_endpoint_with_prefix(self, app, orchestrator):
        """Test health endpoint with prefix."""
        config = HealthComponentConfig(prefix="/api/v1")
        component = HealthAndMetricsComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/v1/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_metrics_endpoint_no_prefix(self, app, orchestrator):
        """Test metrics endpoint without prefix."""
        # Add some metrics to orchestrator
        orchestrator.metrics["agent_runs"] = 42
        orchestrator.metrics["artifacts_published"] = 100

        component = HealthAndMetricsComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/metrics")

            assert response.status_code == 200
            content = response.text

            assert "blackboard_agent_runs 42" in content
            assert "blackboard_artifacts_published 100" in content

    @pytest.mark.asyncio
    async def test_metrics_endpoint_with_prefix(self, app, orchestrator):
        """Test metrics endpoint with prefix."""
        orchestrator.metrics["test_metric"] = 123

        config = HealthComponentConfig(prefix="/api/v1")
        component = HealthAndMetricsComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/api/v1/metrics")

            assert response.status_code == 200
            content = response.text
            assert "blackboard_test_metric 123" in content

    @pytest.mark.asyncio
    async def test_metrics_empty_orchestrator(self, app, orchestrator):
        """Test metrics endpoint with no metrics."""
        # Clear any default metrics
        orchestrator.metrics.clear()

        component = HealthAndMetricsComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/metrics")

            assert response.status_code == 200
            content = response.text
            assert content == ""  # No metrics

    @pytest.mark.asyncio
    async def test_on_startup_async_no_op(self, orchestrator):
        """Test that on_startup_async is a no-op."""
        component = HealthAndMetricsComponent()

        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async_no_op(self, orchestrator):
        """Test that on_shutdown_async is a no-op."""
        component = HealthAndMetricsComponent()

        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies_none(self):
        """Test that component has no dependencies."""
        component = HealthAndMetricsComponent()

        deps = component.get_dependencies()

        assert deps == []


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response_default(self):
        """Test HealthResponse with default values."""
        response = HealthResponse()

        # Should have a status field (exact default depends on model)
        assert hasattr(response, "status")

    def test_health_response_ok_status(self):
        """Test HealthResponse with ok status."""
        response = HealthResponse(status="ok")

        assert response.status == "ok"

    def test_health_response_serialization(self):
        """Test that HealthResponse can be serialized."""
        response = HealthResponse(status="ok")

        # Should be serializable to dict
        data = response.model_dump()
        assert isinstance(data, dict)
        assert data["status"] == "ok"


class TestHealthAndMetricsIntegration:
    """Integration tests for HealthAndMetricsComponent."""

    @pytest.mark.asyncio
    async def test_both_endpoints_work_together(self, app, orchestrator):
        """Test that health and metrics endpoints work together."""
        orchestrator.metrics["total_requests"] = 999

        component = HealthAndMetricsComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Health check
            health_resp = await client.get("/health")
            assert health_resp.status_code == 200
            assert health_resp.json()["status"] == "ok"

            # Metrics
            metrics_resp = await client.get("/metrics")
            assert metrics_resp.status_code == 200
            assert "blackboard_total_requests 999" in metrics_resp.text

    @pytest.mark.asyncio
    async def test_with_prefix_both_endpoints(self, app, orchestrator):
        """Test both endpoints with prefix."""
        orchestrator.metrics["count"] = 5

        config = HealthComponentConfig(prefix="/monitoring")
        component = HealthAndMetricsComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Health at prefixed path
            health_resp = await client.get("/monitoring/health")
            assert health_resp.status_code == 200

            # Metrics at prefixed path
            metrics_resp = await client.get("/monitoring/metrics")
            assert metrics_resp.status_code == 200
            assert "blackboard_count 5" in metrics_resp.text

            # Original paths should 404
            resp = await client.get("/health")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_metrics_updates_reflected(self, app, orchestrator):
        """Test that metric updates are reflected in endpoint."""
        component = HealthAndMetricsComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Set initial metric
            orchestrator.metrics["dynamic"] = 10
            resp1 = await client.get("/metrics")
            assert "blackboard_dynamic 10" in resp1.text

            # Update metric
            orchestrator.metrics["dynamic"] = 20
            resp2 = await client.get("/metrics")
            assert "blackboard_dynamic 20" in resp2.text

    @pytest.mark.asyncio
    async def test_multiple_metrics(self, app, orchestrator):
        """Test metrics endpoint with multiple values."""
        orchestrator.metrics.clear()
        orchestrator.metrics["metric_a"] = 1
        orchestrator.metrics["metric_b"] = 2
        orchestrator.metrics["metric_c"] = 3

        component = HealthAndMetricsComponent()
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/metrics")

            content = response.text
            lines = content.split("\n")

            assert "blackboard_metric_a 1" in lines
            assert "blackboard_metric_b 2" in lines
            assert "blackboard_metric_c 3" in lines
