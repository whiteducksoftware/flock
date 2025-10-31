"""
Tracing Component Examples

This example demonstrates the TracingComponent capabilities:
1. OpenTelemetry trace collection
2. Trace export and visualization
3. Custom trace configuration
4. Integration with observability platforms
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.components.server import TracingComponent, TracingComponentConfig


class DataRequest(BaseModel):
    """Example artifact for data requests."""

    query: str
    limit: int = 10


class DataResponse(BaseModel):
    """Example artifact for data responses."""

    results: list[dict]
    count: int


async def main():
    """Demonstrate Tracing component usage."""
    print("🔍 Tracing Component Examples\n")
    print("=" * 60)

    # Example 1: Basic Tracing component
    print("\n1️⃣  Basic Tracing Component")
    print("-" * 60)

    flock = Flock("openai/gpt-4o")

    tracing_component = TracingComponent(
        config=TracingComponentConfig(
            enabled=True,
            prefix="/api/v1",
            tags=["Tracing"],
        )
    )

    print("✅ Tracing component created")
    print(f"   Enabled: {tracing_component.config.enabled}")
    print("   Endpoints:")
    print(f"   - GET {tracing_component.config.prefix}/traces")
    print(f"   - GET {tracing_component.config.prefix}/traces/{{trace_id}}")

    # Example 2: What gets traced
    print("\n2️⃣  What Gets Traced")
    print("-" * 60)
    print("""
    The TracingComponent automatically captures:

    🔸 Agent Execution
       - Agent activation
       - Input artifacts consumed
       - LLM calls and responses
       - Output artifacts produced
       - Execution duration

    🔸 Orchestrator Events
       - Workflow initiation
       - Agent scheduling
       - Blackboard operations
       - Error propagation

    🔸 Component Lifecycle
       - Component startup
       - Route registration
       - Shutdown sequences

    All traces are exported in OpenTelemetry format
    for integration with observability platforms like:
    - Jaeger
    - Zipkin
    - Honeycomb
    - Datadog
    - New Relic
    """)

    # Example 3: Create traced agent workflow
    print("\n3️⃣  Creating Traced Workflow")
    print("-" * 60)

    data_fetcher = (
        flock.agent("data_fetcher")
        .description("Fetches data based on query")
        .consumes(DataRequest)
        .publishes(DataResponse)
        .instruction("Process the query and return relevant results")
    )

    print(f"✅ Agent created: {data_fetcher.name}")
    print("   All executions will be automatically traced")

    # Example 4: Full server setup
    print("\n4️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with Tracing component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Available endpoints:")
    print("   - GET http://127.0.0.1:8344/api/v1/traces")
    print("   - GET http://127.0.0.1:8344/api/v1/traces/{trace_id}")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[tracing_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Example 5: Generate some traced operations
    print("\n5️⃣  Generating Traced Operations")
    print("-" * 60)

    test_requests = [
        DataRequest(query="user analytics", limit=5),
        DataRequest(query="performance metrics", limit=10),
        DataRequest(query="error logs", limit=20),
    ]

    for i, request in enumerate(test_requests, 1):
        print(f"\n📤 Publishing request {i}/{len(test_requests)}")
        print(f"   Query: {request.query}")
        print(f"   Limit: {request.limit}")

        await flock.publish(request)
        await flock.run_until_idle()

        # Small delay between requests
        await asyncio.sleep(1)

    print("\n✅ All operations completed and traced!")

    # Example 6: Query traces via API
    print("\n6️⃣  Query Traces via REST API")
    print("-" * 60)

    print("\n   You can now query traces using curl:")
    print("\n   # Get all recent traces:")
    print("   curl http://127.0.0.1:8344/api/v1/traces")
    print("\n   # Get specific trace:")
    print("   curl http://127.0.0.1:8344/api/v1/traces/{trace_id}")
    print("\n   # Filter traces by agent:")
    print("   curl 'http://127.0.0.1:8344/api/v1/traces?agent=data_fetcher'")
    print("\n   # Get traces in time range:")
    print(
        "   curl 'http://127.0.0.1:8344/api/v1/traces?start=2024-01-01&end=2024-12-31'"
    )

    print("\n   Example Python code:")
    print("""
    import requests

    # Get all traces
    response = requests.get("http://127.0.0.1:8344/api/v1/traces")
    traces = response.json()

    # Analyze trace data
    for trace in traces['traces']:
        print(f"Trace ID: {trace['trace_id']}")
        print(f"Duration: {trace['duration_ms']}ms")
        print(f"Spans: {len(trace['spans'])}")
    """)

    # Keep server running
    print("\n⏳ Keeping server running for 60 seconds...")
    print("   Try the curl commands above!")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
