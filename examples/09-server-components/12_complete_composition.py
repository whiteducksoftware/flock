"""
Complete Server Component Composition Example

This example demonstrates how to compose multiple server components together
to build a production-ready Flock server with:
1. Health monitoring
2. CORS configuration
3. Authentication
4. WebSocket real-time updates
5. REST API for agents and artifacts
6. Dashboard UI
7. Distributed tracing
"""

import asyncio

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from flock import Flock
from flock.components.server import (
    AgentsServerComponent,
    AgentsServerComponentConfig,
    ArtifactComponentConfig,
    ArtifactsComponent,
    AuthenticationComponent,
    AuthenticationComponentConfig,
    CORSComponent,
    CORSComponentConfig,
    HealthAndMetricsComponent,
    HealthComponentConfig,
    RouteSpecificAuthConfig,
    RouteSpecificCORSConfig,
    TracingComponent,
    TracingComponentConfig,
    WebSocketComponentConfig,
    WebSocketServerComponent,
)


# Example artifacts for the workflow
class Order(BaseModel):
    """Customer order artifact."""

    order_id: str
    customer_name: str
    items: list[dict]
    total_amount: float


class OrderValidation(BaseModel):
    """Order validation result."""

    order_id: str
    is_valid: bool
    issues: list[str]


class OrderConfirmation(BaseModel):
    """Order confirmation artifact."""

    order_id: str
    customer_name: str
    confirmation_code: str
    estimated_delivery: str


# Authentication handlers
async def api_key_handler(request: Request) -> tuple[bool, Response | None]:
    """Validate API key for general access."""
    api_key = request.headers.get("X-API-Key")

    if api_key and api_key.startswith("sk-"):
        return True, None

    return False, JSONResponse({"error": "Invalid API key"}, status_code=401)


async def admin_handler(request: Request) -> tuple[bool, Response | None]:
    """Validate admin token for privileged operations."""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return False, JSONResponse(
            {"error": "Admin access requires Bearer token"}, status_code=403
        )

    token = auth_header[7:]

    # In production, validate JWT properly
    if token == "admin-token-123":
        return True, None

    return False, JSONResponse({"error": "Insufficient privileges"}, status_code=403)


async def main():
    """Demonstrate complete server component composition."""
    print("🏗️  Complete Server Component Composition\n")
    print("=" * 60)

    # Create Flock instance
    print("\n1️⃣  Creating Flock Orchestrator")
    print("-" * 60)

    flock = Flock("openai/gpt-4o")

    # Create workflow agents
    print("\n2️⃣  Creating Workflow Agents")
    print("-" * 60)

    order_validator = (
        flock.agent("order_validator")
        .description("Validates customer orders")
        .consumes(Order)
        .publishes(OrderValidation)
        .instruction(
            "Validate the order by checking:\n"
            "1. All required fields are present\n"
            "2. Items are available\n"
            "3. Total amount is correct\n"
            "4. Customer information is valid"
        )
    )

    order_processor = (
        flock.agent("order_processor")
        .description("Processes validated orders")
        .consumes(OrderValidation, where=lambda v: v.is_valid)
        .publishes(OrderConfirmation)
        .instruction(
            "Process the validated order:\n"
            "1. Generate confirmation code\n"
            "2. Calculate estimated delivery\n"
            "3. Create order confirmation"
        )
    )

    print("✅ Created agents:")
    print(f"   - {order_validator.name}")
    print(f"   - {order_processor.name}")

    # Configure server components
    print("\n3️⃣  Configuring Server Components")
    print("-" * 60)

    # Priority order:
    # 0-5: Infrastructure (health)
    # 6-10: Security (CORS, auth)
    # 11-50: Business logic (agents, artifacts, control)
    # 51-99: Static files (if any)

    components = [
        # 1. Health monitoring (priority 0)
        HealthAndMetricsComponent(
            config=HealthComponentConfig(prefix="/api/v1", tags=["Health & Metrics"]),
            priority=0,
        ),
        # 2. CORS configuration (priority 8)
        CORSComponent(
            config=CORSComponentConfig(
                # Global settings - restrictive by default
                allow_origins=["https://app.example.com"],
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_credentials=True,
                # Route-specific overrides
                route_configs=[
                    # Public endpoints - allow all origins
                    RouteSpecificCORSConfig(
                        path_pattern=r"^/api/v1/health$",
                        allow_origins=["*"],
                        allow_credentials=False,
                    ),
                    # Admin endpoints - strict
                    RouteSpecificCORSConfig(
                        path_pattern=r"^/api/v1/admin/.*",
                        allow_origins=["https://admin.example.com"],
                        allow_methods=["GET", "POST"],
                    ),
                ],
            ),
            priority=8,
        ),
        # 3. Authentication (priority 7)
        AuthenticationComponent(
            config=AuthenticationComponentConfig(
                default_handler="api_key",
                route_configs=[
                    # Admin routes require admin token
                    RouteSpecificAuthConfig(
                        path_pattern=r"^/api/v1/admin/.*", handler_name="admin"
                    )
                ],
                # Public endpoints
                exclude_paths=[
                    r"^/health$",
                    r"^/api/v1/health$",
                    r"^/api/v1/metrics$",
                    r"^/docs.*",
                    r"^/openapi\.json$",
                ],
            ),
            priority=7,
        ),
        # 4. WebSocket for real-time updates (priority 15)
        WebSocketServerComponent(
            config=WebSocketComponentConfig(prefix="/ws", max_connections=100),
            priority=15,
        ),
        # 5. Agents API (priority 20)
        AgentsServerComponent(
            config=AgentsServerComponentConfig(prefix="/api/v1", tags=["Agents"]),
            priority=20,
        ),
        # 6. Artifacts API (priority 20)
        ArtifactsComponent(
            config=ArtifactComponentConfig(
                prefix="/api/v1",
                tags=["Artifacts"],
                enable_pagination=True,
                default_page_size=50,
            ),
            priority=20,
        ),
        # 7. Distributed tracing (priority 25)
        TracingComponent(
            config=TracingComponentConfig(
                enabled=True, prefix="/api/v1", tags=["Tracing"]
            ),
            priority=25,
        ),
    ]

    # Register authentication handlers
    auth_component = components[2]  # AuthenticationComponent
    auth_component.register_handler("api_key", api_key_handler)
    auth_component.register_handler("admin", admin_handler)

    print("✅ Configured components:")
    for comp in components:
        print(f"   [{comp.priority:2d}] {comp.name}")

    # Start server
    print("\n4️⃣  Starting Production Server")
    print("-" * 60)

    print("\n🚀 Server starting on http://127.0.0.1:8344")
    print("\n📡 Available Endpoints:\n")

    print("   Health & Monitoring:")
    print("   - GET  /api/v1/health    (public)")
    print("   - GET  /api/v1/metrics   (public)")

    print("\n   Agents:")
    print("   - GET  /api/v1/agents         (requires API key)")
    print("   - GET  /api/v1/agents/{name}  (requires API key)")

    print("\n   Artifacts:")
    print("   - GET  /api/v1/artifacts      (requires API key)")
    print("   - POST /api/v1/artifacts      (requires API key)")

    print("\n   Tracing:")
    print("   - GET  /api/v1/traces         (requires API key)")
    print("   - GET  /api/v1/traces/{id}    (requires API key)")

    print("\n   WebSocket:")
    print("   - WS   /ws                    (real-time updates)")

    print("\n   Admin (requires admin token):")
    print("   - GET  /api/v1/admin/*        (Bearer token required)")

    print("\n🔐 Authentication:")
    print("   - API Key: X-API-Key: sk-your-key-here")
    print("   - Admin:   Authorization: Bearer admin-token-123")

    print("\n📝 Example Requests:\n")
    print("   # Health check (public):")
    print("   curl http://127.0.0.1:8344/api/v1/health")

    print("\n   # List agents (authenticated):")
    print('   curl -H "X-API-Key: sk-demo-key" \\')
    print("     http://127.0.0.1:8344/api/v1/agents")

    print("\n   # Submit order (authenticated):")
    print("   curl -X POST http://127.0.0.1:8344/api/v1/artifacts \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -H "X-API-Key: sk-demo-key" \\')
    print('     -d \'{"type": "__main__.Order", "payload": {...}}\'')

    # Start server (non-blocking)
    await flock.serve(
        components=components, host="127.0.0.1", port=8344, blocking=False
    )

    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Test the workflow
    print("\n5️⃣  Testing Workflow")
    print("-" * 60)

    test_order = Order(
        order_id="ORD-2024-001",
        customer_name="Alice Johnson",
        items=[
            {"product": "Widget A", "quantity": 2, "price": 29.99},
            {"product": "Gadget B", "quantity": 1, "price": 49.99},
        ],
        total_amount=109.97,
    )

    print(f"\n📤 Submitting order: {test_order.order_id}")
    print(f"   Customer: {test_order.customer_name}")
    print(f"   Items: {len(test_order.items)}")
    print(f"   Total: ${test_order.total_amount}")

    await flock.publish(test_order)
    await flock.run_until_idle()

    print("\n✅ Order processed!")
    print(
        "   Chain: Order → order_validator → OrderValidation → order_processor → OrderConfirmation"
    )

    # Keep server running
    print("\n⏳ Server running for 60 seconds...")
    print("   Try the example requests above!")
    print("\n   Press Ctrl+C to stop")

    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
