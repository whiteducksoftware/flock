# Server Components Guide

Server Components extend Flock's HTTP API with custom middleware, routes, and lifecycle management. They provide a modular way to add authentication, CORS, custom endpoints, and other server-side functionality.

## Overview

Server Components follow the same pattern as Agent Components but operate at the HTTP server level. They can:

- **Configure middleware** - Add authentication, CORS, logging, etc.
- **Register routes** - Create custom HTTP endpoints
- **Manage lifecycle** - Run startup/shutdown tasks
- **Control ordering** - Use priority to control registration order

## Architecture

### Lifecycle Phases

```
1. __init__()                    # Component creation
2. configure(app, orchestrator)  # Configure FastAPI app (middleware, etc.)
3. register_routes(app, orchestrator)  # Add endpoints
4. on_startup_async(orchestrator)  # Async startup tasks
5. ...service runs...
6. on_shutdown_async(orchestrator)  # Async cleanup
```

### Priority System

Components register in priority order (lower numbers first):

- `0-5`: Core infrastructure (health, metrics)
- `6-10`: Security (CORS, authentication)
- `11-50`: Business logic (agents, artifacts, control)
- `51-99`: Static files (must be last to avoid route conflicts)

## Built-in Components

### HealthAndMetricsComponent

Provides health check and Prometheus-style metrics endpoints.

```python
from flock import Flock
from flock.components.server import (
    HealthAndMetricsComponent,
    HealthComponentConfig
)

flock = Flock()

health = HealthAndMetricsComponent(
    config=HealthComponentConfig(
        prefix="/api/v1",
        tags=["Health & Metrics"]
    )
)

await flock.serve(components=[health])
```

**Endpoints:**
- `GET /health` - Returns `{"status": "ok"}`
- `GET /metrics` - Returns Prometheus-style metrics

### CORSComponent

Configures Cross-Origin Resource Sharing (CORS) policies.

```python
from flock.components.server import (
    CORSComponent,
    CORSComponentConfig,
    RouteSpecificCORSConfig
)

cors = CORSComponent(
    config=CORSComponentConfig(
        # Global settings
        allow_origins=["https://example.com"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_credentials=True,
        
        # Route-specific overrides
        route_configs=[
            RouteSpecificCORSConfig(
                path_pattern=r"^/api/public/.*",
                allow_origins=["*"],
                allow_credentials=False
            ),
            RouteSpecificCORSConfig(
                path_pattern=r"^/api/admin/.*",
                allow_origins=["https://admin.example.com"],
                allow_methods=["GET", "POST"]
            )
        ]
    )
)
```

**See also:** [examples/09-server-components/cors_advanced_example.py](../../examples/09-server-components/cors_advanced_example.py)

### AuthenticationComponent

Flexible authentication middleware with support for multiple strategies.

```python
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from flock.components.server import (
    AuthenticationComponent,
    AuthenticationComponentConfig,
    RouteSpecificAuthConfig
)

# Define authentication handler
async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
    """Validate API key from headers."""
    api_key = request.headers.get("X-API-Key")
    
    if api_key == "secret-key":
        return True, None  # Authentication successful
    
    # Authentication failed - return error response
    return False, JSONResponse(
        {"error": "Invalid API key"},
        status_code=401
    )

# Create component
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[
            r"^/health$",
            r"^/docs.*"
        ]
    )
)

# Register handler
auth.register_handler("api_key", api_key_auth)

await flock.serve(components=[auth])
```

#### Route-Specific Authentication

Different routes can use different authentication strategies:

```python
async def public_auth(request: Request) -> tuple[bool, Response | None]:
    """Simple API key for public endpoints."""
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.startswith("public-"):
        return True, None
    return False, JSONResponse({"error": "Invalid public key"}, status_code=401)

async def admin_auth(request: Request) -> tuple[bool, Response | None]:
    """JWT authentication for admin endpoints."""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return False, JSONResponse(
            {"error": "Admin access requires Bearer token"},
            status_code=403
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Validate JWT (simplified)
    if token == "valid-admin-token":
        return True, None
    
    return False, JSONResponse(
        {"error": "Insufficient privileges"},
        status_code=403
    )

auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        route_configs=[
            RouteSpecificAuthConfig(
                path_pattern=r"^/api/public/.*",
                handler_name="public_auth"
            ),
            RouteSpecificAuthConfig(
                path_pattern=r"^/api/admin/.*",
                handler_name="admin_auth"
            )
        ],
        exclude_paths=[r"^/health$", r"^/docs.*"]
    )
)

auth.register_handler("public_auth", public_auth)
auth.register_handler("admin_auth", admin_auth)
```

#### Disabling Authentication for Specific Routes

You can explicitly disable authentication for certain routes:

```python
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="strict_auth",  # Global authentication
        route_configs=[
            RouteSpecificAuthConfig(
                path_pattern=r"^/api/public/.*",
                handler_name="unused",
                enabled=False  # Disable auth for this route
            )
        ]
    )
)
```

**See also:** [examples/09-server-components/authentication_examples.py](../../examples/09-server-components/authentication_examples.py)

### WebSocketServerComponent

Manages WebSocket connections for real-time dashboard updates.

```python
from flock.components.server import (
    WebSocketServerComponent,
    WebSocketComponentConfig
)

websocket = WebSocketServerComponent(
    config=WebSocketComponentConfig(
        prefix="/ws",
        max_connections=100
    )
)
```

**Endpoints:**
- `WS /ws` - WebSocket connection for live updates

### AgentsServerComponent

Exposes agent metadata and control via HTTP endpoints.

```python
from flock.components.server import (
    AgentsServerComponent,
    AgentsServerComponentConfig
)

agents = AgentsServerComponent(
    config=AgentsServerComponentConfig(
        prefix="/api/v1",
        tags=["Agents"]
    )
)
```

**Endpoints:**
- `GET /api/v1/agents` - List all agents
- `GET /api/v1/agents/{name}` - Get agent details

### ArtifactsComponent

Provides REST API for querying and publishing artifacts.

```python
from flock.components.server import (
    ArtifactsComponent,
    ArtifactComponentConfig
)

artifacts = ArtifactsComponent(
    config=ArtifactComponentConfig(
        prefix="/api/v1",
        tags=["Artifacts"],
        enable_pagination=True,
        default_page_size=50
    )
)
```

**Endpoints:**
- `GET /api/v1/artifacts` - Query artifacts (with filtering)
- `POST /api/v1/artifacts` - Publish new artifact

### ControlRoutesComponent

Provides control endpoints for agent execution.

```python
from flock.components.server import (
    ControlRoutesComponent,
    ControlRoutesComponentConfig
)

control = ControlRoutesComponent(
    config=ControlRoutesComponentConfig(
        prefix="/api/v1",
        tags=["Control"]
    )
)
```

**Endpoints:**
- `POST /api/v1/agents/{name}/invoke` - Execute specific agent

### StaticFilesServerComponent

Serves static files (dashboard UI, assets).

```python
from flock.components.server import (
    StaticFilesServerComponent,
    StaticFilesComponentConfig
)

static = StaticFilesServerComponent(
    config=StaticFilesComponentConfig(
        directory="/path/to/static/files",
        html=True  # Serve index.html for SPA routing
    ),
    priority=99  # Must be LAST to avoid route conflicts
)
```

## Creating Custom Components

### Basic Structure

```python
from typing import Any
from flock.components.server import ServerComponent, ServerComponentConfig

class MyComponentConfig(ServerComponentConfig):
    """Configuration for my component."""
    
    my_setting: str = "default_value"

class MyComponent(ServerComponent):
    """My custom server component."""
    
    name: str = "my_component"
    priority: int = 10
    config: MyComponentConfig = MyComponentConfig()
    
    def configure(self, app: Any, orchestrator: Any) -> None:
        """Configure middleware, etc."""
        # Add middleware if needed
        pass
    
    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """Register HTTP endpoints."""
        
        @app.get("/my-endpoint")
        async def my_endpoint():
            return {"status": "ok"}
    
    async def on_startup_async(self, orchestrator: Any) -> None:
        """Async startup tasks."""
        print("MyComponent starting...")
    
    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Async cleanup tasks."""
        print("MyComponent stopping...")
```

### Example: Custom Logging Component

```python
import time
from typing import Any
from starlette.types import ASGIApp, Receive, Scope, Send
from flock.components.server import ServerComponent, ServerComponentConfig

class LoggingComponent(ServerComponent):
    """Component that logs all HTTP requests."""
    
    name: str = "request_logging"
    priority: int = 5  # Run early to capture all requests
    
    def configure(self, app: Any, orchestrator: Any) -> None:
        """Add logging middleware."""
        
        class RequestLoggingMiddleware:
            def __init__(self, app: ASGIApp):
                self.app = app
            
            async def __call__(
                self,
                scope: Scope,
                receive: Receive,
                send: Send
            ) -> None:
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return
                
                start_time = time.time()
                path = scope.get("path", "")
                method = scope.get("method", "")
                
                # Process request
                await self.app(scope, receive, send)
                
                duration = time.time() - start_time
                print(f"{method} {path} - {duration:.3f}s")
        
        app.add_middleware(RequestLoggingMiddleware)
    
    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """No routes needed for logging."""
        pass
```

### Example: Rate Limiting Component

```python
from collections import defaultdict
import time
from typing import Any
from starlette.requests import Request
from starlette.responses import JSONResponse
from pydantic import Field
from flock.components.server import ServerComponent, ServerComponentConfig

class RateLimitConfig(ServerComponentConfig):
    """Configuration for rate limiting."""
    
    max_requests: int = Field(
        default=100,
        description="Maximum requests per window"
    )
    window_seconds: int = Field(
        default=60,
        description="Time window in seconds"
    )

class RateLimitComponent(ServerComponent):
    """Component that implements rate limiting."""
    
    name: str = "rate_limit"
    priority: int = 6  # Before business logic, after CORS
    config: RateLimitConfig = RateLimitConfig()
    
    # Track requests per IP
    _request_counts: dict[str, list[float]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True
    )
    
    def configure(self, app: Any, orchestrator: Any) -> None:
        """Add rate limiting middleware."""
        from starlette.types import ASGIApp, Receive, Scope, Send
        
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
                
                # Get client IP
                client_ip = scope.get("client", ["unknown"])[0]
                
                # Check rate limit
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
                
                # Process request
                await self.app(scope, receive, send)
        
        app.add_middleware(RateLimitMiddleware, parent=self)
    
    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """No routes needed."""
        pass
```

## Best Practices

### 1. Use Priority Correctly

```python
# ✅ CORRECT: Core infrastructure first
health = HealthAndMetricsComponent(priority=0)
cors = CORSComponent(priority=8)
auth = AuthenticationComponent(priority=7)
agents = AgentsServerComponent(priority=20)
static = StaticFilesServerComponent(priority=99)  # Last!

# ❌ WRONG: Static files before business logic
static = StaticFilesServerComponent(priority=10)  # Will catch all routes!
agents = AgentsServerComponent(priority=20)  # Never reached
```

### 2. Handle Errors in Middleware

```python
async def auth_handler(request: Request) -> tuple[bool, Response | None]:
    """Always handle exceptions in auth handlers."""
    try:
        api_key = request.headers.get("X-API-Key")
        # Validate key...
        return True, None
    except Exception as e:
        # Return proper error response
        return False, JSONResponse(
            {"error": f"Authentication error: {str(e)}"},
            status_code=500
        )
```

### 3. Use Dependencies Wisely

```python
class MyComponent(ServerComponent):
    def get_dependencies(self) -> list[type[ServerComponent]]:
        """Declare dependencies for validation."""
        return [AuthenticationComponent]  # Requires auth component
```

### 4. Clean Up Resources

```python
class MyComponent(ServerComponent):
    _db_connection = None
    
    async def on_startup_async(self, orchestrator: Any) -> None:
        """Connect to database."""
        self._db_connection = await connect_to_db()
    
    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Close database connection."""
        if self._db_connection:
            await self._db_connection.close()
```

### 5. Path Joining Helper

Use `_join_path()` for consistent URL handling:

```python
def register_routes(self, app: Any, orchestrator: Any) -> None:
    prefix = self.config.prefix or ""
    
    # ✅ CORRECT: Use helper
    health_path = self._join_path(prefix, "health")
    metrics_path = self._join_path(prefix, "metrics")
    
    # ❌ WRONG: Manual joining
    health_path = f"{prefix}/health"  # Can create double slashes
```

## Complete Example

Here's a production-ready setup with multiple components:

```python
from flock import Flock
from flock.components.server import (
    HealthAndMetricsComponent,
    CORSComponent,
    CORSComponentConfig,
    AuthenticationComponent,
    AuthenticationComponentConfig,
    RouteSpecificAuthConfig,
    AgentsServerComponent,
    ArtifactsComponent,
    StaticFilesServerComponent,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Authentication handlers
async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.startswith("sk-"):
        return True, None
    return False, JSONResponse({"error": "Invalid API key"}, status_code=401)

async def admin_auth(request: Request) -> tuple[bool, Response | None]:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Validate JWT
        return True, None
    return False, JSONResponse({"error": "Admin access denied"}, status_code=403)

# Create Flock instance
flock = Flock()

# Configure components
components = [
    # 1. Health (priority 0)
    HealthAndMetricsComponent(),
    
    # 2. CORS (priority 8)
    CORSComponent(
        config=CORSComponentConfig(
            allow_origins=["https://app.example.com"],
            allow_credentials=True
        )
    ),
    
    # 3. Authentication (priority 7)
    AuthenticationComponent(
        config=AuthenticationComponentConfig(
            default_handler="api_key",
            route_configs=[
                RouteSpecificAuthConfig(
                    path_pattern=r"^/api/admin/.*",
                    handler_name="admin_auth"
                )
            ],
            exclude_paths=[r"^/health$", r"^/metrics$", r"^/docs.*"]
        )
    ),
    
    # 4. Business logic (priority 20)
    AgentsServerComponent(),
    ArtifactsComponent(),
    
    # 5. Static files (priority 99 - MUST BE LAST!)
    StaticFilesServerComponent(priority=99),
]

# Register auth handlers
auth_component = components[2]  # AuthenticationComponent
auth_component.register_handler("api_key", api_key_auth)
auth_component.register_handler("admin_auth", admin_auth)

# Start server
await flock.serve(
    components=components,
    host="0.0.0.0",
    port=8000
)
```

## Related Documentation

- **[REST API Guide](rest-api.md)** - HTTP API reference
- **[Agent Components](components.md)** - Agent-level components
- **[Orchestrator Components](orchestrator-components.md)** - Orchestrator-level components

## Examples

- **[examples/09-server-components/cors_advanced_example.py](../../examples/09-server-components/cors_advanced_example.py)** - CORS configuration patterns
- **[examples/09-server-components/authentication_examples.py](../../examples/09-server-components/authentication_examples.py)** - Authentication strategies
