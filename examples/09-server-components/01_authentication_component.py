"""
Authentication Component Examples

This example demonstrates the AuthenticationComponent capabilities:
1. Basic API key authentication
2. JWT token authentication
3. Route-specific authentication handlers
4. Excluded paths (public endpoints)
5. Custom error responses
6. Multiple authentication strategies
"""

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from flock import Flock
from flock.components.server import (
    AuthenticationComponent,
    AuthenticationComponentConfig,
    RouteSpecificAuthConfig,
)


# Example 1: Basic API Key Authentication
def example_basic_api_key():
    """Simple API key authentication for all routes."""

    async def api_key_handler(request: Request) -> tuple[bool, Response | None]:
        """Check for valid API key in headers."""
        api_key = request.headers.get("X-API-Key")

        if api_key == "secret-key-123":
            return True, None

        # Authentication failed
        return False, JSONResponse(
            {"error": "Invalid or missing API key"}, status_code=401
        )

    flock = Flock()

    # Create authentication component
    auth_component = AuthenticationComponent(
        config=AuthenticationComponentConfig(
            default_handler="api_key",
            exclude_paths=[
                r"^/health$",  # Health check endpoint
                r"^/docs.*",  # API documentation
                r"^/openapi\.json$",  # OpenAPI schema
            ],
        )
    )

    # Register the authentication handler
    auth_component.register_handler("api_key", api_key_handler)

    return flock, auth_component


# Example 2: JWT Token Authentication
def example_jwt_authentication():
    """JWT token authentication with proper error handling."""

    async def jwt_handler(request: Request) -> tuple[bool, Response | None]:
        """Validate JWT token from Authorization header."""
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return False, JSONResponse(
                {"error": "Missing Authorization header"}, status_code=401
            )

        if not auth_header.startswith("Bearer "):
            return False, JSONResponse(
                {"error": "Invalid Authorization header format. Use: Bearer <token>"},
                status_code=401,
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # In production, validate the JWT token properly
        # For this example, we just check if it's not empty
        if token and len(token) > 10:
            # Token is valid - in production, verify signature, expiration, etc.
            return True, None

        return False, JSONResponse(
            {"error": "Invalid or expired token"}, status_code=401
        )

    flock = Flock()

    auth_component = AuthenticationComponent(
        config=AuthenticationComponentConfig(
            default_handler="jwt", exclude_paths=[r"^/health$", r"^/login$"]
        )
    )

    auth_component.register_handler("jwt", jwt_handler)

    return flock, auth_component


# Example 3: Route-Specific Authentication
def example_route_specific_auth():
    """Different authentication strategies for different routes."""

    # Handler for public API - just check basic key
    async def public_auth(request: Request) -> tuple[bool, Response | None]:
        """Simple authentication for public API."""
        api_key = request.headers.get("X-API-Key")

        if api_key and api_key.startswith("public-"):
            return True, None

        return False, JSONResponse(
            {"error": "Public API requires an API key starting with 'public-'"},
            status_code=401,
        )

    # Handler for admin API - strict JWT validation
    async def admin_auth(request: Request) -> tuple[bool, Response | None]:
        """Strict authentication for admin endpoints."""
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return False, JSONResponse(
                {"error": "Admin access requires Bearer token"}, status_code=403
            )

        token = auth_header[7:]

        # In production: verify JWT, check admin role claim
        if token == "admin-secret-token":
            return True, None

        return False, JSONResponse(
            {"error": "Insufficient privileges"}, status_code=403
        )

    # Handler for webhooks - signature verification
    async def webhook_auth(request: Request) -> tuple[bool, Response | None]:
        """Verify webhook signatures from external services."""
        signature = request.headers.get("X-Webhook-Signature")

        # In production: verify HMAC signature
        if signature and signature.startswith("sha256="):
            return True, None

        return False, JSONResponse(
            {"error": "Invalid webhook signature"}, status_code=401
        )

    flock = Flock()

    auth_component = AuthenticationComponent(
        config=AuthenticationComponentConfig(
            # No default handler - require explicit configuration per route
            default_handler=None,
            route_configs=[
                RouteSpecificAuthConfig(
                    path_pattern=r"^/api/public/.*", handler_name="public_auth"
                ),
                RouteSpecificAuthConfig(
                    path_pattern=r"^/api/admin/.*", handler_name="admin_auth"
                ),
                RouteSpecificAuthConfig(
                    path_pattern=r"^/webhooks/.*", handler_name="webhook_auth"
                ),
            ],
            exclude_paths=[r"^/health$", r"^/docs.*"],
        )
    )

    # Register all handlers
    auth_component.register_handler("public_auth", public_auth)
    auth_component.register_handler("admin_auth", admin_auth)
    auth_component.register_handler("webhook_auth", webhook_auth)

    return flock, auth_component


# Example 4: Disable Authentication for Specific Routes
def example_mixed_authentication():
    """Global authentication with specific routes disabled."""

    async def default_auth(request: Request) -> tuple[bool, Response | None]:
        """Default authentication for most endpoints."""
        api_key = request.headers.get("X-API-Key")

        if api_key == "valid-key":
            return True, None

        return False, JSONResponse(
            {"error": "Authentication required"}, status_code=401
        )

    flock = Flock()

    auth_component = AuthenticationComponent(
        config=AuthenticationComponentConfig(
            # Apply default authentication globally
            default_handler="default_auth",
            route_configs=[
                # Explicitly disable auth for public endpoints
                RouteSpecificAuthConfig(
                    path_pattern=r"^/api/public/.*",
                    handler_name="default_auth",  # Name doesn't matter when disabled
                    enabled=False,  # Disable authentication for this route
                ),
            ],
            # Also exclude some paths entirely
            exclude_paths=[r"^/health$", r"^/metrics$"],
        )
    )

    auth_component.register_handler("default_auth", default_auth)

    return flock, auth_component


# Example 5: Custom Error Responses
def example_custom_errors():
    """Authentication with detailed custom error responses."""

    async def detailed_auth(request: Request) -> tuple[bool, Response | None]:
        """Authentication with detailed error messages."""
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return False, JSONResponse(
                {
                    "error": "API key required",
                    "message": "Please provide an API key in the X-API-Key header",
                    "docs": "https://docs.example.com/authentication",
                },
                status_code=401,
                headers={"WWW-Authenticate": 'ApiKey realm="API"'},
            )

        if not api_key.startswith("sk-"):
            return False, JSONResponse(
                {
                    "error": "Invalid API key format",
                    "message": "API keys must start with 'sk-'",
                    "example": "sk-1234567890abcdef",
                },
                status_code=401,
            )

        # In production: validate the key against database
        if api_key == "sk-valid-key":
            return True, None

        return False, JSONResponse(
            {
                "error": "Invalid API key",
                "message": "The provided API key is not valid",
            },
            status_code=401,
        )

    flock = Flock()

    auth_component = AuthenticationComponent(
        config=AuthenticationComponentConfig(
            default_handler="detailed_auth", exclude_paths=[r"^/health$"]
        )
    )

    auth_component.register_handler("detailed_auth", detailed_auth)

    return flock, auth_component


# Example 6: Complete Production Setup
def example_production_setup():
    """Production-ready authentication setup with multiple strategies."""

    # API key authentication
    async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
        """Validate API key from database."""
        api_key = request.headers.get("X-API-Key")
        # In production: check database, rate limits, etc.
        if api_key and api_key.startswith("sk-"):
            return True, None
        return False, JSONResponse({"error": "Invalid API key"}, status_code=401)

    # OAuth2 token authentication
    async def oauth_auth(request: Request) -> tuple[bool, Response | None]:
        """Validate OAuth2 bearer token."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # In production: validate with OAuth2 provider
            return True, None
        return False, JSONResponse({"error": "Invalid OAuth token"}, status_code=401)

    # Internal service authentication
    async def service_auth(request: Request) -> tuple[bool, Response | None]:
        """Validate internal service credentials."""
        service_key = request.headers.get("X-Service-Key")
        # In production: validate service-to-service key
        if service_key and service_key.startswith("svc-"):
            return True, None
        return False, JSONResponse({"error": "Invalid service key"}, status_code=403)

    flock = Flock()

    auth_component = AuthenticationComponent(
        config=AuthenticationComponentConfig(
            # Default to API key for backwards compatibility
            default_handler="api_key",
            route_configs=[
                # OAuth for user-facing API
                RouteSpecificAuthConfig(
                    path_pattern=r"^/api/v1/user/.*", handler_name="oauth"
                ),
                # Service authentication for internal APIs
                RouteSpecificAuthConfig(
                    path_pattern=r"^/internal/.*", handler_name="service"
                ),
                # Public webhooks (no auth)
                RouteSpecificAuthConfig(
                    path_pattern=r"^/webhooks/public/.*",
                    handler_name="none",
                    enabled=False,
                ),
            ],
            # Standard public endpoints
            exclude_paths=[
                r"^/health$",
                r"^/metrics$",
                r"^/docs.*",
                r"^/openapi\.json$",
                r"^/redoc$",
            ],
        )
    )

    # Register all handlers
    auth_component.register_handler("api_key", api_key_auth)
    auth_component.register_handler("oauth", oauth_auth)
    auth_component.register_handler("service", service_auth)

    return flock, auth_component


# Run a simple example
async def main():
    """Run the basic API key example."""
    print("🔐 Authentication Component Example\n")

    _flock, auth_component = example_basic_api_key()

    print("✅ Created Flock instance with authentication")
    print(f"   - Default handler: {auth_component.config.default_handler}")
    print(f"   - Excluded paths: {auth_component.config.exclude_paths}")
    print(f"   - Registered handlers: {list(auth_component._handlers.keys())}")
    print(
        "\n🚀 Start the server with: await orchestrator.serve(components=[auth_component])"
    )
    print("\n📝 Try accessing endpoints with:")
    print(
        "   ✅ With auth:    curl -H 'X-API-Key: secret-key-123' http://localhost:8000/api/agents"
    )
    print("   ❌ Without auth: curl http://localhost:8000/api/agents")
    print("   ✅ Public:       curl http://localhost:8000/health")


if __name__ == "__main__":
    asyncio.run(main())
