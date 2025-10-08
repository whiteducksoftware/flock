# Flock Architecture Guide for AI Agents

This document provides architectural details for AI agents working with Flock Flow.

## 🏗️ Project Structure

```
flock-flow/
├── src/flock/              # Core Python framework
│   ├── orchestrator.py          # Main orchestrator (scheduling, blackboard)
│   ├── agent.py                 # Agent & AgentBuilder (fluent API)
│   ├── artifacts.py             # Artifact model & specs
│   ├── subscription.py          # Subscription system
│   ├── visibility.py            # Visibility/security controls
│   ├── components.py            # Component base classes
│   ├── runtime.py               # EvalInputs, EvalResult, Context
│   ├── registry.py              # Type & function registries
│   ├── store.py                 # Blackboard storage abstractions
│   ├── dashboard/               # 🆕 Real-time dashboard backend
│   │   ├── collector.py         # Event collection for streaming
│   │   ├── websocket.py         # WebSocket manager
│   │   ├── service.py           # Dashboard HTTP service
│   │   └── launcher.py          # One-line dashboard activation
│   ├── mcp/                     # MCP (Model Context Protocol) support
│   │   ├── client.py            # MCP client implementation
│   │   ├── manager.py           # MCP server management
│   │   └── servers/             # MCP server implementations
│   └── engines/                 # Engine implementations
│       └── dspy_engine.py       # DSPy LLM engine with streaming
├── frontend/                    # 🆕 React/TypeScript dashboard
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── hooks/               # Custom React hooks
│   │   ├── store/               # Zustand state management
│   │   ├── services/            # WebSocket, API clients
│   │   └── types/               # TypeScript type definitions
│   ├── package.json             # Node.js dependencies
│   └── vite.config.ts           # Vite build configuration
├── examples/                    # Working examples
│   ├── showcase/                # Engaging demos for workshops
│   └── features/                # Feature validation with assertions
├── tests/                       # Comprehensive test suite
│   ├── contract/                # Contract tests (system behavior)
│   ├── integration/             # Component interaction tests
│   ├── e2e/                     # End-to-end tests
│   └── conftest.py              # Shared test fixtures
├── docs/patterns/               # 🆕 Analysis documentation
│   ├── development-workflow.md  # Development patterns
│   ├── project-configuration.md # Technical configuration
│   ├── core-architecture.md     # Architecture deep dive
│   └── repository-structure.md  # Code organization
├── docs/ai-agents/              # AI agent documentation
│   ├── architecture.md          # This file
│   ├── development.md           # Development workflow
│   ├── frontend.md              # Frontend guide
│   ├── dependencies.md          # Package management
│   └── common-tasks.md          # Common tasks
├── pyproject.toml               # UV project configuration
├── uv.lock                      # Locked dependencies
├── README.md                    # User-facing documentation
└── AGENTS.md                    # AI agent quick start
```

## 🔬 Core Architecture

### 1. Flock Orchestrator (`src/flock/orchestrator.py`)

**Purpose:** Central coordinator—manages blackboard, schedules agents

**Key Methods:**
- `agent(name)` → Create new agent builder
- `run(agent, *inputs)` → Synchronous execution
- `arun(agent, *inputs)` → Async execution
- `run_until_idle()` → Wait for all tasks to complete
- `serve(dashboard=True)` → Start HTTP service + dashboard
- `publish_external(type_name, payload)` → External artifact publishing

**Safety Features:**
- **Circuit Breaker**: `max_agent_iterations=1000` stops runaway agents
- **Duplicate Prevention**: Tracks processed (artifact_id, agent_name) pairs
- **Self-Trigger Protection**: `prevent_self_trigger=True` by default

### 2. Agent System (`src/flock/agent.py`)

**Builder Pattern:**
```python
agent = (
    orchestrator.agent("name")
    .description("What this agent does")
    .consumes(InputType, where=lambda x: x.valid)
    .publishes(OutputType, visibility=PrivateVisibility(["agent_a"]))
    .with_utilities(MetricsComponent(), LoggingComponent())
    .with_engines(DSPyEngine(model="gpt-4o"))
    .best_of(5, score=lambda r: r.metrics["confidence"])
    .max_concurrency(10)
    .prevent_self_trigger(False)  # Explicit opt-in for feedback loops
)
```

**Lifecycle Stages (9 total):**
1. `on_initialize` - Setup
2. `on_pre_consume` - Transform input artifacts
3. `on_pre_evaluate` - Prepare evaluation
4. **Engines run** - Core processing
5. `on_post_evaluate` - Transform results
6. **Publish** - Create artifacts
7. `on_post_publish` - React to publications
8. `on_error` - Handle failures
9. `on_terminate` - Cleanup

### 3. Dashboard System (`src/flock/dashboard/`)

**One-Line Activation:**
```python
# Start dashboard with real-time monitoring
await orchestrator.serve(dashboard=True)
```

**Components:**
- **DashboardEventCollector** - Captures agent lifecycle events
- **WebSocketManager** - Real-time event broadcasting to frontend
- **DashboardHTTPService** - HTTP API for dashboard controls
- **DashboardLauncher** - Handles npm install, process management, browser launch

**Frontend Features:**
- **Dual Visualization Modes**: Agent View vs Blackboard View
- **Real-time Updates**: WebSocket streaming with 2-minute heartbeat
- **Control Panel**: Publish artifacts and invoke agents from UI
- **EventLog Module**: Comprehensive event viewing with filtering
- **Persistence**: Node positions, preferences, session data in IndexedDB

### 4. MCP Integration (`src/flock/mcp/`)

**Purpose:** Model Context Protocol support for external tool integration

**Key Classes:**
- **MCPClientManager** - Manages MCP server connections
- **FlockMCPConfiguration** - Server configuration and tool assignments
- **MCPClientWrapper** - Client interface with lazy connection establishment

**Usage:**
```python
# Register MCP server with tools
orchestrator.register_mcp_server("server_name", config)

# Assign tools to agents
agent.uses_mcp("server_name")
```

### 5. Visibility System (`src/flock/visibility.py`)

**Access Control Types:**
- `PublicVisibility` - Everyone can see
- `PrivateVisibility` - Allowlist of agents
- `LabelledVisibility` - RBAC (agents need required labels)
- `TenantVisibility` - Multi-tenancy (per-tenant isolation)
- `AfterVisibility` - Time-delayed (embargo periods)

**Enforcement:**
```python
if not artifact.visibility.allows(agent.identity):
    continue  # Don't schedule agent
```

## 🎨 Code Style & Conventions

### Python Style

```python
# ✅ Good: Type hints everywhere
async def execute(self, ctx: Context, artifacts: List[Artifact]) -> List[Artifact]:
    ...

# ✅ Good: Descriptive names and docstrings
def _schedule_artifact(self, artifact: Artifact) -> None:
    """Schedule artifact for agent processing."""
    ...

# ✅ Good: Pydantic models with Field descriptions
@flock_type
class Movie(BaseModel):
    title: str = Field(description="Movie title in CAPS")
    runtime: int = Field(ge=60, le=400, description="Runtime in minutes")
```

### TypeScript/React Style

```typescript
// ✅ Good: Type-safe components with proper props
interface DashboardLayoutProps {
  children: React.ReactNode;
}

const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  // Component implementation
};

// ✅ Good: Custom hooks with proper typing
const useWebSocket = (url: string) => {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  // Hook implementation
};
```

### Async Patterns

```python
# ✅ Always use async for I/O operations
async def publish(self, artifact: Artifact) -> None:
    async with self._lock:
        await self.store.publish(artifact)

# ✅ Use asyncio.gather for parallel operations
results = await asyncio.gather(
    agent_a.execute(ctx, artifacts),
    agent_b.execute(ctx, artifacts),
)
```

---

*For more details, see [docs/patterns/core-architecture.md](../patterns/core-architecture.md)*
