# Server Component Refactoring - Executive Summary

**Problem:** Current HTTP service architecture uses inheritance, forcing code duplication when adding new endpoint types (MCP, A2A, custom protocols).

**Solution:** Refactor to composition-based architecture mirroring the successful `AgentComponent` pattern.

---

## Documents

1. **[server_component_refactoring.md](./server_component_refactoring.md)** - Complete refactoring proposal with implementation details
2. **[server_component_architecture.md](./server_component_architecture.md)** - Visual diagrams and usage examples

---

## Quick Summary

### Current Architecture (Problems)

```python
# ❌ Inheritance forces you to get ALL parent routes
class BlackboardHTTPService:
    def _register_routes(self):
        # artifact routes, agent routes, health routes

class DashboardHTTPService(BlackboardHTTPService):  # extends
    def __init__(self):
        super().__init__()  # Gets all base routes
        self._register_all_routes()  # Adds dashboard routes

# Where does MCP fit? Extend BlackboardHTTPService or DashboardHTTPService?
# Either way, you get routes you don't need!
```

**Problems:**
- Forced inheritance chain
- Code duplication
- Can't compose just what you need
- Hard to test in isolation

### Proposed Architecture (Solution)

```python
# ✅ Compose exactly what you need
from flock.components.server import (
    HealthComponent,
    ArtifactComponent,
    AgentManagementComponent,
    DashboardComponent,
    MCPComponent,
)

# Use ServerManager for convenience
await ServerManager.serve(
    orchestrator,
    components=[
        HealthComponent(priority=5),
        ArtifactComponent(priority=10),
        AgentManagementComponent(priority=15),
        DashboardComponent(priority=20),
        MCPComponent(priority=30),
    ]
)
```

**Benefits:**
- ✅ Mix and match components
- ✅ Zero duplication
- ✅ Test components in isolation
- ✅ Priority-based ordering
- ✅ Lifecycle hooks (startup/shutdown)

---

## Key Concepts

### 1. ServerComponent Base Class

```python
class ServerComponent(BaseModel):
    """Base class for HTTP service components."""
    
    name: str | None = None
    priority: int = 0  # Lower runs first
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)
    
    # Lifecycle hooks (same pattern as AgentComponent!)
    def configure(self, app: FastAPI, orchestrator: Flock) -> None:
        """Configure FastAPI app (add middleware, CORS, etc.)"""
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register HTTP routes"""
    
    async def on_startup(self, orchestrator: Flock) -> None:
        """Async startup tasks"""
    
    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Async cleanup tasks"""
```

### 2. BaseHTTPService (Component Host)

```python
class BaseHTTPService:
    """HTTP service built from composable ServerComponents."""
    
    def __init__(self, orchestrator: Flock, **kwargs):
        self.orchestrator = orchestrator
        self.components: list[ServerComponent] = []
        self.app = FastAPI(**kwargs)
    
    def add_component(self, component: ServerComponent) -> None:
        """Add a component to the service."""
    
    def configure(self) -> None:
        """Configure FastAPI app with all components."""
        # 1. Sort components by priority
        # 2. Validate dependencies
        # 3. Call component.configure() for each
        # 4. Register startup/shutdown hooks
        # 5. Call component.register_routes() for each
    
    async def run_async(self, host: str, port: int) -> None:
        """Run the service asynchronously."""
```

### 3. Concrete Components

**HealthComponent** - Health check and metrics
```python
class HealthComponent(ServerComponent):
    priority = 5  # Early registration
    
    async def register_routes(self, app, orchestrator):
        @app.get("/health")
        async def health(): ...
        
        @app.get("/metrics")
        async def metrics(): ...
```

**ArtifactComponent** - Artifact CRUD operations
```python
class ArtifactComponent(ServerComponent):
    priority = 10
    
    async def register_routes(self, app, orchestrator):
        @app.post("/api/v1/artifacts")
        async def publish_artifact(): ...
        
        @app.get("/api/v1/artifacts")
        async def list_artifacts(): ...
```

**DashboardComponent** - WebSocket dashboard
```python
class DashboardComponent(ServerComponent):
    priority = 20  # After base routes
    
    async def on_startup(self, orchestrator):
        # Initialize WebSocketManager, EventCollector, etc.
        self.websocket_manager = WebSocketManager()
        self.launcher = DashboardLauncher()
        self.launcher.start()
    
    async def register_routes(self, app, orchestrator):
        # Register WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(): ...
        
        # Mount static files (MUST BE LAST!)
        app.mount("/", StaticFiles(...))
    
    async def on_shutdown(self, orchestrator):
        # Cleanup
        await self.websocket_manager.shutdown()
        self.launcher.stop()
```

**MCPComponent** (NEW!) - MCP server endpoints
```python
class MCPComponent(ServerComponent):
    priority = 30
    config: MCPComponentConfig = Field(default_factory=MCPComponentConfig)
    
    async def register_routes(self, app, orchestrator):
        @app.post("/mcp/tools/list")
        async def list_mcp_tools(): ...
        
        @app.post("/mcp/tools/call")
        async def call_mcp_tool(): ...
```

---

## Usage Examples

### Example 1: REST API Only (No Dashboard)

```python
# Option A: Explicit composition
service = BaseHTTPService(orchestrator)
service.add_components([
    HealthComponent(),
    ArtifactComponent(),
    AgentManagementComponent(),
])
await service.run_async()

# Option B: Use ServerManager
await ServerManager.serve(orchestrator, dashboard=False)
```

### Example 2: Dashboard + MCP

```python
await ServerManager.serve(
    orchestrator,
    components=[
        HealthComponent(),
        ArtifactComponent(),
        AgentManagementComponent(),
        DashboardComponent(config={"launch_browser": True}),
        MCPComponent(config={"expose_tools": ["agent_invoke"]}),
    ]
)
```

### Example 3: Custom Authentication

```python
class AuthComponent(ServerComponent):
    priority = 1  # Run FIRST
    
    def configure(self, app, orchestrator):
        @app.middleware("http")
        async def auth_middleware(request, call_next):
            # Your auth logic
            if not self._validate_token(request):
                raise HTTPException(401)
            return await call_next(request)
    
    async def register_routes(self, app, orchestrator):
        pass  # No routes needed

await ServerManager.serve(
    orchestrator,
    components=[
        AuthComponent(priority=1),
        HealthComponent(priority=5),
        ArtifactComponent(priority=10),
    ]
)
```

---

## Migration Path

**Phase 1: Create infrastructure**
1. Create `src/flock/components/server/base.py`
2. Create `src/flock/api/base_service.py`

**Phase 2: Extract routes to components**
1. `health.py` - Health & metrics
2. `artifact.py` - Artifact routes
3. `agent.py` - Agent routes
4. `dashboard.py` - Dashboard routes

**Phase 3: Update ServerManager**
1. Modify `server_manager.py` to use `BaseHTTPService`
2. Add `components` parameter

**Phase 4: Deprecate old classes (optional)**
1. Mark `BlackboardHTTPService` as deprecated
2. Keep for 1-2 versions for backward compatibility

---

## Backward Compatibility

```python
# OLD CODE - still works!
service = BlackboardHTTPService(orchestrator)
await service.run_async()

# NEW CODE - recommended
service = BaseHTTPService(orchestrator)
service.add_components([...])
await service.run_async()

# EASIEST - ServerManager (same interface!)
await ServerManager.serve(orchestrator, dashboard=True)
```

---

## Testing

```python
# Test component in isolation
def test_artifact_component():
    orchestrator = Flock("openai/gpt-4o")
    
    service = BaseHTTPService(orchestrator)
    service.add_component(ArtifactComponent())
    service.configure()
    
    client = TestClient(service.app)
    response = client.post("/api/v1/artifacts", json={...})
    
    assert response.status_code == 200
```

---

## Next Steps

1. **Review proposal** - Get team feedback on architecture
2. **Prototype** - Implement `ArtifactComponent` extraction
3. **Validate** - Test component isolation and composition
4. **Iterate** - Add MCP/A2A components to prove extensibility
5. **Document** - Update guides and examples
6. **Migrate** - Gradual rollout with backward compatibility

---

## Questions?

Read the detailed proposal: [server_component_refactoring.md](./server_component_refactoring.md)

See visual examples: [server_component_architecture.md](./server_component_architecture.md)

---

**Status:** Draft proposal - ready for review

**Author:** AI Assistant

**Date:** October 21, 2025
