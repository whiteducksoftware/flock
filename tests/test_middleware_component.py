"""Tests for MiddlewareComponent."""

import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from flock.components.server.middleware import (
    MiddlewareComponent,
    MiddlewareComponentConfig,
    MiddlewareConfig,
)


class CustomTestMiddleware(BaseHTTPMiddleware):
    """Test middleware that adds a custom header."""

    def __init__(self, app: ASGIApp, header_value: str = "test"):
        super().__init__(app)
        self.header_value = header_value

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Test"] = self.header_value
        return response


def create_test_middleware_factory(app: ASGIApp):
    """Factory for test middleware."""

    def factory(**options):
        header_value = options.get("header_value", "test")
        return CustomTestMiddleware(app, header_value=header_value)

    return factory


class TestMiddlewareComponent:
    """Test suite for MiddlewareComponent."""

    def test_component_creation(self):
        """Test basic component creation."""
        component = MiddlewareComponent()
        assert component.name == "middleware"
        assert component.priority == 6
        assert isinstance(component.config, MiddlewareComponentConfig)

    def test_component_with_config(self):
        """Test component creation with configuration."""
        config = MiddlewareComponentConfig(
            middlewares=[
                MiddlewareConfig(name="test", options={"key": "value"}),
            ]
        )
        component = MiddlewareComponent(config=config)
        assert len(component.config.middlewares) == 1
        assert component.config.middlewares[0].name == "test"
        assert component.config.middlewares[0].options == {"key": "value"}

    def test_register_middleware(self):
        """Test registering middleware factories."""
        component = MiddlewareComponent()
        component.register_middleware("test", create_test_middleware_factory)
        assert "test" in component._factories

    def test_register_duplicate_middleware_raises(self):
        """Test that registering duplicate middleware raises error."""
        component = MiddlewareComponent()
        component.register_middleware("test", create_test_middleware_factory)

        with pytest.raises(ValueError, match="already registered"):
            component.register_middleware("test", create_test_middleware_factory)

    def test_validate_missing_factory(self):
        """Test that validation fails if factory is not registered."""
        config = MiddlewareComponentConfig(
            middlewares=[
                MiddlewareConfig(name="missing_factory"),
            ]
        )
        component = MiddlewareComponent(config=config)

        with pytest.raises(ValueError, match="not registered"):
            component._validate_factories()

    def test_validate_with_disabled_middleware(self):
        """Test that disabled middleware don't require factories."""
        config = MiddlewareComponentConfig(
            middlewares=[
                MiddlewareConfig(name="missing_factory", enabled=False),
            ]
        )
        component = MiddlewareComponent(config=config)
        # Should not raise because middleware is disabled
        component._validate_factories()

    def test_middleware_config_defaults(self):
        """Test MiddlewareConfig default values."""
        config = MiddlewareConfig(name="test")
        assert config.name == "test"
        assert config.options == {}
        assert config.enabled is True

    def test_middleware_config_with_options(self):
        """Test MiddlewareConfig with custom options."""
        config = MiddlewareConfig(
            name="test", options={"key1": "value1", "key2": 42}, enabled=False
        )
        assert config.name == "test"
        assert config.options == {"key1": "value1", "key2": 42}
        assert config.enabled is False

    def test_component_config_defaults(self):
        """Test MiddlewareComponentConfig default values."""
        config = MiddlewareComponentConfig()
        assert config.middlewares == []
        assert config.enabled is True

    def test_multiple_middleware_registration(self):
        """Test registering multiple middleware factories."""
        component = MiddlewareComponent()

        def factory1(app):
            def f(**opts):
                return None

            return f

        def factory2(app):
            def f(**opts):
                return None

            return f

        component.register_middleware("middleware1", factory1)
        component.register_middleware("middleware2", factory2)

        assert len(component._factories) == 2
        assert "middleware1" in component._factories
        assert "middleware2" in component._factories

    def test_configure_validates_factories(self):
        """Test that configure() validates factories are registered."""
        from unittest.mock import MagicMock

        config = MiddlewareComponentConfig(
            middlewares=[
                MiddlewareConfig(name="unregistered"),
            ]
        )
        component = MiddlewareComponent(config=config)

        mock_app = MagicMock()
        mock_orchestrator = MagicMock()

        with pytest.raises(ValueError, match="not registered"):
            component.configure(mock_app, mock_orchestrator)

    def test_lifecycle_hooks_implemented(self):
        """Test that all required lifecycle hooks are implemented."""
        component = MiddlewareComponent()
        assert hasattr(component, "register_routes")
        assert hasattr(component, "on_startup_async")
        assert hasattr(component, "on_shutdown_async")

    def test_get_dependencies_returns_empty(self):
        """Test that get_dependencies returns empty list."""
        component = MiddlewareComponent()
        assert component.get_dependencies() == []
