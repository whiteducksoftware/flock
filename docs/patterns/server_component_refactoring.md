# Server Component System - Refactoring Proposal

**Date:** October 21, 2025  
**Status:** Draft Proposal  
**Author:** AI Assistant  

## Executive Summary

This document proposes refactoring the HTTP service system to mirror the successful `AgentComponent` pattern, eliminating code duplication and enabling flexible endpoint composition for MCP, A2A, and custom protocols.

**Key Benefits:**
- ✅ **Zero duplication** - Compose services from reusable components
- ✅ **Extensibility** - Add MCP/A2A/custom endpoints without modifying core
- ✅ **Consistency** - Same component pattern developers already know
- ✅ **Testability** - Test components in isolation
- ✅ **Priority ordering** - Control route registration order
- ✅ **Lifecycle hooks** - Initialize/configure/cleanup logic

---

## Current Problems

### 1. Code Duplication
```python
# BlackboardHTTPService has these routes
class BlackboardHTTPService:
    def _register_routes(self):
        @app.post("/api/v1/artifacts")
        async def publish_artifact(): ...
        
        @app.get("/api/v1/artifacts")
        async def list_artifacts(): ...

# DashboardHTTPService EXTENDS and ADDS MORE
class DashboardHTTPService(BlackboardHTTPService):
    def __init__(self):
        super().__init__()  # Gets base routes
        self._register_all_routes()  # Adds dashboard routes
```

**Problem:** If we want MCP endpoints, do we:
- Extend `BlackboardHTTPService`? (gets artifact routes we don't need)
- Extend `DashboardHTTPService`? (gets dashboard routes we don't need)
- Copy-paste route code? (duplication!)

### 2. Forced Inheritance Chain
```
BlackboardHTTPService
  ↓ extends
DashboardHTTPService
  ↓ extends
MCPHTTPService?  ← Where does this fit?
  ↓ extends
A2AHTTPService?  ← Diamond problem incoming!
```

### 3. ServerManager Knows Too Much
```python
# ServerManager._serve_dashboard() creates EVERYTHING
websocket_manager = WebSocketManager()
event_collector = DashboardEventCollector.get_instance(...)
launcher = DashboardLauncher(...)
service = DashboardHTTPService(...)

# If we add MCP, do we duplicate this in _serve_mcp()?
```

---

## Proposed Solution: Server Component System

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│            ServerManager (Orchestrator)             │
│  - Manages component lifecycle                     │
│  - Composes services from components                │
│  - Handles startup/shutdown                         │
└─────────────────────────────────────────────────────┘
                      ↓
    ┌─────────────────────────────────────────┐
    │   BaseHTTPService (Component Host)      │
    │  - Hosts ServerComponent instances      │
    │  - Manages component priority ordering  │
    │  - Delegates lifecycle to components    │
    └─────────────────────────────────────────┘
                      ↓
    ┌─────────────────────────────────────────┐
    │      ServerComponent (Base Class)       │
    │  - register_routes()                    │
    │  - on_startup() / on_shutdown()         │
    │  - configure()                          │
    └─────────────────────────────────────────┘
                      ↓
    ┌──────────┬──────────┬──────────┬──────────┐
    │ Artifact │Dashboard │   MCP    │   A2A    │
    │Component │Component │Component │Component │
    └──────────┴──────────┴──────────┴──────────┘
```

### Component-Based Composition

**Current (inheritance-based):**
```python
# ❌ Forced to choose ONE parent class
service = DashboardHTTPService(orchestrator)
# ^ Gets artifact routes + dashboard routes (no choice!)
```

**Proposed (composition-based):**
```python
# ✅ Compose exactly what you need
service = BaseHTTPService(orchestrator)
service.add_component(ArtifactComponent(priority=10))
service.add_component(DashboardComponent(priority=20))
service.add_component(MCPComponent(priority=30))
service.add_component(CustomComponent(priority=40))

# Or use ServerManager helper
await ServerManager.serve(
    orchestrator,
    components=[
        ArtifactComponent(),
        DashboardComponent(launch_browser=True),
        MCPComponent(expose_tools=["agent_invoke", "blackboard_query"]),
    ]
)
```

---

## Implementation Details

### 1. ServerComponent Base Class

```python
# src/flock/components/server/base.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from flock.core import Flock

class ServerComponentConfig(BaseModel):
    """Configuration for server components."""
    enabled: bool = Field(default=True, description="Enable this component")


class ServerComponent(BaseModel):
    """Base class for HTTP service components.
    
    Mirrors AgentComponent pattern for consistency.
    Components register routes, handle startup/shutdown, and can configure FastAPI.
    
    Lifecycle:
        1. __init__() - Component creation
        2. configure() - Configure FastAPI app (middleware, exception handlers, etc.)
        3. register_routes() - Add endpoints to FastAPI app
        4. on_startup() - Async startup tasks (connect to resources, etc.)
        5. ... service runs ...
        6. on_shutdown() - Async cleanup tasks
    
    Example:
        >>> class MyComponent(ServerComponent):
        ...     async def register_routes(self, app, orchestrator):
        ...         @app.get("/my-endpoint")
        ...         async def my_endpoint():
        ...             return {"status": "ok"}
        ...
        ...     async def on_startup(self, orchestrator):
        ...         print("My component started!")
    """
    
    name: str | None = Field(default=None, description="Component name (auto-generated if None)")
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)
    priority: int = Field(
        default=0,
        description="Registration priority (lower runs first, controls route order)"
    )
    
    # Lifecycle hooks
    
    def configure(self, app: FastAPI, orchestrator: Flock) -> None:
        """Configure FastAPI app (sync - runs before server starts).
        
        Use this to add middleware, exception handlers, CORS, etc.
        
        Args:
            app: FastAPI application instance
            orchestrator: Flock orchestrator instance
        """
        pass
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register HTTP routes to FastAPI app.
        
        Called in priority order. Lower priority numbers register first.
        
        Args:
            app: FastAPI application instance
            orchestrator: Flock orchestrator instance
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement register_routes()"
        )
    
    async def on_startup(self, orchestrator: Flock) -> None:
        """Async startup hook - runs when service starts.
        
        Use this for async initialization (connect to databases, start background tasks, etc.)
        
        Args:
            orchestrator: Flock orchestrator instance
        """
        pass
    
    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Async shutdown hook - runs when service stops.
        
        Use this for cleanup (close connections, stop background tasks, etc.)
        
        Args:
            orchestrator: Flock orchestrator instance
        """
        pass
    
    # Helper methods
    
    def get_dependencies(self) -> list[type[ServerComponent]]:
        """Return list of component types this component depends on.
        
        Used for automatic ordering and validation.
        
        Example:
            >>> class MyComponent(ServerComponent):
            ...     def get_dependencies(self):
            ...         return [ArtifactComponent]  # Requires artifact routes
        """
        return []


__all__ = ["ServerComponent", "ServerComponentConfig"]
```

### 2. BaseHTTPService (Component Host)

```python
# src/flock/api/base_service.py

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from flock.components.server.base import ServerComponent
    from flock.core import Flock


class BaseHTTPService:
    """HTTP service built from composable ServerComponents.
    
    Replaces inheritance-based BlackboardHTTPService with composition.
    Components are registered in priority order and manage their own routes.
    
    Example:
        >>> service = BaseHTTPService(orchestrator, title="My API")
        >>> service.add_component(ArtifactComponent(priority=10))
        >>> service.add_component(DashboardComponent(priority=20))
        >>> await service.run_async(host="0.0.0.0", port=8080)
    """
    
    def __init__(
        self,
        orchestrator: Flock,
        *,
        title: str = "Flock API",
        version: str = "1.0.0",
        description: str = "Composable API for Flock orchestrator",
    ):
        self.orchestrator = orchestrator
        self.components: list[ServerComponent] = []
        
        # Create FastAPI app
        self.app = FastAPI(title=title, version=version, description=description)
        
        # Track initialization state
        self._configured = False
        self._started = False
    
    def add_component(self, component: ServerComponent) -> None:
        """Add a server component (must be called before configure()).
        
        Args:
            component: ServerComponent instance to add
        
        Raises:
            RuntimeError: If called after configure()
        """
        if self._configured:
            raise RuntimeError("Cannot add components after configure()")
        
        self.components.append(component)
    
    def add_components(self, components: list[ServerComponent]) -> None:
        """Add multiple components at once.
        
        Args:
            components: List of ServerComponent instances
        """
        for component in components:
            self.add_component(component)
    
    def configure(self) -> None:
        """Configure FastAPI app with all components.
        
        1. Sorts components by priority
        2. Validates dependencies
        3. Calls component.configure() for each
        4. Calls component.register_routes() for each
        
        Must be called before run_async().
        """
        if self._configured:
            return
        
        # Sort by priority (lower first)
        self.components.sort(key=lambda c: c.priority)
        
        # Validate dependencies
        self._validate_dependencies()
        
        # Configure phase (sync)
        for component in self.components:
            if component.config.enabled:
                component.configure(self.app, self.orchestrator)
        
        # Register routes phase (async wrapper needed)
        @self.app.on_event("startup")
        async def _register_routes():
            for component in self.components:
                if component.config.enabled:
                    await component.register_routes(self.app, self.orchestrator)
        
        # Startup/shutdown hooks
        @self.app.on_event("startup")
        async def _startup():
            for component in self.components:
                if component.config.enabled:
                    await component.on_startup(self.orchestrator)
            self._started = True
        
        @self.app.on_event("shutdown")
        async def _shutdown():
            for component in reversed(self.components):  # Reverse order
                if component.config.enabled:
                    await component.on_shutdown(self.orchestrator)
            self._started = False
        
        self._configured = True
    
    def _validate_dependencies(self) -> None:
        """Validate that all component dependencies are satisfied."""
        enabled_types = {type(c) for c in self.components if c.config.enabled}
        
        for component in self.components:
            if not component.config.enabled:
                continue
            
            for dep_type in component.get_dependencies():
                if dep_type not in enabled_types:
                    raise ValueError(
                        f"Component {component.name or component.__class__.__name__} "
                        f"requires {dep_type.__name__} but it's not enabled"
                    )
    
    async def run_async(self, host: str = "127.0.0.1", port: int = 8344) -> None:
        """Run the service asynchronously.
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        import uvicorn
        
        # Configure if not already done
        if not self._configured:
            self.configure()
        
        # Run server
        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self, host: str = "127.0.0.1", port: int = 8344) -> None:
        """Run the service synchronously (blocks).
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        import uvicorn
        
        # Configure if not already done
        if not self._configured:
            self.configure()
        
        # Run server
        uvicorn.run(self.app, host=host, port=port)


__all__ = ["BaseHTTPService"]
```

### 3. Concrete Components

#### ArtifactComponent (Replaces BlackboardHTTPService routes)

```python
# src/flock/components/server/artifact.py

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from flock.api.models import (
    ArtifactListResponse,
    ArtifactPublishRequest,
    ArtifactPublishResponse,
    ArtifactSummaryResponse,
)
from flock.components.server.base import ServerComponent
from flock.core.store import ArtifactEnvelope, ConsumptionRecord, FilterConfig

if TYPE_CHECKING:
    from flock.core import Flock


class ArtifactComponent(ServerComponent):
    """HTTP endpoints for artifact management.
    
    Provides:
    - POST /api/v1/artifacts - Publish artifacts
    - GET /api/v1/artifacts - List/query artifacts
    - GET /api/v1/artifacts/{id} - Get single artifact
    - GET /api/v1/artifacts/summary - Summary statistics
    """
    
    name: str = "artifact"
    priority: int = 10  # Base routes - register early
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register artifact management routes."""
        
        def _serialize_artifact(artifact, consumptions=None) -> dict[str, Any]:
            # ... (same as current implementation)
            pass
        
        def _parse_datetime(value: str | None, label: str) -> datetime | None:
            # ... (same as current implementation)
            pass
        
        def _make_filter_config(...) -> FilterConfig:
            # ... (same as current implementation)
            pass
        
        @app.post("/api/v1/artifacts", response_model=ArtifactPublishResponse, tags=["Artifacts"])
        async def publish_artifact(body: ArtifactPublishRequest) -> ArtifactPublishResponse:
            try:
                await orchestrator.publish({"type": body.type, **body.payload})
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return ArtifactPublishResponse(status="accepted")
        
        @app.get("/api/v1/artifacts", response_model=ArtifactListResponse, tags=["Artifacts"])
        async def list_artifacts(...) -> ArtifactListResponse:
            # ... (same as current implementation)
            pass
        
        @app.get("/api/v1/artifacts/summary", response_model=ArtifactSummaryResponse, tags=["Artifacts"])
        async def summarize_artifacts(...) -> ArtifactSummaryResponse:
            # ... (same as current implementation)
            pass
        
        @app.get("/api/v1/artifacts/{artifact_id}", tags=["Artifacts"])
        async def get_artifact(artifact_id: UUID) -> dict[str, Any]:
            # ... (same as current implementation)
            pass


__all__ = ["ArtifactComponent"]
```

#### AgentComponent (Agent management routes)

```python
# src/flock/components/server/agent.py

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException

from flock.api.models import (
    Agent,
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentSubscription,
    ProducedArtifact,
)
from flock.components.server.base import ServerComponent
from flock.registry import type_registry

if TYPE_CHECKING:
    from flock.core import Flock


class AgentManagementComponent(ServerComponent):
    """HTTP endpoints for agent management and execution.
    
    Provides:
    - GET /api/v1/agents - List agents
    - POST /api/v1/agents/{name}/run - Execute agent
    - GET /api/v1/agents/{id}/history-summary - Agent history
    - GET /api/v1/correlations/{id}/status - Workflow status
    """
    
    name: str = "agent"
    priority: int = 15  # After artifacts
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register agent management routes."""
        
        @app.get("/api/v1/agents", response_model=AgentListResponse, tags=["Agents"])
        async def list_agents() -> AgentListResponse:
            # ... (same as current implementation)
            pass
        
        @app.post("/api/v1/agents/{name}/run", response_model=AgentRunResponse, tags=["Agents"])
        async def run_agent(name: str, body: AgentRunRequest) -> AgentRunResponse:
            # ... (same as current implementation)
            pass
        
        @app.get("/api/v1/agents/{agent_id}/history-summary", tags=["Agents"])
        async def agent_history(agent_id: str, ...) -> dict:
            # ... (same as current implementation)
            pass
        
        @app.get("/api/v1/correlations/{correlation_id}/status", tags=["Agents"])
        async def get_correlation_status(correlation_id: str) -> dict:
            # ... (same as current implementation)
            pass


__all__ = ["AgentManagementComponent"]
```

#### DashboardComponent (Dashboard-specific features)

```python
# src/flock/components/server/dashboard.py

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.graph_builder import GraphAssembler
from flock.dashboard.launcher import DashboardLauncher
from flock.dashboard.websocket import WebSocketManager

if TYPE_CHECKING:
    from flock.core import Flock


class DashboardComponentConfig(ServerComponentConfig):
    """Configuration for dashboard component."""
    launch_browser: bool = Field(default=True, description="Auto-launch browser")
    use_v2: bool = Field(default=False, description="Use v2 dashboard frontend")
    enable_cors: bool = Field(
        default=False,
        description="Enable CORS for development (auto-enabled if DASHBOARD_DEV=1)"
    )


class DashboardComponent(ServerComponent):
    """WebSocket dashboard with real-time agent visualization.
    
    Provides:
    - WebSocket endpoint at /ws
    - Static file serving for dashboard UI
    - Real-time event streaming
    - Agent graph visualization
    - Trace viewing
    
    Dependencies:
    - Optionally works better with ArtifactComponent for full API
    """
    
    name: str = "dashboard"
    priority: int = 20  # After base routes
    config: DashboardComponentConfig = Field(default_factory=DashboardComponentConfig)
    
    # Runtime state
    websocket_manager: WebSocketManager | None = None
    event_collector: DashboardEventCollector | None = None
    graph_assembler: GraphAssembler | None = None
    launcher: DashboardLauncher | None = None
    
    def configure(self, app: FastAPI, orchestrator: Flock) -> None:
        """Configure CORS middleware if needed."""
        enable_cors = self.config.enable_cors or os.environ.get("DASHBOARD_DEV") == "1"
        
        if enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
    
    async def on_startup(self, orchestrator: Flock) -> None:
        """Initialize dashboard components."""
        from flock.core import Agent
        
        # Create WebSocket manager and event collector
        self.websocket_manager = WebSocketManager()
        self.event_collector = DashboardEventCollector(store=orchestrator.store)
        self.event_collector.set_websocket_manager(self.websocket_manager)
        await self.event_collector.load_persistent_snapshots()
        
        # Store references on orchestrator
        orchestrator._dashboard_collector = self.event_collector
        orchestrator._websocket_manager = self.websocket_manager
        orchestrator._event_emitter.set_websocket_manager(self.websocket_manager)
        
        # Set WebSocket broadcast on Agent class
        async def _broadcast_wrapper(event):
            return await self.websocket_manager.broadcast(event)
        Agent._websocket_broadcast_global = _broadcast_wrapper
        
        # Inject collector into existing agents
        for agent in orchestrator._agents.values():
            agent._add_utilities([self.event_collector])
        
        # Create graph assembler
        self.graph_assembler = GraphAssembler(
            orchestrator.store, self.event_collector, orchestrator
        )
        
        # Start dashboard launcher (npm + browser)
        if self.config.launch_browser:
            launcher_kwargs = {"port": 8344}  # TODO: Get from run_async() args
            if self.config.use_v2:
                dashboard_pkg_dir = Path(__file__).parent.parent.parent / "dashboard"
                launcher_kwargs["frontend_dir"] = dashboard_pkg_dir.parent / "frontend_v2"
                launcher_kwargs["static_dir"] = dashboard_pkg_dir / "static_v2"
            
            self.launcher = DashboardLauncher(**launcher_kwargs)
            self.launcher.start()
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register dashboard routes (WebSocket, static files, etc.)."""
        from flock.dashboard.routes import (
            register_control_routes,
            register_theme_routes,
            register_trace_routes,
            register_websocket_routes,
        )
        
        # Register dashboard route modules
        register_control_routes(app, orchestrator, self.websocket_manager, self.event_collector)
        register_trace_routes(app, orchestrator, self.websocket_manager, self.event_collector)
        register_theme_routes(app)
        register_websocket_routes(
            app,
            orchestrator,
            self.websocket_manager,
            self.event_collector,
            self.graph_assembler,
            use_v2=self.config.use_v2,
        )
    
    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Clean up dashboard resources."""
        if self.websocket_manager:
            await self.websocket_manager.shutdown()
        
        if self.launcher:
            self.launcher.stop()


__all__ = ["DashboardComponent", "DashboardComponentConfig"]
```

#### MCPComponent (NEW - for MCP server endpoints)

```python
# src/flock/components/server/mcp.py

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig

if TYPE_CHECKING:
    from flock.core import Flock


class MCPComponentConfig(ServerComponentConfig):
    """Configuration for MCP server component."""
    expose_tools: list[str] = Field(
        default_factory=lambda: ["agent_invoke", "blackboard_query"],
        description="MCP tools to expose"
    )
    base_path: str = Field(default="/mcp", description="Base path for MCP endpoints")


class MCPComponent(ServerComponent):
    """Model Context Protocol (MCP) server endpoints.
    
    Provides:
    - POST /mcp/tools/list - List available tools
    - POST /mcp/tools/call - Execute tool
    - POST /mcp/resources/list - List available resources
    - POST /mcp/resources/read - Read resource
    
    Exposes Flock agents and artifacts via MCP protocol for AI assistants.
    """
    
    name: str = "mcp"
    priority: int = 30  # After core routes
    config: MCPComponentConfig = Field(default_factory=MCPComponentConfig)
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register MCP protocol endpoints."""
        base = self.config.base_path
        
        @app.post(f"{base}/tools/list", tags=["MCP"])
        async def list_mcp_tools():
            """List available MCP tools."""
            tools = []
            
            if "agent_invoke" in self.config.expose_tools:
                tools.append({
                    "name": "agent_invoke",
                    "description": "Execute a Flock agent with inputs",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "agent_name": {"type": "string"},
                            "inputs": {"type": "array"},
                        },
                        "required": ["agent_name", "inputs"],
                    },
                })
            
            if "blackboard_query" in self.config.expose_tools:
                tools.append({
                    "name": "blackboard_query",
                    "description": "Query artifacts from the blackboard",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                    },
                })
            
            return {"tools": tools}
        
        @app.post(f"{base}/tools/call", tags=["MCP"])
        async def call_mcp_tool(request: dict):
            """Execute an MCP tool."""
            tool_name = request.get("name")
            arguments = request.get("arguments", {})
            
            if tool_name == "agent_invoke":
                agent_name = arguments["agent_name"]
                inputs = arguments["inputs"]
                
                agent = orchestrator.get_agent(agent_name)
                outputs = await orchestrator.direct_invoke(agent, inputs)
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Agent {agent_name} produced {len(outputs)} artifacts",
                        }
                    ]
                }
            
            elif tool_name == "blackboard_query":
                type_name = arguments.get("type")
                limit = arguments.get("limit", 10)
                
                artifacts, _ = await orchestrator.store.query_artifacts(
                    FilterConfig(type_names={type_name} if type_name else None),
                    limit=limit,
                )
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(artifacts)} artifacts",
                        }
                    ]
                }
            
            return {"error": f"Unknown tool: {tool_name}"}


__all__ = ["MCPComponent", "MCPComponentConfig"]
```

#### HealthComponent (Health & Metrics)

```python
# src/flock/components/server/health.py

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from flock.api.models import HealthResponse
from flock.components.server.base import ServerComponent

if TYPE_CHECKING:
    from flock.core import Flock


class HealthComponent(ServerComponent):
    """Health check and metrics endpoints.
    
    Provides:
    - GET /health - Health check
    - GET /metrics - Prometheus-style metrics
    """
    
    name: str = "health"
    priority: int = 5  # Early registration (no dependencies)
    
    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register health and metrics routes."""
        
        @app.get("/health", response_model=HealthResponse, tags=["Health"])
        async def health() -> HealthResponse:
            return HealthResponse(status="ok")
        
        @app.get("/metrics", tags=["Health"])
        async def metrics() -> PlainTextResponse:
            lines = [
                f"blackboard_{key} {value}"
                for key, value in orchestrator.metrics.items()
            ]
            return PlainTextResponse("\n".join(lines))


__all__ = ["HealthComponent"]
```

### 4. Updated ServerManager

```python
# src/flock/orchestrator/server_manager.py (refactored)

from __future__ import annotations

import asyncio
from asyncio import Task
from typing import TYPE_CHECKING

from flock.api.base_service import BaseHTTPService
from flock.components.server import (
    AgentManagementComponent,
    ArtifactComponent,
    DashboardComponent,
    HealthComponent,
)

if TYPE_CHECKING:
    from flock.components.server.base import ServerComponent
    from flock.core.orchestrator import Flock


class ServerManager:
    """Manages HTTP service startup for the orchestrator.
    
    Now uses composable ServerComponents instead of inheritance.
    """
    
    @staticmethod
    async def serve(
        orchestrator: Flock,
        *,
        dashboard: bool = False,
        dashboard_v2: bool = False,
        host: str = "127.0.0.1",
        port: int = 8344,
        blocking: bool = True,
        components: list[ServerComponent] | None = None,
    ) -> Task[None] | None:
        """Start HTTP service for the orchestrator.
        
        Args:
            orchestrator: The Flock orchestrator instance to serve
            dashboard: Enable real-time dashboard (default: False)
            dashboard_v2: Use v2 dashboard frontend (implies dashboard=True)
            host: Host to bind to (default: "127.0.0.1")
            port: Port to bind to (default: 8344)
            blocking: Block until server stops (default: True)
            components: Custom components (None = use defaults based on dashboard flag)
        
        Returns:
            None if blocking=True, or Task handle if blocking=False
        
        Examples:
            # Basic API (artifacts + agents + health)
            await ServerManager.serve(orchestrator)
            
            # With dashboard
            await ServerManager.serve(orchestrator, dashboard=True)
            
            # Custom components
            from flock.components.server import MCPComponent
            await ServerManager.serve(
                orchestrator,
                components=[
                    HealthComponent(),
                    ArtifactComponent(),
                    AgentManagementComponent(),
                    MCPComponent(config={"expose_tools": ["agent_invoke"]}),
                ]
            )
        """
        # Determine components
        if components is None:
            components = ServerManager._default_components(dashboard, dashboard_v2)
        
        # Create service
        service = BaseHTTPService(
            orchestrator,
            title="Flock API",
            version="1.0.0",
        )
        service.add_components(components)
        service.configure()
        
        # Non-blocking mode
        if not blocking:
            server_task = asyncio.create_task(
                service.run_async(host=host, port=port)
            )
            orchestrator._server_task = server_task
            await asyncio.sleep(0.1)  # Let server start
            return server_task
        
        # Blocking mode
        await service.run_async(host=host, port=port)
        return None
    
    @staticmethod
    def _default_components(dashboard: bool, dashboard_v2: bool) -> list[ServerComponent]:
        """Build default component list based on flags."""
        components = [
            HealthComponent(priority=5),
            ArtifactComponent(priority=10),
            AgentManagementComponent(priority=15),
        ]
        
        if dashboard or dashboard_v2:
            components.append(
                DashboardComponent(
                    priority=20,
                    config={"use_v2": dashboard_v2, "launch_browser": True},
                )
            )
        
        return components


__all__ = ["ServerManager"]
```

---

## Migration Guide

### Step 1: Create Component Base Classes

1. Create `src/flock/components/server/` directory
2. Implement `base.py` (ServerComponent, ServerComponentConfig)
3. Create `__init__.py` with exports

### Step 2: Extract Routes to Components

1. Create `artifact.py` - Extract artifact routes from `BlackboardHTTPService`
2. Create `agent.py` - Extract agent routes
3. Create `health.py` - Extract health/metrics routes
4. Create `dashboard.py` - Wrap existing dashboard routes

### Step 3: Implement BaseHTTPService

1. Create `src/flock/api/base_service.py`
2. Implement component hosting logic
3. Add priority ordering and lifecycle hooks

### Step 4: Update ServerManager

1. Modify `server_manager.py` to use `BaseHTTPService` + components
2. Add `components` parameter to `serve()`
3. Keep backward compatibility (dashboard flag still works)

### Step 5: Deprecate Old Classes (Optional)

1. Mark `BlackboardHTTPService` as deprecated
2. Keep for 1-2 versions for backward compatibility
3. Update documentation to recommend new approach

### Backward Compatibility

```python
# OLD CODE - still works!
service = BlackboardHTTPService(orchestrator)
await service.run_async()

# NEW CODE - recommended
service = BaseHTTPService(orchestrator)
service.add_components([
    HealthComponent(),
    ArtifactComponent(),
    AgentManagementComponent(),
])
await service.run_async()

# EASIEST - use ServerManager
await ServerManager.serve(orchestrator)  # Same as before!
```

---

## Use Cases Enabled

### 1. MCP Server Only (No Web UI)

```python
from flock.components.server import MCPComponent, HealthComponent

await ServerManager.serve(
    orchestrator,
    components=[
        HealthComponent(),
        MCPComponent(config={"expose_tools": ["agent_invoke", "blackboard_query"]}),
    ]
)
```

### 2. A2A Protocol Support

```python
from flock.components.server import A2AComponent

await ServerManager.serve(
    orchestrator,
    components=[
        HealthComponent(),
        ArtifactComponent(),
        AgentManagementComponent(),
        A2AComponent(config={"discovery_enabled": True}),
    ]
)
```

### 3. Custom Enterprise Endpoints

```python
class CustomAuthComponent(ServerComponent):
    name = "custom_auth"
    priority = 1  # Run first!
    
    def configure(self, app, orchestrator):
        # Add custom middleware
        app.add_middleware(MyAuthMiddleware)
    
    async def register_routes(self, app, orchestrator):
        @app.post("/api/v1/custom/authenticate")
        async def custom_auth(credentials):
            # Custom logic
            pass

await ServerManager.serve(
    orchestrator,
    components=[
        CustomAuthComponent(),  # Your custom logic
        HealthComponent(),
        ArtifactComponent(),
        DashboardComponent(),
    ]
)
```

### 4. Testing Isolation

```python
# Test only artifact endpoints
service = BaseHTTPService(orchestrator)
service.add_component(ArtifactComponent())
service.configure()

# Test client
from fastapi.testclient import TestClient
client = TestClient(service.app)
response = client.post("/api/v1/artifacts", json={...})
```

---

## Benefits Summary

| Current System | Proposed System |
|---------------|----------------|
| ❌ Inheritance chain | ✅ Composition |
| ❌ Code duplication | ✅ Reusable components |
| ❌ Hard to extend | ✅ Plugin architecture |
| ❌ Testing full service | ✅ Test components in isolation |
| ❌ Fixed route order | ✅ Priority-based ordering |
| ❌ Middleware conflicts | ✅ Component-level configuration |
| ❌ ServerManager knows everything | ✅ ServerManager orchestrates components |

---

## Open Questions

1. **Component Discovery:** Should we support auto-discovery via entry points?
   ```python
   # pyproject.toml
   [project.entry-points."flock.server_components"]
   mcp = "flock_mcp.components:MCPComponent"
   ```

2. **Component Communication:** Do components need to communicate?
   ```python
   # Example: DashboardComponent needs WebSocketManager from another component
   class MyComponent(ServerComponent):
       def get_shared_resources(self) -> dict:
           return {"websocket_manager": self.websocket_manager}
   ```

3. **Hot Reload:** Should components support hot reload in dev mode?

4. **Versioning:** Should components declare API version compatibility?

---

## Next Steps

1. **Review this proposal** - Get feedback on architecture
2. **Prototype ArtifactComponent** - Validate extraction approach
3. **Implement BaseHTTPService** - Test component hosting
4. **Create MCPComponent** - Prove extensibility works
5. **Update tests** - Ensure backward compatibility
6. **Document migration** - Help users adopt new pattern

---

## Conclusion

This refactoring mirrors the successful `AgentComponent` pattern, providing:
- **Consistency** - Same component model across codebase
- **Extensibility** - Add MCP/A2A/custom protocols without modifying core
- **Testability** - Test components in isolation
- **Maintainability** - Each component owns its routes/lifecycle

The migration path preserves backward compatibility while enabling powerful new composition patterns.

**Recommendation:** Proceed with incremental migration starting with `ArtifactComponent` extraction.
