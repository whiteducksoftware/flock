"""Test version endpoint for dashboard API."""

from importlib.metadata import version as get_version

import pytest
from httpx import ASGITransport, AsyncClient

from flock.core import Flock
from flock.dashboard.service import DashboardHTTPService


@pytest.mark.asyncio
async def test_version_endpoint():
    """Test that version endpoint returns correct version information."""
    # Create orchestrator and service
    orchestrator = Flock()
    service = DashboardHTTPService(orchestrator)
    app = service.get_app()

    # Create test client
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Request version endpoint
        response = await client.get("/api/version")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "backend_version" in data
        assert "package_name" in data

        # Verify package name
        assert data["package_name"] == "flock-flow"

        # Verify version matches actual package version
        try:
            expected_version = get_version("flock-flow")
            assert data["backend_version"] == expected_version
        except Exception:
            # If package not installed, should return dev version
            assert data["backend_version"] in ["0.2.0-dev", "0.1.18"]


@pytest.mark.asyncio
async def test_version_endpoint_format():
    """Test that version endpoint returns proper format."""
    orchestrator = Flock()
    service = DashboardHTTPService(orchestrator)
    app = service.get_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/version")
        data = response.json()

        # Verify version string format (semver-like)
        version_str = data["backend_version"]
        assert isinstance(version_str, str)
        assert len(version_str) > 0

        # Should contain digits
        assert any(c.isdigit() for c in version_str)
