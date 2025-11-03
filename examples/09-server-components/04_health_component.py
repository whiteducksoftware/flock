"""
Health and Metrics Component Examples

This example demonstrates the HealthAndMetricsComponent capabilities:
1. Basic health check endpoint
2. Custom metrics endpoint
3. Configuring endpoint paths
4. Integration with monitoring systems
"""

import asyncio

from flock import Flock
from flock.components.server import (
    HealthAndMetricsComponent,
    HealthComponentConfig,
)


# Example 1: Basic health check
def example_basic_health():
    """Simple health check endpoint."""
    flock = Flock()

    health_component = HealthAndMetricsComponent(
        config=HealthComponentConfig(
            prefix="/api/v1",
            tags=["Health & Metrics"],
        )
    )

    return flock, health_component


# Example 2: Custom prefix
def example_custom_prefix():
    """Health endpoint with custom prefix."""
    flock = Flock()

    health_component = HealthAndMetricsComponent(
        config=HealthComponentConfig(
            prefix="/system",  # Endpoints will be at /system/health, /system/metrics
            tags=["System"],
        )
    )

    return flock, health_component


# Example 3: Root-level endpoints
def example_root_health():
    """Health endpoint at root level (no prefix)."""
    flock = Flock()

    health_component = HealthAndMetricsComponent(
        config=HealthComponentConfig(
            prefix="",  # Empty prefix = root level
            tags=["Health"],
        )
    )

    return flock, health_component


async def main():
    """Demonstrate health component usage."""
    print("🏥 Health and Metrics Component Examples\n")
    print("=" * 60)

    # Example 1: Basic setup
    print("\n1️⃣  Basic Health Check")
    print("-" * 60)
    flock, health = example_basic_health()

    print("✅ Health component created")
    print(f"   Priority: {health.priority}")
    print(f"   Prefix: {health.config.prefix}")
    print("   Endpoints:")
    print(f"   - GET {health.config.prefix}/health")
    print(f"   - GET {health.config.prefix}/metrics")

    # Example 2: Custom prefix
    print("\n2️⃣  Custom Prefix")
    print("-" * 60)
    _, _health2 = example_custom_prefix()

    print("✅ Health component with custom prefix created")
    print("   Endpoints:")
    print("   - GET /system/health")
    print("   - GET /system/metrics")

    # Example 3: Root-level
    print("\n3️⃣  Root-Level Endpoints")
    print("-" * 60)
    _, _health3 = example_root_health()

    print("✅ Health component at root level created")
    print("   Endpoints:")
    print("   - GET /health")
    print("   - GET /metrics")

    # Example 4: Full server setup
    print("\n4️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with health component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Try these endpoints:")
    print("   - http://127.0.0.1:8344/api/v1/health")
    print("   - http://127.0.0.1:8344/api/v1/metrics")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[health],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait a bit to allow connections
    await asyncio.sleep(2)

    print("\n✅ Server is running!")
    print("   Use curl or browser to test endpoints:")
    print("   curl http://127.0.0.1:8344/api/v1/health")

    # Keep server running for demo
    try:
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
