"""Example demonstrating the MiddlewareComponent.

This example shows how to:
1. Create custom middleware
2. Register middleware factories with the component
3. Configure multiple middleware with options
4. Use built-in Starlette middleware
"""

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from flock import Flock
from flock.components.server.middleware import (
    MiddlewareComponent,
    MiddlewareComponentConfig,
    MiddlewareConfig,
)


# Example 1: Custom timing middleware
class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware that adds request timing headers."""

    def __init__(self, app: ASGIApp, header_name: str = "X-Process-Time"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        import time

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers[self.header_name] = str(process_time)
        return response


def timing_middleware_factory(app: ASGIApp):
    """Factory for creating timing middleware."""

    def factory(**options):
        header_name = options.get("header_name", "X-Process-Time")
        return TimingMiddleware(app, header_name=header_name)

    return factory


# Example 2: Custom header middleware
class CustomHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware that adds custom headers to responses."""

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


# Example 3: GZip middleware factory
def gzip_middleware_factory(app: ASGIApp):
    """Factory for creating GZip middleware."""

    def factory(**options):
        minimum_size = options.get("minimum_size", 1000)
        return GZipMiddleware(app, minimum_size=minimum_size)

    return factory


async def main():
    """Demonstrate middleware component usage."""
    print("🔧 Creating Flock instance...")
    _flock = Flock("openai/gpt-4o")

    # Create middleware component with configuration
    print("\n📦 Creating MiddlewareComponent...")
    middleware_component = MiddlewareComponent(
        config=MiddlewareComponentConfig(
            middlewares=[
                # Timing middleware - will be outermost (runs first)
                MiddlewareConfig(
                    name="timing",
                    options={"header_name": "X-Request-Duration"},
                ),
                # Custom headers middleware
                MiddlewareConfig(
                    name="custom_headers",
                    options={
                        "headers": {
                            "X-App-Name": "Flock Example",
                            "X-App-Version": "1.0.0",
                        }
                    },
                ),
                # GZip compression middleware - will be innermost (runs last)
                MiddlewareConfig(
                    name="gzip",
                    options={"minimum_size": 500},
                ),
            ]
        )
    )

    # Register middleware factories
    print("\n🔌 Registering middleware factories...")
    middleware_component.register_middleware("timing", timing_middleware_factory)
    middleware_component.register_middleware(
        "custom_headers", custom_header_middleware_factory
    )
    middleware_component.register_middleware("gzip", gzip_middleware_factory)

    print("\n✅ Middleware component configured!")
    print("\nMiddleware chain (request processing order):")
    print("  1. timing          -> Measures request duration")
    print("  2. custom_headers  -> Adds X-App-Name and X-App-Version")
    print("  3. gzip            -> Compresses response if > 500 bytes")
    print("\nNote: Response flows back through the chain in reverse order")

    # You can now add this component when starting the server:
    # await flock.serve(
    #     dashboard=True,
    #     server_components=[middleware_component]
    # )

    print("\n💡 To use this component, start the server with:")
    print(
        "   await flock.serve(dashboard=True, server_components=[middleware_component])"
    )
    print("\n📝 Test the middleware by making requests and checking response headers:")
    print("   - X-Request-Duration: Time taken to process the request")
    print("   - X-App-Name: Flock Example")
    print("   - X-App-Version: 1.0.0")
    print("   - Content-Encoding: gzip (if response > 500 bytes)")


if __name__ == "__main__":
    asyncio.run(main())
