"""Comprehensive tests for CORSComponent."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flock.components.server.cors import (
    CORSComponent,
    CORSComponentConfig,
    RouteSpecificCORSConfig,
)
from flock.core.orchestrator import Flock


@pytest.fixture
def orchestrator():
    """Create a test orchestrator."""
    return Flock("openai/gpt-4o")


@pytest.fixture
def app():
    """Create a FastAPI app."""
    app = FastAPI()

    # Add a test endpoint
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/api/public/test")
    async def public_test():
        return {"public": True}

    @app.get("/api/private/test")
    async def private_test():
        return {"private": True}

    return app


class TestRouteSpecificCORSConfig:
    """Tests for RouteSpecificCORSConfig."""

    def test_default_values(self):
        """Test default values for route-specific config."""
        config = RouteSpecificCORSConfig(path_pattern="^/api/.*")

        assert config.path_pattern == "^/api/.*"
        assert config.allow_origins == ["*"]
        assert config.allow_methods == ["GET"]
        assert config.allow_headers == ["*"]
        assert config.expose_headers == []
        assert config.allow_credentials is False
        assert config.max_age == 600

    def test_custom_values(self):
        """Test custom values for route-specific config."""
        config = RouteSpecificCORSConfig(
            path_pattern="^/custom/.*",
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Content-Type"],
            expose_headers=["X-Custom-Header"],
            allow_credentials=True,
            max_age=3600,
        )

        assert config.path_pattern == "^/custom/.*"
        assert config.allow_origins == ["https://example.com"]
        assert config.allow_methods == ["GET", "POST", "PUT"]
        assert config.allow_headers == ["Content-Type"]
        assert config.expose_headers == ["X-Custom-Header"]
        assert config.allow_credentials is True
        assert config.max_age == 3600

    def test_invalid_regex_raises(self):
        """Test that invalid regex pattern raises validation error."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            RouteSpecificCORSConfig(path_pattern="[invalid(regex")


class TestCORSComponentConfig:
    """Tests for CORSComponentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CORSComponentConfig()

        assert config.allow_origins == ["*"]
        assert config.allow_origin_regex is None
        assert config.allow_credentials is True
        assert config.allow_methods == ["*"]
        assert config.allow_headers == ["*"]
        assert config.expose_headers == []
        assert config.max_age == 600
        assert config.route_configs == []

    def test_custom_global_settings(self):
        """Test custom global CORS settings."""
        config = CORSComponentConfig(
            allow_origins=["https://example.com", "https://api.example.com"],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization"],
            expose_headers=["X-Request-ID"],
            max_age=3600,
        )

        assert config.allow_origins == [
            "https://example.com",
            "https://api.example.com",
        ]
        assert config.allow_credentials is False
        assert config.allow_methods == ["GET", "POST"]
        assert config.allow_headers == ["Content-Type", "Authorization"]
        assert config.expose_headers == ["X-Request-ID"]
        assert config.max_age == 3600

    def test_allow_origin_regex(self):
        """Test allow_origin_regex configuration."""
        config = CORSComponentConfig(allow_origin_regex=r"https://.*\.example\.com")

        assert config.allow_origin_regex == r"https://.*\.example\.com"

    def test_invalid_origin_regex_raises(self):
        """Test that invalid origin regex raises validation error."""
        with pytest.raises(ValueError, match="Invalid origin regex pattern"):
            CORSComponentConfig(allow_origin_regex="[invalid(regex")

    def test_route_configs(self):
        """Test route-specific configurations."""
        route_config = RouteSpecificCORSConfig(
            path_pattern="^/api/.*", allow_origins=["https://api.example.com"]
        )

        config = CORSComponentConfig(route_configs=[route_config])

        assert len(config.route_configs) == 1
        assert config.route_configs[0].path_pattern == "^/api/.*"


class TestCORSComponent:
    """Tests for CORSComponent."""

    def test_init_defaults(self):
        """Test component initialization with defaults."""
        component = CORSComponent()

        assert component.name == "cors"
        assert component.priority == 8
        assert component.config.allow_origins == ["*"]

    def test_init_custom_config(self):
        """Test component initialization with custom config."""
        config = CORSComponentConfig(
            allow_origins=["https://example.com"], allow_credentials=False
        )
        component = CORSComponent(config=config)

        assert component.config.allow_origins == ["https://example.com"]
        assert component.config.allow_credentials is False

    @pytest.mark.asyncio
    async def test_global_cors_allows_all_origins(self, app, orchestrator):
        """Test global CORS with allow all origins."""
        component = CORSComponent()
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/test", headers={"Origin": "https://example.com"}
            )

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_global_cors_specific_origin(self, app, orchestrator):
        """Test global CORS with specific allowed origin."""
        config = CORSComponentConfig(allow_origins=["https://allowed.com"])
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Allowed origin
            response = await client.get(
                "/test", headers={"Origin": "https://allowed.com"}
            )
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_preflight_request(self, app, orchestrator):
        """Test CORS preflight OPTIONS request."""
        component = CORSComponent()
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.options(
                "/test",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "POST",
                },
            )

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert "access-control-allow-methods" in response.headers

    @pytest.mark.asyncio
    async def test_register_routes_no_op(self, app, orchestrator):
        """Test that register_routes is a no-op."""
        component = CORSComponent()

        # Should not raise or add routes
        component.register_routes(app, orchestrator)

    @pytest.mark.asyncio
    async def test_on_startup_async_no_op(self, orchestrator):
        """Test that on_startup_async is a no-op."""
        component = CORSComponent()

        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async_no_op(self, orchestrator):
        """Test that on_shutdown_async is a no-op."""
        component = CORSComponent()

        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies_none(self):
        """Test that component has no dependencies."""
        component = CORSComponent()

        deps = component.get_dependencies()

        assert deps == []


class TestCORSComponentAdvanced:
    """Advanced tests for CORS functionality."""

    @pytest.mark.asyncio
    async def test_credentials_allowed(self, app, orchestrator):
        """Test that credentials are allowed when configured."""
        config = CORSComponentConfig(
            allow_origins=["https://example.com"], allow_credentials=True
        )
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/test", headers={"Origin": "https://example.com"}
            )

            # Check for credentials header
            assert "access-control-allow-credentials" in response.headers
            assert response.headers["access-control-allow-credentials"] == "true"

    @pytest.mark.asyncio
    async def test_custom_methods(self, app, orchestrator):
        """Test custom allowed methods."""
        config = CORSComponentConfig(allow_methods=["GET", "POST", "DELETE"])
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.options(
                "/test",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "POST",
                },
            )

            assert "access-control-allow-methods" in response.headers

    @pytest.mark.asyncio
    async def test_custom_headers(self, app, orchestrator):
        """Test custom allowed headers."""
        config = CORSComponentConfig(allow_headers=["Content-Type", "X-Custom-Header"])
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.options(
                "/test",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )

            assert "access-control-allow-headers" in response.headers

    @pytest.mark.asyncio
    async def test_expose_headers(self, app, orchestrator):
        """Test expose headers configuration."""
        config = CORSComponentConfig(expose_headers=["X-Request-ID", "X-Total-Count"])
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/test", headers={"Origin": "https://example.com"}
            )

            assert "access-control-expose-headers" in response.headers

    @pytest.mark.asyncio
    async def test_max_age(self, app, orchestrator):
        """Test max age configuration for preflight cache."""
        config = CORSComponentConfig(max_age=7200)
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.options(
                "/test",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

            assert "access-control-max-age" in response.headers
            assert response.headers["access-control-max-age"] == "7200"


class TestCORSComponentRouteSpecific:
    """Tests for route-specific CORS functionality."""

    @pytest.mark.asyncio
    async def test_route_specific_cors_public_route(self, app, orchestrator):
        """Test route-specific CORS for public routes."""
        route_config = RouteSpecificCORSConfig(
            path_pattern="^/api/public/.*",
            allow_origins=["*"],
            allow_credentials=False,
        )
        config = CORSComponentConfig(
            allow_origins=["https://private.com"],
            allow_credentials=True,
            route_configs=[route_config],
        )
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Public route should allow all origins
            response = await client.get(
                "/api/public/test", headers={"Origin": "https://anyone.com"}
            )

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_route_specific_cors_private_route(self, app, orchestrator):
        """Test route-specific CORS falls back to global for non-matching routes."""
        route_config = RouteSpecificCORSConfig(
            path_pattern="^/api/public/.*", allow_origins=["*"]
        )
        config = CORSComponentConfig(
            allow_origins=["https://private.com"], route_configs=[route_config]
        )
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Private route should use global config
            response = await client.get(
                "/api/private/test", headers={"Origin": "https://private.com"}
            )

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_multiple_route_configs(self, app, orchestrator):
        """Test multiple route-specific configurations."""
        public_config = RouteSpecificCORSConfig(
            path_pattern="^/api/public/.*", allow_origins=["*"]
        )
        private_config = RouteSpecificCORSConfig(
            path_pattern="^/api/private/.*",
            allow_origins=["https://trusted.com"],
            allow_credentials=True,
        )

        config = CORSComponentConfig(route_configs=[public_config, private_config])
        component = CORSComponent(config=config)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Test public route
            pub_response = await client.get(
                "/api/public/test", headers={"Origin": "https://anyone.com"}
            )
            assert pub_response.status_code == 200

            # Test private route
            priv_response = await client.get(
                "/api/private/test", headers={"Origin": "https://trusted.com"}
            )
            assert priv_response.status_code == 200
