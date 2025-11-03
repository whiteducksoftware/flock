"""Comprehensive tests for MiddlewareComponent."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flock.components.server.middleware import (
    MiddlewareComponent,
    MiddlewareComponentConfig,
    MiddlewareConfig,
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

    @app.get("/test")
    async def test_route():
        return {"status": "ok"}

    return app


class TestMiddlewareConfig:
    """Tests for MiddlewareConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MiddlewareConfig(name="test_middleware")

        assert config.name == "test_middleware"
        assert config.options == {}
        assert config.enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MiddlewareConfig(
            name="custom_middleware",
            options={"option1": "value1", "option2": 42},
            enabled=False,
        )

        assert config.name == "custom_middleware"
        assert config.options == {"option1": "value1", "option2": 42}
        assert config.enabled is False


class TestMiddlewareComponentConfig:
    """Tests for MiddlewareComponentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MiddlewareComponentConfig()

        assert config.middlewares == []

    def test_with_middleware_configs(self):
        """Test configuration with middleware configs."""
        middleware1 = MiddlewareConfig(name="middleware1")
        middleware2 = MiddlewareConfig(name="middleware2")

        config = MiddlewareComponentConfig(middlewares=[middleware1, middleware2])

        assert len(config.middlewares) == 2
        assert config.middlewares[0].name == "middleware1"
        assert config.middlewares[1].name == "middleware2"


class TestMiddlewareComponent:
    """Tests for MiddlewareComponent."""

    def test_init_defaults(self):
        """Test component initialization with defaults."""
        component = MiddlewareComponent()

        assert component.name == "middleware"
        assert component.priority == 6
        assert component.config.middlewares == []

    def test_init_custom_config(self):
        """Test component initialization with custom config."""
        middleware_config = MiddlewareConfig(name="custom")
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)

        assert len(component.config.middlewares) == 1
        assert component.config.middlewares[0].name == "custom"

    def test_register_middleware(self):
        """Test registering a middleware factory."""

        def test_factory(app):
            return lambda: None

        component = MiddlewareComponent()
        component.register_middleware("test_middleware", test_factory)

        assert "test_middleware" in component._factories
        assert component._factories["test_middleware"] is test_factory

    def test_register_middleware_duplicate_raises(self):
        """Test that registering duplicate middleware raises error."""

        def test_factory(app):
            return lambda: None

        component = MiddlewareComponent()
        component.register_middleware("test_middleware", test_factory)

        with pytest.raises(ValueError, match="already registered"):
            component.register_middleware("test_middleware", test_factory)

    def test_validate_factories_missing_raises(self, app, orchestrator):
        """Test that missing middleware factory raises error."""
        middleware_config = MiddlewareConfig(name="missing_middleware")
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)

        with pytest.raises(ValueError, match="not registered"):
            component.configure(app, orchestrator)

    @pytest.mark.asyncio
    async def test_register_routes_no_op(self, app, orchestrator):
        """Test that register_routes is a no-op."""
        component = MiddlewareComponent()

        # Should not raise
        component.register_routes(app, orchestrator)

    @pytest.mark.asyncio
    async def test_on_startup_async_no_op(self, orchestrator):
        """Test that on_startup_async is a no-op."""
        component = MiddlewareComponent()

        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async_no_op(self, orchestrator):
        """Test that on_shutdown_async is a no-op."""
        component = MiddlewareComponent()

        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies_none(self):
        """Test that component has no dependencies."""
        component = MiddlewareComponent()

        deps = component.get_dependencies()

        assert deps == []


class TestMiddlewareExecution:
    """Tests for middleware execution."""

    @pytest.mark.asyncio
    async def test_simple_middleware(self, app, orchestrator):
        """Test simple middleware that adds a header."""
        executed = []

        def header_middleware_factory(asgi_app):
            def factory(**options):
                class HeaderMiddleware:
                    def __init__(self, app):
                        self.app = app

                    async def __call__(self, scope, receive, send):
                        executed.append("middleware_called")

                        async def send_wrapper(message):
                            if message["type"] == "http.response.start":
                                headers = list(message.get("headers", []))
                                headers.append((b"x-custom-header", b"test-value"))
                                message["headers"] = headers
                            await send(message)

                        await self.app(scope, receive, send_wrapper)

                return HeaderMiddleware(asgi_app)

            return factory

        middleware_config = MiddlewareConfig(name="header_middleware")
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)
        component.register_middleware("header_middleware", header_middleware_factory)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/test")

            assert response.status_code == 200
            assert "x-custom-header" in response.headers
            assert response.headers["x-custom-header"] == "test-value"
            assert len(executed) > 0

    @pytest.mark.asyncio
    async def test_middleware_with_options(self, app, orchestrator):
        """Test middleware that uses configuration options."""

        def configurable_middleware_factory(asgi_app):
            def factory(**options):
                header_name = options.get("header_name", "x-default")
                header_value = options.get("header_value", "default")

                class ConfigurableMiddleware:
                    def __init__(self, app):
                        self.app = app
                        self.header_name = header_name
                        self.header_value = header_value

                    async def __call__(self, scope, receive, send):
                        async def send_wrapper(message):
                            if message["type"] == "http.response.start":
                                headers = list(message.get("headers", []))
                                headers.append((
                                    self.header_name.encode(),
                                    self.header_value.encode(),
                                ))
                                message["headers"] = headers
                            await send(message)

                        await self.app(scope, receive, send_wrapper)

                return ConfigurableMiddleware(asgi_app)

            return factory

        middleware_config = MiddlewareConfig(
            name="configurable",
            options={"header_name": "x-app-version", "header_value": "1.0.0"},
        )
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)
        component.register_middleware("configurable", configurable_middleware_factory)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/test")

            assert response.status_code == 200
            assert "x-app-version" in response.headers
            assert response.headers["x-app-version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_multiple_middleware_order(self, app, orchestrator):
        """Test that multiple middleware execute in correct order."""
        execution_order = []

        def create_tracking_middleware(name):
            def factory(asgi_app):
                def inner_factory(**options):
                    class TrackingMiddleware:
                        def __init__(self, app):
                            self.app = app
                            self.name = name

                        async def __call__(self, scope, receive, send):
                            execution_order.append(f"{self.name}_before")
                            await self.app(scope, receive, send)
                            execution_order.append(f"{self.name}_after")

                    return TrackingMiddleware(asgi_app)

                return inner_factory

            return factory

        # Register middleware in specific order
        middleware1 = MiddlewareConfig(name="first")
        middleware2 = MiddlewareConfig(name="second")
        middleware3 = MiddlewareConfig(name="third")

        config = MiddlewareComponentConfig(
            middlewares=[middleware1, middleware2, middleware3]
        )
        component = MiddlewareComponent(config=config)
        component.register_middleware("first", create_tracking_middleware("first"))
        component.register_middleware("second", create_tracking_middleware("second"))
        component.register_middleware("third", create_tracking_middleware("third"))
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            await client.get("/test")

            # First middleware is outermost, so it executes first on the way in
            # and last on the way out
            assert execution_order[0] == "first_before"
            assert execution_order[-1] == "first_after"

    @pytest.mark.asyncio
    async def test_disabled_middleware_not_executed(self, app, orchestrator):
        """Test that disabled middleware is not executed."""
        executed = []

        def tracking_middleware_factory(app):
            class TrackingMiddleware:
                def __init__(self, asgi_app):
                    self.app = asgi_app

                async def __call__(self, scope, receive, send):
                    executed.append("middleware_called")
                    await self.app(scope, receive, send)

            return TrackingMiddleware

        middleware_config = MiddlewareConfig(name="tracking", enabled=False)
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)
        component.register_middleware("tracking", tracking_middleware_factory)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            await client.get("/test")

            # Middleware was disabled, should not execute
            assert len(executed) == 0


class TestMiddlewareIntegration:
    """Integration tests for middleware component."""

    @pytest.mark.asyncio
    async def test_logging_middleware(self, app, orchestrator):
        """Test realistic logging middleware."""
        logs = []

        def logging_middleware_factory(asgi_app):
            def factory(**options):
                class LoggingMiddleware:
                    def __init__(self, app):
                        self.app = app

                    async def __call__(self, scope, receive, send):
                        if scope["type"] == "http":
                            method = scope["method"]
                            path = scope["path"]
                            logs.append(f"{method} {path}")

                        await self.app(scope, receive, send)

                return LoggingMiddleware(asgi_app)

            return factory

        middleware_config = MiddlewareConfig(name="logging")
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)
        component.register_middleware("logging", logging_middleware_factory)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            await client.get("/test")

            assert len(logs) == 1
            assert "GET /test" in logs[0]

    @pytest.mark.asyncio
    async def test_request_id_middleware(self, app, orchestrator):
        """Test middleware that adds request ID."""
        request_id_counter = [0]

        def request_id_middleware_factory(asgi_app):
            def factory(**options):
                class RequestIDMiddleware:
                    def __init__(self, app):
                        self.app = app

                    async def __call__(self, scope, receive, send):
                        request_id_counter[0] += 1
                        request_id = f"req-{request_id_counter[0]}"

                        async def send_wrapper(message):
                            if message["type"] == "http.response.start":
                                headers = list(message.get("headers", []))
                                headers.append((b"x-request-id", request_id.encode()))
                                message["headers"] = headers
                            await send(message)

                        await self.app(scope, receive, send_wrapper)

                return RequestIDMiddleware(asgi_app)

            return factory

        middleware_config = MiddlewareConfig(name="request_id")
        config = MiddlewareComponentConfig(middlewares=[middleware_config])
        component = MiddlewareComponent(config=config)
        component.register_middleware("request_id", request_id_middleware_factory)
        component.configure(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response1 = await client.get("/test")
            response2 = await client.get("/test")

            assert "x-request-id" in response1.headers
            assert "x-request-id" in response2.headers
            assert response1.headers["x-request-id"] == "req-1"
            assert response2.headers["x-request-id"] == "req-2"
