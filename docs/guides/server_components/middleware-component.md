---
title: MiddlewareComponent
description: Documentation for the generic Middleware ServerComponent
tags:
 - middleware
 - authentication
 - logging
 - telemetry
 - security
search:
  boost: 2.4
---
# MiddlewareComponent

The `MiddlewareComponent` is a server component that enables developers to attach custom middleware to the FastAPI application used by Flock. This provides flexibility to add cross-cutting concerns like logging, timing, compression, custom headers, and more.

## Features

- **Generic Middleware Support**: Register any ASGI-compatible middleware
- **Configuration-Based**: Define middleware and their options via Pydantic configuration
- **Priority-Based**: Control middleware order through configuration
- **Validation**: Automatically validates that all referenced middleware factories are registered
- **Flexible Options**: Pass custom options to each middleware instance

## Quick Start

```python
from flock import Flock
from flock.components.server.middleware import (
    MiddlewareComponent,
    MiddlewareComponentConfig,
    MiddlewareConfig,
)

# Create middleware component with configuration
middleware_component = MiddlewareComponent(
    config=MiddlewareComponentConfig(
        middlewares=[
            MiddlewareConfig(
                name="timing",
                options={"header_name": "X-Request-Duration"},
            ),
        ]
    )
)

# Register middleware factory
middleware_component.register_middleware("timing", timing_middleware_factory)

# Use with Flock server
await flock.serve(
    dashboard=True,
    server_components=[middleware_component]
)
```

## Architecture

### Middleware Registration Flow

1. **Create Component**: Instantiate `MiddlewareComponent` with configuration
2. **Register Factories**: Call `register_middleware(name, factory)` for each middleware
3. **Configure**: Component validates factories and adds middleware to FastAPI app
4. **Process Requests**: Middleware executes in order during request processing

### Middleware Order

Middleware is registered in the order specified in the configuration. The **first middleware in the list is the outermost** (processes requests first, responses last):

```python
config = MiddlewareComponentConfig(
    middlewares=[
        MiddlewareConfig(name="logging"),   # Runs FIRST (outermost)
        MiddlewareConfig(name="timing"),    # Runs SECOND
        MiddlewareConfig(name="gzip"),      # Runs LAST (innermost)
    ]
)

# Request flow:  logging → timing → gzip → app
# Response flow: gzip → timing → logging
```

## Configuration

### MiddlewareComponentConfig

Main configuration for the middleware component.

```python
class MiddlewareComponentConfig(ServerComponentConfig):
    middlewares: list[MiddlewareConfig]  # List of middleware to register
```

### MiddlewareConfig

Configuration for a single middleware instance.

```python
class MiddlewareConfig(ServerComponentConfig):
    name: str                      # Unique name (must match registered factory)
    options: dict[str, Any]        # Options passed to middleware factory
    enabled: bool = True           # Whether this middleware is enabled
```

## Creating Middleware Factories

A middleware factory is a function that:
1. Takes an ASGI app as input
2. Returns a factory function that accepts `**options` kwargs
3. Creates and returns a middleware instance

### Example: Custom Header Middleware

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

class CustomHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, headers: dict[str, str] | None = None):
        super().__init__(app)
        self.headers = headers or {}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header_name, header_value in self.headers.items():
            response.headers[header_name] = header_value
        return response

def custom_header_middleware_factory(app: ASGIApp):
    """Factory for creating custom header middleware."""
    def factory(**options):
        headers = options.get("headers", {})
        return CustomHeaderMiddleware(app, headers=headers)
    return factory

# Register and configure
component.register_middleware("custom_headers", custom_header_middleware_factory)
config = MiddlewareConfig(
    name="custom_headers",
    options={
        "headers": {
            "X-App-Name": "My App",
            "X-App-Version": "1.0.0",
        }
    }
)
```

### Example: Timing Middleware

```python
import time
from starlette.middleware.base import BaseHTTPMiddleware

class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "X-Process-Time"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers[self.header_name] = str(process_time)
        return response

def timing_middleware_factory(app: ASGIApp):
    def factory(**options):
        header_name = options.get("header_name", "X-Process-Time")
        return TimingMiddleware(app, header_name=header_name)
    return factory
```

## Using Built-in Starlette Middleware

You can also wrap Starlette's built-in middleware:

```python
from starlette.middleware.gzip import GZipMiddleware

def gzip_middleware_factory(app: ASGIApp):
    def factory(**options):
        minimum_size = options.get("minimum_size", 1000)
        return GZipMiddleware(app, minimum_size=minimum_size)
    return factory

# Configure
component.register_middleware("gzip", gzip_middleware_factory)
config = MiddlewareConfig(
    name="gzip",
    options={"minimum_size": 500},  # Compress responses > 500 bytes
)
```

## Complete Example

```python
from flock import Flock
from flock.components.server.middleware import (
    MiddlewareComponent,
    MiddlewareComponentConfig,
    MiddlewareConfig,
)

# Create component with multiple middleware
middleware_component = MiddlewareComponent(
    config=MiddlewareComponentConfig(
        middlewares=[
            # Logging middleware (outermost)
            MiddlewareConfig(
                name="logging",
                options={"log_level": "INFO"},
            ),
            # Timing middleware
            MiddlewareConfig(
                name="timing",
                options={"header_name": "X-Request-Duration"},
            ),
            # Custom headers
            MiddlewareConfig(
                name="custom_headers",
                options={
                    "headers": {
                        "X-App-Name": "Flock App",
                        "X-App-Version": "1.0.0",
                    }
                },
            ),
            # GZip compression (innermost)
            MiddlewareConfig(
                name="gzip",
                options={"minimum_size": 500},
            ),
        ]
    )
)

# Register all factories
middleware_component.register_middleware("logging", logging_middleware_factory)
middleware_component.register_middleware("timing", timing_middleware_factory)
middleware_component.register_middleware("custom_headers", custom_header_middleware_factory)
middleware_component.register_middleware("gzip", gzip_middleware_factory)

# Start server with middleware component
flock = Flock("openai/gpt-4o")
await flock.serve(
    dashboard=True,
    server_components=[middleware_component]
)
```

## Best Practices

### 1. Order Matters
Place middleware in the correct order:
- **Logging/Monitoring**: Outermost (first in list)
- **Authentication/Security**: Early in chain
- **Compression/Transformation**: Later in chain
- **Custom Headers**: Can be anywhere

### 2. Use Descriptive Names
```python
# ✅ Good
MiddlewareConfig(name="request_timing")
MiddlewareConfig(name="custom_headers")

# ❌ Bad
MiddlewareConfig(name="middleware1")
MiddlewareConfig(name="m1")
```

### 3. Validate Configuration
The component automatically validates that all referenced middleware factories are registered before starting the server.

### 4. Disable Middleware Conditionally
```python
import os

config = MiddlewareComponentConfig(
    middlewares=[
        MiddlewareConfig(
            name="debug_logging",
            enabled=os.getenv("DEBUG") == "true",  # Only in debug mode
        ),
    ]
)
```

### 5. Use Type Hints
```python
from typing import Any
from starlette.types import ASGIApp

def my_middleware_factory(app: ASGIApp) -> Callable[..., Any]:
    def factory(**options: Any) -> Any:
        return MyMiddleware(app, **options)
    return factory
```

## Error Handling

### Missing Factory Registration
```python
config = MiddlewareComponentConfig(
    middlewares=[
        MiddlewareConfig(name="unregistered"),
    ]
)
component = MiddlewareComponent(config=config)
component.configure(app, orchestrator)
# ❌ Raises ValueError: middleware factories are referenced in config but not registered
```

### Duplicate Registration
```python
component.register_middleware("my_middleware", factory)
component.register_middleware("my_middleware", factory)
# ❌ Raises ValueError: Middleware factory 'my_middleware' is already registered
```

## Testing

Test your middleware factories independently:

```python
import pytest
from starlette.testclient import TestClient

def test_custom_header_middleware():
    component = MiddlewareComponent(
        config=MiddlewareComponentConfig(
            middlewares=[
                MiddlewareConfig(
                    name="headers",
                    options={"headers": {"X-Test": "value"}},
                )
            ]
        )
    )
    component.register_middleware("headers", custom_header_middleware_factory)

    # Test with FastAPI app
    app = FastAPI()
    component.configure(app, orchestrator)

    client = TestClient(app)
    response = client.get("/")
    assert response.headers["X-Test"] == "value"
```

## Advanced Patterns

### Conditional Middleware
```python
def create_conditional_middleware(condition: Callable) -> MiddlewareFactory:
    def factory(app: ASGIApp):
        def middleware_factory(**options):
            class ConditionalMiddleware:
                def __init__(self, app):
                    self.app = app

                async def __call__(self, scope, receive, send):
                    if condition(scope):
                        # Apply middleware logic
                        pass
                    await self.app(scope, receive, send)

            return ConditionalMiddleware(app)
        return middleware_factory
    return factory
```

### Request/Response Inspection
```python
class InspectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Inspect/modify request
        print(f"Request: {request.method} {request.url}")

        response = await call_next(request)

        # Inspect/modify response
        print(f"Response: {response.status_code}")

        return response
```

## See Also

- [ServerComponent Base Class](../base.py)
- [CORSComponent](../cors/cors_component.py)
- [AuthenticationComponent](../auth/auth_component.py)
- [Example Usage](../../../../examples/09-server-components/03_middleware_component.py)
- [Starlette Middleware Documentation](https://www.starlette.io/middleware/)
