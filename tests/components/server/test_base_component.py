"""Comprehensive tests for ServerComponent base classes."""

import pytest
from fastapi import FastAPI
from pydantic import Field

from flock.components.server.base import (
    ServerComponent,
    ServerComponentConfig,
)
from flock.core.orchestrator import Flock


class ConcreteServerComponent(ServerComponent):
    """Concrete implementation for testing."""

    name: str = "concrete"
    priority: int = 10
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)

    def register_routes(self, app, orchestrator):
        @app.get("/test")
        async def test_route():
            return {"status": "ok"}


class TestServerComponentConfig:
    """Tests for ServerComponentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ServerComponentConfig()

        assert config.enabled is True
        assert config.prefix == ""
        assert config.tags == []

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ServerComponentConfig(
            enabled=False, prefix="/api/v1", tags=["API", "V1"]
        )

        assert config.enabled is False
        assert config.prefix == "/api/v1"
        assert config.tags == ["API", "V1"]


class TestServerComponent:
    """Tests for ServerComponent base class."""

    def test_init_default_values(self):
        """Test component initialization with defaults."""
        component = ConcreteServerComponent()

        assert component.name == "concrete"
        assert component.priority == 10
        assert component.config.enabled is True

    def test_init_custom_config(self):
        """Test component initialization with custom config."""
        config = ServerComponentConfig(enabled=False, prefix="/custom")
        component = ConcreteServerComponent(config=config)

        assert component.config.enabled is False
        assert component.config.prefix == "/custom"

    def test_configure_default_implementation(self):
        """Test that configure() has a default no-op implementation."""
        component = ConcreteServerComponent()
        app = FastAPI()
        orchestrator = Flock("openai/gpt-4o")

        # Should not raise
        component.configure(app, orchestrator)

    def test_register_routes_must_be_implemented(self):
        """Test that register_routes must be implemented by subclasses."""

        class IncompleteComponent(ServerComponent):
            name: str = "incomplete"

        component = IncompleteComponent()
        app = FastAPI()
        orchestrator = Flock("openai/gpt-4o")

        with pytest.raises(NotImplementedError, match="must implement register_routes"):
            component.register_routes(app, orchestrator)

    @pytest.mark.asyncio
    async def test_on_startup_async_default(self):
        """Test default on_startup_async is no-op."""
        component = ConcreteServerComponent()
        orchestrator = Flock("openai/gpt-4o")

        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async_default(self):
        """Test default on_shutdown_async is no-op."""
        component = ConcreteServerComponent()
        orchestrator = Flock("openai/gpt-4o")

        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies_default(self):
        """Test default get_dependencies returns empty list."""
        component = ConcreteServerComponent()

        deps = component.get_dependencies()

        assert deps == []

    def test_get_dependencies_custom(self):
        """Test custom dependencies."""

        class DependentComponent(ServerComponent):
            name: str = "dependent"

            def register_routes(self, app, orchestrator):
                pass

            def get_dependencies(self):
                return [ConcreteServerComponent]

        component = DependentComponent()
        deps = component.get_dependencies()

        assert deps == [ConcreteServerComponent]


class TestServerComponentJoinPath:
    """Tests for _join_path helper method."""

    def test_join_path_simple(self):
        """Test simple path joining."""
        component = ConcreteServerComponent()

        result = component._join_path("/api", "v1")

        assert result == "/api/v1"

    def test_join_path_with_trailing_slash(self):
        """Test joining paths with trailing slashes."""
        component = ConcreteServerComponent()

        result = component._join_path("/api/", "v1")

        assert result == "/api/v1"

    def test_join_path_with_leading_slash(self):
        """Test joining paths with leading slashes."""
        component = ConcreteServerComponent()

        result = component._join_path("/api", "/v1")

        assert result == "/api/v1"

    def test_join_path_both_slashes(self):
        """Test joining paths with both trailing and leading slashes."""
        component = ConcreteServerComponent()

        result = component._join_path("/api/", "/v1")

        assert result == "/api/v1"

    def test_join_path_multiple_parts(self):
        """Test joining multiple path parts."""
        component = ConcreteServerComponent()

        result = component._join_path("/api", "v1", "users", "123")

        assert result == "/api/v1/users/123"

    def test_join_path_preserves_trailing_slash_on_last(self):
        """Test that trailing slash on last part is preserved."""
        component = ConcreteServerComponent()

        result = component._join_path("/api", "v1/")

        assert result == "/api/v1/"

    def test_join_path_empty_string(self):
        """Test joining with empty strings."""
        component = ConcreteServerComponent()

        result = component._join_path("", "api", "v1")

        assert result == "/api/v1"

    def test_join_path_single_part(self):
        """Test joining single part."""
        component = ConcreteServerComponent()

        result = component._join_path("/api")

        # Single part without second argument just strips trailing slash
        assert result == "api"  # Leading slash removed when single part


class TestServerComponentLifecycle:
    """Integration tests for component lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete component lifecycle."""
        configure_called = False
        register_called = False
        startup_called = False
        shutdown_called = False

        class LifecycleComponent(ServerComponent):
            name: str = "lifecycle"

            def configure(self, app, orchestrator):
                nonlocal configure_called
                configure_called = True

            def register_routes(self, app, orchestrator):
                nonlocal register_called
                register_called = True

                @app.get("/test")
                async def test():
                    return {"ok": True}

            async def on_startup_async(self, orchestrator):
                nonlocal startup_called
                startup_called = True

            async def on_shutdown_async(self, orchestrator):
                nonlocal shutdown_called
                shutdown_called = True

        component = LifecycleComponent()
        app = FastAPI()
        orchestrator = Flock("openai/gpt-4o")

        # Configure phase
        component.configure(app, orchestrator)
        assert configure_called

        # Register routes phase
        component.register_routes(app, orchestrator)
        assert register_called

        # Startup phase
        await component.on_startup_async(orchestrator)
        assert startup_called

        # Shutdown phase
        await component.on_shutdown_async(orchestrator)
        assert shutdown_called


class TestServerComponentPriority:
    """Tests for component priority system."""

    def test_priority_comparison(self):
        """Test that components can be sorted by priority."""

        class LowPriorityComponent(ServerComponent):
            name: str = "low"
            priority: int = 10

            def register_routes(self, app, orchestrator):
                pass

        class HighPriorityComponent(ServerComponent):
            name: str = "high"
            priority: int = 100

            def register_routes(self, app, orchestrator):
                pass

        low = LowPriorityComponent()
        high = HighPriorityComponent()

        components = [high, low]
        sorted_components = sorted(components, key=lambda c: c.priority)

        assert sorted_components[0] is low
        assert sorted_components[1] is high


class TestServerComponentFieldValidation:
    """Tests for Pydantic field validation."""

    def test_arbitrary_types_allowed(self):
        """Test that arbitrary types are allowed in config."""

        class CustomType:
            pass

        class ComponentWithCustomType(ServerComponent):
            name: str = "custom"
            custom_field: CustomType = CustomType()

            def register_routes(self, app, orchestrator):
                pass

        # Should not raise validation error
        component = ComponentWithCustomType()
        assert isinstance(component.custom_field, CustomType)

    def test_config_field_validation(self):
        """Test that config fields are validated."""
        config = ServerComponentConfig(enabled=True, prefix="/api")

        assert config.enabled is True
        assert config.prefix == "/api"
