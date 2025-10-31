# Server Components Concepts

Server Components are Flock's modular architecture for extending the HTTP API server with custom middleware, routes, and lifecycle management. They enable composable, production-ready server configurations without code duplication or inheritance hierarchies.

## Overview

### What are Server Components?

Server Components are reusable, self-contained modules that extend Flock's HTTP server capabilities. Each component can:

- **Configure middleware** - Add authentication, CORS, logging, rate limiting, etc.
- **Register routes** - Create custom HTTP endpoints
- **Manage lifecycle** - Run startup/shutdown tasks
- **Control ordering** - Use priority to control registration order
- **Declare dependencies** - Ensure required components are present

### Why Server Components?

**Problem:**
Traditional server architectures force you to choose between:
- **Inheritance** - Rigid hierarchies, tight coupling, hard to test
- **Monoliths** - Everything in one class, impossible to compose
- **Duplication** - Copy-paste code across different server types

**Solution:**
Server Components provide a **composable architecture** where you mix and match exactly the features you need:

```python
# ✅ Compose exactly what you need
await flock.serve(
    components=[
        HealthAndMetricsComponent(),
        CORSComponent(),
        AuthenticationComponent(),
        AgentsServerComponent(),
        ArtifactsComponent(),
        WebSocketServerComponent(),
    ]
)
```

**Benefits:**
- ✅ **Zero duplication** - Each feature implemented once
- ✅ **Easy testing** - Test components in isolation
- ✅ **Clear dependencies** - Components declare what they need
- ✅ **Flexible composition** - Mix and match for different use cases
- ✅ **Production-ready** - Built-in components for common needs

---

## Architecture

### Component Lifecycle

Every server component goes through a well-defined lifecycle:

```
┌─────────────────────────────────────────────┐
│  1. Component Creation (__init__)           │
│     - Instantiate with configuration        │
│     - Set priority for ordering             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  2. Dependency Validation                   │
│     - Check required components present     │
│     - Validate configuration                │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  3. Configure (configure())                 │
│     - Add middleware to FastAPI app         │
│     - Configure exception handlers          │
│     - Set up CORS, authentication, etc.     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  4. Register Routes (register_routes())     │
│     - Add HTTP endpoints to FastAPI app     │
│     - Define request handlers               │
│     - Set up WebSocket connections          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  5. Startup (on_startup_async())            │
│     - Connect to databases                  │
│     - Initialize resources                  │
│     - Start background tasks                │
└─────────────────────────────────────────────┘
                    ↓
         ┌────────────────────┐
         │  Server Running    │
         │  Handle Requests   │
         └────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  6. Shutdown (on_shutdown_async())          │
│     - Close database connections            │
│     - Stop background tasks                 │
│     - Clean up resources                    │
└─────────────────────────────────────────────┘
```

### Priority System

Components register in **priority order** (lower numbers first):

| Priority Range | Purpose | Examples |
|----------------|---------|----------|
| **0-5** | Core infrastructure | Health checks, metrics |
| **6-10** | Security layer | CORS, authentication, rate limiting |
| **11-50** | Business logic | Agents API, artifacts API, control routes |
| **51-99** | Static assets | Dashboard UI, static files |

**Why priority matters:**

```python
# ❌ WRONG: Static files registered first
components = [
    StaticFilesServerComponent(priority=10),  # Catches all routes!
    AgentsServerComponent(priority=20),        # Never reached
]

# ✅ CORRECT: Static files registered last
components = [
    HealthAndMetricsComponent(priority=0),     # Core
    CORSComponent(priority=8),                 # Security
    AgentsServerComponent(priority=20),         # Business logic
    StaticFilesServerComponent(priority=99),   # Static files last
]
```

**Rule:** Static files MUST have the highest priority (99) because they use catch-all routes.

---

## Component Types

### 1. Infrastructure Components

**Purpose:** Core server functionality

**Examples:**
- **HealthAndMetricsComponent** - Health checks and Prometheus metrics
- **TracingComponent** - Distributed tracing with OpenTelemetry

**Typical priority:** 0-5

```python
health = HealthAndMetricsComponent(
    config=HealthComponentConfig(
        prefix="/api/v1",
        tags=["Health"]
    ),
    priority=0
)
```

### 2. Security Components

**Purpose:** Authentication, authorization, CORS, rate limiting

**Examples:**
- **CORSComponent** - Cross-origin resource sharing
- **AuthenticationComponent** - Flexible auth strategies
- **MiddlewareComponent** - Custom middleware stacks

**Typical priority:** 6-10

```python
auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="api_key",
        exclude_paths=[r"^/health$"]
    ),
    priority=7
)
```

### 3. Business Logic Components

**Purpose:** Core API functionality

**Examples:**
- **AgentsServerComponent** - Agent metadata and management
- **ArtifactsComponent** - Blackboard artifact queries
- **ControlRoutesComponent** - Agent invocation endpoints
- **WebSocketServerComponent** - Real-time updates

**Typical priority:** 11-50

```python
agents = AgentsServerComponent(
    config=AgentsServerComponentConfig(
        prefix="/api/v1",
        tags=["Agents"]
    ),
    priority=20
)
```

### 4. Presentation Components

**Purpose:** User interfaces and static assets

**Examples:**
- **StaticFilesServerComponent** - Dashboard UI, static files
- **ThemesComponent** - UI theme configuration

**Typical priority:** 51-99

```python
static = StaticFilesServerComponent(
    config=StaticFilesComponentConfig(
        directory="./dashboard",
        html=True  # SPA routing
    ),
    priority=99  # MUST BE LAST!
)
```

---

## Creating Custom Components

### Basic Structure

```python
from flock.components.server import ServerComponent, ServerComponentConfig

class MyComponentConfig(ServerComponentConfig):
    """Configuration for my component."""

    my_setting: str = "default_value"
    enable_feature: bool = True

class MyComponent(ServerComponent):
    """My custom server component."""

    name: str = "my_component"
    priority: int = 20
    config: MyComponentConfig = MyComponentConfig()

    def configure(self, app, orchestrator):
        """Configure middleware (optional)."""
        # Add middleware if needed
        pass

    def register_routes(self, app, orchestrator):
        """Register HTTP endpoints."""

        @app.get("/my-endpoint")
        async def my_endpoint():
            return {"status": "ok"}

    async def on_startup_async(self, orchestrator):
        """Async startup tasks (optional)."""
        print("MyComponent starting...")

    async def on_shutdown_async(self, orchestrator):
        """Async cleanup (optional)."""
        print("MyComponent stopping...")
```

### Advanced Pattern: Middleware Component

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        import time

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        print(f"{request.method} {request.url.path} - {duration:.3f}s")
        return response

class LoggingComponent(ServerComponent):
    """Component that adds request logging."""

    name: str = "logging"
    priority: int = 5  # Early in the chain

    def configure(self, app, orchestrator):
        """Add logging middleware."""
        app.add_middleware(RequestLoggingMiddleware)
```

### Advanced Pattern: Dependency Declaration

```python
class MyAdvancedComponent(ServerComponent):
    """Component that requires authentication."""

    name: str = "my_advanced"
    priority: int = 30

    def get_dependencies(self):
        """Declare required components."""
        return [AuthenticationComponent]

    def register_routes(self, app, orchestrator):
        """Routes that assume auth is configured."""

        @app.get("/protected/data")
        async def get_protected_data():
            # Auth middleware already applied
            return {"secret": "data"}
```

**Validation:**
If `AuthenticationComponent` is not added, `configure()` will raise:
```
ValueError: MyAdvancedComponent requires AuthenticationComponent but it's not enabled
```

---

## Composition Patterns

### Pattern 1: Minimal Server (Health Only)

```python
# Bare minimum for monitoring
await flock.serve(
    components=[
        HealthAndMetricsComponent()
    ]
)
```

**Use case:** Internal services, dev/test environments

### Pattern 2: Public API Server

```python
# Public-facing API with security
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        CORSComponent(priority=8),
        AuthenticationComponent(priority=7),
        AgentsServerComponent(priority=20),
        ArtifactsComponent(priority=20),
    ]
)
```

**Use case:** Production APIs with authentication

### Pattern 3: Full Dashboard Server

```python
# Complete setup with UI
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        CORSComponent(priority=8),
        AuthenticationComponent(priority=7),
        WebSocketServerComponent(priority=15),
        AgentsServerComponent(priority=20),
        ArtifactsComponent(priority=20),
        TracingComponent(priority=25),
        ThemesComponent(priority=30),
        StaticFilesServerComponent(priority=99),  # LAST!
    ]
)
```

**Use case:** Production with real-time dashboard

### Pattern 4: Development Server

```python
# Dev server with tracing, no auth
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        WebSocketServerComponent(priority=15),
        AgentsServerComponent(priority=20),
        ArtifactsComponent(priority=20),
        TracingComponent(priority=25),
        StaticFilesServerComponent(priority=99),
    ]
)
```

**Use case:** Local development, debugging

---

## Relationship to Other Components

Flock has three types of components:

### 1. Agent Components
- **Scope:** Individual agent behavior
- **Purpose:** Extend agent execution (quality gates, retry logic, validation)
- **Examples:** OutputUtilityComponent, DSPyEngine
- **Lifecycle:** Per-agent execution

### 2. Orchestrator Components
- **Scope:** Global orchestration behavior
- **Purpose:** Coordination, monitoring, metrics collection
- **Examples:** CircuitBreakerComponent, DeduplicationComponent
- **Lifecycle:** Per-workflow execution

### 3. Server Components ⭐ (This Guide)
- **Scope:** HTTP server configuration
- **Purpose:** API endpoints, middleware, real-time updates
- **Examples:** CORSComponent, AuthenticationComponent, AgentsServerComponent
- **Lifecycle:** Server startup/shutdown

**Key Difference:**
- **Agent/Orchestrator Components** = Runtime behavior (how agents execute)
- **Server Components** = HTTP layer (how users interact with the system)

---

## Best Practices

### ✅ DO

**1. Use correct priorities:**
```python
# Infrastructure first, static files last
HealthAndMetricsComponent(priority=0)
CORSComponent(priority=8)
AgentsServerComponent(priority=20)
StaticFilesServerComponent(priority=99)
```

**2. Declare dependencies:**
```python
def get_dependencies(self):
    return [AuthenticationComponent]
```

**3. Handle errors in middleware:**
```python
async def auth_handler(request):
    try:
        # Validate...
        return True, None
    except Exception as e:
        return False, JSONResponse({"error": str(e)}, status_code=500)
```

**4. Clean up resources:**
```python
async def on_shutdown_async(self, orchestrator):
    if self._connection:
        await self._connection.close()
```

**5. Use configuration objects:**
```python
config = HealthComponentConfig(
    prefix="/api/v1",
    tags=["Health"]
)
```

### ❌ DON'T

**1. Static files with low priority:**
```python
# ❌ WRONG: Will catch all routes!
StaticFilesServerComponent(priority=10)
```

**2. Skip error handling:**
```python
# ❌ WRONG: Uncaught exceptions crash server
async def handler(request):
    api_key = request.headers["X-API-Key"]  # KeyError if missing!
```

**3. Forget cleanup:**
```python
# ❌ WRONG: Resource leak
async def on_startup_async(self, orchestrator):
    self._connection = await connect_to_db()
    # No on_shutdown_async to close connection!
```

**4. Hardcode paths:**
```python
# ❌ WRONG: Manual path joining
path = f"{prefix}/endpoint"  # Can create double slashes

# ✅ CORRECT: Use helper
path = self._join_path(prefix, "endpoint")
```

---

## Testing Components

### Unit Testing

```python
import pytest
from fastapi import FastAPI
from flock import Flock

@pytest.mark.asyncio
async def test_my_component():
    """Test component in isolation."""

    # Arrange
    app = FastAPI()
    orchestrator = Flock()
    component = MyComponent()

    # Act
    component.configure(app, orchestrator)
    component.register_routes(app, orchestrator)
    await component.on_startup_async(orchestrator)

    # Assert
    assert "/my-endpoint" in [route.path for route in app.routes]

    # Cleanup
    await component.on_shutdown_async(orchestrator)
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_component_composition():
    """Test multiple components together."""

    flock = Flock()

    components = [
        HealthAndMetricsComponent(),
        MyComponent(),
    ]

    await flock.serve(
        components=components,
        blocking=False
    )

    # Test endpoints
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8344/health")
        assert response.status_code == 200
```

---

## Common Use Cases

### Use Case 1: MCP Server Only (No Web UI)

```python
# Minimal MCP server for external integrations
await flock.serve(
    components=[
        HealthAndMetricsComponent(),
        MCPComponent(config={"expose_tools": ["agent_invoke"]}),
    ]
)
```

### Use Case 2: Multi-Tenant SaaS

```python
# Per-tenant authentication and CORS
async def tenant_auth(request: Request):
    tenant_id = request.headers.get("X-Tenant-ID")
    # Validate tenant...
    return True, None

auth = AuthenticationComponent(
    config=AuthenticationComponentConfig(
        default_handler="tenant_auth"
    )
)
auth.register_handler("tenant_auth", tenant_auth)

cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origin_regex=r"https://.*\.myapp\.com"
    )
)

await flock.serve(components=[auth, cors, ...])
```

### Use Case 3: Rate-Limited Public API

```python
# Public API with rate limiting
await flock.serve(
    components=[
        HealthAndMetricsComponent(priority=0),
        RateLimitComponent(
            config=RateLimitConfig(
                max_requests=100,
                window_seconds=60
            ),
            priority=6
        ),
        AgentsServerComponent(priority=20),
    ]
)
```

---

## Further Reading

- **[Server Components Guide](../guides/server-components.md)** - Complete API reference
- **[REST API Guide](../guides/rest-api.md)** - HTTP API documentation
- **[Agent Components](../guides/components.md)** - Agent-level components
- **[Orchestrator Components](../guides/orchestrator-components.md)** - Orchestrator-level components

## Examples

- **[examples/09-server-components/](../../examples/09-server-components/)** - Complete example suite:
  - `01_authentication_component.py` - Authentication strategies
  - `02_cors_component.py` - CORS configuration
  - `03_middleware_component.py` - Custom middleware
  - `04_health_component.py` - Health monitoring
  - `05_websocket_component.py` - Real-time updates
  - `06_artifacts_component.py` - Artifacts API
  - `07_agents_component.py` - Agents API
  - `08_control_routes_component.py` - Agent invocation
  - `09_static_files_component.py` - Static file serving
  - `10_themes_component.py` - UI themes
  - `11_tracing_component.py` - Distributed tracing
  - `12_complete_composition.py` - Production setup

---

## Summary

**Server Components provide:**
- ✅ Modular, composable HTTP server architecture
- ✅ Built-in components for common needs (auth, CORS, health, etc.)
- ✅ Priority-based ordering for predictable behavior
- ✅ Lifecycle hooks for resource management
- ✅ Dependency declaration for validation
- ✅ Easy testing and customization

**Key Principles:**
1. **Composition over inheritance** - Mix and match components
2. **Priority matters** - Static files must be last
3. **Declare dependencies** - Let the system validate
4. **Clean lifecycle** - Startup and shutdown hooks
5. **Production-ready** - Built-in security and monitoring

Start with built-in components, then create custom ones as needed!
