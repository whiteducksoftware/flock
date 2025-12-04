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
    AgentComponent, EngineComponent, OrchestratorComponent, ServerComponent,
    AgentComponentConfig, OrchestratorComponentConfig, ServerComponentConfig,
    
    # Runtime (for custom engines/components)
    Context, EvalInputs, EvalResult,
    
    # Artifacts
    Artifact,
    
    # Visibility (access control)
    Visibility, PublicVisibility, PrivateVisibility, 
    LabelledVisibility, TenantVisibility, AfterVisibility, AgentIdentity,
    
    # Workflow control
    Until, When,
    
    # Advanced subscriptions
    BatchSpec, JoinSpec, ScheduleSpec,
    
    # Filtering
    FilterConfig,
    
    # Logging
    get_logger, configure_logging,
)
```

---

## Categories

### Core Orchestration

| Import | Description | Learn More |
|--------|-------------|------------|
| `Flock` | Main orchestrator class | [Quick Start](../getting-started/quick-start.md) |
| `flock_type` | Decorator to register Pydantic models as artifact types | [Core Concepts](../getting-started/concepts.md) |
| `flock_tool` | Decorator to register functions as agent tools | [Agents Guide](agents.md#tools) |
| `start_orchestrator` | Utility to start the orchestrator | [Quick Start](../getting-started/quick-start.md) |

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

| Import | Description | Learn More |
|--------|-------------|------------|
| `DSPyEngine` | Default DSPy-powered engine for LLM interactions | [DSPy Engine Deep Dive](dspy-engine.md) |
| `BAMLAdapter` | BAML output format adapter | [DSPy Engine - Adapters](dspy-engine.md#adapters) |
| `JSONAdapter` | JSON output format adapter | [DSPy Engine - Adapters](dspy-engine.md#adapters) |
| `XMLAdapter` | XML output format adapter | [DSPy Engine - Adapters](dspy-engine.md#adapters) |
| `ChatAdapter` | Chat-style output format adapter | [DSPy Engine - Adapters](dspy-engine.md#adapters) |
| `TwoStepAdapter` | Two-step reasoning adapter | [DSPy Engine - Adapters](dspy-engine.md#adapters) |

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

[:octicons-arrow-right-24: DSPy Engine Deep Dive](dspy-engine.md){ .md-button }
[:octicons-arrow-right-24: Local Models (Transformers)](local-models.md){ .md-button }

---

### Components

| Import | Description | Learn More |
|--------|-------------|------------|
| `AgentComponent` | Base class for custom agent components | [Agent Components Guide](components.md) |
| `AgentComponentConfig` | Configuration for agent components | [Agent Components Guide](components.md#configuration) |
| `EngineComponent` | Base class for custom engines | [Custom Engines Tutorial](../tutorials/custom-engines.md) |
| `OrchestratorComponent` | Base class for orchestrator-level components | [Orchestrator Components Guide](orchestrator-components.md) |
| `OrchestratorComponentConfig` | Configuration for orchestrator components | [Orchestrator Components Guide](orchestrator-components.md) |
| `ServerComponent` | Base class for custom HTTP server components | [Server Components Guide](server-components.md) |
| `ServerComponentConfig` | Configuration for server components | [Server Components Guide](server-components.md) |

```python
from flock import AgentComponent, Context, EvalInputs, EvalResult

class LoggingComponent(AgentComponent):
    async def on_pre_evaluate(
        self, agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        print(f"Agent {agent.name} processing {len(inputs.artifacts)} artifacts")
        return inputs
```

[:octicons-arrow-right-24: Agent Components](components.md){ .md-button }
[:octicons-arrow-right-24: Orchestrator Components](orchestrator-components.md){ .md-button }
[:octicons-arrow-right-24: Server Components](server-components.md){ .md-button }

---

### Runtime Types

| Import | Description | Learn More |
|--------|-------------|------------|
| `Context` | Execution context passed to components/engines | [Custom Engines Tutorial](../tutorials/custom-engines.md) |
| `EvalInputs` | Input wrapper containing artifacts and state | [Custom Engines Tutorial](../tutorials/custom-engines.md) |
| `EvalResult` | Result wrapper from engine evaluation | [Custom Engines Tutorial](../tutorials/custom-engines.md) |

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

[:octicons-arrow-right-24: Custom Engines Tutorial](../tutorials/custom-engines.md){ .md-button }

---

### Artifacts

| Import | Description | Learn More |
|--------|-------------|------------|
| `Artifact` | Core artifact class for blackboard data | [Blackboard Guide](blackboard.md) |

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

[:octicons-arrow-right-24: Blackboard Guide](blackboard.md){ .md-button }

---

### Visibility Controls

| Import | Description | Learn More |
|--------|-------------|------------|
| `Visibility` | Base visibility class | [Visibility Guide](visibility.md) |
| `PublicVisibility` | Artifacts visible to all agents | [Visibility - Public](visibility.md#1-publicvisibility-default) |
| `PrivateVisibility` | Artifacts visible only to specific agents | [Visibility - Private](visibility.md#2-privatevisibility-agent-specific) |
| `LabelledVisibility` | Visibility based on agent labels | [Visibility - Labelled](visibility.md#4-labelledvisibility-rbac) |
| `TenantVisibility` | Multi-tenant visibility | [Visibility - Tenant](visibility.md#3-tenantvisibility-multi-tenancy) |
| `AfterVisibility` | Time-delayed visibility | [Visibility - After](visibility.md#5-aftervisibility-time-delayed) |
| `AgentIdentity` | Agent identity for visibility checks | [Visibility Guide](visibility.md) |

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

[:octicons-arrow-right-24: Visibility Controls Guide](visibility.md){ .md-button }

---

### Workflow Control

| Import | Description | Learn More |
|--------|-------------|------------|
| `Until` | DSL for workflow termination conditions | [Workflow Control Guide](workflow-control.md) |
| `When` | DSL for subscription activation conditions | [Workflow Control Guide](workflow-control.md#when-conditions) |

```python
from flock import Until, When

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

# Conditional subscription activation
agent.consumes(
    Approval,
    when=When.correlation(Vote).count_at_least(3)
)
```

[:octicons-arrow-right-24: Workflow Control Guide](workflow-control.md){ .md-button }

---

### Subscription Patterns

| Import | Description | Learn More |
|--------|-------------|------------|
| `BatchSpec` | Configure batch processing of artifacts | [Batch Processing Guide](batch-processing.md) |
| `JoinSpec` | Correlate related artifacts | [Join Operations Guide](join-operations.md) |
| `ScheduleSpec` | Timer-based scheduling | [Timer Scheduling Guide](scheduling.md) |

```python
from flock import BatchSpec, JoinSpec, ScheduleSpec
from datetime import timedelta

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

# Timer-based execution
agent.schedule(every=timedelta(minutes=5))
```

[:octicons-arrow-right-24: Batch Processing](batch-processing.md){ .md-button }
[:octicons-arrow-right-24: Join Operations](join-operations.md){ .md-button }
[:octicons-arrow-right-24: Timer Scheduling](scheduling.md){ .md-button }

---

### Filtering

| Import | Description | Learn More |
|--------|-------------|------------|
| `FilterConfig` | Configuration for context/store filtering | [Context Providers Guide](context-providers.md) |

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

[:octicons-arrow-right-24: Context Providers Guide](context-providers.md){ .md-button }

---

### Logging

| Import | Description | Learn More |
|--------|-------------|------------|
| `get_logger` | Get a Flock logger instance for your module | [Distributed Tracing](tracing/index.md) |
| `configure_logging` | Configure logging level and formatting | [Configuration](../reference/configuration.md) |

```python
from flock import get_logger, configure_logging
import logging

# Configure logging level
configure_logging(level=logging.DEBUG)

# Get a logger for your module
logger = get_logger(__name__)

logger.info("Starting workflow")
logger.debug("Processing artifact", extra={"artifact_id": "123"})
logger.warning("Retrying operation")
```

[:octicons-arrow-right-24: Distributed Tracing](tracing/index.md){ .md-button }

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
    "ServerComponent",
    "ServerComponentConfig",
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
    "When",
    # Subscriptions
    "BatchSpec",
    "JoinSpec",
    "ScheduleSpec",
    # Store
    "FilterConfig",
    # Logging
    "configure_logging",
    "get_logger",
]
```
