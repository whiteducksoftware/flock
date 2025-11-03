"""ServerComponent for configuring CORS."""

import re

from pydantic import Field, field_validator
from starlette.middleware.cors import CORSMiddleware

from flock.components.server.base import ServerComponent, ServerComponentConfig


class RouteSpecificCORSConfig(ServerComponentConfig):
    """Configuration for route-specific CORS settings."""

    path_pattern: str = Field(
        ...,
        description="Regex pattern to match request paths. Example: '^/api/public/.*' for all /api/public routes.",
    )
    allow_origins: list[str] = Field(
        default=["*"], description="List of allowed origins for this route pattern."
    )
    allow_methods: list[str] = Field(
        default=["GET"],
        description="List of allowed HTTP methods for this route pattern.",
    )
    allow_headers: list[str] = Field(
        default=["*"], description="List of allowed headers for this route pattern."
    )
    expose_headers: list[str] = Field(
        default_factory=list,
        description="List of headers to expose to the browser for this route pattern.",
    )
    allow_credentials: bool = Field(
        default=False,
        description="Whether to allow credentials for this route pattern.",
    )
    max_age: int = Field(
        default=600,
        description="Maximum age (in seconds) for preflight cache for this route pattern.",
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


class CORSComponentConfig(ServerComponentConfig):
    """Config for CORS-ServerComponent."""

    # Global CORS settings
    allow_origins: list[str] = Field(
        default=["*"], description="List of allowed origins. Use ['*'] for all origins."
    )
    allow_origin_regex: str | None = Field(
        default=None,
        description="Regex pattern for allowed origins. Example: 'https://.*\\.example\\.com' allows all subdomains.",
    )
    allow_credentials: bool = Field(
        default=True,
        description="Whether to allow credentials (cookies, authorization headers).",
    )
    allow_methods: list[str] = Field(
        default=["*"],
        description="List of allowed HTTP methods. Use ['*'] for all methods.",
    )
    allow_headers: list[str] = Field(
        default=["*"], description="List of allowed headers. Use ['*'] for all headers."
    )
    expose_headers: list[str] = Field(
        default_factory=list,
        description="List of response headers to expose to the browser.",
    )
    max_age: int = Field(
        default=600,
        description="Maximum age (in seconds) for browsers to cache preflight responses.",
    )

    # Route-specific CORS overrides
    route_configs: list[RouteSpecificCORSConfig] = Field(
        default_factory=list,
        description="Route-specific CORS configurations that override global settings.",
    )

    @field_validator("allow_origin_regex")
    @classmethod
    def validate_origin_regex(cls, v: str | None) -> str | None:
        """Validate that the origin regex is valid if provided."""
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid origin regex pattern: {e}")
        return v


class CORSComponent(ServerComponent):
    """Component that allows configuring CORS behavior.

    Supports both global CORS settings and route-specific overrides.

    Examples:
        Basic usage with global settings:
        >>> component = CORSComponent(
        ...     config=CORSComponentConfig(
        ...         allow_origins=["https://example.com"],
        ...         allow_methods=["GET", "POST"],
        ...     )
        ... )

        With origin regex pattern:
        >>> component = CORSComponent(
        ...     config=CORSComponentConfig(
        ...         allow_origin_regex=r"https://.*\\.example\\.com",
        ...         allow_credentials=True,
        ...     )
        ... )

        With route-specific configs:
        >>> component = CORSComponent(
        ...     config=CORSComponentConfig(
        ...         allow_origins=["https://example.com"],
        ...         route_configs=[
        ...             RouteSpecificCORSConfig(
        ...                 path_pattern="^/api/public/.*",
        ...                 allow_origins=["*"],
        ...                 allow_credentials=False,
        ...             )
        ...         ],
        ...     )
        ... )
    """

    name: str = Field(default="cors", description="Name for the Component")
    priority: int = Field(default=8, description="Registration priority.")
    config: CORSComponentConfig = Field(
        default_factory=CORSComponentConfig, description="CORS Configuration."
    )

    def configure(self, app, orchestrator):
        """Configure CORS middleware.

        If route_configs are specified, adds custom middleware for route-specific handling.
        Otherwise, uses standard CORSMiddleware with global settings.
        """
        if self.config.route_configs:
            # Add custom middleware for route-specific CORS
            self._add_route_specific_cors(app)
        else:
            # Add standard CORS middleware with global settings
            self._add_global_cors(app)

    def _add_global_cors(self, app):
        """Add standard CORS middleware with global configuration."""
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.allow_origins,
            allow_origin_regex=self.config.allow_origin_regex,
            allow_credentials=self.config.allow_credentials,
            allow_methods=self.config.allow_methods,
            allow_headers=self.config.allow_headers,
            expose_headers=self.config.expose_headers,
            max_age=self.config.max_age,
        )

    def _add_route_specific_cors(self, app):
        """Add custom middleware that applies different CORS settings per route."""
        from starlette.types import ASGIApp, Receive, Scope, Send

        # Compile all route patterns
        compiled_patterns = [
            (re.compile(rc.path_pattern), rc) for rc in self.config.route_configs
        ]

        class RouteSpecificCORSMiddleware:
            """Custom CORS middleware that applies different settings per route."""

            def __init__(self, app: ASGIApp, parent: "CORSComponent"):
                self.app = app
                self.parent = parent
                self.compiled_patterns = compiled_patterns

            async def __call__(
                self, scope: Scope, receive: Receive, send: Send
            ) -> None:
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                # Get the request path
                path = scope.get("path", "")

                # Find matching route config
                route_config = None
                for pattern, config in self.compiled_patterns:
                    if pattern.match(path):
                        route_config = config
                        break

                # Use route-specific config if found, otherwise global
                if route_config:
                    cors_config = route_config
                else:
                    cors_config = self.parent.config

                # Create CORS middleware instance with appropriate config
                cors_middleware = CORSMiddleware(
                    app=self.app,
                    allow_origins=cors_config.allow_origins,
                    allow_origin_regex=getattr(cors_config, "allow_origin_regex", None),
                    allow_credentials=cors_config.allow_credentials,
                    allow_methods=cors_config.allow_methods,
                    allow_headers=cors_config.allow_headers,
                    expose_headers=getattr(cors_config, "expose_headers", []),
                    max_age=getattr(cors_config, "max_age", 600),
                )

                await cors_middleware(scope, receive, send)

        app.add_middleware(RouteSpecificCORSMiddleware, parent=self)

    def register_routes(self, app, orchestrator):
        """No routes to register for CORS component."""

    async def on_shutdown_async(self, orchestrator):
        """No cleanup needed for CORS component."""

    async def on_startup_async(self, orchestrator):
        """No startup tasks needed for CORS component."""

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """No dependencies for CORS component."""
        return []
