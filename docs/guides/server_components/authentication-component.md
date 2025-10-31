---
title: AuthenticationComponent
description: The Authentication ServerComponent
tags:
 - server-components
 - authentication
 - endpoints
 - middleware
search:
  boost: 0.6
---
# AuthenticationComponent

The `AuthenticationComponent` provides flexible authentication middleware with support for multiple strategies, route-specific authentication, and easy integration with various authentication schemes (API keys, JWT, OAuth, etc.).

## Overview

This component acts as a security gateway for your Flock HTTP API, validating requests before they reach your business logic. It supports global authentication with per-route overrides, making it ideal for multi-tenant applications or APIs with different security requirements.

## Features

- **Multiple Auth Strategies** - Support different authentication methods (API key, JWT, OAuth, custom)
- **Route-Specific Authentication** - Different routes use different auth strategies
- **Path Exclusions** - Public endpoints bypass authentication
- **Async Handlers** - Fully async authentication for non-blocking I/O
- **Flexible Error Responses** - Custom error messages and status codes
- **Handler Registration** - Register auth handlers dynamically

## Configuration

### AuthenticationComponentConfig

Main configuration for the authentication component.

**Fields:**

- `default_handler` (str | None, default: `None`) - Name of the default authentication handler for all routes
- `route_configs` (list[RouteSpecificAuthConfig], default: `[]`) - Route-specific authentication overrides
- `exclude_paths` (list[str], default: `[]`) - Regex patterns for paths that bypass authentication

### RouteSpecificAuthConfig

Configuration for applying different authentication to specific routes.

**Fields:**

- `path_pattern` (str, **required**) - Regex pattern to match request paths (e.g., `^/api/admin/.*`)
- `handler_name` (str, **required**) - Name of the registered handler for this route
- `enabled` (bool, default: `True`) - Whether authentication is enabled for this route

## Authentication Handler Interface

An authentication handler is an async function with this signature:

```python
async def auth_handler(request: Request) -> tuple[bool, Response | None]:
    """
    Args:
        request: Starlette Request object

    Returns:
        tuple[bool, Response | None]:
            - (True, None): Authentication successful, continue processing
            - (False, Response): Authentication failed, return the Response
    """
```

## Usage Examples

### Example 1: Simple API Key Authentication

```python
from flock import Flock
from flock.components.server import (
    AuthenticationComponent,
    AuthenticationComponentConfig
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
    """Validate API key from headers."""
    api_key = request.headers.get("X-API-Key")

    if api_key == "secret-key-12345":
        return True, None  # ✅ Authentication successful

    # ❌ Authentication failed
    return False, JSONResponse(
        {"error": "Invalid API key"},
        status_code=401
    )

# Create component
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[
            r"^/health$",      # Public health endpoint
            r"^/docs.*",       # Public API docs
            r"^/openapi.json$" # Public OpenAPI schema
        ]
    )
)

# Register handler
auth.register_handler("api_key", api_key_auth)

flock = Flock()
await flock.serve(components=[auth])
```

### Example 2: JWT Bearer Token Authentication

```python
import jwt
from datetime import datetime

async def jwt_auth(request: Request) -> tuple[bool, Response | None]:
    """Validate JWT token from Authorization header."""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return False, JSONResponse(
            {"error": "Missing or invalid Authorization header"},
            status_code=401
        )

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        # Validate JWT (use your secret key)
        payload = jwt.decode(
            token,
            "your-secret-key",
            algorithms=["HS256"]
        )

        # Check expiration
        if payload.get("exp", 0) < datetime.now().timestamp():
            return False, JSONResponse(
                {"error": "Token expired"},
                status_code=401
            )

        # ✅ Token valid
        return True, None

    except jwt.InvalidTokenError as e:
        return False, JSONResponse(
            {"error": f"Invalid token: {str(e)}"},
            status_code=401
        )

auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(default_handler="jwt")
)
auth.register_handler("jwt", jwt_auth)
```

### Example 3: Route-Specific Authentication

Different routes require different authentication levels:

```python
async def public_auth(request: Request) -> tuple[bool, Response | None]:
    """Simple API key for public endpoints."""
    api_key = request.headers.get("X-API-Key")

    if api_key and api_key.startswith("public-"):
        return True, None

    return False, JSONResponse(
        {"error": "Public API key required"},
        status_code=401
    )

async def admin_auth(request: Request) -> tuple[bool, Response | None]:
    """JWT authentication with admin role check."""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return False, JSONResponse(
            {"error": "Admin access requires Bearer token"},
            status_code=403
        )

    token = auth_header[7:]

    try:
        payload = jwt.decode(token, "secret", algorithms=["HS256"])

        # Check admin role
        if payload.get("role") != "admin":
            return False, JSONResponse(
                {"error": "Insufficient privileges"},
                status_code=403
            )

        return True, None

    except jwt.InvalidTokenError:
        return False, JSONResponse(
            {"error": "Invalid admin token"},
            status_code=403
        )

# Configure route-specific auth
from flock.components.server import RouteSpecificAuthConfig

auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="public_auth",  # Default for all routes
        route_configs=[
            RouteSpecificAuthConfig(
                path_pattern=r"^/api/admin/.*",  # Admin routes
                handler_name="admin_auth"
            ),
            RouteSpecificAuthConfig(
                path_pattern=r"^/api/internal/.*",  # Internal routes
                handler_name="admin_auth"
            )
        ],
        exclude_paths=[
            r"^/health$",
            r"^/docs.*"
        ]
    )
)

auth.register_handler("public_auth", public_auth)
auth.register_handler("admin_auth", admin_auth)
```

### Example 4: Disabling Authentication for Specific Routes

```python
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="strict_auth",  # Global authentication
        route_configs=[
            RouteSpecificAuthConfig(
                path_pattern=r"^/api/public/.*",
                handler_name="unused",
                enabled=False  # ⚠️ Disable auth for this route
            )
        ],
        exclude_paths=[r"^/health$"]
    )
)
```

### Example 5: Database-Backed Authentication

```python
from sqlalchemy import select
from myapp.models import User
from myapp.database import async_session

async def db_api_key_auth(request: Request) -> tuple[bool, Response | None]:
    """Validate API key against database."""
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        return False, JSONResponse(
            {"error": "API key required"},
            status_code=401
        )

    # Query database
    async with async_session() as session:
        stmt = select(User).where(User.api_key == api_key, User.active == True)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user:
        # Optional: Store user info in request state
        request.state.user = user
        return True, None

    return False, JSONResponse(
        {"error": "Invalid or inactive API key"},
        status_code=401
    )
```

## Best Practices

### 1. Always Exclude Health Endpoints

```python
# ✅ CORRECT: Health checks don't require auth
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[
            r"^/health$",
            r"^/metrics$",
        ]
    )
)
```

### 2. Use Appropriate Status Codes

```python
# ✅ CORRECT: 401 for authentication, 403 for authorization
async def auth_handler(request: Request) -> tuple[bool, Response | None]:
    if not has_credentials(request):
        return False, JSONResponse(
            {"error": "Authentication required"},
            status_code=401  # ✅ Missing/invalid credentials
        )

    if not has_permission(request):
        return False, JSONResponse(
            {"error": "Insufficient permissions"},
            status_code=403  # ✅ Valid credentials, insufficient access
        )

    return True, None
```

### 3. Handle Errors Gracefully

```python
# ✅ CORRECT: Catch exceptions in handlers
async def safe_auth_handler(request: Request) -> tuple[bool, Response | None]:
    try:
        # Authentication logic
        return validate_token(request)
    except Exception as e:
        # Log error
        logger.error(f"Authentication error: {e}")

        # Return generic error (don't leak implementation details)
        return False, JSONResponse(
            {"error": "Authentication service error"},
            status_code=500
        )
```

### 4. Store User Context in Request State

```python
async def auth_with_context(request: Request) -> tuple[bool, Response | None]:
    """Store authenticated user in request state for downstream use."""
    token = extract_token(request)

    if not token:
        return False, JSONResponse({"error": "No token"}, status_code=401)

    user = await validate_and_get_user(token)

    if user:
        # ✅ Store user for use in route handlers
        request.state.user = user
        request.state.user_id = user.id
        return True, None

    return False, JSONResponse({"error": "Invalid token"}, status_code=401)

# In your route handler:
@app.get("/api/profile")
async def get_profile(request: Request):
    user = request.state.user  # ✅ Access authenticated user
    return {"username": user.username}
```

### 5. Test Authentication Paths

```python
# Test both success and failure paths
async def test_api_key_auth():
    # ✅ Valid key
    request = MockRequest(headers={"X-API-Key": "valid-key"})
    success, response = await api_key_auth(request)
    assert success is True
    assert response is None

    # ❌ Invalid key
    request = MockRequest(headers={"X-API-Key": "invalid-key"})
    success, response = await api_key_auth(request)
    assert success is False
    assert response.status_code == 401

    # ❌ Missing key
    request = MockRequest(headers={})
    success, response = await api_key_auth(request)
    assert success is False
    assert response.status_code == 401
```

## Security Considerations

### 1. Never Log Sensitive Data

```python
# ❌ WRONG: Logging secrets
async def bad_auth(request: Request) -> tuple[bool, Response | None]:
    api_key = request.headers.get("X-API-Key")
    logger.info(f"Validating key: {api_key}")  # ❌ Leaks secrets!

# ✅ CORRECT: Log without secrets
async def good_auth(request: Request) -> tuple[bool, Response | None]:
    api_key = request.headers.get("X-API-Key")
    logger.info(f"Validating key: {api_key[:4]}****")  # ✅ Redacted
```

### 2. Use HTTPS in Production

```python
# Add middleware to enforce HTTPS
async def enforce_https(request: Request) -> tuple[bool, Response | None]:
    if not request.url.scheme == "https":
        return False, JSONResponse(
            {"error": "HTTPS required"},
            status_code=403
        )

    # Continue with normal auth
    return await api_key_auth(request)
```

### 3. Implement Rate Limiting

```python
from collections import defaultdict
import time

# Simple rate limiter
_request_counts = defaultdict(list)

async def rate_limited_auth(request: Request) -> tuple[bool, Response | None]:
    """Rate limit authentication attempts."""
    client_ip = request.client.host

    # Clean old attempts (last 60 seconds)
    cutoff = time.time() - 60
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if t > cutoff
    ]

    # Check rate limit (max 10 attempts per minute)
    if len(_request_counts[client_ip]) >= 10:
        return False, JSONResponse(
            {"error": "Too many authentication attempts"},
            status_code=429
        )

    # Record this attempt
    _request_counts[client_ip].append(time.time())

    # Continue with normal auth
    return await api_key_auth(request)
```

## Component Properties

- **Name:** `authentication`
- **Priority:** `7` (before business logic, after CORS)
- **Default Handler:** `None` (must be configured)
- **Dependencies:** None
- **Middleware:** Yes (adds authentication middleware)

## Related Components

- **[CORSComponent](cors-component.md)** - Handle preflight requests before authentication
- **[MiddlewareComponent](middleware-component.md)** - Add logging/timing around authentication
- **[ControlRoutesComponent](control-routes-component.md)** - Secure control endpoints

## Example Code

See the complete example: **[examples/09-server-components/01_authentication_component.py](../../../examples/09-server-components/01_authentication_component.py)**

## Troubleshooting

### Authentication not applied to routes

**Problem:** Routes accessible without authentication

**Solution:** Check handler registration and default_handler config

```python
# ❌ WRONG: Handler not registered
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(default_handler="api_key")
)
# Missing: auth.register_handler("api_key", api_key_auth)

# ✅ CORRECT: Handler registered
auth.register_handler("api_key", api_key_auth)
```

### CORS preflight fails with 401/403

**Problem:** OPTIONS requests rejected by authentication

**Solution:** Configure CORS component BEFORE authentication

```python
# ✅ CORRECT: CORS handles OPTIONS before auth middleware
components = [
    HealthAndMetricsComponent(priority=0),
    CORSComponent(priority=6),           # ✅ Before auth
    AuthenticationComponent(priority=7), # ✅ After CORS
]
```

### Public endpoints require authentication

**Problem:** Health checks or docs require auth

**Solution:** Add to exclude_paths

```python
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[
            r"^/health$",
            r"^/metrics$",
            r"^/docs$",
            r"^/openapi.json$",
            r"^/redoc$",
        ]
    )
)
```
