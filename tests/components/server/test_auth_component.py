"""Comprehensive tests for AuthenticationComponent."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from flock.components.server.auth import (
    AuthenticationComponent,
    AuthenticationComponentConfig,
    RouteSpecificAuthConfig,
)
from flock.core.orchestrator import Flock


@pytest.fixture
def orchestrator():
    """Create a test orchestrator."""
    return Flock("openai/gpt-4o")


@pytest.fixture
def app():
    """Create a FastAPI app with test routes."""
    app = FastAPI()

    @app.get("/public")
    async def public_route():
        return {"public": True}

    @app.get("/api/admin/test")
    async def admin_route():
        return {"admin": True}

    @app.get("/api/user/test")
    async def user_route():
        return {"user": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


class TestRouteSpecificAuthConfig:
    """Tests for RouteSpecificAuthConfig."""

    def test_default_values(self):
        """Test default values for route-specific auth config."""
        config = RouteSpecificAuthConfig(
            path_pattern="^/api/.*", handler_name="api_auth"
        )

        assert config.path_pattern == "^/api/.*"
        assert config.handler_name == "api_auth"
        assert config.enabled is True

    def test_disabled_config(self):
        """Test disabled auth config."""
        config = RouteSpecificAuthConfig(
            path_pattern="^/public/.*", handler_name="public_auth", enabled=False
        )

        assert config.enabled is False

    def test_invalid_regex_raises(self):
        """Test that invalid regex pattern raises validation error."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            RouteSpecificAuthConfig(path_pattern="[invalid(regex", handler_name="test")


class TestAuthenticationComponentConfig:
    """Tests for AuthenticationComponentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AuthenticationComponentConfig()

        assert config.default_handler is None
        assert config.route_configs == []
        assert config.exclude_paths == []

    def test_with_default_handler(self):
        """Test configuration with default handler."""
        config = AuthenticationComponentConfig(default_handler="api_key_auth")

        assert config.default_handler == "api_key_auth"

    def test_with_route_configs(self):
        """Test configuration with route-specific configs."""
        route_config = RouteSpecificAuthConfig(
            path_pattern="^/api/.*", handler_name="api_auth"
        )
        config = AuthenticationComponentConfig(route_configs=[route_config])

        assert len(config.route_configs) == 1
        assert config.route_configs[0].path_pattern == "^/api/.*"

    def test_with_exclude_paths(self):
        """Test configuration with excluded paths."""
        config = AuthenticationComponentConfig(
            exclude_paths=[r"^/health$", r"^/docs.*"]
        )

        assert len(config.exclude_paths) == 2
        assert r"^/health$" in config.exclude_paths

    def test_invalid_exclude_path_raises(self):
        """Test that invalid exclude path regex raises validation error."""
        with pytest.raises(ValueError, match="Invalid exclude path regex pattern"):
            AuthenticationComponentConfig(exclude_paths=["[invalid(regex"])


class TestAuthenticationComponent:
    """Tests for AuthenticationComponent."""

    def test_init_defaults(self):
        """Test component initialization with defaults."""
        component = AuthenticationComponent()

        assert component.name == "authentication"
        assert component.priority == 7
        assert component.config.default_handler is None

    def test_init_custom_config(self):
        """Test component initialization with custom config."""
        config = AuthenticationComponentConfig(default_handler="custom_auth")
        component = AuthenticationComponent(config=config)

        assert component.config.default_handler == "custom_auth"

    def test_register_handler(self):
        """Test registering an authentication handler."""

        async def test_handler(request: Request) -> tuple[bool, Response | None]:
            return True, None

        component = AuthenticationComponent()
        component.register_handler("test_auth", test_handler)

        assert "test_auth" in component._handlers
        assert component._handlers["test_auth"] is test_handler

    def test_register_handler_duplicate_raises(self):
        """Test that registering duplicate handler raises error."""

        async def test_handler(request: Request) -> tuple[bool, Response | None]:
            return True, None

        component = AuthenticationComponent()
        component.register_handler("test_auth", test_handler)

        with pytest.raises(ValueError, match="already registered"):
            component.register_handler("test_auth", test_handler)

    def test_validate_handlers_missing_default(self, app, orchestrator):
        """Test that missing default handler raises error."""
        config = AuthenticationComponentConfig(default_handler="missing_auth")
        component = AuthenticationComponent(config=config)

        with pytest.raises(ValueError, match="not registered"):
            component.configure(app, orchestrator)

    def test_validate_handlers_missing_route_handler(self, app, orchestrator):
        """Test that missing route-specific handler raises error."""
        route_config = RouteSpecificAuthConfig(
            path_pattern="^/api/.*", handler_name="missing_auth"
        )
        config = AuthenticationComponentConfig(route_configs=[route_config])
        component = AuthenticationComponent(config=config)

        with pytest.raises(ValueError, match="not registered"):
            component.configure(app, orchestrator)

    @pytest.mark.asyncio
    async def test_register_routes_no_op(self, app, orchestrator):
        """Test that register_routes is a no-op."""
        component = AuthenticationComponent()

        # Should not raise
        component.register_routes(app, orchestrator)

    @pytest.mark.asyncio
    async def test_on_startup_async_no_op(self, orchestrator):
        """Test that on_startup_async is a no-op."""
        component = AuthenticationComponent()

        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async_no_op(self, orchestrator):
        """Test that on_shutdown_async is a no-op."""
        component = AuthenticationComponent()

        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies_none(self):
        """Test that component has no dependencies."""
        component = AuthenticationComponent()

        deps = component.get_dependencies()

        assert deps == []


class TestAuthenticationMiddleware:
    """Tests for authentication middleware functionality."""

    @pytest.mark.asyncio
    async def test_no_auth_allows_all_requests(self, app, orchestrator):
        """Test that requests are allowed when no auth is configured."""
        component = AuthenticationComponent()
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/public")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_excluded_paths_bypass_auth(self, app, orchestrator):
        """Test that excluded paths bypass authentication."""

        async def always_fail_auth(
            request: Request,
        ) -> tuple[bool, Response | None]:
            return False, JSONResponse({"error": "Unauthorized"}, status_code=401)

        config = AuthenticationComponentConfig(
            default_handler="fail_auth", exclude_paths=[r"^/health$", r"^/public$"]
        )
        component = AuthenticationComponent(config=config)
        component.register_handler("fail_auth", always_fail_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Excluded paths should succeed
            health_resp = await client.get("/health")
            assert health_resp.status_code == 200

            public_resp = await client.get("/public")
            assert public_resp.status_code == 200

            # Non-excluded paths should fail
            admin_resp = await client.get("/api/admin/test")
            assert admin_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_successful_authentication(self, app, orchestrator):
        """Test successful authentication."""

        async def pass_auth(request: Request) -> tuple[bool, Response | None]:
            return True, None

        config = AuthenticationComponentConfig(default_handler="pass_auth")
        component = AuthenticationComponent(config=config)
        component.register_handler("pass_auth", pass_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/public")
            assert response.status_code == 200
            assert response.json() == {"public": True}

    @pytest.mark.asyncio
    async def test_failed_authentication_custom_response(self, app, orchestrator):
        """Test failed authentication with custom error response."""

        async def fail_auth(request: Request) -> tuple[bool, Response | None]:
            return False, JSONResponse({"error": "Invalid API key"}, status_code=403)

        config = AuthenticationComponentConfig(default_handler="fail_auth")
        component = AuthenticationComponent(config=config)
        component.register_handler("fail_auth", fail_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/public")
            assert response.status_code == 403
            assert response.json() == {"error": "Invalid API key"}

    @pytest.mark.asyncio
    async def test_failed_authentication_default_response(self, app, orchestrator):
        """Test failed authentication with default 401 response."""

        async def fail_auth(request: Request) -> tuple[bool, Response | None]:
            return False, None  # No custom response

        config = AuthenticationComponentConfig(default_handler="fail_auth")
        component = AuthenticationComponent(config=config)
        component.register_handler("fail_auth", fail_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/public")
            assert response.status_code == 401
            assert response.json() == {"error": "Unauthorized"}

    @pytest.mark.asyncio
    async def test_route_specific_auth(self, app, orchestrator):
        """Test route-specific authentication."""

        async def admin_auth(request: Request) -> tuple[bool, Response | None]:
            # Check for admin token
            token = request.headers.get("X-Admin-Token")
            if token == "admin-secret":
                return True, None
            return False, JSONResponse({"error": "Admin only"}, status_code=403)

        async def user_auth(request: Request) -> tuple[bool, Response | None]:
            # Check for user token
            token = request.headers.get("X-User-Token")
            if token == "user-secret":
                return True, None
            return False, JSONResponse({"error": "User auth failed"}, status_code=401)

        admin_route = RouteSpecificAuthConfig(
            path_pattern=r"^/api/admin/.*", handler_name="admin_auth"
        )
        user_route = RouteSpecificAuthConfig(
            path_pattern=r"^/api/user/.*", handler_name="user_auth"
        )

        config = AuthenticationComponentConfig(route_configs=[admin_route, user_route])
        component = AuthenticationComponent(config=config)
        component.register_handler("admin_auth", admin_auth)
        component.register_handler("user_auth", user_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Admin route with correct token
            admin_resp = await client.get(
                "/api/admin/test", headers={"X-Admin-Token": "admin-secret"}
            )
            assert admin_resp.status_code == 200

            # Admin route with wrong token
            admin_fail = await client.get(
                "/api/admin/test", headers={"X-Admin-Token": "wrong"}
            )
            assert admin_fail.status_code == 403

            # User route with correct token
            user_resp = await client.get(
                "/api/user/test", headers={"X-User-Token": "user-secret"}
            )
            assert user_resp.status_code == 200

            # User route with wrong token
            user_fail = await client.get(
                "/api/user/test", headers={"X-User-Token": "wrong"}
            )
            assert user_fail.status_code == 401

    @pytest.mark.asyncio
    async def test_disabled_route_auth(self, app, orchestrator):
        """Test that disabled route-specific auth allows requests."""

        async def fail_auth(request: Request) -> tuple[bool, Response | None]:
            return False, JSONResponse({"error": "No access"}, status_code=403)

        # Admin auth is disabled
        admin_route = RouteSpecificAuthConfig(
            path_pattern=r"^/api/admin/.*", handler_name="fail_auth", enabled=False
        )

        config = AuthenticationComponentConfig(
            default_handler="fail_auth", route_configs=[admin_route]
        )
        component = AuthenticationComponent(config=config)
        component.register_handler("fail_auth", fail_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Admin route should succeed (auth disabled)
            admin_resp = await client.get("/api/admin/test")
            assert admin_resp.status_code == 200

            # Other routes should fail (default handler applies)
            public_resp = await client.get("/public")
            assert public_resp.status_code == 403

    @pytest.mark.asyncio
    async def test_handler_exception_returns_500(self, app, orchestrator):
        """Test that handler exceptions return 500."""

        async def broken_auth(request: Request) -> tuple[bool, Response | None]:
            raise RuntimeError("Auth handler crashed!")

        config = AuthenticationComponentConfig(default_handler="broken_auth")
        component = AuthenticationComponent(config=config)
        component.register_handler("broken_auth", broken_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/public")
            assert response.status_code == 500
            assert "Internal authentication error" in response.json()["error"]


class TestAuthenticationIntegration:
    """Integration tests for authentication component."""

    @pytest.mark.asyncio
    async def test_api_key_authentication(self, app, orchestrator):
        """Test realistic API key authentication."""

        VALID_API_KEYS = {"secret-key-1", "secret-key-2"}

        async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
            api_key = request.headers.get("X-API-Key")
            if api_key in VALID_API_KEYS:
                return True, None
            return False, JSONResponse(
                {"error": "Invalid API key", "code": "INVALID_API_KEY"},
                status_code=401,
            )

        config = AuthenticationComponentConfig(
            default_handler="api_key", exclude_paths=[r"^/health$"]
        )
        component = AuthenticationComponent(config=config)
        component.register_handler("api_key", api_key_auth)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Valid API key
            valid_resp = await client.get(
                "/public", headers={"X-API-Key": "secret-key-1"}
            )
            assert valid_resp.status_code == 200

            # Invalid API key
            invalid_resp = await client.get(
                "/public", headers={"X-API-Key": "wrong-key"}
            )
            assert invalid_resp.status_code == 401
            assert invalid_resp.json()["code"] == "INVALID_API_KEY"

            # No API key
            no_key_resp = await client.get("/public")
            assert no_key_resp.status_code == 401

            # Health endpoint bypasses auth
            health_resp = await client.get("/health")
            assert health_resp.status_code == 200
