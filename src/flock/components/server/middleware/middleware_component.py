"""ServerComponent for configuring generic middleware."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field, PrivateAttr
from starlette.types import ASGIApp, Receive, Scope, Send

from flock.components.server.base import ServerComponent, ServerComponentConfig


# Type alias for middleware factory
MiddlewareFactory = Callable[[ASGIApp], ASGIApp]

# Type alias for ASGI middleware callable
ASGIMiddleware = Callable[[Scope, Receive, Send], Awaitable[None]]


class MiddlewareConfig(ServerComponentConfig):
    """Configuration for a single middleware registration."""

    name: str = Field(
        ...,
        description="Unique name for this middleware registration.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional configuration options passed to the middleware factory.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this middleware is enabled.",
    )


class MiddlewareComponentConfig(ServerComponentConfig):
    """Config for Middleware-ServerComponent."""

    middlewares: list[MiddlewareConfig] = Field(
        default_factory=list,
        description="List of middleware configurations to register.",
    )


class MiddlewareComponent(ServerComponent):
    """Component that allows configuring generic middleware.

    Supports registering custom middleware factories that can be configured
    through the component configuration.

    Middleware is registered in the order specified in the configuration,
    meaning the first middleware in the list will be the outermost middleware
    in the request processing chain.

    Examples:
        Basic usage with custom middleware:
        >>> from starlette.middleware.base import BaseHTTPMiddleware
        >>> from starlette.requests import Request
        >>>
        >>> class CustomHeaderMiddleware(BaseHTTPMiddleware):
        ...     def __init__(self, app, header_name: str, header_value: str):
        ...         super().__init__(app)
        ...         self.header_name = header_name
        ...         self.header_value = header_value
        ...
        ...     async def dispatch(self, request: Request, call_next):
        ...         response = await call_next(request)
        ...         response.headers[self.header_name] = self.header_value
        ...         return response
        >>>
        >>> def create_custom_header_middleware(app):
        ...     def factory(**options):
        ...         return CustomHeaderMiddleware(
        ...             app,
        ...             header_name=options.get("header_name", "X-Custom"),
        ...             header_value=options.get("header_value", "default"),
        ...         )
        ...
        ...     return factory
        >>>
        >>> component = MiddlewareComponent(
        ...     config=MiddlewareComponentConfig(
        ...         middlewares=[
        ...             MiddlewareConfig(
        ...                 name="custom_header",
        ...                 options={
        ...                     "header_name": "X-App-Version",
        ...                     "header_value": "1.0.0",
        ...                 },
        ...             )
        ...         ]
        ...     )
        ... )
        >>> component.register_middleware(
        ...     "custom_header", create_custom_header_middleware
        ... )

        Using Starlette's built-in middleware:
        >>> from starlette.middleware.gzip import GZipMiddleware
        >>>
        >>> def gzip_factory(app):
        ...     def factory(**options):
        ...         minimum_size = options.get("minimum_size", 1000)
        ...         return GZipMiddleware(app, minimum_size=minimum_size)
        ...
        ...     return factory
        >>>
        >>> component = MiddlewareComponent(
        ...     config=MiddlewareComponentConfig(
        ...         middlewares=[
        ...             MiddlewareConfig(
        ...                 name="gzip",
        ...                 options={"minimum_size": 500},
        ...             )
        ...         ]
        ...     )
        ... )
        >>> component.register_middleware("gzip", gzip_factory)

        With multiple middleware (order matters):
        >>> component = MiddlewareComponent(
        ...     config=MiddlewareComponentConfig(
        ...         middlewares=[
        ...             MiddlewareConfig(name="logging"),
        ...             MiddlewareConfig(
        ...                 name="gzip", options={"minimum_size": 500}
        ...             ),
        ...             MiddlewareConfig(name="custom_header"),
        ...         ]
        ...     )
        ... )
        >>> # Request processing order: logging -> gzip -> custom_header -> app
    """

    name: str = Field(default="middleware", description="Name for the Component")
    priority: int = Field(
        default=6,
        description="Registration priority. Should run after CORS and auth but before most other components.",
    )
    config: MiddlewareComponentConfig = Field(
        default_factory=MiddlewareComponentConfig,
        description="Middleware Configuration.",
    )

    # Internal registry for middleware factories
    _factories: dict[str, MiddlewareFactory] = PrivateAttr(default_factory=dict)

    def register_middleware(self, name: str, factory: MiddlewareFactory) -> None:
        """Register a custom middleware factory.

        Args:
            name: Unique name for the middleware
            factory: Function that takes an ASGI app and returns a middleware-wrapped app.
                    The factory should accept **options kwargs from the configuration.

        Example:
            >>> def my_middleware_factory(app):
            ...     def factory(**options):
            ...         class MyMiddleware:
            ...             def __init__(self, app):
            ...                 self.app = app
            ...                 self.config = options
            ...
            ...             async def __call__(self, scope, receive, send):
            ...                 # Process request
            ...                 await self.app(scope, receive, send)
            ...
            ...         return MyMiddleware(app)
            ...
            ...     return factory
            >>>
            >>> component.register_middleware("my_middleware", my_middleware_factory)
        """
        if name in self._factories:
            raise ValueError(f"Middleware factory '{name}' is already registered")
        self._factories[name] = factory

    def configure(self, app: Any, orchestrator: Any) -> None:
        """Configure middleware.

        Validates that all referenced factories are registered and adds
        middleware to the app in the order specified in the configuration.

        Note: FastAPI's add_middleware() adds middleware in reverse order
        (last added is outermost), so we reverse the list before adding.
        """
        # Validate that all referenced factories are registered
        self._validate_factories()

        # Add middleware in reverse order because FastAPI's add_middleware
        # makes the last added middleware the outermost
        for middleware_config in reversed(self.config.middlewares):
            if middleware_config.enabled:
                self._add_middleware(app, middleware_config)

    def _validate_factories(self) -> None:
        """Validate that all factories referenced in config are registered."""
        required_factories = set()

        for middleware_config in self.config.middlewares:
            if middleware_config.enabled:
                required_factories.add(middleware_config.name)

        missing_factories = required_factories - set(self._factories.keys())
        if missing_factories:
            raise ValueError(
                f"The following middleware factories are referenced in config but not registered: "
                f"{', '.join(sorted(missing_factories))}. "
                f"Use component.register_middleware(name, factory) to register them before starting the server."
            )

    def _add_middleware(self, app: Any, middleware_config: MiddlewareConfig) -> None:
        """Add a single middleware to the FastAPI app."""
        factory = self._factories[middleware_config.name]

        # Get the factory function from the outer factory
        # factory(app) returns a function that accepts **options and returns a middleware class
        inner_factory = factory(app.app if hasattr(app, "app") else app)

        # If the factory returns a callable that accepts options, create a middleware class
        # that will be instantiated by FastAPI with the ASGI app
        if callable(inner_factory):

            class MiddlewareWrapper:
                def __init__(self, asgi_app: ASGIApp):
                    # Call the inner factory to get the middleware instance
                    # Pass the options from the config
                    self.middleware = inner_factory(**middleware_config.options)
                    # Set the app on the middleware if it has an app attribute
                    if hasattr(self.middleware, "app"):
                        self.middleware.app = asgi_app

                async def __call__(
                    self, scope: Scope, receive: Receive, send: Send
                ) -> None:
                    await self.middleware(scope, receive, send)

            app.add_middleware(MiddlewareWrapper)
        else:
            # Assume it's already a middleware class
            app.add_middleware(inner_factory, **middleware_config.options)

    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """No routes to register for middleware component."""

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """No cleanup needed for middleware component."""

    async def on_startup_async(self, orchestrator: Any) -> None:
        """No startup tasks needed for middleware component."""

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """No dependencies for middleware component."""
        return []
