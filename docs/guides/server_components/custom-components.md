---
title: Custom ServerComponents
description: How to create your own Custom Server Components
tags:
 - endpoints
 - middleware
 - custom-endpoints
 - api
search:
  boost: 2.5
---
# Creating Custom Server Components

This guide walks you through creating your own Server Components to extend Flock's HTTP API with custom functionality.

## What Are Server Components?

Server Components are modular extensions that add functionality to Flock's HTTP server. They can:

- **Add middleware** - Authentication, logging, rate limiting, etc.
- **Register routes** - Custom HTTP endpoints
- **Manage lifecycle** - Startup and shutdown tasks
- **Control ordering** - Execute in specific order via priority

## Basic Component Structure

Every Server Component extends the `ServerComponent` base class:

```python
from typing import Any
from pydantic import Field
from flock.components.server import ServerComponent, ServerComponentConfig

class MyComponentConfig(ServerComponentConfig):
    """Configuration for my component."""

    my_setting: str = "default_value"
    enable_feature: bool = True

class MyComponent(ServerComponent):
    """My custom server component."""

    name: str = "my_component"  # Unique identifier
    priority: int = 10  # Registration order (0-99)
    config: MyComponentConfig = Field(
        default_factory=MyComponentConfig,
        description="Component configuration"
    )

    def configure(self, app: Any, orchestrator: Any) -> None:
        """Configure middleware, app settings, etc."""
        pass

    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """Register HTTP endpoints."""
        pass

    async def on_startup_async(self, orchestrator: Any) -> None:
        """Async startup tasks."""
        pass

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Async cleanup tasks."""
        pass
```

## Step-by-Step: Building a Custom Component

### Step 1: Define Configuration

Start by defining your component's configuration using Pydantic:

```python
from pydantic import Field
from flock.components.server import ServerComponentConfig

class RateLimitConfig(ServerComponentConfig):
    """Configuration for rate limiting component."""

    max_requests: int = Field(
        default=100,
        description="Maximum requests per window"
    )
    window_seconds: int = Field(
        default=60,
        description="Time window in seconds"
    )
    exclude_paths: list[str] = Field(
        default_factory=lambda: [r"^/health$"],
        description="Paths excluded from rate limiting"
    )
```

### Step 2: Create Component Class

Define your component by extending `ServerComponent`:

```python
from collections import defaultdict
import time
from typing import Any
from pydantic import Field, PrivateAttr

class RateLimitComponent(ServerComponent):
    """Component that implements rate limiting."""

    name: str = "rate_limit"
    priority: int = 6  # Before business logic, after CORS
    config: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting configuration"
    )

    # Private fields for internal state (excluded from serialization)
    _request_counts: dict[str, list[float]] = PrivateAttr(
        default_factory=lambda: defaultdict(list)
    )
```

### Step 3: Implement `configure()` for Middleware

Add middleware in the `configure()` method:

```python
def configure(self, app: Any, orchestrator: Any) -> None:
    """Add rate limiting middleware."""
    from starlette.types import ASGIApp, Receive, Scope, Send
    from starlette.responses import JSONResponse
    import re

    class RateLimitMiddleware:
        def __init__(self, app: ASGIApp, parent: "RateLimitComponent"):
            self.app = app
            self.parent = parent

        async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send
        ) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            # Check if path is excluded
            path = scope.get("path", "")
            for pattern in self.parent.config.exclude_paths:
                if re.match(pattern, path):
                    await self.app(scope, receive, send)
                    return

            # Get client IP
            client_ip = scope.get("client", ["unknown"])[0]

            # Rate limiting logic
            now = time.time()
            window_start = now - self.parent.config.window_seconds

            # Clean old requests
            self.parent._request_counts[client_ip] = [
                t for t in self.parent._request_counts[client_ip]
                if t > window_start
            ]

            # Check if over limit
            if len(self.parent._request_counts[client_ip]) >= self.parent.config.max_requests:
                response = JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "retry_after": int(window_start + self.parent.config.window_seconds - now)
                    },
                    status_code=429
                )
                await response(scope, receive, send)
                return

            # Record this request
            self.parent._request_counts[client_ip].append(now)

            # Continue to next middleware/route
            await self.app(scope, receive, send)

    # Add middleware to FastAPI app
    app.add_middleware(RateLimitMiddleware, parent=self)
```

### Step 4: Implement `register_routes()` for Endpoints

Add HTTP endpoints in the `register_routes()` method:

```python
def register_routes(self, app: Any, orchestrator: Any) -> None:
    """Register rate limit status endpoint."""

    @app.get("/rate-limit/status")
    async def get_rate_limit_status() -> dict[str, Any]:
        """Get current rate limit statistics."""
        total_ips = len(self._request_counts)
        active_limits = sum(
            1 for counts in self._request_counts.values()
            if len(counts) >= self.config.max_requests * 0.8  # >80% of limit
        )

        return {
            "max_requests": self.config.max_requests,
            "window_seconds": self.config.window_seconds,
            "tracked_ips": total_ips,
            "active_limits": active_limits
        }

    @app.delete("/rate-limit/reset")
    async def reset_rate_limits() -> dict[str, str]:
        """Reset all rate limits (admin only)."""
        self._request_counts.clear()
        return {"status": "Rate limits reset"}
```

### Step 5: Implement Lifecycle Hooks

Add startup and shutdown logic:

```python
async def on_startup_async(self, orchestrator: Any) -> None:
    """Initialize component on startup."""
    from flock.logging.logging import get_logger

    logger = get_logger(__name__)
    logger.info(
        f"RateLimitComponent started: "
        f"{self.config.max_requests} requests per {self.config.window_seconds}s"
    )

async def on_shutdown_async(self, orchestrator: Any) -> None:
    """Cleanup on shutdown."""
    from flock.logging.logging import get_logger

    logger = get_logger(__name__)
    logger.info("RateLimitComponent shutting down")

    # Optional: Persist rate limit data to database
    # await save_rate_limits(self._request_counts)
```

### Step 6: Use the Component

```python
from flock import Flock

flock = Flock()

# Create component with custom config
rate_limiter = RateLimitComponent(
    config=RateLimitConfig(
        max_requests=50,  # 50 requests
        window_seconds=60,  # per minute
        exclude_paths=[
            r"^/health$",
            r"^/metrics$"
        ]
    )
)

# Use with Flock
await flock.serve(
    components=[rate_limiter],
    port=8000
)
```

## Advanced Patterns

### Pattern 1: Components with Dependencies

Declare dependencies on other components:

```python
class MyComponent(ServerComponent):
    name: str = "my_component"

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """Declare required components."""
        from flock.components.server import AuthenticationComponent

        return [AuthenticationComponent]  # Requires auth

    def configure(self, app: Any, orchestrator: Any) -> None:
        # Now we can safely assume AuthenticationComponent is registered
        pass
```

### Pattern 2: Path Joining Helper

Use the `_join_path()` helper for consistent URL construction:

```python
def register_routes(self, app: Any, orchestrator: Any) -> None:
    """Register routes with proper path handling."""
    prefix = self.config.prefix or ""

    # ✅ CORRECT: Use helper
    users_path = self._join_path(prefix, "users")
    posts_path = self._join_path(prefix, "posts")

    # Helper handles:
    # - Double slashes: "/api/" + "users" → "/api/users" (not "/api//users")
    # - Missing slashes: "/api" + "users" → "/api/users"
    # - Empty prefixes: "" + "users" → "/users"

    @app.get(users_path)
    async def get_users():
        return {"users": []}
```

### Pattern 3: Request State Management

Store component state in requests:

```python
class SessionComponent(ServerComponent):
    """Component that manages sessions."""

    def configure(self, app: Any, orchestrator: Any) -> None:
        from starlette.types import ASGIApp, Receive, Scope, Send

        class SessionMiddleware:
            def __init__(self, app: ASGIApp, parent: "SessionComponent"):
                self.app = app
                self.parent = parent

            async def __call__(
                self,
                scope: Scope,
                receive: Receive,
                send: Send
            ) -> None:
                if scope["type"] == "http":
                    # Create session and store in scope
                    session_id = self.parent._create_session()
                    scope["state"] = {"session_id": session_id}

                await self.app(scope, receive, send)

        app.add_middleware(SessionMiddleware, parent=self)

    def _create_session(self) -> str:
        """Create a new session."""
        import uuid
        return str(uuid.uuid4())
```

### Pattern 4: Database Integration

Components with database connections:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from pydantic import PrivateAttr

class DatabaseComponent(ServerComponent):
    """Component that provides database connectivity."""

    name: str = "database"
    priority: int = 0  # Initialize early

    _engine: Any = PrivateAttr(default=None)
    _session_factory: Any = PrivateAttr(default=None)

    async def on_startup_async(self, orchestrator: Any) -> None:
        """Create database engine and session factory."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        # Create async engine
        self._engine = create_async_engine(
            "postgresql+asyncpg://user:pass@localhost/db",
            echo=True
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()

    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """Register database-backed endpoints."""

        @app.get("/users")
        async def get_users():
            async with self._session_factory() as session:
                # Use session for queries
                result = await session.execute("SELECT * FROM users")
                return {"users": result.all()}
```

### Pattern 5: External Service Integration

Components that call external APIs:

```python
import httpx
from pydantic import PrivateAttr

class NotificationComponent(ServerComponent):
    """Component for sending notifications via external service."""

    name: str = "notifications"

    _http_client: httpx.AsyncClient = PrivateAttr(default=None)

    async def on_startup_async(self, orchestrator: Any) -> None:
        """Create HTTP client."""
        self._http_client = httpx.AsyncClient(
            base_url="https://api.notifications.example.com",
            headers={"Authorization": "Bearer <token>"}
        )

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    async def send_notification(self, message: str) -> None:
        """Send a notification."""
        response = await self._http_client.post(
            "/notifications",
            json={"message": message}
        )
        response.raise_for_status()
```

## Priority Guidelines

Choose priority based on when your component should execute:

```python
# 0-5: Core infrastructure
HealthAndMetricsComponent(priority=0)
DatabaseComponent(priority=1)

# 6-10: Security and cross-cutting concerns
CORSComponent(priority=6)
AuthenticationComponent(priority=7)
RateLimitComponent(priority=8)

# 11-50: Business logic
AgentsServerComponent(priority=20)
ArtifactsComponent(priority=20)
CustomBusinessComponent(priority=25)

# 51-99: Static files (MUST BE LAST!)
StaticFilesServerComponent(priority=99)
```

## Testing Custom Components

### Unit Testing

```python
import pytest
from fastapi import FastAPI
from flock import Flock

@pytest.mark.asyncio
async def test_rate_limit_component():
    """Test rate limiting component."""
    app = FastAPI()
    orchestrator = Flock()

    # Create component
    rate_limiter = RateLimitComponent(
        config=RateLimitConfig(
            max_requests=5,
            window_seconds=60
        )
    )

    # Configure and register
    rate_limiter.configure(app, orchestrator)
    rate_limiter.register_routes(app, orchestrator)

    # Test routes exist
    routes = [route.path for route in app.routes]
    assert "/rate-limit/status" in routes

    # Test startup
    await rate_limiter.on_startup_async(orchestrator)

    # Test functionality
    # ... make requests and verify rate limiting ...

    # Test shutdown
    await rate_limiter.on_shutdown_async(orchestrator)
```

### Integration Testing

```python
from fastapi.testclient import TestClient

def test_rate_limit_integration():
    """Test rate limiting with real HTTP requests."""
    app = FastAPI()
    orchestrator = Flock()

    rate_limiter = RateLimitComponent(
        config=RateLimitConfig(max_requests=3, window_seconds=60)
    )

    rate_limiter.configure(app, orchestrator)
    rate_limiter.register_routes(app, orchestrator)

    # Add a test endpoint
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    client = TestClient(app)

    # Make requests within limit
    for i in range(3):
        response = client.get("/test")
        assert response.status_code == 200

    # Next request should be rate limited
    response = client.get("/test")
    assert response.status_code == 429
    assert "retry_after" in response.json()
```

## Best Practices

### 1. Use Type Hints

```python
# ✅ CORRECT: Proper type hints
def register_routes(self, app: Any, orchestrator: Any) -> None:
    @app.get("/endpoint")
    async def my_endpoint() -> dict[str, str]:
        return {"status": "ok"}
```

### 2. Handle Errors Gracefully

```python
async def on_startup_async(self, orchestrator: Any) -> None:
    """Handle startup errors."""
    try:
        await self._initialize_resources()
    except Exception as e:
        logger.error(f"Failed to start {self.name}: {e}")
        raise  # Re-raise to prevent partial initialization
```

### 3. Use Pydantic Validation

```python
class MyComponentConfig(ServerComponentConfig):
    """Configuration with validation."""

    port: int = Field(ge=1, le=65535, description="Server port")
    timeout: float = Field(gt=0, description="Timeout in seconds")

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        if v > 300:
            raise ValueError("Timeout cannot exceed 5 minutes")
        return v
```

### 4. Document Your Component

```python
class MyComponent(ServerComponent):
    """Component for X functionality.

    This component provides:
    - Feature A: Description
    - Feature B: Description

    Configuration:
        setting1: What it does
        setting2: What it does

    Endpoints:
        GET /endpoint1 - Description
        POST /endpoint2 - Description

    Example:
        >>> component = MyComponent(
        ...     config=MyComponentConfig(setting1="value")
        ... )
        >>> await flock.serve(components=[component])
    """
```

### 5. Clean Up Resources

```python
async def on_shutdown_async(self, orchestrator: Any) -> None:
    """Ensure all resources are cleaned up."""
    if self._http_client:
        await self._http_client.aclose()

    if self._database_connection:
        await self._database_connection.close()

    if self._cache:
        await self._cache.clear()
```

## Common Pitfalls

### ❌ Forgetting to Call super()

```python
# ❌ WRONG: Doesn't call super()
def configure(self, app: Any, orchestrator: Any) -> None:
    # Your code here
    pass  # Missing: return super().configure(app, orchestrator)

# ✅ CORRECT: Calls super()
def configure(self, app: Any, orchestrator: Any) -> None:
    # Your code here
    return super().configure(app, orchestrator)
```

### ❌ Using Blocking I/O

```python
# ❌ WRONG: Blocks event loop
def configure(self, app: Any, orchestrator: Any) -> None:
    result = requests.get("https://api.example.com")  # Blocking!

# ✅ CORRECT: Use async
async def on_startup_async(self, orchestrator: Any) -> None:
    async with httpx.AsyncClient() as client:
        result = await client.get("https://api.example.com")
```

### ❌ Incorrect Priority

```python
# ❌ WRONG: Static files before business logic
StaticFilesServerComponent(priority=10)  # Catches all routes!
AgentsServerComponent(priority=20)       # Never reached

# ✅ CORRECT: Static files LAST
AgentsServerComponent(priority=20)
StaticFilesServerComponent(priority=99)  # Catch-all at end
```

## Next Steps

- **Review built-in components** - Study source code of existing components
- **Check examples** - See `examples/09-server-components/` for patterns
- **Read related docs** - [Server Components Guide](../server-components.md)
- **Test thoroughly** - Write unit and integration tests

## Related Documentation

- **[Server Components Guide](../server-components.md)** - Overview and built-in components
- **[MiddlewareComponent](middleware-component.md)** - Generic middleware pattern
- **[CORSComponent](cors-component.md)** - CORS middleware example
- **[AuthenticationComponent](authentication-component.md)** - Auth middleware example
