# Orchestrator Components

Orchestrator Components are a powerful extensibility pattern that lets you inject custom logic into the orchestrator's scheduling pipeline without modifying core orchestrator code.

---

## What Are Orchestrator Components?

Orchestrator Components are **pluggable modules** that hook into specific points in the orchestrator's scheduling lifecycle. Think of them as middleware for the orchestrator that can:

- **Filter scheduling** based on custom rules (maintenance windows, rate limits)
- **Modify artifacts** before scheduling (enrichment, transformation)
- **Collect artifacts** for batch processing, correlation, or AND gates
- **Track metrics** about scheduling and execution
- **Integrate external systems** (dashboards, monitoring, event streams)

```python
from flock.orchestrator_component import OrchestratorComponent, ScheduleDecision

# Example: Skip scheduling during maintenance windows
class MaintenanceWindowComponent(OrchestratorComponent):
    maintenance_start: int = 22  # 10 PM
    maintenance_end: int = 6     # 6 AM
    
    async def on_before_schedule(self, orch, artifact, agent, subscription):
        current_hour = datetime.now().hour
        if self.maintenance_start <= current_hour or current_hour < self.maintenance_end:
            logger.info(f"Deferring {agent.name} during maintenance window")
            return ScheduleDecision.DEFER
        return ScheduleDecision.CONTINUE

# Add to orchestrator
flock = Flock("openai/gpt-4.1")
flock.add_component(MaintenanceWindowComponent())
```

---

## Component Lifecycle Hooks

Orchestrator Components implement **8 lifecycle hooks** that fire at specific points during orchestrator operation:

### 1. on_initialize

**When**: Once, when the orchestrator first starts scheduling artifacts

**Purpose**: Setup phase for component initialization, resource allocation, loading state

**Signature**: `async def on_initialize(self, orchestrator: Flock) -> None`

**Example**:
```python
async def on_initialize(self, orch):
    logger.info(f"Initializing {self.name}")
    # Load previous state, allocate resources, etc.
    self._metrics = {}
```

---

### 2. on_artifact_published

**When**: Right after an artifact is published to the blackboard

**Purpose**: Transform, enrich, or filter artifacts before subscription matching

**Signature**: `async def on_artifact_published(self, orchestrator: Flock, artifact: Artifact) -> Artifact | None`

**Return**: Modified artifact (or None to block scheduling)

**Example**:
```python
async def on_artifact_published(self, orch, artifact):
    # Enrich artifact with metadata
    artifact.metadata["processed_at"] = datetime.utcnow()
    artifact.metadata["component"] = self.name
    return artifact  # Modified artifact continues to scheduling

# Or block scheduling entirely
async def on_artifact_published(self, orch, artifact):
    if not self.is_valid(artifact):
        logger.warning(f"Blocking invalid artifact: {artifact.id}")
        return None  # None = block scheduling
    return artifact
```

---

### 3. on_before_schedule

**When**: After subscription match, before artifact collection

**Purpose**: Decide whether to proceed with scheduling for a specific agent/subscription pair

**Signature**: `async def on_before_schedule(self, orchestrator: Flock, artifact: Artifact, agent: Agent, subscription: Subscription) -> ScheduleDecision`

**Return**: `ScheduleDecision.CONTINUE` | `SKIP` | `DEFER`

**Example**:
```python
# Circuit breaker example
async def on_before_schedule(self, orch, artifact, agent, subscription):
    count = self._iteration_counts.get(agent.name, 0)
    if count >= self.max_iterations:
        logger.warning(f"Circuit breaker tripped for {agent.name}")
        return ScheduleDecision.SKIP  # Skip this agent
    
    self._iteration_counts[agent.name] = count + 1
    return ScheduleDecision.CONTINUE  # Proceed normally
```

---

### 4. on_collect_artifacts

**When**: After `on_before_schedule` returns CONTINUE

**Purpose**: Collect/group artifacts for scheduling (AND gates, batching, correlation)

**Signature**: `async def on_collect_artifacts(self, orchestrator: Flock, artifact: Artifact, agent: Agent, subscription: Subscription) -> CollectionResult | None`

**Return**: `CollectionResult(artifacts=[...], complete=True/False)` or None (use default)

**Example**:
```python
# AND gate example: wait for 3 Orders
async def on_collect_artifacts(self, orch, artifact, agent, subscription):
    # Store artifact
    key = (agent.name, subscription)
    self._collected[key].append(artifact)
    
    # Check if we have enough
    if len(self._collected[key]) >= 3:
        artifacts = self._collected[key][:3]
        del self._collected[key]
        return CollectionResult(artifacts=artifacts, complete=True)
    else:
        # Still waiting for more
        return CollectionResult.waiting()
```

---

### 5. on_before_agent_schedule

**When**: After artifact collection completes, before agent task creation

**Purpose**: Transform collected artifacts, validate inputs, prepare execution context

**Signature**: `async def on_before_agent_schedule(self, orchestrator: Flock, agent: Agent, artifacts: list[Artifact]) -> list[Artifact] | None`

**Return**: Modified artifact list (or None to cancel scheduling)

**Example**:
```python
async def on_before_agent_schedule(self, orch, agent, artifacts):
    # Sort artifacts by priority before passing to agent
    sorted_artifacts = sorted(artifacts, key=lambda a: a.metadata.get("priority", 0), reverse=True)
    return sorted_artifacts

# Or cancel scheduling
async def on_before_agent_schedule(self, orch, agent, artifacts):
    if not self.validate_batch(artifacts):
        logger.error(f"Invalid artifact batch for {agent.name}")
        return None  # Cancel scheduling
    return artifacts
```

---

### 6. on_agent_scheduled

**When**: Right after agent task is created and scheduled

**Purpose**: Track metrics, notify external systems, log execution

**Signature**: `async def on_agent_scheduled(self, orchestrator: Flock, agent: Agent, artifacts: list[Artifact], task: asyncio.Task) -> None`

**Example**:
```python
async def on_agent_scheduled(self, orch, agent, artifacts, task):
    # Track metrics
    self._metrics["scheduled_count"] += 1
    self._metrics["agents"][agent.name] = self._metrics["agents"].get(agent.name, 0) + 1
    
    # Notify dashboard
    await self.dashboard.notify_agent_scheduled(agent.name, len(artifacts))
```

---

### 7. on_idle

**When**: When `run_until_idle()` completes (no more work to do)

**Purpose**: Cleanup temporary state, reset counters, flush metrics

**Signature**: `async def on_idle(self, orchestrator: Flock) -> None`

**Example**:
```python
async def on_idle(self, orch):
    logger.info(f"Orchestrator idle, resetting circuit breaker counts")
    self._iteration_counts.clear()
    
    # Flush metrics to external system
    await self.metrics_client.flush(self._metrics)
```

---

### 8. on_shutdown

**When**: When orchestrator is shutting down

**Purpose**: Final cleanup, close connections, save state

**Signature**: `async def on_shutdown(self, orchestrator: Flock) -> None`

**Example**:
```python
async def on_shutdown(self, orch):
    logger.info(f"Shutting down {self.name}")
    
    # Close external connections
    await self.dashboard_client.close()
    
    # Save state to disk
    await self.save_state()
```

---

## Hook Execution Model

### Priority-Based Ordering

Components execute in **priority order** (lower number = earlier execution):

```python
# High priority component runs first
flock.add_component(CircuitBreakerComponent(priority=10))

# Medium priority
flock.add_component(MetricsComponent(priority=50))

# Low priority runs last
flock.add_component(DashboardComponent(priority=100))
```

### Hook Chaining

**Data transformation hooks** (return modified data):
- `on_artifact_published`: First component's output becomes next component's input
- `on_before_agent_schedule`: Artifacts flow through all components in sequence

**Notification hooks** (return None):
- `on_initialize`, `on_agent_scheduled`, `on_idle`, `on_shutdown`: All components execute independently

**Decision hooks** (can short-circuit):
- `on_before_schedule`: First SKIP/DEFER stops the chain
- `on_collect_artifacts`: First complete=True result is used

---

## Built-In Components

Flock includes two built-in components that are **automatically added** to every orchestrator:

### CircuitBreakerComponent

Prevents runaway agent execution by limiting iterations per agent:

```python
# Auto-added to all orchestrators
flock = Flock("openai/gpt-4.1")  # Has CircuitBreakerComponent(max_iterations=1000)

# Override default limit
flock = Flock("openai/gpt-4.1")
flock.add_component(CircuitBreakerComponent(max_iterations=500, priority=5))
```

**Behavior**: After `max_iterations` executions, returns `ScheduleDecision.SKIP` for that agent.

### DeduplicationComponent

Prevents duplicate processing of the same artifact by the same agent:

```python
# Auto-added to all orchestrators
flock = Flock("openai/gpt-4.1")  # Has DeduplicationComponent()

# Duplicate publications are automatically skipped
await flock.publish(my_artifact)
await flock.run_until_idle()  # Agent runs

await flock.publish(my_artifact)  # Same artifact
await flock.run_until_idle()  # Agent does NOT run (deduplicated)
```

**Behavior**: Tracks `(artifact.id, agent.name)` pairs and returns `ScheduleDecision.SKIP` for duplicates.

---

## Creating Custom Components

### Basic Component Template

```python
from flock.orchestrator_component import (
    OrchestratorComponent,
    ScheduleDecision,
    CollectionResult,
)

class MyCustomComponent(OrchestratorComponent):
    """Custom component description.
    
    Attributes:
        my_config: Configuration parameter description
    """
    
    # Configuration (Pydantic fields)
    my_config: str = "default_value"
    priority: int = 50  # Execution order
    
    # Implement lifecycle hooks as needed
    async def on_initialize(self, orch):
        logger.info(f"Initializing {self.name}")
        self._state = {}
    
    async def on_before_schedule(self, orch, artifact, agent, subscription):
        # Your logic here
        if some_condition:
            return ScheduleDecision.SKIP
        return ScheduleDecision.CONTINUE
    
    async def on_idle(self, orch):
        # Cleanup
        self._state.clear()

# Use it
flock.add_component(MyCustomComponent(my_config="custom_value"))
```

### Real-World Examples

#### Rate Limiter Component

```python
from datetime import datetime, timedelta
from collections import defaultdict

class RateLimiterComponent(OrchestratorComponent):
    """Limit agent executions per time window."""
    
    max_calls: int = 100
    window_seconds: int = 60
    priority: int = 15
    
    async def on_initialize(self, orch):
        self._call_times = defaultdict(list)
    
    async def on_before_schedule(self, orch, artifact, agent, subscription):
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old timestamps
        recent_calls = [
            t for t in self._call_times[agent.name]
            if t > window_start
        ]
        self._call_times[agent.name] = recent_calls
        
        # Check limit
        if len(recent_calls) >= self.max_calls:
            logger.warning(f"Rate limit exceeded for {agent.name}")
            return ScheduleDecision.DEFER
        
        # Record this call
        self._call_times[agent.name].append(now)
        return ScheduleDecision.CONTINUE
```

#### Priority Queue Component

```python
class PriorityQueueComponent(OrchestratorComponent):
    """Schedule high-priority artifacts first."""
    
    priority: int = 20
    
    async def on_before_agent_schedule(self, orch, agent, artifacts):
        # Sort by priority (metadata field)
        sorted_artifacts = sorted(
            artifacts,
            key=lambda a: a.metadata.get("priority", 0),
            reverse=True
        )
        logger.info(f"Reordered {len(artifacts)} artifacts by priority")
        return sorted_artifacts
```

#### Metrics Collection Component

```python
class MetricsComponent(OrchestratorComponent):
    """Collect orchestrator metrics."""
    
    priority: int = 100  # Run last to capture everything
    
    async def on_initialize(self, orch):
        self._metrics = {
            "artifacts_published": 0,
            "agents_scheduled": 0,
            "agents_skipped": 0,
        }
    
    async def on_artifact_published(self, orch, artifact):
        self._metrics["artifacts_published"] += 1
        return artifact  # Pass through
    
    async def on_before_schedule(self, orch, artifact, agent, subscription):
        # Just track, don't modify
        return ScheduleDecision.CONTINUE
    
    async def on_agent_scheduled(self, orch, agent, artifacts, task):
        self._metrics["agents_scheduled"] += 1
    
    async def on_idle(self, orch):
        logger.info(f"Metrics: {self._metrics}")
        # Send to monitoring system
        await self.send_metrics(self._metrics)
```

---

## Best Practices

### 1. Keep Components Focused

Each component should handle **one concern**:

```python
# ✅ GOOD: Single responsibility
class CircuitBreakerComponent(OrchestratorComponent):
    """Only handles iteration limits."""

# ❌ BAD: Multiple responsibilities
class MegaComponent(OrchestratorComponent):
    """Handles circuit breaking, metrics, rate limiting, and caching."""
```

### 2. Use Priority Wisely

Lower priority = earlier execution:

- **0-10**: Critical filtering (security, authorization)
- **10-50**: Core features (circuit breaker, deduplication, rate limiting)
- **50-90**: Optional features (metrics, enrichment)
- **90-100**: Observability (logging, dashboard notifications)

### 3. Handle Errors Gracefully

Components should not crash the orchestrator:

```python
async def on_before_schedule(self, orch, artifact, agent, subscription):
    try:
        # Your logic
        return ScheduleDecision.CONTINUE
    except Exception as e:
        logger.error(f"Component error: {e}")
        return ScheduleDecision.CONTINUE  # Safe default
```

### 4. Clean Up Resources

Use `on_idle` and `on_shutdown` for cleanup:

```python
async def on_initialize(self, orch):
    self._temp_storage = []

async def on_idle(self, orch):
    # Clear temporary state
    self._temp_storage.clear()

async def on_shutdown(self, orch):
    # Close connections, save state
    await self.cleanup()
```

### 5. Document Hook Behavior

Make it clear what each hook does:

```python
class MyComponent(OrchestratorComponent):
    """One-line description.
    
    Detailed explanation of what this component does,
    when to use it, and any important caveats.
    """
    
    async def on_before_schedule(self, orch, artifact, agent, subscription):
        """Skip scheduling if agent is overloaded.
        
        Returns SKIP if agent has >10 pending tasks,
        otherwise returns CONTINUE.
        """
```

---

## Testing Components

### Unit Testing

Test components in isolation:

```python
@pytest.mark.asyncio
async def test_circuit_breaker_trips():
    component = CircuitBreakerComponent(max_iterations=3)
    await component.on_initialize(mock_orch)
    
    # First 3 calls succeed
    for _ in range(3):
        result = await component.on_before_schedule(
            mock_orch, artifact, agent, subscription
        )
        assert result == ScheduleDecision.CONTINUE
    
    # 4th call trips breaker
    result = await component.on_before_schedule(
        mock_orch, artifact, agent, subscription
    )
    assert result == ScheduleDecision.SKIP
```

### Integration Testing

Test components with orchestrator:

```python
@pytest.mark.asyncio
async def test_component_integration():
    flock = Flock("openai/gpt-4.1")
    flock.add_component(MyCustomComponent())
    
    agent = flock.agent("test").consumes(Input).publishes(Output)
    
    await flock.publish(Input(data="test"))
    await flock.run_until_idle()
    
    # Assert component behavior
    outputs = await flock.store.get_by_type(Output)
    assert len(outputs) == 1
```

---

## Comparison: Agent Components vs Orchestrator Components

| Aspect | Agent Components | Orchestrator Components |
|--------|------------------|------------------------|
| **Scope** | Single agent execution | Entire orchestrator scheduling |
| **Hooks** | 7 hooks (agent lifecycle) | 8 hooks (orchestrator lifecycle) |
| **Granularity** | Per-agent customization | System-wide policies |
| **Examples** | Rate limiting, caching | Circuit breaking, batching |
| **Attach to** | `agent.with_utilities()` | `flock.add_component()` |
| **When to use** | Agent-specific behavior | Cross-agent concerns |

**Rule of thumb**: Use Agent Components for agent-specific logic, Orchestrator Components for system-wide policies.

---

## Common Patterns

### Conditional Scheduling

```python
# Skip based on external condition
async def on_before_schedule(self, orch, artifact, agent, subscription):
    if await self.external_api.is_paused(agent.name):
        return ScheduleDecision.DEFER
    return ScheduleDecision.CONTINUE
```

### Artifact Enrichment

```python
# Add metadata before scheduling
async def on_artifact_published(self, orch, artifact):
    artifact.metadata["enriched_at"] = datetime.utcnow()
    artifact.metadata["source_ip"] = self.get_client_ip()
    return artifact
```

### Batch Collection

```python
# Collect artifacts into batches
async def on_collect_artifacts(self, orch, artifact, agent, subscription):
    key = (agent.name, subscription)
    self._buffer[key].append(artifact)
    
    if len(self._buffer[key]) >= self.batch_size:
        batch = self._buffer[key]
        self._buffer[key] = []
        return CollectionResult(artifacts=batch, complete=True)
    
    return CollectionResult.waiting()
```

---

## Migration from Old Patterns

### Before (Hardcoded Logic)

```python
# Old way: hardcoded in orchestrator
class Flock:
    def __init__(self, max_iterations=1000):
        self.max_iterations = max_iterations
        self._iteration_counts = {}
    
    async def _schedule_artifact(self, artifact):
        # Circuit breaker hardcoded here
        if self._iteration_counts[agent.name] >= self.max_iterations:
            return  # Skip
```

### After (Component Pattern)

```python
# New way: component-based
flock = Flock("openai/gpt-4.1")
flock.add_component(CircuitBreakerComponent(max_iterations=1000))

# Orchestrator core is now clean:
async def _schedule_artifact(self, artifact):
    # Delegate to components
    decision = await self._run_before_schedule(artifact, agent, subscription)
    if decision != ScheduleDecision.CONTINUE:
        return
```

**Benefits**: Cleaner core, extensible, testable, reusable

---

## Troubleshooting

### Component Not Executing

**Check priority ordering**:
```python
# Components execute in priority order
flock.add_component(MyComponent(priority=10))  # Earlier
flock.add_component(OtherComponent(priority=20))  # Later
```

### Component Blocking Scheduling

**Check return values**:
```python
# SKIP/DEFER stops scheduling
async def on_before_schedule(self, ...):
    return ScheduleDecision.SKIP  # Agent won't run!

# None in transformation hooks blocks scheduling
async def on_artifact_published(self, orch, artifact):
    return None  # Artifact won't be scheduled!
```

### Performance Issues

**Profile component execution**:
```python
# Components are auto-traced via TracedModelMeta
# Check .flock/traces.duckdb for timing data
import duckdb
conn = duckdb.connect('.flock/traces.duckdb')
slow_components = conn.execute("""
    SELECT name, AVG(duration_ms) as avg_ms
    FROM spans
    WHERE service LIKE '%Component'
    GROUP BY name
    ORDER BY avg_ms DESC
""").fetchall()
```

---

## Examples

### Beginner Examples

**Quest Tracker** - Game quest monitoring with scoring and leaderboards  
[`examples/07-orchestrator-components/quest_tracker_component.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/07-orchestrator-components/quest_tracker_component.py)

- Demonstrates: `on_pre_publish`, `on_post_publish`, `on_cycle_complete`
- Use case: Real-time game state tracking
- Complexity: ⭐ Beginner

**Kitchen Monitor** - Restaurant kitchen performance monitoring  
[`examples/07-orchestrator-components/kitchen_monitor_component.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/07-orchestrator-components/kitchen_monitor_component.py)

- Demonstrates: Resource tracking, spice alerts, chef rankings
- Use case: Multi-metric monitoring across agents
- Complexity: ⭐⭐ Intermediate

### Advanced Examples

**Performance Monitor** - Production-grade service monitoring  
[`examples/03-claudes-workshop/lesson_11_performance_monitor.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/03-claudes-workshop/lesson_11_performance_monitor.py)

- Demonstrates: SLA monitoring, alerting, performance dashboards
- Use case: Production system health monitoring
- Complexity: ⭐⭐⭐ Advanced
- Part of: Claude's Workshop

---

## Next Steps

- **[Agent Components](components.md)** - Agent-level lifecycle hooks
- **[Custom Engines](../guides/custom-engines.md)** - Build deterministic logic engines
- **[Testing Guide](testing.md)** - Testing orchestrator components
- **[Patterns Guide](patterns.md)** - Common orchestrator patterns
- **[API Reference](../reference/api/orchestrator_component.md)** - Full API documentation

---

**Last Updated**: October 14, 2025
