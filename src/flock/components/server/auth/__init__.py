"""Authentication server component."""

from flock.components.server.auth.auth_component import (
    AuthenticationComponent,
    AuthenticationComponentConfig,
    RouteSpecificAuthConfig,
)


__all__ = [
    "AuthenticationComponent",
    "AuthenticationComponentConfig",
    "RouteSpecificAuthConfig",
]
