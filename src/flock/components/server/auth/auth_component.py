"""ServerComponent for configuring authentication middleware."""

import re
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field, PrivateAttr, field_validator
from starlette.requests import Request
from starlette.responses import Response

from flock.components.server.base import ServerComponent, ServerComponentConfig


# Type alias for authentication handler
AuthHandler = Callable[[Request], Awaitable[tuple[bool, Response | None]]]


class RouteSpecificAuthConfig(ServerComponentConfig):
    """Configuration for route-specific authentication settings."""

    path_pattern: str = Field(
        ...,
        description="Regex pattern to match request paths. Example: '^/api/admin/.*' for all /api/admin routes.",
    )
    handler_name: str = Field(
        ...,
        description="Name of the registered authentication handler to use for this route pattern.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether authentication is enabled for this route pattern.",
    )

    @field_validator("path_pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        """Validate that the path pattern is a valid regex."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        return v


class AuthenticationComponentConfig(ServerComponentConfig):
    """Config for Authentication-ServerComponent."""

    # Global authentication settings
    default_handler: str | None = Field(
        default=None,
        description="Name of the default authentication handler to apply globally. If None, no global auth is applied.",
    )

    # Route-specific authentication overrides
    route_configs: list[RouteSpecificAuthConfig] = Field(
        default_factory=list,
        description="Route-specific authentication configurations that override global settings.",
    )

    # Excluded paths (no authentication required)
    exclude_paths: list[str] = Field(
        default_factory=list,
        description="List of regex patterns for paths that should bypass authentication entirely.",
    )

    @field_validator("exclude_paths")
    @classmethod
    def validate_exclude_paths(cls, v: list[str]) -> list[str]:
        """Validate that all exclude paths are valid regex patterns."""
        for pattern in v:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid exclude path regex pattern '{pattern}': {e}")
        return v


class AuthenticationComponent(ServerComponent):
    """Component that allows configuring authentication middleware.

    Supports both global authentication and route-specific overrides.
    Developers can register custom authentication handlers that return
    (is_authenticated: bool, error_response: Response | None) tuples.

    Examples:
        Basic usage with global authentication:
        >>> async def api_key_auth(
        ...     request: Request,
        ... ) -> tuple[bool, Response | None]:
        ...     api_key = request.headers.get("X-API-Key")
        ...     if api_key == "secret-key":
        ...         return True, None
        ...     return False, JSONResponse(
        ...         {"error": "Invalid API key"}, status_code=401
        ...     )
        >>>
        >>> component = AuthenticationComponent(
        ...     config=AuthenticationComponentConfig(
        ...         default_handler="api_key",
        ...         exclude_paths=[r"^/health$", r"^/docs.*"],
        ...     )
        ... )
        >>> component.register_handler("api_key", api_key_auth)

        With route-specific handlers:
        >>> component = AuthenticationComponent(
        ...     config=AuthenticationComponentConfig(
        ...         route_configs=[
        ...             RouteSpecificAuthConfig(
        ...                 path_pattern=r"^/api/admin/.*",
        ...                 handler_name="admin_auth",
        ...             ),
        ...             RouteSpecificAuthConfig(
        ...                 path_pattern=r"^/api/public/.*",
        ...                 handler_name="public_auth",
        ...             ),
        ...         ]
        ...     )
        ... )
        >>> component.register_handler("admin_auth", admin_auth_handler)
        >>> component.register_handler("public_auth", public_auth_handler)
    """

    name: str = Field(default="authentication", description="Name for the Component")
    priority: int = Field(
        default=7,
        description="Registration priority. Should run before most components but after CORS.",
    )
    config: AuthenticationComponentConfig = Field(
        default_factory=AuthenticationComponentConfig,
        description="Authentication Configuration.",
    )

    # Internal registry for authentication handlers
    _handlers: dict[str, AuthHandler] = PrivateAttr(default_factory=dict)

    def register_handler(self, name: str, handler: AuthHandler) -> None:
        """Register a custom authentication handler.

        Args:
            name: Unique name for the handler
            handler: Async function that takes a Request and returns (bool, Response | None)
                    - True, None if authentication succeeds
                    - False, Response if authentication fails (Response is returned to client)

        Example:
            >>> async def my_auth(request: Request) -> tuple[bool, Response | None]:
            ...     token = request.headers.get("Authorization")
            ...     if validate_token(token):
            ...         return True, None
            ...     return False, JSONResponse(
            ...         {"error": "Unauthorized"}, status_code=401
            ...     )
            >>>
            >>> component.register_handler("my_auth", my_auth)
        """
        if name in self._handlers:
            raise ValueError(f"Authentication handler '{name}' is already registered")
        self._handlers[name] = handler

    def configure(self, app: Any, orchestrator: Any) -> None:
        """Configure authentication middleware.

        Adds custom middleware that applies authentication based on configuration.
        """
        # Validate that all referenced handlers are registered
        self._validate_handlers()

        # Add authentication middleware
        self._add_auth_middleware(app)

    def _validate_handlers(self) -> None:
        """Validate that all handlers referenced in config are registered."""
        required_handlers = set()

        if self.config.default_handler:
            required_handlers.add(self.config.default_handler)

        for route_config in self.config.route_configs:
            if route_config.enabled:
                required_handlers.add(route_config.handler_name)

        missing_handlers = required_handlers - set(self._handlers.keys())
        if missing_handlers:
            raise ValueError(
                f"The following authentication handlers are referenced in config but not registered: "
                f"{', '.join(sorted(missing_handlers))}. "
                f"Use component.register_handler(name, handler) to register them before starting the server."
            )

    def _add_auth_middleware(self, app: Any) -> None:
        """Add authentication middleware to the FastAPI app."""
        from starlette.types import ASGIApp, Receive, Scope, Send

        # Compile all route patterns
        compiled_routes = [
            (re.compile(rc.path_pattern), rc) for rc in self.config.route_configs
        ]

        # Compile exclude patterns
        compiled_excludes = [
            re.compile(pattern) for pattern in self.config.exclude_paths
        ]

        class AuthenticationMiddleware:
            """Custom authentication middleware that applies handlers per route."""

            def __init__(self, app: ASGIApp, parent: "AuthenticationComponent"):
                self.app = app
                self.parent = parent
                self.compiled_routes = compiled_routes
                self.compiled_excludes = compiled_excludes

            async def __call__(
                self, scope: Scope, receive: Receive, send: Send
            ) -> None:
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                # Get the request path
                path = scope.get("path", "")

                # Check if path is excluded
                for exclude_pattern in self.compiled_excludes:
                    if exclude_pattern.match(path):
                        # Bypass authentication for excluded paths
                        await self.app(scope, receive, send)
                        return

                # Determine which handler to use
                handler_name = self._get_handler_for_path(path)

                # If no handler applies, allow the request
                if handler_name is None:
                    await self.app(scope, receive, send)
                    return

                # Execute authentication and handle result
                await self._authenticate_and_handle(handler_name, scope, receive, send)

            def _get_handler_for_path(self, path: str) -> str | None:
                """Determine which authentication handler to use for a path."""
                # Find matching route config
                for pattern, route_config in self.compiled_routes:
                    if pattern.match(path):
                        if route_config.enabled:
                            return route_config.handler_name
                        # Route-specific auth is disabled
                        return None

                # Fall back to default handler if no route-specific match
                return self.parent.config.default_handler

            async def _authenticate_and_handle(
                self, handler_name: str, scope: Scope, receive: Receive, send: Send
            ) -> None:
                """Execute authentication handler and process result."""
                # Get the handler
                handler = self.parent._handlers.get(handler_name)
                if handler is None:
                    # This shouldn't happen due to validation, but be safe
                    await self.app(scope, receive, send)
                    return

                # Create a request object
                request = Request(scope, receive)

                # Execute authentication handler
                try:
                    is_authenticated, error_response = await handler(request)
                except Exception as e:
                    # Log the error and return 500
                    print(
                        f"Authentication handler '{handler_name}' raised exception: {e}"
                    )
                    from starlette.responses import JSONResponse

                    error_response = JSONResponse(
                        {"error": "Internal authentication error"}, status_code=500
                    )
                    await error_response(scope, receive, send)
                    return

                if not is_authenticated:
                    # Return the error response from the handler
                    if error_response is not None:
                        await error_response(scope, receive, send)
                    else:
                        # Handler didn't provide a response, use default 401
                        from starlette.responses import JSONResponse

                        default_response = JSONResponse(
                            {"error": "Unauthorized"}, status_code=401
                        )
                        await default_response(scope, receive, send)
                    return

                # Authentication successful, continue to the app
                await self.app(scope, receive, send)

        app.add_middleware(AuthenticationMiddleware, parent=self)

    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """No routes to register for authentication component."""

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """No cleanup needed for authentication component."""

    async def on_startup_async(self, orchestrator: Any) -> None:
        """No startup tasks needed for authentication component."""

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """No dependencies for authentication component."""
        return []
