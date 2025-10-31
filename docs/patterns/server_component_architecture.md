# Server Component Architecture - Visual Reference

## System Architecture Comparison

### Current Architecture (Inheritance-Based)

```
┌────────────────────────────────────────────────────────┐
│                   ServerManager                        │
│  ├─ _serve_standard()  → BlackboardHTTPService        │
│  └─ _serve_dashboard() → DashboardHTTPService         │
└────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │    BlackboardHTTPService              │
        │  - FastAPI app                        │
        │  - _register_routes()                 │
        │    ├─ /api/v1/artifacts/*             │
        │    ├─ /api/v1/agents/*                │
        │    └─ /health, /metrics               │
        └───────────────────────────────────────┘
                            ↓ (extends)
        ┌───────────────────────────────────────┐
        │    DashboardHTTPService               │
        │  - Inherits all base routes           │
        │  - WebSocketManager                   │
        │  - DashboardEventCollector            │
        │  - _register_all_routes()             │
        │    ├─ /ws (WebSocket)                 │
        │    ├─ /api/v1/traces/*                │
        │    └─ /* (static files)               │
        └───────────────────────────────────────┘

❌ Problems:
- Inheritance forces you to get ALL parent routes
- Adding MCP requires choosing: extend base or dashboard?
- Code duplication when creating new service types
- Hard to test routes in isolation
```

### Proposed Architecture (Composition-Based)

```
┌────────────────────────────────────────────────────────┐
│                   ServerManager                        │
│  - serve(components=[...])                             │
│  - _default_components(dashboard=True/False)           │
└────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │         BaseHTTPService               │
        │  - FastAPI app                        │
        │  - components: list[ServerComponent]  │
        │  - configure()                        │
        │  - run_async()                        │
        └───────────────────────────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │         ServerComponent               │
        │  Base class for all components        │
        │  - priority: int                      │
        │  - configure(app, orchestrator)       │
        │  - register_routes(app, orchestrator) │
        │  - on_startup(orchestrator)           │
        │  - on_shutdown(orchestrator)          │
        └───────────────────────────────────────┘
                            ↓
    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    │  Health  │ Artifact │  Agent   │Dashboard │   MCP    │
    │Component │Component │Component │Component │Component │
    │          │          │          │          │          │
    │ priority │ priority │ priority │ priority │ priority │
    │    5     │    10    │    15    │    20    │    30    │
    │          │          │          │          │          │
    │ /health  │/artifacts│ /agents  │   /ws    │ /mcp/*   │
    │ /metrics │ routes   │  routes  │ /traces  │  routes  │
    └──────────┴──────────┴──────────┴──────────┴──────────┘

✅ Benefits:
- Mix and match components as needed
- Each component is independently testable
- Priority ordering controls route registration
- Zero duplication - components are reusable
- Add new protocols without modifying existing code
```

## Component Lifecycle

```
1. User calls ServerManager.serve()
        ↓
2. ServerManager creates BaseHTTPService
        ↓
3. ServerManager adds components (or uses defaults)
        ↓
4. BaseHTTPService.configure()
   ├─ Sort components by priority (5 → 10 → 15 → 20 → 30)
   ├─ Validate dependencies
   ├─ Call component.configure(app, orchestrator) for each
   │  └─ Example: DashboardComponent adds CORS middleware
   └─ Register startup/shutdown hooks
        ↓
5. BaseHTTPService.run_async()
   ├─ Uvicorn starts FastAPI app
   ├─ FastAPI triggers "startup" event
   │  ├─ Call component.register_routes() for each (in priority order)
   │  └─ Call component.on_startup() for each
   │     └─ Example: DashboardComponent creates WebSocketManager
   └─ Server runs...
        ↓
6. User stops server (Ctrl+C)
        ↓
7. FastAPI triggers "shutdown" event
   └─ Call component.on_shutdown() for each (reverse order!)
      └─ Example: DashboardComponent closes WebSocket connections
```

## Component Priority System

```
Priority determines registration order:

┌─────────────────────────────────────────────────────┐
│ Priority 5:  HealthComponent                        │
│              ├─ GET /health                         │
│              └─ GET /metrics                        │
├─────────────────────────────────────────────────────┤
│ Priority 10: ArtifactComponent                      │
│              ├─ POST /api/v1/artifacts              │
│              ├─ GET /api/v1/artifacts               │
│              └─ GET /api/v1/artifacts/{id}          │
├─────────────────────────────────────────────────────┤
│ Priority 15: AgentManagementComponent               │
│              ├─ GET /api/v1/agents                  │
│              ├─ POST /api/v1/agents/{name}/run      │
│              └─ GET /api/v1/correlations/{id}/status│
├─────────────────────────────────────────────────────┤
│ Priority 20: DashboardComponent                     │
│              ├─ GET /ws (WebSocket)                 │
│              ├─ GET /api/v1/traces/*                │
│              └─ GET /* (static files - MUST BE LAST!)│
├─────────────────────────────────────────────────────┤
│ Priority 30: MCPComponent                           │
│              ├─ POST /mcp/tools/list                │
│              └─ POST /mcp/tools/call                │
└─────────────────────────────────────────────────────┘

⚠️ CRITICAL: Static file mount (/*) must be LAST!
   DashboardComponent has priority 20 specifically for this.
```

## Dependency Resolution

```
Components can declare dependencies:

class MyCustomComponent(ServerComponent):
    def get_dependencies(self) -> list[type[ServerComponent]]:
        return [ArtifactComponent]  # Requires artifact routes

BaseHTTPService validates dependencies at configure() time:

┌─────────────────────────────────────────────────────┐
│ User adds components:                               │
│   service.add_component(MyCustomComponent())        │
│   service.add_component(HealthComponent())          │
│                                                     │
│ ❌ ERROR: MyCustomComponent requires ArtifactComponent│
│           but it's not in the component list!      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ User adds components:                               │
│   service.add_component(MyCustomComponent())        │
│   service.add_component(ArtifactComponent())        │
│   service.add_component(HealthComponent())          │
│                                                     │
│ ✅ OK: All dependencies satisfied                   │
└─────────────────────────────────────────────────────┘
```

## Real-World Usage Examples

### Example 1: Basic REST API (No Dashboard)

```python
from flock.components.server import (
    HealthComponent,
    ArtifactComponent,
    AgentManagementComponent,
)

# Option A: Explicit composition
service = BaseHTTPService(orchestrator)
service.add_components([
    HealthComponent(),
    ArtifactComponent(),
    AgentManagementComponent(),
])
await service.run_async()

# Option B: Use ServerManager defaults
await ServerManager.serve(orchestrator, dashboard=False)
```

**Result:**
- GET /health
- GET /metrics
- POST /api/v1/artifacts
- GET /api/v1/artifacts
- GET /api/v1/agents
- POST /api/v1/agents/{name}/run

### Example 2: Dashboard + MCP Server

```python
from flock.components.server import (
    HealthComponent,
    ArtifactComponent,
    AgentManagementComponent,
    DashboardComponent,
    MCPComponent,
)

await ServerManager.serve(
    orchestrator,
    components=[
        HealthComponent(priority=5),
        ArtifactComponent(priority=10),
        AgentManagementComponent(priority=15),
        DashboardComponent(priority=20, config={"launch_browser": True}),
        MCPComponent(priority=30, config={
            "expose_tools": ["agent_invoke", "blackboard_query"]
        }),
    ]
)
```

**Result:**
- All basic routes (health, artifacts, agents)
- WebSocket dashboard at /ws
- MCP endpoints at /mcp/*
- Browser auto-launches with UI

### Example 3: Custom Authentication Component

```python
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer

class AuthComponent(ServerComponent):
    """Add authentication to all routes."""

    name = "auth"
    priority = 1  # Run FIRST (before other routes)

    def configure(self, app, orchestrator):
        security = HTTPBearer()

        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            # Skip health check
            if request.url.path == "/health":
                return await call_next(request)

            # Verify bearer token
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(401, "Unauthorized")

            # Validate token (your logic here)
            token = auth_header[7:]
            if not self._validate_token(token):
                raise HTTPException(401, "Invalid token")

            return await call_next(request)

    async def register_routes(self, app, orchestrator):
        # No routes needed - just middleware
        pass

    def _validate_token(self, token: str) -> bool:
        # Your validation logic
        return token == "secret-token-123"


# Use it
await ServerManager.serve(
    orchestrator,
    components=[
        AuthComponent(priority=1),      # Auth runs first
        HealthComponent(priority=5),
        ArtifactComponent(priority=10),
    ]
)
```

### Example 4: Multi-Tenant Isolation

```python
class TenantComponent(ServerComponent):
    """Add tenant isolation to all API calls."""

    name = "tenant"
    priority = 2

    def configure(self, app, orchestrator):
        @app.middleware("http")
        async def tenant_middleware(request: Request, call_next):
            tenant_id = request.headers.get("X-Tenant-ID")
            if not tenant_id:
                raise HTTPException(400, "X-Tenant-ID header required")

            # Store tenant context
            request.state.tenant_id = tenant_id

            return await call_next(request)

    async def register_routes(self, app, orchestrator):
        # Override artifact endpoints to filter by tenant
        @app.get("/api/v1/artifacts/tenant")
        async def list_tenant_artifacts(request: Request):
            tenant_id = request.state.tenant_id

            # Query only this tenant's artifacts
            artifacts, total = await orchestrator.store.query_artifacts(
                FilterConfig(tags={f"tenant:{tenant_id}"}),
                limit=50,
            )

            return {"tenant_id": tenant_id, "artifacts": artifacts}
```

## Component Communication

Components can share resources via orchestrator or app state:

```python
class ComponentA(ServerComponent):
    async def on_startup(self, orchestrator):
        # Store resource on orchestrator
        self.websocket_manager = WebSocketManager()
        orchestrator._websocket_manager = self.websocket_manager


class ComponentB(ServerComponent):
    async def on_startup(self, orchestrator):
        # Access resource from orchestrator
        ws_manager = orchestrator._websocket_manager
        await ws_manager.broadcast({"event": "component_b_started"})
```

## Testing Components

```python
# Test component in isolation
from fastapi.testclient import TestClient

def test_artifact_component():
    orchestrator = Flock("openai/gpt-4o")

    # Create service with ONLY artifact component
    service = BaseHTTPService(orchestrator)
    service.add_component(ArtifactComponent())
    service.configure()

    # Test with FastAPI test client
    client = TestClient(service.app)

    response = client.post("/api/v1/artifacts", json={
        "type": "MyType",
        "payload": {"message": "hello"}
    })

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


def test_component_ordering():
    """Verify components register in priority order."""
    orchestrator = Flock("openai/gpt-4o")

    service = BaseHTTPService(orchestrator)
    service.add_components([
        DashboardComponent(priority=20),
        HealthComponent(priority=5),
        ArtifactComponent(priority=10),
    ])

    # Should be sorted by priority
    assert service.components[0].priority == 5   # Health
    assert service.components[1].priority == 10  # Artifact
    assert service.components[2].priority == 20  # Dashboard
```

## Migration Checklist

- [ ] Create `src/flock/components/server/` directory
- [ ] Implement `base.py` (ServerComponent, ServerComponentConfig)
- [ ] Extract routes to components:
  - [ ] `health.py` (HealthComponent)
  - [ ] `artifact.py` (ArtifactComponent)
  - [ ] `agent.py` (AgentManagementComponent)
  - [ ] `dashboard.py` (DashboardComponent)
- [ ] Implement `BaseHTTPService` in `src/flock/api/base_service.py`
- [ ] Update `ServerManager` to use composition
- [ ] Add tests for component system
- [ ] Update documentation and examples
- [ ] (Optional) Mark `BlackboardHTTPService` as deprecated

## FAQ

**Q: Why not just use FastAPI's dependency injection?**
A: FastAPI's DI is great for per-request dependencies. ServerComponent handles service-level lifecycle (startup/shutdown), route registration order, and component composition. They serve different purposes.

**Q: Can components depend on each other?**
A: Yes! Use `get_dependencies()` to declare dependencies. BaseHTTPService validates them at configure() time.

**Q: What if two components register the same route?**
A: FastAPI will raise an error. Use priority ordering to control which component "wins", or namespace routes (`/mcp/*`, `/dashboard/*`).

**Q: How do I disable a component?**
A: Set `config.enabled = False` or don't add it to the component list.

**Q: Can I hot-reload components in dev mode?**
A: Not currently, but this is a great future enhancement!

---

*This architecture document complements the main refactoring proposal.*
