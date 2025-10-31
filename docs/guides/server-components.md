---
title: Server Components
description: Guide on how server components can be used to extend and modify the behavior of the flock API
tags:
 - http
 - custom endpoints
 - endpoints
 - websockets
 - authentication
 - telemetry
search:
 boost: 1.3
---

# ⚙️ Server Components Guide

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

Flock provides a comprehensive set of built-in server components:

### Infrastructure & Monitoring

- **[HealthAndMetricsComponent](server_components/health-component.md)** - Health checks and metrics endpoints
- **[TracingComponent](server_components/tracing-component.md)** - OpenTelemetry trace query API

### Security

- **[CORSComponent](server_components/cors-component.md)** - Cross-Origin Resource Sharing configuration
- **[AuthenticationComponent](server_components/authentication-component.md)** - Flexible authentication middleware
- **[MiddlewareComponent](server_components/middleware-component.md)** - Generic middleware support

### Business Logic

- **[AgentsServerComponent](server_components/agents-component.md)** - Agent metadata and control API
- **[ArtifactsComponent](server_components/artifacts-component.md)** - Artifact query and publishing API
- **[ControlRoutesComponent](server_components/control-routes-component.md)** - Control endpoints for orchestrator

### Real-time & Presentation

- **[WebSocketServerComponent](server_components/websocket-component.md)** - Real-time WebSocket updates
- **[StaticFilesServerComponent](server_components/static-files-component.md)** - Static file serving for dashboard
- **[ThemesComponent](server_components/themes-component.md)** - UI theme configuration

### Quick Reference

Below are brief examples for each component. Click the component name above for complete documentation.

### HealthAndMetricsComponent

Provides health check and Prometheus-style metrics endpoints.

```python
from flock import Flock
from flock.components.server import HealthAndMetricsComponent

health = HealthAndMetricsComponent()
await flock.serve(components=[health])
```

**Endpoints:**
- `GET /health` - Returns `{"status": "ok"}`
- `GET /metrics` - Returns Prometheus-style metrics

**📚 [Full Documentation](server_components/health-component.md)**

### CORSComponent

Configures Cross-Origin Resource Sharing (CORS) policies.

```python
from flock.components.server import CORSComponent, CORSComponentConfig

cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["https://example.com"],
        allow_credentials=True
    )
)
```

**📚 [Full Documentation](server_components/cors-component.md)**

### AuthenticationComponent

Flexible authentication middleware with support for multiple strategies.

```python
from flock.components.server import AuthenticationComponent, AuthenticationComponentConfig
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
    api_key = request.headers.get("X-API-Key")
    if api_key == "secret-key":
        return True, None
    return False, JSONResponse({"error": "Invalid API key"}, status_code=401)

auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[r"^/health$", r"^/docs.*"]
    )
)
auth.register_handler("api_key", api_key_auth)
```

**📚 [Full Documentation](server_components/authentication-component.md)**

### MiddlewareComponent

Generic middleware support for custom cross-cutting concerns.

```python
from flock.components.server import MiddlewareComponent, MiddlewareComponentConfig

middleware = MiddlewareComponent(
    config=MiddlewareComponentConfig(middlewares=[...])
)
```

**📚 [Full Documentation](server_components/middleware-component.md)**

### WebSocketServerComponent

Manages WebSocket connections for real-time dashboard updates.

```python
from flock.components.server import WebSocketServerComponent

websocket = WebSocketServerComponent()
```

**Endpoints:**
- `WS /plugin/ws` - WebSocket connection for live updates

**📚 [Full Documentation](server_components/websocket-component.md)**

### AgentsServerComponent

Exposes agent metadata and control via HTTP endpoints.

```python
from flock.components.server import AgentsServerComponent

agents = AgentsServerComponent()
```

**Endpoints:**
- `GET /api/v1/plugin/agents` - List all agents
- `GET /api/v1/plugin/agents/{name}/history-summary` - Agent execution history
- `GET /api/v1/plugin/correlations/{id}/status` - Workflow status

**📚 [Full Documentation](server_components/agents-component.md)**

### ArtifactsComponent

Provides REST API for querying and publishing artifacts.

```python
from flock.components.server import ArtifactsComponent

artifacts = ArtifactsComponent()
```

**Endpoints:**
- `GET /api/v1/plugin/artifacts` - Query artifacts (with filtering)
- `POST /api/v1/plugin/artifacts` - Publish new artifact

**📚 [Full Documentation](server_components/artifacts-component.md)**

### ControlRoutesComponent

Provides control endpoints for agent execution and graph visualization.

```python
from flock.components.server import ControlRoutesComponent

control = ControlRoutesComponent()
```

**Endpoints:**
- `GET /api/plugin/artifact_types` - List artifact types with schemas
- `POST /api/plugin/publish` - Publish artifact and trigger agents
- `GET /api/plugin/graph` - Get current graph snapshot

**📚 [Full Documentation](server_components/control-routes-component.md)**

### TracingComponent

Provides HTTP API for querying and managing OpenTelemetry traces.

```python
from flock.components.server import TracingComponent

tracing = TracingComponent()
```

**Endpoints:**
- `GET /api/plugin/traces` - Query traces
- `DELETE /api/plugin/traces/clear` - Clear all traces
- `POST /api/plugin/traces/query` - Execute custom SQL queries
- `GET /api/plugin/traces/stats` - Get trace statistics

**📚 [Full Documentation](server_components/tracing-component.md)**

### StaticFilesServerComponent

Serves static files (dashboard UI, assets).

```python
from flock.components.server import StaticFilesServerComponent

static = StaticFilesServerComponent(priority=99)  # MUST be last!
```

**⚠️ Important:** Must have highest priority to avoid catching API routes.

**📚 [Full Documentation](server_components/static-files-component.md)**

### ThemesComponent

Serves UI theme configuration files.

```python
from flock.components.server import ThemesComponent

themes = ThemesComponent()
```

**Endpoints:**
- `GET /plugin/themes` - List available themes
- `GET /plugin/themes/{name}` - Get theme configuration

**📚 [Full Documentation](server_components/themes-component.md)**

## Creating Custom Components

Learn how to build your own server components to extend Flock's HTTP API with custom functionality.

**📚 [Custom Components Guide](server_components/custom-components.md)** - Complete tutorial with examples

## Creating Custom Components (Quick Overview)

Server Components are modular extensions that add functionality to Flock's HTTP server. Here's a minimal example:

### Basic Structure

```python
from flock.components.server import ServerComponent, ServerComponentConfig
from pydantic import Field

class MyComponentConfig(ServerComponentConfig):
    """Configuration for my component."""
    my_setting: str = "default_value"

class MyComponent(ServerComponent):
    """My custom server component."""

    name: str = "my_component"
    priority: int = 10
    config: MyComponentConfig = Field(default_factory=MyComponentConfig)

    def configure(self, app, orchestrator):
        """Configure middleware, etc."""
        pass

    def register_routes(self, app, orchestrator):
        """Register HTTP endpoints."""
        @app.get("/my-endpoint")
        async def my_endpoint():
            return {"status": "ok"}
```

### Complete Tutorial

For a comprehensive guide on creating custom server components, including:

- Middleware implementation
- Lifecycle hooks
- Database integration
- External service integration
- Testing strategies
- Best practices and common pitfalls

**📚 See: [Custom Components Guide](server_components/custom-components.md)**
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
# ✅ CORRECT: Core infrastructure first, static files last
health = HealthAndMetricsComponent(priority=0)
cors = CORSComponent(priority=6)
auth = AuthenticationComponent(priority=7)
agents = AgentsServerComponent(priority=20)
static = StaticFilesServerComponent(priority=99)  # Last!

# ❌ WRONG: Static files before business logic
static = StaticFilesServerComponent(priority=10)  # Will catch all routes!
agents = AgentsServerComponent(priority=20)  # Never reached
```

### 2. Always Exclude Health Endpoints from Auth

```python
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

### 3. Use Consistent Prefixes

```python
# ✅ CORRECT: Consistent versioning
health = HealthAndMetricsComponent(
    config=HealthComponentConfig(prefix="/api/v1")
)
agents = AgentsServerComponent(
    config=AgentsServerComponentConfig(prefix="/api/v1")
)
```

### 4. Configure CORS Before Authentication

```python
# ✅ CORRECT: CORS handles OPTIONS before auth
components = [
    CORSComponent(priority=6),           # Before auth
    AuthenticationComponent(priority=7), # After CORS
]
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
    AgentsServerComponent,
    ArtifactsComponent,
    WebSocketServerComponent,
    StaticFilesServerComponent,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Authentication handler
async def api_key_auth(request: Request) -> tuple[bool, Response | None]:
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.startswith("sk-"):
        return True, None
    return False, JSONResponse({"error": "Invalid API key"}, status_code=401)

# Create Flock instance
flock = Flock()

# Configure components
components = [
    # 1. Health (priority 0)
    HealthAndMetricsComponent(),

    # 2. CORS (priority 6)
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
            exclude_paths=[r"^/health$", r"^/metrics$", r"^/docs.*"]
        )
    ),


    # 4. Business logic (priority 20)
    AgentsServerComponent(),
    ArtifactsComponent(),
    WebSocketServerComponent(),

    # 5. Static files (priority 99 - MUST BE LAST!)
    StaticFilesServerComponent(priority=99),
]

# Register auth handler
auth_component = components[2]  # AuthenticationComponent
auth_component.register_handler("api_key", api_key_auth)

# Start server
await flock.serve(
    components=components,
    host="0.0.0.0",
    port=8000
)
```

## Related Documentation

- **[Custom Components Guide](server_components/custom-components.md)** - Build your own server components ⭐ **Start Here for Custom Development!**
- **[REST API Guide](rest-api.md)** - HTTP API reference
- **[Agent Components](components.md)** - Agent-level components
- **[Orchestrator Components](orchestrator-components.md)** - Orchestrator-level components

## Examples

Complete example suite in `examples/09-server-components/`:

### Security Components
- **[01_authentication_component.py](../../examples/09-server-components/01_authentication_component.py)** - API key, JWT, route-specific auth
- **[02_cors_component.py](../../examples/09-server-components/02_cors_component.py)** - CORS policies and route overrides
- **[03_middleware_component.py](../../examples/09-server-components/03_middleware_component.py)** - Custom middleware stacks

### Infrastructure Components
- **[04_health_component.py](../../examples/09-server-components/04_health_component.py)** - Health checks and metrics
- **[11_tracing_component.py](../../examples/09-server-components/11_tracing_component.py)** - Distributed tracing with OpenTelemetry

### Business Logic Components
- **[05_websocket_component.py](../../examples/09-server-components/05_websocket_component.py)** - Real-time WebSocket updates
- **[06_artifacts_component.py](../../examples/09-server-components/06_artifacts_component.py)** - Artifacts REST API
- **[07_agents_component.py](../../examples/09-server-components/07_agents_component.py)** - Agents REST API
- **[08_control_routes_component.py](../../examples/09-server-components/08_control_routes_component.py)** - Agent invocation endpoints

### Presentation Components
- **[09_static_files_component.py](../../examples/09-server-components/09_static_files_component.py)** - Static file serving and SPA routing
- **[10_themes_component.py](../../examples/09-server-components/10_themes_component.py)** - UI theme configuration

### Complete Examples
- **[12_complete_composition.py](../../examples/09-server-components/12_complete_composition.py)** - Production-ready server with all components ⭐ **Best Example!**

```

## Related Documentation

- **[Server Components Concepts](../getting-started/server-components-concepts.md)** - Architecture and design patterns ⭐ **Start Here!**
- **[REST API Guide](rest-api.md)** - HTTP API reference
- **[Agent Components](components.md)** - Agent-level components
- **[Orchestrator Components](orchestrator-components.md)** - Orchestrator-level components

## Examples

Complete example suite in `examples/09-server-components/`:

### Security Components
- **[01_authentication_component.py](../../examples/09-server-components/01_authentication_component.py)** - API key, JWT, route-specific auth
- **[02_cors_component.py](../../examples/09-server-components/02_cors_component.py)** - CORS policies and route overrides
- **[03_middleware_component.py](../../examples/09-server-components/03_middleware_component.py)** - Custom middleware stacks

### Infrastructure Components
- **[04_health_component.py](../../examples/09-server-components/04_health_component.py)** - Health checks and metrics
- **[11_tracing_component.py](../../examples/09-server-components/11_tracing_component.py)** - Distributed tracing with OpenTelemetry

### Business Logic Components
- **[05_websocket_component.py](../../examples/09-server-components/05_websocket_component.py)** - Real-time WebSocket updates
- **[06_artifacts_component.py](../../examples/09-server-components/06_artifacts_component.py)** - Artifacts REST API
- **[07_agents_component.py](../../examples/09-server-components/07_agents_component.py)** - Agents REST API
- **[08_control_routes_component.py](../../examples/09-server-components/08_control_routes_component.py)** - Agent invocation endpoints

### Presentation Components
- **[09_static_files_component.py](../../examples/09-server-components/09_static_files_component.py)** - Static file serving and SPA routing
- **[10_themes_component.py](../../examples/09-server-components/10_themes_component.py)** - UI theme configuration

### Complete Examples
- **[12_complete_composition.py](../../examples/09-server-components/12_complete_composition.py)** - Production-ready server with all components ⭐ **Best Example!**
