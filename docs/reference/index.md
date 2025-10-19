# Reference Documentation

Complete technical reference for Flock API and configuration.

---

## 📖 API Reference

<div class="grid cards" markdown>

-   **🔧 Core API**

    ---

    Complete API documentation for Flock classes, agents, and components.

    [:octicons-arrow-right-24: API Reference](api.md)

-   **⚙️ Configuration**

    ---

    All configuration options, environment variables, and settings.

    [:octicons-arrow-right-24: Configuration Reference](configuration.md)

</div>

---

## Core Classes

### Orchestrator
- **`Flock`** - Main orchestrator for agent coordination
- **`Orchestrator`** - Base orchestration engine (legacy)

### Agents
- **`Agent`** - Autonomous worker that transforms artifacts
- **`AgentConfig`** - Agent configuration and metadata
- **`AgentState`** - Runtime agent state

### Blackboard
- **`Blackboard`** - Shared artifact workspace
- **`Artifact`** - Typed data published to blackboard
- **`ArtifactType`** - Type metadata for artifacts

### Components
- **`Component`** - Pluggable utilities for agents
- **`Engine`** - Evaluation engine (DSPy, custom)
- **`LifecycleHook`** - Hook interface for lifecycle events

### Tracing
- **`Tracer`** - OpenTelemetry tracer wrapper
- **`TraceContext`** - Trace context management
- **`traced_run()`** - Unified trace wrapper

---

## Configuration Reference

### Environment Variables

#### Model Configuration
```bash
# Default LLM model (LiteLLM format)
DEFAULT_MODEL="openai/gpt-4.1"

# API keys for providers
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="..."
COHERE_API_KEY="..."
```

#### Tracing Configuration
```bash
# Enable auto-tracing
FLOCK_AUTO_TRACE=true
FLOCK_TRACE_FILE=true

# Trace filtering
FLOCK_TRACE_SERVICES=["flock", "agent"]
FLOCK_TRACE_IGNORE=["DashboardEventCollector"]

# Trace retention
FLOCK_TRACE_TTL_DAYS=30
```

#### Dashboard Configuration
```bash
# Dashboard port
FLOCK_DASHBOARD_PORT=8344

# Dashboard host
FLOCK_DASHBOARD_HOST="0.0.0.0"
```

### Configuration Files

#### `.flock/config.yaml`
```yaml
# Default model
model: "openai/gpt-4.1"

# Tracing settings
tracing:
  enabled: true
  file_output: true
  services:
    - flock
    - agent
    - dspyengine
  ttl_days: 30

# Dashboard settings
dashboard:
  port: 8344
  host: "0.0.0.0"
  enable_websocket: true
```

---

## Type Annotations

Flock uses Python type hints extensively for clear APIs:

```python
from typing import Type, List, Optional
from pydantic import BaseModel
from flock import Flock, Agent, Artifact

# Type-safe agent creation
def create_agent(
    flock: Flock,
    name: str,
    consumes: Type[BaseModel],
    publishes: Type[BaseModel]
) -> Agent:
    return (
        flock.agent(name)
        .consumes(consumes)
        .publishes(publishes)
    )
```

---

## Pydantic Models

All artifacts must be Pydantic models decorated with `@flock_type`:

```python
from pydantic import BaseModel, Field
from flock import flock_type

@flock_type
class UserRequest(BaseModel):
    """User input artifact"""
    message: str = Field(..., description="User message")
    user_id: str = Field(..., description="Unique user ID")
    timestamp: float = Field(default_factory=time.time)

@flock_type
class BotResponse(BaseModel):
    """Bot response artifact"""
    response: str = Field(..., description="Bot reply")
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: List[str] = Field(default_factory=list)
```

---

## Visibility Enums

```python
from flock.core.visibility import (
    Visibility,      # Base visibility enum
    PublicVisibility,
    PrivateVisibility,
    TenantVisibility,
    LabelVisibility,
    TimeBasedVisibility
)

# Usage
artifact = UserRequest(message="Hello")
await flock.publish(
    artifact,
    visibility=TenantVisibility(tenant_id="tenant_1")
)
```

---

## Agent Lifecycle Hooks

```python
from flock import Agent, Component

class MyComponent(Component):
    async def on_initialize(self, agent: Agent) -> None:
        """Called when agent starts"""
        pass

    async def on_pre_consume(self, agent: Agent, artifacts: List[Artifact]) -> None:
        """Called before agent evaluates"""
        pass

    async def on_post_publish(self, agent: Agent, output: Artifact) -> None:
        """Called after agent publishes"""
        pass

    async def on_terminate(self, agent: Agent) -> None:
        """Called when agent stops"""
        pass
```

---

## Tracing Schema

### DuckDB Tables

#### `spans` table
```sql
CREATE TABLE spans (
    trace_id VARCHAR,
    span_id VARCHAR,
    parent_id VARCHAR,
    name VARCHAR,
    service VARCHAR,
    start_time BIGINT,
    end_time BIGINT,
    duration_ms DOUBLE,
    status_code VARCHAR,
    status_description VARCHAR,
    attributes JSON
);
```

#### `events` table
```sql
CREATE TABLE events (
    trace_id VARCHAR,
    span_id VARCHAR,
    name VARCHAR,
    timestamp BIGINT,
    attributes JSON
);
```

See [Trace Module Reference](../guides/tracing/trace-module.md) for complete schema details.

---

## Error Codes

Common error codes and their meanings:

| Code | Description | Solution |
|------|-------------|----------|
| `AGENT_NOT_FOUND` | Agent name doesn't exist | Check agent registration |
| `TYPE_MISMATCH` | Artifact type incompatible | Verify type contracts |
| `VISIBILITY_DENIED` | Access control violation | Check visibility settings |
| `TRACE_DB_ERROR` | DuckDB connection failed | Check `.flock/` permissions |
| `ENGINE_ERROR` | Evaluation engine failed | Check LLM API keys |

---

## CLI Commands

```bash
# Clear trace database
python -c "from flock import Flock; Flock.clear_traces()"

# Validate configuration
python -c "from flock import Flock; flock = Flock(); print('✅ Config valid')"

# List registered agents
python -c "from flock import Flock; flock = Flock(); print(flock.agents)"
```

---

## Performance Benchmarks

Typical operation timings:

| Operation | Latency | Throughput |
|-----------|---------|------------|
| `publish()` | < 1ms | 10,000+ ops/sec |
| `query()` | < 5ms | 1,000+ ops/sec |
| LLM evaluation | ~500ms | 2-5 ops/sec |
| Trace write | < 1ms | 5,000+ ops/sec |

Note: LLM evaluation depends on provider and model.

---

## Migration Guides

### From 0.4.x to 0.5.x

**Breaking changes:**
- `arun()` → `invoke()` (method renamed)
- `Orchestrator` → `Flock` (class renamed, Orchestrator still works)
- Visibility API updated (now uses dedicated classes)

**New features:**
- Unified tracing with `traced_run()`
- Auto-tracing configuration
- Dashboard trace module

See [Changelog](https://github.com/whiteducksoftware/flock/releases) for complete details.

---

## Related Documentation

- **[Getting Started](../getting-started/index.md)** - Installation and quick start
- **[User Guides](../guides/index.md)** - Comprehensive guides
- **[Examples](https://github.com/whiteducksoftware/flock/tree/main/examples)** - Working code examples

---

## External Resources

- **[LiteLLM Docs](https://docs.litellm.ai/)** - Model providers
- **[Pydantic Docs](https://docs.pydantic.dev/)** - Data validation
- **[OpenTelemetry](https://opentelemetry.io/)** - Distributed tracing
- **[DuckDB](https://duckdb.org/)** - Analytics database

---

**Need help?** → [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions){ .md-button }
