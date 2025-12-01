---
title: Top-Level Imports
description: Convenient imports from the flock namespace for common development patterns
tags:
  - imports
  - api
  - getting-started
  - convenience
search:
  boost: 1.5
---

# Top-Level Imports

**Everything you need, one import away.**

Flock exposes the most commonly used classes and utilities at the top level for convenient imports. No more hunting through submodules!

---

## Quick Reference

```python
from flock import (
    # Core
    Flock, flock_type, flock_tool, start_orchestrator,
    
    # Engines & Adapters
    DSPyEngine, BAMLAdapter, JSONAdapter, XMLAdapter, ChatAdapter, TwoStepAdapter,
    
    # Components (for extending)
    AgentComponent, EngineComponent, OrchestratorComponent,
    AgentComponentConfig, OrchestratorComponentConfig,
    
    # Runtime (for custom engines/components)
    Context, EvalInputs, EvalResult,
    
    # Artifacts
    Artifact,
    
    # Visibility (access control)
    Visibility, PublicVisibility, PrivateVisibility, 
    LabelledVisibility, TenantVisibility, AfterVisibility, AgentIdentity,
    
    # Workflow control
    Until,
    
    # Advanced subscriptions
    BatchSpec, JoinSpec, ScheduleSpec,
    
    # Filtering
    FilterConfig,
)
```

---

## Categories

### Core Orchestration

| Import | Description |
|--------|-------------|
| `Flock` | Main orchestrator class |
| `flock_type` | Decorator to register Pydantic models as artifact types |
| `flock_tool` | Decorator to register functions as agent tools |
| `start_orchestrator` | Utility to start the orchestrator |

```python
from flock import Flock, flock_type

@flock_type
class Task(BaseModel):
    title: str
    priority: int

flock = Flock("openai/gpt-4.1")
```

---

### Engines & Adapters

| Import | Description |
|--------|-------------|
| `DSPyEngine` | Default DSPy-powered engine for LLM interactions |
| `BAMLAdapter` | BAML output format adapter |
| `JSONAdapter` | JSON output format adapter |
| `XMLAdapter` | XML output format adapter |
| `ChatAdapter` | Chat-style output format adapter |
| `TwoStepAdapter` | Two-step reasoning adapter |

```python
from flock import Flock, DSPyEngine, BAMLAdapter

# Use a specific adapter
engine = DSPyEngine(
    model="openai/gpt-4.1",
    adapter=BAMLAdapter()
)

agent = (
    flock.agent("processor")
    .consumes(Input)
    .publishes(Output)
    .with_engines(engine)
)
```

---

### Components

| Import | Description |
|--------|-------------|
| `AgentComponent` | Base class for custom agent components |
| `AgentComponentConfig` | Configuration for agent components |
| `EngineComponent` | Base class for custom engines |
| `OrchestratorComponent` | Base class for orchestrator-level components |
| `OrchestratorComponentConfig` | Configuration for orchestrator components |

```python
from flock import AgentComponent, Context, EvalInputs, EvalResult

class LoggingComponent(AgentComponent):
    async def on_pre_evaluate(
        self, agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        print(f"Agent {agent.name} processing {len(inputs.artifacts)} artifacts")
        return inputs
```

---

### Runtime Types

| Import | Description |
|--------|-------------|
| `Context` | Execution context passed to components/engines |
| `EvalInputs` | Input wrapper containing artifacts and state |
| `EvalResult` | Result wrapper from engine evaluation |

```python
from flock import EngineComponent, Context, EvalInputs, EvalResult

class CustomEngine(EngineComponent):
    async def evaluate(
        self, agent, ctx: Context, inputs: EvalInputs, output_group
    ) -> EvalResult:
        # Access input artifacts
        for artifact in inputs.artifacts:
            print(f"Processing: {artifact.type}")
        
        # Return results
        return EvalResult(artifacts=[...])
```

---

### Artifacts

| Import | Description |
|--------|-------------|
| `Artifact` | Core artifact class for blackboard data |

```python
from flock import Artifact

# Type hints for artifact handling
def process_artifact(artifact: Artifact) -> dict:
    return {
        "type": artifact.type,
        "producer": artifact.produced_by,
        "payload": artifact.payload
    }
```

---

### Visibility Controls

| Import | Description |
|--------|-------------|
| `Visibility` | Base visibility class |
| `PublicVisibility` | Artifacts visible to all agents |
| `PrivateVisibility` | Artifacts visible only to specific agents |
| `LabelledVisibility` | Visibility based on agent labels |
| `TenantVisibility` | Multi-tenant visibility |
| `AfterVisibility` | Time-delayed visibility |
| `AgentIdentity` | Agent identity for visibility checks |

```python
from flock import PrivateVisibility, TenantVisibility

# Private to specific agents
agent.publishes(
    SensitiveData, 
    visibility=PrivateVisibility(agents={"admin", "auditor"})
)

# Multi-tenant isolation
agent.publishes(
    CustomerData, 
    visibility=TenantVisibility(tenant_id="customer_123")
)
```

---

### Workflow Control

| Import | Description |
|--------|-------------|
| `Until` | DSL for workflow termination conditions |

```python
from flock import Until

# Stop when you have enough results
await flock.run_until(
    Until.artifact_count(Result).at_least(5),
    timeout=60
)

# Composite conditions
stop_condition = (
    Until.artifact_count(Analysis).at_least(3) |
    Until.workflow_error(correlation_id)
)
await flock.run_until(stop_condition, timeout=120)
```

---

### Subscription Patterns

| Import | Description |
|--------|-------------|
| `BatchSpec` | Configure batch processing of artifacts |
| `JoinSpec` | Correlate related artifacts |
| `ScheduleSpec` | Timer-based scheduling |

```python
from flock import BatchSpec, JoinSpec

# Batch processing
agent.consumes(Task, batch=BatchSpec(size=10, timeout=5.0))

# Join related artifacts
agent.consumes(
    Order,
    join=JoinSpec(
        with_types=[Customer, Inventory],
        on="order_id"
    )
)
```

---

### Filtering

| Import | Description |
|--------|-------------|
| `FilterConfig` | Configuration for context/store filtering |

```python
from flock import FilterConfig
from flock.core.context_provider import FilteredContextProvider

# Filter context by tags
provider = FilteredContextProvider(
    FilterConfig(tags={"urgent", "critical"}),
    limit=50
)
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

---

## Migration from Deep Imports

If you're using deep imports, here's how to migrate:

```python
# Before (deep imports)
from flock.engines import DSPyEngine
from flock.components.agent import AgentComponent, EngineComponent
from flock.core.visibility import PrivateVisibility
from flock.utils.runtime import Context, EvalInputs, EvalResult

# After (top-level imports)
from flock import (
    DSPyEngine,
    AgentComponent, EngineComponent,
    PrivateVisibility,
    Context, EvalInputs, EvalResult,
)
```

Both styles work—use whichever you prefer. The deep imports are still available for cases where you need to import less common utilities.

---

## Complete Import List

```python
__all__ = [
    # Core
    "Flock",
    "flock_tool",
    "flock_type",
    "main",
    "start_orchestrator",
    # Engines
    "BAMLAdapter",
    "ChatAdapter",
    "DSPyEngine",
    "JSONAdapter",
    "TwoStepAdapter",
    "XMLAdapter",
    # Components
    "AgentComponent",
    "AgentComponentConfig",
    "EngineComponent",
    "OrchestratorComponent",
    "OrchestratorComponentConfig",
    # Runtime
    "Context",
    "EvalInputs",
    "EvalResult",
    # Artifacts
    "Artifact",
    # Visibility
    "AfterVisibility",
    "AgentIdentity",
    "LabelledVisibility",
    "PrivateVisibility",
    "PublicVisibility",
    "TenantVisibility",
    "Visibility",
    # Conditions
    "Until",
    # Subscriptions
    "BatchSpec",
    "JoinSpec",
    "ScheduleSpec",
    # Store
    "FilterConfig",
]
```
