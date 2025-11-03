"""HTTP control plane for the blackboard orchestrator."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from flock.components.server.base import ServerComponent
from flock.core.orchestrator import Flock
from flock.logging.logging import get_logger


logger = get_logger(__name__)


class BaseHTTPService:
    """HTTP control plane for the blackboard orchestrator.

    HTTP service built from composable ServerComponents.

    Components are registered in priority order and manage their own routes.

    Example:
        >>> service = BaseHTTPService(orchestrator, title="My API")
        >>> service.add_component(ArtifactComponent(priority=10))
        >>> service.add_component(DasboardComponent(priority=20))
        >>> await service.run_async(...)
    """

    def __init__(
        self,
        orchestrator: Flock,
        *,
        title: str = "Flock API",
        version: str = "0.5.0",
        description: str = "API for Flock Orchestrator",
    ):
        self.orchestrator = orchestrator
        self.components: list[ServerComponent] = []

        # Start out with no app at first.
        self.app: FastAPI | None = None

        # Track initialization state
        self._configured = False
        self._started = False
        self._version = version
        self._description = description
        self._title = title

    def add_component(self, component: ServerComponent) -> "BaseHTTPService":
        """Add a server component (must be called before configure()).

        Args:
            component: ServerComponent instance to add

        Raises:
            RuntimeError: if called after configure()
        """
        if self._configured or self.app:
            raise RuntimeError("Cannot add components after configure()")

        self.components.append(component)
        logger.debug(f"Added ServerComponent: {component.name} to Server.")
        return self

    def add_components(self, components: list[ServerComponent]) -> "BaseHTTPService":
        """Add multiple components at once.

        Args:
            components: List of ServerComponent instances

        Raises:
            RuntimeError: if called after configure()
        """
        if self._configured or self.app:
            raise RuntimeError("Cannot add components after configure()")
        for component in components:
            self.add_component(component)
        return self

    def configure(self) -> "BaseHTTPService":
        """Configure FastAPI app with all components.

        1. Sorts components by priority
        2. Validates dependencies
        3. Calls component.configure() for each
        4. Calls component.register_routes() for each

        Must be called before run_async()
        """
        logger.info("Configuring BaseHTTPService")
        if self._configured:
            return  # Noting to do
        if self.app is None:
            logger.debug("Creating FastAPI app")
            # No FastAPI app has been instantiated yet
            lifespan_context_manager = self._create_lifespan_context_manager(
                orchestrator=self.orchestrator
            )
            self.app = FastAPI(
                version=self._version,
                title=self._title,
                description=self._description,
                lifespan=lifespan_context_manager,
            )
        # Sort by priority (lower first)
        sorted_components: list[ServerComponent] = self.components[:]
        sorted_components.sort(key=lambda c: c.priority)
        # Configure phase (sync)
        logger.debug("Configuring ServerComponents")
        for component in sorted_components:
            if component.config.enabled:
                component.configure(self.app, self.orchestrator)
        # Register routes phase
        logger.debug("Registering Routes for ServerComponent")
        for component in sorted_components:
            if component.config.enabled:
                component.register_routes(self.app, self.orchestrator)
                logger.debug(f"Registered Routes for ServerComponent: {component.name}")
        self._configured = True

    async def run_async(self, host: str = "127.0.0.1", port: int = 8344) -> None:
        """Run the service asynchronously.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        import uvicorn

        # Configure if not already done
        if not self._configured:
            self.configure()

        # Run server
        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()

    def run(self, host: str = "127.0.0.1", port: int = 8344) -> None:
        """Run the service synchronously (blocks).

        Args:
            host: host to bind to
            port: port to bind to
        """
        import uvicorn

        if not self._configured:
            self.configure()
        # Run server
        uvicorn.run(self.app, host=host, port=port)

    def get_app(self) -> FastAPI | None:
        """Return the App instance.

        Mainly used for getting acces to the underlying
        FastAPI-App for testing and special use-cases.

        Returns:
            FastAPI app
        """
        return self.app

    def _validate_dependencies(self) -> None:
        """Validate that all component dependencies are satisfied."""
        logger.debug("Validating dependencies for configured server-components")
        enabled_types = {type(c) for c in self.components if c.config.enabled}
        for component in self.components:
            if not component.config.enabled:
                continue
            for dep_type in component.get_dependencies():
                if dep_type not in enabled_types:
                    logger.exception(f"Component: {component.name} is NOT Valid.")
                    raise ValueError(
                        f"Component {component.name or component.__class__.__name__} "
                        f"requires {dep_type.__name__} but it's not enabled"
                    )
                logger.debug(f"Component: {component.name}: Valid")

    def _create_lifespan_context_manager(self, orchestrator: Flock):
        """Create the lifespan callback for the app."""
        # https://fastapi.tiangolo.com/advanced/events/#lifespan-function
        sorted_components: list[ServerComponent] = self.components[:]
        sorted_components.sort(key=lambda c: c.priority)
        reverse_components: list[ServerComponent] = reversed(sorted_components[:])

        # Validate dependencies before creating the lifespan-callback
        self._validate_dependencies()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # The first part of the function will be executed BEFORE the app starts
            for component in sorted_components:
                if not component.config.enabled:
                    continue
                try:
                    await component.on_startup_async(orchestrator=orchestrator)
                except Exception as e:
                    logger.exception(
                        f"Exception during startup of application: Affected ServerComponent: {component.name}. Exception: {e}"
                    )
                    raise  # Raise the exception and stop execution
            self._started = True
            yield  # App runs...
            # The second part of the function will be executed AFTER the application has finished
            for component in reverse_components:
                if not component.config.enabled:
                    continue
                try:
                    await component.on_shutdown_async(orchestrator=orchestrator)
                except Exception as e:
                    logger.exception(
                        f"Exception during shutdown of application: Affected ServerComponent: {component.name}. Exception: {e}"
                    )
                    continue  # Ignore the exception to ensure proper shutdown if possible.
            self._started = False
            self._configured = False

        return lifespan
