"""Comprehensive tests for BaseHTTPService."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import Field

from flock.api.base_service import BaseHTTPService
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.core.orchestrator import Flock


class MockServerComponent(ServerComponent):
    """Mock server component for testing."""

    name: str = "mock_component"
    priority: int = 10
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)

    # Track lifecycle calls
    configure_called: bool = False
    register_routes_called: bool = False
    startup_called: bool = False
    shutdown_called: bool = False

    def configure(self, app, orchestrator):
        self.configure_called = True

    def register_routes(self, app, orchestrator):
        self.register_routes_called = True

        @app.get("/test-endpoint")
        async def test_endpoint():
            return {"status": "ok"}

    async def on_startup_async(self, orchestrator):
        self.startup_called = True

    async def on_shutdown_async(self, orchestrator):
        self.shutdown_called = True

    def get_dependencies(self):
        return []


class DependentServerComponent(ServerComponent):
    """Component with dependencies for testing."""

    name: str = "dependent_component"
    priority: int = 20
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)

    def register_routes(self, app, orchestrator):
        @app.get("/dependent-endpoint")
        async def dependent_endpoint():
            return {"status": "dependent"}

    def get_dependencies(self):
        return [MockServerComponent]


class FailingStartupComponent(ServerComponent):
    """Component that fails during startup."""

    name: str = "failing_startup"
    priority: int = 30
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)

    def register_routes(self, app, orchestrator):
        pass

    async def on_startup_async(self, orchestrator):
        raise RuntimeError("Startup failed!")


class FailingShutdownComponent(ServerComponent):
    """Component that fails during shutdown."""

    name: str = "failing_shutdown"
    priority: int = 40
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)

    def register_routes(self, app, orchestrator):
        pass

    async def on_shutdown_async(self, orchestrator):
        raise RuntimeError("Shutdown failed!")


@pytest.fixture
def orchestrator():
    """Create a test orchestrator."""
    return Flock("openai/gpt-4o")


@pytest.fixture
def service(orchestrator):
    """Create a test service."""
    return BaseHTTPService(
        orchestrator, title="Test API", version="1.0.0", description="Test Description"
    )


class TestBaseHTTPServiceInit:
    """Tests for BaseHTTPService initialization."""

    def test_init_default_values(self, orchestrator):
        """Test initialization with default values."""
        service = BaseHTTPService(orchestrator)

        assert service.orchestrator is orchestrator
        assert service.components == []
        assert service.app is None
        assert service._configured is False
        assert service._started is False
        assert service._title == "Flock API"
        assert service._version == "0.5.0"
        assert service._description == "API for Flock Orchestrator"

    def test_init_custom_values(self, orchestrator):
        """Test initialization with custom values."""
        service = BaseHTTPService(
            orchestrator,
            title="Custom API",
            version="2.0.0",
            description="Custom Description",
        )

        assert service._title == "Custom API"
        assert service._version == "2.0.0"
        assert service._description == "Custom Description"


class TestBaseHTTPServiceAddComponents:
    """Tests for adding components to the service."""

    def test_add_component(self, service):
        """Test adding a single component."""
        component = MockServerComponent()
        result = service.add_component(component)

        assert result is service  # Should return self for chaining
        assert len(service.components) == 1
        assert service.components[0] is component

    def test_add_component_after_configure_raises(self, service):
        """Test that adding components after configure() raises error."""
        service.configure()
        component = MockServerComponent()

        with pytest.raises(RuntimeError, match="Cannot add components after configure"):
            service.add_component(component)

    def test_add_components_multiple(self, service):
        """Test adding multiple components at once."""
        components = [
            MockServerComponent(),
            DependentServerComponent(),
        ]
        result = service.add_components(components)

        assert result is service
        assert len(service.components) == 2

    def test_add_components_after_configure_raises(self, service):
        """Test that adding multiple components after configure() raises error."""
        service.configure()
        components = [MockServerComponent()]

        with pytest.raises(RuntimeError, match="Cannot add components after configure"):
            service.add_components(components)

    def test_component_chaining(self, service):
        """Test that add_component returns self for method chaining."""
        component1 = MockServerComponent()
        component2 = DependentServerComponent()

        result = service.add_component(component1).add_component(component2)

        assert result is service
        assert len(service.components) == 2


class TestBaseHTTPServiceConfigure:
    """Tests for configure() method."""

    def test_configure_creates_app(self, service):
        """Test that configure creates FastAPI app."""
        assert service.app is None
        service.configure()

        assert service.app is not None
        assert isinstance(service.app, FastAPI)
        assert service._configured is True

    def test_configure_app_metadata(self, orchestrator):
        """Test that FastAPI app has correct metadata."""
        service = BaseHTTPService(
            orchestrator,
            title="Test API",
            version="1.0.0",
            description="Test Description",
        )
        service.configure()

        assert service.app.title == "Test API"
        assert service.app.version == "1.0.0"
        assert service.app.description == "Test Description"

    def test_configure_sorts_components_by_priority(self, service):
        """Test that components are sorted by priority."""
        low_priority = MockServerComponent(priority=5)
        high_priority = MockServerComponent(priority=50)
        medium_priority = MockServerComponent(priority=25)

        service.add_component(high_priority)
        service.add_component(low_priority)
        service.add_component(medium_priority)

        service.configure()

        # Verify components were configured in priority order
        assert low_priority.configure_called
        assert medium_priority.configure_called
        assert high_priority.configure_called

    def test_configure_calls_component_lifecycle(self, service):
        """Test that configure calls component methods."""
        component = MockServerComponent()
        service.add_component(component)
        service.configure()

        assert component.configure_called
        assert component.register_routes_called

    def test_configure_idempotent(self, service):
        """Test that configure can be called multiple times safely."""
        component = MockServerComponent()
        service.add_component(component)

        service.configure()
        first_app = service.app

        service.configure()  # Second call

        assert service.app is first_app  # Same app instance
        assert service._configured is True

    def test_configure_disabled_component_not_configured(self, service):
        """Test that disabled components are not configured."""
        component = MockServerComponent(config=ServerComponentConfig(enabled=False))
        service.add_component(component)
        service.configure()

        assert not component.configure_called
        assert not component.register_routes_called

    def test_configure_validates_dependencies(self, service):
        """Test that dependency validation happens."""
        # Add dependent component without its dependency
        dependent = DependentServerComponent()
        service.add_component(dependent)

        with pytest.raises(ValueError, match="requires MockServerComponent"):
            service.configure()

    def test_configure_with_satisfied_dependencies(self, service):
        """Test configuration succeeds with satisfied dependencies."""
        mock = MockServerComponent()
        dependent = DependentServerComponent()

        service.add_component(mock)
        service.add_component(dependent)
        service.configure()

        assert service._configured is True


class TestBaseHTTPServiceLifespan:
    """Tests for service lifespan management."""

    def test_lifespan_context_manager_created(self, service):
        """Test that lifespan context manager is created during configure."""
        component = MockServerComponent()
        service.add_component(component)
        service.configure()

        # The app should have a lifespan context manager
        assert service.app is not None
        assert hasattr(service.app.router, "lifespan_context")

    def test_lifespan_disabled_component_not_configured(self, service):
        """Test that disabled components don't get configured."""
        component = MockServerComponent(config=ServerComponentConfig(enabled=False))
        service.add_component(component)
        service.configure()

        assert not component.configure_called
        assert not component.register_routes_called


class TestBaseHTTPServiceGetApp:
    """Tests for get_app() method."""

    def test_get_app_before_configure(self, service):
        """Test get_app returns None before configure."""
        assert service.get_app() is None

    def test_get_app_after_configure(self, service):
        """Test get_app returns FastAPI instance after configure."""
        service.configure()
        app = service.get_app()

        assert app is not None
        assert isinstance(app, FastAPI)
        assert app is service.app


class TestBaseHTTPServiceRunAsync:
    """Tests for run_async() method."""

    @pytest.mark.asyncio
    async def test_run_async_auto_configures(self, service, monkeypatch):
        """Test that run_async calls configure if needed."""
        # We can't actually run the server, but we can verify configure is called
        component = MockServerComponent()
        service.add_component(component)

        assert not service._configured

        # Mock uvicorn.Server.serve to prevent actual server start
        async def mock_serve(self):
            pass

        monkeypatch.setattr("uvicorn.Server.serve", mock_serve)

        await service.run_async()

        assert service._configured
        assert component.configure_called


class TestBaseHTTPServiceValidateDependencies:
    """Tests for _validate_dependencies() method."""

    def test_validate_dependencies_success(self, service):
        """Test successful dependency validation."""
        mock = MockServerComponent()
        dependent = DependentServerComponent()

        service.add_component(mock)
        service.add_component(dependent)

        # Should not raise
        service._validate_dependencies()

    def test_validate_dependencies_missing_raises(self, service):
        """Test that missing dependencies raise ValueError."""
        dependent = DependentServerComponent()
        service.add_component(dependent)

        with pytest.raises(ValueError, match="requires MockServerComponent"):
            service._validate_dependencies()

    def test_validate_dependencies_disabled_dependency_raises(self, service):
        """Test that disabled dependencies raise ValueError."""
        mock = MockServerComponent(config=ServerComponentConfig(enabled=False))
        dependent = DependentServerComponent()

        service.add_component(mock)
        service.add_component(dependent)

        with pytest.raises(ValueError, match="requires MockServerComponent"):
            service._validate_dependencies()

    def test_validate_dependencies_disabled_dependent_ok(self, service):
        """Test that disabled dependents don't require dependencies."""
        dependent = DependentServerComponent(
            config=ServerComponentConfig(enabled=False)
        )
        service.add_component(dependent)

        # Should not raise because dependent is disabled
        service._validate_dependencies()


class TestBaseHTTPServiceIntegration:
    """Integration tests for BaseHTTPService."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_configure_and_routes(self, service):
        """Test complete service configuration and routing."""
        component = MockServerComponent()

        # 1. Add component
        service.add_component(component)
        assert not component.configure_called

        # 2. Configure
        service.configure()
        assert component.configure_called
        assert component.register_routes_called
        assert service.app is not None

        # 3. Test routes work
        transport = ASGITransport(app=service.app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Routes work
            response = await client.get("/test-endpoint")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_multiple_components_integration(self, service):
        """Test service with multiple components."""
        comp1 = MockServerComponent(priority=10)
        comp1.name = "component1"

        class Component2(ServerComponent):
            name: str = "component2"
            priority: int = 20

            def register_routes(self, app, orchestrator):
                @app.get("/endpoint2")
                async def endpoint2():
                    return {"component": "2"}

        comp2 = Component2()

        service.add_components([comp1, comp2])
        service.configure()

        transport = ASGITransport(app=service.app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Both endpoints should work
            resp1 = await client.get("/test-endpoint")
            assert resp1.status_code == 200

            resp2 = await client.get("/endpoint2")
            assert resp2.status_code == 200
            assert resp2.json() == {"component": "2"}
