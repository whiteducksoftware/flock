# Backend API Architecture for Logic Operations UX

**Document**: 03_backend_api_architecture.md
**Created**: 2025-10-13
**Status**: Architecture Proposal
**Related**: 01_requirements.md, 02_frontend_architecture.md

## Executive Summary

This document defines the backend API extensions required to enable rich UX for JoinSpec (correlated AND gates) and BatchSpec (batch accumulation) logic operations in the Flock dashboard.

**Key Findings**:
- Current `/api/agents` endpoint exposes basic agent metadata but lacks logic operation state
- CorrelationEngine and BatchEngine already track rich state internally - we need to expose it
- Real-time WebSocket events needed for countdown timers and progress indicators
- State lives in orchestrator memory - no new persistence layer required

**Architecture Goals**:
1. **Backend-Heavy**: Minimize frontend computation, maximize backend intelligence
2. **Real-Time**: WebSocket events for live batch/join state updates
3. **Zero Breaking Changes**: Extend existing APIs, don't modify schemas
4. **Efficient Queries**: O(1) lookups for agent waiting state

---

## 1. Current State Analysis

### 1.1 Existing API Endpoints

#### `/api/agents` - Agent List Endpoint
**Current Response Schema**:
```json
{
  "agents": [
    {
      "name": "radiologist",
      "description": "Expert radiologist...",
      "status": "ready",
      "subscriptions": ["XRayImage", "LabResults"],
      "output_types": ["DiagnosticReport"]
    }
  ]
}
```

**Location**: `src/flock/dashboard/service.py:202-241`

**Gaps for Logic Operations**:
- ❌ No indication which subscriptions use JoinSpec or BatchSpec
- ❌ No correlation key extraction function visibility
- ❌ No time/count window information
- ❌ No batch size or timeout configuration
- ❌ No current waiting state (items collected, time elapsed)

### 1.2 Existing WebSocket Events

**Event Types** (`src/flock/dashboard/events.py`):
1. `AgentActivatedEvent` - Agent begins consuming
2. `MessagePublishedEvent` - Artifact published
3. `StreamingOutputEvent` - LLM token streaming
4. `AgentCompletedEvent` - Agent finishes execution
5. `AgentErrorEvent` - Agent encounters error

**Gaps for Logic Operations**:
- ❌ No "batch item added" event
- ❌ No "correlation group updated" event
- ❌ No "waiting for inputs" event
- ❌ No "batch timeout approaching" event

### 1.3 Internal State Tracking

**CorrelationEngine** (`src/flock/correlation_engine.py`):
```python
class CorrelationGroup:
    correlation_key: Any
    required_types: set[str]
    type_counts: dict[str, int]  # {"XRayImage": 1, "LabResults": 1}
    window_spec: timedelta | int
    created_at_sequence: int
    created_at_time: datetime | None
    waiting_artifacts: dict[str, list[Artifact]]

    def is_complete() -> bool
    def is_expired(current_sequence: int) -> bool
```

**BatchEngine** (`src/flock/batch_accumulator.py`):
```python
class BatchAccumulator:
    batch_spec: BatchSpec
    created_at: datetime
    artifacts: list[Artifact]
    _group_count: int  # For group batching

    def is_timeout_expired() -> bool
```

**Key Insight**: All the data we need already exists! We just need to expose it via API.

---

## 2. Proposed Data Schema Extensions

### 2.1 Extended Agent Response Schema

**New Endpoint**: `/api/agents` (enhanced)

```typescript
interface AgentResponse {
  name: string;
  description: string;
  status: "ready" | "waiting" | "active";
  subscriptions: string[];  // Type names (existing)
  output_types: string[];   // Type names (existing)

  // NEW: Logic Operations Configuration
  logic_operations?: LogicOperationsConfig[];
}

interface LogicOperationsConfig {
  subscription_index: number;
  subscription_types: string[];  // ["XRayImage", "LabResults"]

  // JoinSpec configuration
  join?: {
    correlation_strategy: "by_key";
    window_type: "time" | "count";
    window_value: number;  // 300 (seconds) or 10 (count)
    window_unit: "seconds" | "artifacts";
    required_types: string[];  // ["XRayImage", "LabResults"]
    type_counts: Record<string, number>;  // {"XRayImage": 1, "LabResults": 1}
  };

  // BatchSpec configuration
  batch?: {
    size?: number;  // 25
    timeout_seconds?: number;  // 30
    strategy: "size" | "timeout" | "hybrid";
  };

  // Current waiting state (refreshed per request)
  waiting_state?: WaitingState;
}

interface WaitingState {
  is_waiting: boolean;

  // For JoinSpec
  correlation_groups?: CorrelationGroupState[];

  // For BatchSpec
  batch_state?: BatchState;
}

interface CorrelationGroupState {
  correlation_key: string;  // "patient_123"
  created_at: string;  // ISO timestamp
  elapsed_seconds: number;  // 45
  expires_in_seconds?: number;  // 255 (for time windows)
  expires_in_artifacts?: number;  // 5 (for count windows)

  collected_types: Record<string, number>;  // {"XRayImage": 1, "LabResults": 0}
  required_types: Record<string, number>;   // {"XRayImage": 1, "LabResults": 1}

  waiting_for: string[];  // ["LabResults"]
  is_complete: boolean;
  is_expired: boolean;
}

interface BatchState {
  created_at: string;  // ISO timestamp when first artifact arrived
  elapsed_seconds: number;

  // Size-based batching
  items_collected?: number;  // 18
  items_target?: number;     // 25
  items_remaining?: number;  // 7

  // Timeout-based batching
  timeout_seconds?: number;  // 30
  timeout_remaining_seconds?: number;  // 12

  will_flush: "on_size" | "on_timeout" | "unknown";
}
```

**Implementation Strategy**:

```python
# src/flock/dashboard/service.py (enhanced)

@app.get("/api/agents")
async def get_agents() -> dict[str, Any]:
    agents = []

    for agent in orchestrator.agents:
        # Existing logic (unchanged)
        consumed_types = []
        for sub in agent.subscriptions:
            consumed_types.extend(sub.type_names)

        produced_types = [output.spec.type_name for output in agent.outputs]

        # NEW: Logic operations configuration
        logic_operations = []
        for idx, subscription in enumerate(agent.subscriptions):
            logic_config = _build_logic_config(
                agent, subscription, idx, orchestrator
            )
            if logic_config:  # Only include if has join/batch
                logic_operations.append(logic_config)

        agent_data = {
            "name": agent.name,
            "description": agent.description or "",
            "status": _compute_agent_status(agent, orchestrator),
            "subscriptions": consumed_types,
            "output_types": produced_types,
        }

        if logic_operations:
            agent_data["logic_operations"] = logic_operations

        agents.append(agent_data)

    return {"agents": agents}


def _build_logic_config(
    agent: Agent,
    subscription: Subscription,
    idx: int,
    orchestrator: Flock
) -> dict[str, Any] | None:
    """Build logic operations config for a subscription."""
    if not subscription.join and not subscription.batch:
        return None

    config = {
        "subscription_index": idx,
        "subscription_types": list(subscription.type_names),
    }

    # JoinSpec configuration
    if subscription.join:
        join_spec = subscription.join
        window_type = "time" if isinstance(join_spec.within, timedelta) else "count"
        window_value = (
            int(join_spec.within.total_seconds())
            if isinstance(join_spec.within, timedelta)
            else join_spec.within
        )

        config["join"] = {
            "correlation_strategy": "by_key",
            "window_type": window_type,
            "window_value": window_value,
            "window_unit": "seconds" if window_type == "time" else "artifacts",
            "required_types": list(subscription.type_names),
            "type_counts": dict(subscription.type_counts),
        }

        # Get waiting state from CorrelationEngine
        correlation_groups = _get_correlation_groups(
            orchestrator._correlation_engine,
            agent.name,
            idx
        )
        if correlation_groups:
            config["waiting_state"] = {
                "is_waiting": True,
                "correlation_groups": correlation_groups,
            }

    # BatchSpec configuration
    if subscription.batch:
        batch_spec = subscription.batch
        strategy = (
            "hybrid" if batch_spec.size and batch_spec.timeout
            else "size" if batch_spec.size
            else "timeout"
        )

        config["batch"] = {
            "strategy": strategy,
        }
        if batch_spec.size:
            config["batch"]["size"] = batch_spec.size
        if batch_spec.timeout:
            config["batch"]["timeout_seconds"] = int(batch_spec.timeout.total_seconds())

        # Get waiting state from BatchEngine
        batch_state = _get_batch_state(
            orchestrator._batch_engine,
            agent.name,
            idx,
            batch_spec
        )
        if batch_state:
            if "waiting_state" not in config:
                config["waiting_state"] = {"is_waiting": True}
            config["waiting_state"]["batch_state"] = batch_state

    return config


def _get_correlation_groups(
    engine: CorrelationEngine,
    agent_name: str,
    subscription_index: int
) -> list[dict[str, Any]]:
    """Extract correlation group state from CorrelationEngine."""
    pool_key = (agent_name, subscription_index)
    groups = engine.correlation_groups.get(pool_key, {})

    now = datetime.now()
    result = []

    for corr_key, group in groups.items():
        # Calculate elapsed time
        elapsed = (
            (now - group.created_at_time).total_seconds()
            if group.created_at_time
            else 0
        )

        # Calculate time remaining (for time windows)
        expires_in_seconds = None
        if isinstance(group.window_spec, timedelta):
            window_seconds = group.window_spec.total_seconds()
            expires_in_seconds = max(0, window_seconds - elapsed)

        # Calculate artifact count remaining (for count windows)
        expires_in_artifacts = None
        if isinstance(group.window_spec, int):
            artifacts_passed = engine.global_sequence - group.created_at_sequence
            expires_in_artifacts = max(0, group.window_spec - artifacts_passed)

        # Determine what we're waiting for
        collected_types = {
            type_name: len(group.waiting_artifacts.get(type_name, []))
            for type_name in group.required_types
        }

        waiting_for = [
            type_name
            for type_name, required_count in group.type_counts.items()
            if collected_types.get(type_name, 0) < required_count
        ]

        result.append({
            "correlation_key": str(corr_key),
            "created_at": group.created_at_time.isoformat() if group.created_at_time else None,
            "elapsed_seconds": round(elapsed, 1),
            "expires_in_seconds": round(expires_in_seconds, 1) if expires_in_seconds is not None else None,
            "expires_in_artifacts": expires_in_artifacts,
            "collected_types": collected_types,
            "required_types": dict(group.type_counts),
            "waiting_for": waiting_for,
            "is_complete": group.is_complete(),
            "is_expired": group.is_expired(engine.global_sequence),
        })

    return result


def _get_batch_state(
    engine: BatchEngine,
    agent_name: str,
    subscription_index: int,
    batch_spec: BatchSpec
) -> dict[str, Any] | None:
    """Extract batch state from BatchEngine."""
    batch_key = (agent_name, subscription_index)
    accumulator = engine.batches.get(batch_key)

    if not accumulator or not accumulator.artifacts:
        return None

    now = datetime.now()
    elapsed = (now - accumulator.created_at).total_seconds()

    result = {
        "created_at": accumulator.created_at.isoformat(),
        "elapsed_seconds": round(elapsed, 1),
    }

    # Size-based metrics
    if batch_spec.size:
        items_collected = len(accumulator.artifacts)
        # For group batching, use _group_count if available
        if hasattr(accumulator, '_group_count'):
            items_collected = accumulator._group_count

        result["items_collected"] = items_collected
        result["items_target"] = batch_spec.size
        result["items_remaining"] = max(0, batch_spec.size - items_collected)

    # Timeout-based metrics
    if batch_spec.timeout:
        timeout_seconds = batch_spec.timeout.total_seconds()
        timeout_remaining = max(0, timeout_seconds - elapsed)

        result["timeout_seconds"] = int(timeout_seconds)
        result["timeout_remaining_seconds"] = round(timeout_remaining, 1)

    # Determine what will trigger flush
    if batch_spec.size and batch_spec.timeout:
        # Hybrid: predict which will fire first
        size_will_fire = result.get("items_remaining", 999) <= 1
        timeout_will_fire = result.get("timeout_remaining_seconds", 999) <= 1

        result["will_flush"] = (
            "on_size" if size_will_fire
            else "on_timeout" if timeout_will_fire
            else "unknown"
        )
    elif batch_spec.size:
        result["will_flush"] = "on_size"
    elif batch_spec.timeout:
        result["will_flush"] = "on_timeout"

    return result


def _compute_agent_status(agent: Agent, orchestrator: Flock) -> str:
    """Determine agent status based on waiting state."""
    # Check if any subscription is waiting for correlation or batching
    for idx, subscription in enumerate(agent.subscriptions):
        if subscription.join:
            pool_key = (agent.name, idx)
            if pool_key in orchestrator._correlation_engine.correlation_groups:
                groups = orchestrator._correlation_engine.correlation_groups[pool_key]
                if groups:  # Has waiting correlation groups
                    return "waiting"

        if subscription.batch:
            batch_key = (agent.name, idx)
            if batch_key in orchestrator._batch_engine.batches:
                accumulator = orchestrator._batch_engine.batches[batch_key]
                if accumulator and accumulator.artifacts:
                    return "waiting"

    return "ready"
```

---

## 3. WebSocket Event Extensions

### 3.1 New Event Types

#### `BatchItemAddedEvent`
Emitted when an artifact is added to a batch (NOT yet flushed).

```python
class BatchItemAddedEvent(BaseModel):
    """Event emitted when artifact added to batch accumulator."""

    # Event metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Agent identification
    agent_name: str
    subscription_index: int

    # Batch progress
    items_collected: int
    items_target: int | None  # None if no size limit
    items_remaining: int | None

    # Timeout progress
    elapsed_seconds: float
    timeout_seconds: float | None
    timeout_remaining_seconds: float | None

    # Trigger prediction
    will_flush: Literal["on_size", "on_timeout", "unknown"]

    # Artifact that triggered this event
    artifact_id: str
    artifact_type: str
```

**Emission Point**: `orchestrator.py` after `_batch_engine.add_artifact()` returns `False` (not yet ready to flush).

#### `CorrelationGroupUpdatedEvent`
Emitted when an artifact is added to a correlation group.

```python
class CorrelationGroupUpdatedEvent(BaseModel):
    """Event emitted when artifact added to correlation group."""

    # Event metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Agent identification
    agent_name: str
    subscription_index: int

    # Correlation group
    correlation_key: str  # "patient_123"

    # Progress
    collected_types: dict[str, int]  # {"XRayImage": 1, "LabResults": 0}
    required_types: dict[str, int]   # {"XRayImage": 1, "LabResults": 1}
    waiting_for: list[str]  # ["LabResults"]

    # Window progress
    elapsed_seconds: float
    expires_in_seconds: float | None  # For time windows
    expires_in_artifacts: int | None  # For count windows

    # Artifact that triggered this event
    artifact_id: str
    artifact_type: str

    is_complete: bool  # Will trigger agent in next orchestrator cycle
```

**Emission Point**: `orchestrator.py` after `_correlation_engine.add_artifact()` returns `None` (not yet complete).

#### `WaitingStateChangedEvent`
Emitted when agent transitions to/from waiting state.

```python
class WaitingStateChangedEvent(BaseModel):
    """Event emitted when agent waiting state changes."""

    # Event metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Agent identification
    agent_name: str

    # Waiting state
    is_waiting: bool
    waiting_reason: Literal["batch_accumulating", "correlation_pending", "none"]

    # Summary of what we're waiting for
    waiting_summary: str  # "Collecting batch: 18/25 items"
```

**Emission Point**: When agent status changes (computed in `_compute_agent_status()`).

### 3.2 WebSocket Event Emission Strategy

**Approach**: Emit events from orchestrator during artifact routing logic.

```python
# src/flock/orchestrator.py (enhanced)

async def _route_artifact(self, artifact: Artifact) -> None:
    """Route artifact to matching agent subscriptions."""

    for agent in self.agents:
        for idx, subscription in enumerate(agent.subscriptions):
            if not subscription.matches(artifact):
                continue

            # ... existing matching logic ...

            # JoinSpec handling
            if subscription.join is not None:
                completed_group = self._correlation_engine.add_artifact(
                    artifact=artifact,
                    subscription=subscription,
                    subscription_index=idx,
                )

                if completed_group is None:
                    # NOT complete - emit update event
                    await self._emit_correlation_update(
                        agent, subscription, idx, artifact
                    )
                else:
                    # Complete - will trigger agent
                    artifacts = completed_group.get_artifacts()

            # BatchSpec handling
            if subscription.batch is not None:
                should_flush = self._batch_engine.add_artifact(
                    artifact=artifact,
                    subscription=subscription,
                    subscription_index=idx,
                )

                if not should_flush:
                    # NOT ready to flush - emit progress event
                    await self._emit_batch_update(
                        agent, subscription, idx, artifact
                    )
                else:
                    # Ready to flush - will trigger agent
                    artifacts = self._batch_engine.flush_batch(agent.name, idx)


async def _emit_correlation_update(
    self,
    agent: Agent,
    subscription: Subscription,
    idx: int,
    artifact: Artifact
) -> None:
    """Emit CorrelationGroupUpdatedEvent to dashboard."""
    from flock.dashboard.events import CorrelationGroupUpdatedEvent

    # Get updated group state
    pool_key = (agent.name, idx)
    groups = self._correlation_engine.correlation_groups.get(pool_key, {})

    # Find the group that contains this artifact
    model_cls = type_registry.resolve(artifact.type)
    payload_instance = model_cls(**artifact.payload)
    correlation_key = subscription.join.by(payload_instance)

    group = groups.get(correlation_key)
    if not group:
        return

    # Build event
    now = datetime.now()
    elapsed = (
        (now - group.created_at_time).total_seconds()
        if group.created_at_time
        else 0
    )

    collected_types = {
        type_name: len(group.waiting_artifacts.get(type_name, []))
        for type_name in group.required_types
    }

    waiting_for = [
        type_name
        for type_name, required_count in group.type_counts.items()
        if collected_types.get(type_name, 0) < required_count
    ]

    # Calculate expiry
    expires_in_seconds = None
    expires_in_artifacts = None
    if isinstance(group.window_spec, timedelta):
        window_seconds = group.window_spec.total_seconds()
        expires_in_seconds = max(0, window_seconds - elapsed)
    else:
        artifacts_passed = self._correlation_engine.global_sequence - group.created_at_sequence
        expires_in_artifacts = max(0, group.window_spec - artifacts_passed)

    event = CorrelationGroupUpdatedEvent(
        agent_name=agent.name,
        subscription_index=idx,
        correlation_key=str(correlation_key),
        collected_types=collected_types,
        required_types=dict(group.type_counts),
        waiting_for=waiting_for,
        elapsed_seconds=round(elapsed, 1),
        expires_in_seconds=round(expires_in_seconds, 1) if expires_in_seconds else None,
        expires_in_artifacts=expires_in_artifacts,
        artifact_id=str(artifact.id),
        artifact_type=artifact.type,
        is_complete=group.is_complete(),
    )

    # Broadcast via WebSocket
    if hasattr(self, '_dashboard_service'):
        await self._dashboard_service.websocket_manager.broadcast(event)


async def _emit_batch_update(
    self,
    agent: Agent,
    subscription: Subscription,
    idx: int,
    artifact: Artifact
) -> None:
    """Emit BatchItemAddedEvent to dashboard."""
    from flock.dashboard.events import BatchItemAddedEvent

    # Get updated batch state
    batch_key = (agent.name, idx)
    accumulator = self._batch_engine.batches.get(batch_key)

    if not accumulator:
        return

    batch_spec = subscription.batch
    now = datetime.now()
    elapsed = (now - accumulator.created_at).total_seconds()

    # Size metrics
    items_collected = len(accumulator.artifacts)
    if hasattr(accumulator, '_group_count'):
        items_collected = accumulator._group_count

    items_target = batch_spec.size
    items_remaining = max(0, batch_spec.size - items_collected) if batch_spec.size else None

    # Timeout metrics
    timeout_seconds = (
        batch_spec.timeout.total_seconds()
        if batch_spec.timeout
        else None
    )
    timeout_remaining = (
        max(0, timeout_seconds - elapsed)
        if timeout_seconds
        else None
    )

    # Predict flush trigger
    will_flush = "unknown"
    if batch_spec.size and batch_spec.timeout:
        if items_remaining and items_remaining <= 1:
            will_flush = "on_size"
        elif timeout_remaining and timeout_remaining <= 1:
            will_flush = "on_timeout"
    elif batch_spec.size:
        will_flush = "on_size"
    elif batch_spec.timeout:
        will_flush = "on_timeout"

    event = BatchItemAddedEvent(
        agent_name=agent.name,
        subscription_index=idx,
        items_collected=items_collected,
        items_target=items_target,
        items_remaining=items_remaining,
        elapsed_seconds=round(elapsed, 1),
        timeout_seconds=timeout_seconds,
        timeout_remaining_seconds=round(timeout_remaining, 1) if timeout_remaining else None,
        will_flush=will_flush,
        artifact_id=str(artifact.id),
        artifact_type=artifact.type,
    )

    # Broadcast via WebSocket
    if hasattr(self, '_dashboard_service'):
        await self._dashboard_service.websocket_manager.broadcast(event)
```

---

## 4. State Management Architecture

### 4.1 Where State Lives

**State Location Matrix**:

| State Type | Storage | Query Method | Lifetime |
|------------|---------|--------------|----------|
| **Correlation Groups** | `CorrelationEngine.correlation_groups` | Direct dict lookup by `(agent_name, subscription_index)` | Until complete or expired |
| **Batch Accumulators** | `BatchEngine.batches` | Direct dict lookup by `(agent_name, subscription_index)` | Until flushed |
| **Agent Waiting Status** | Computed on-demand | Iterate orchestrator.agents, check engines | Ephemeral |
| **Correlation Keys** | In-memory in CorrelationGroup | Iterate groups dict | Until group expires |
| **Artifact References** | CorrelationGroup.waiting_artifacts, BatchAccumulator.artifacts | Direct list access | Until consumed |

**Key Insight**: All state is in-memory. No database queries required. All lookups are O(1) dict access.

### 4.2 Query Patterns

#### Pattern 1: Get All Waiting Agents
```python
def get_waiting_agents(orchestrator: Flock) -> list[str]:
    """Get list of agent names currently waiting for inputs."""
    waiting = []

    for agent in orchestrator.agents:
        for idx, subscription in enumerate(agent.subscriptions):
            # Check correlation engine
            if subscription.join:
                pool_key = (agent.name, idx)
                if pool_key in orchestrator._correlation_engine.correlation_groups:
                    if orchestrator._correlation_engine.correlation_groups[pool_key]:
                        waiting.append(agent.name)
                        break

            # Check batch engine
            if subscription.batch:
                batch_key = (agent.name, idx)
                if batch_key in orchestrator._batch_engine.batches:
                    accumulator = orchestrator._batch_engine.batches[batch_key]
                    if accumulator and accumulator.artifacts:
                        waiting.append(agent.name)
                        break

    return waiting
```

**Complexity**: O(A * S) where A = agents, S = subscriptions per agent. Typically < 100 agents.

#### Pattern 2: Get Agent Waiting Details
```python
def get_agent_waiting_state(
    orchestrator: Flock,
    agent_name: str
) -> dict[str, Any]:
    """Get detailed waiting state for a specific agent."""
    agent = orchestrator.get_agent(agent_name)

    waiting_state = {
        "is_waiting": False,
        "correlation_groups": [],
        "batches": [],
    }

    for idx, subscription in enumerate(agent.subscriptions):
        # Check JoinSpec
        if subscription.join:
            pool_key = (agent_name, idx)
            groups = orchestrator._correlation_engine.correlation_groups.get(pool_key, {})

            for corr_key, group in groups.items():
                waiting_state["is_waiting"] = True
                waiting_state["correlation_groups"].append({
                    "correlation_key": str(corr_key),
                    "subscription_index": idx,
                    # ... full group details ...
                })

        # Check BatchSpec
        if subscription.batch:
            batch_key = (agent_name, idx)
            accumulator = orchestrator._batch_engine.batches.get(batch_key)

            if accumulator and accumulator.artifacts:
                waiting_state["is_waiting"] = True
                waiting_state["batches"].append({
                    "subscription_index": idx,
                    "items_collected": len(accumulator.artifacts),
                    # ... full batch details ...
                })

    return waiting_state
```

**Complexity**: O(S * G) where S = subscriptions, G = correlation groups per subscription. Typically < 10 groups.

### 4.3 Real-Time Update Strategy

**Approach**: Event-driven updates via WebSocket, with REST API fallback.

```
┌─────────────┐
│  Artifact   │
│  Published  │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│  Orchestrator    │
│  Routes Artifact │
└──────┬───────────┘
       │
       ├─────────────────────────────────┐
       │                                 │
       ▼                                 ▼
┌─────────────────┐           ┌──────────────────┐
│ JoinSpec Logic  │           │ BatchSpec Logic  │
│ Add to Group    │           │ Add to Batch     │
└─────────┬───────┘           └────────┬─────────┘
          │                            │
          │ (not complete)             │ (not ready)
          │                            │
          ▼                            ▼
┌──────────────────────┐    ┌─────────────────────┐
│ Emit Correlation     │    │ Emit Batch          │
│ GroupUpdated Event   │    │ ItemAdded Event     │
└──────────┬───────────┘    └─────────┬───────────┘
           │                          │
           └──────────┬───────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  WebSocket    │
              │  Broadcast    │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │   Frontend    │
              │  Updates UI   │
              └───────────────┘
```

**Fallback Strategy**: If WebSocket disconnects, frontend polls `/api/agents` every 2 seconds for updated waiting state.

---

## 5. Performance Considerations

### 5.1 Computational Complexity

| Operation | Complexity | Frequency | Impact |
|-----------|------------|-----------|--------|
| `/api/agents` request | O(A * S * G) | On-demand (2-5 req/sec) | Low - typically < 100 agents |
| Correlation group lookup | O(1) | Per artifact (100-1000/sec) | Negligible |
| Batch state lookup | O(1) | Per artifact (100-1000/sec) | Negligible |
| WebSocket broadcast | O(C) | Per correlation/batch update | Low - typically < 10 clients |
| Status computation | O(A * S) | Per `/api/agents` request | Low - memoize if needed |

**Optimization Opportunities**:
1. **Cache agent status**: Invalidate on correlation/batch state change
2. **Batch WebSocket events**: Send max 1 event per 100ms per agent
3. **Lazy correlation key serialization**: Only serialize when needed for API

### 5.2 Memory Overhead

**Current State**:
- CorrelationGroup: ~1KB per group (assuming small artifacts)
- BatchAccumulator: ~N KB for N artifacts
- Typical system: < 1000 correlation groups, < 100 batches = ~1-2 MB total

**New Overhead**:
- WebSocket event objects: ~500 bytes each
- Event broadcasting: No persistence, sent immediately
- Total: < 1 MB additional memory

**Conclusion**: Negligible impact on memory.

### 5.3 Network Bandwidth

**WebSocket Event Sizes**:
- `CorrelationGroupUpdatedEvent`: ~500 bytes
- `BatchItemAddedEvent`: ~300 bytes

**Estimated Traffic**:
- High-throughput system: 1000 artifacts/sec
- Assume 20% trigger correlation/batch updates: 200 events/sec
- Bandwidth: 200 * 400 bytes = 80 KB/sec per client
- For 10 clients: 800 KB/sec = **0.8 MB/sec**

**Conclusion**: Low bandwidth impact, well within typical network capacity.

---

## 6. Implementation Complexity Assessment

### 6.1 Difficulty Matrix

| Component | Lines of Code | Complexity | Risk | Effort |
|-----------|---------------|------------|------|--------|
| **Enhanced `/api/agents`** | ~200 LOC | Medium | Low | 4 hours |
| **`_build_logic_config()`** | ~80 LOC | Medium | Low | 2 hours |
| **`_get_correlation_groups()`** | ~60 LOC | Medium | Low | 2 hours |
| **`_get_batch_state()`** | ~50 LOC | Low | Low | 1 hour |
| **New WebSocket events** | ~100 LOC | Low | Low | 2 hours |
| **Event emission in orchestrator** | ~150 LOC | Medium | Medium | 4 hours |
| **Frontend integration** | N/A | High | Medium | 8 hours (separate) |
| **Testing & edge cases** | ~200 LOC | High | Medium | 6 hours |

**Total Backend Effort**: ~25-30 hours
**Total System Effort**: ~35-40 hours (including frontend)

### 6.2 Risk Assessment

**Low Risk**:
- ✅ All state already exists - just exposing it
- ✅ No database schema changes
- ✅ No breaking API changes
- ✅ WebSocket infrastructure already built

**Medium Risk**:
- ⚠️ Orchestrator event emission timing (ensure not dropped)
- ⚠️ Edge cases: agent with multiple subscriptions, mixed join/batch
- ⚠️ Performance under high throughput (need load testing)

**Mitigation**:
- Add comprehensive unit tests for edge cases
- Load test with 10,000 artifacts/sec
- Add logging/metrics for event emission success rate

### 6.3 Alternative Approaches Considered

#### Alternative 1: Dedicated `/api/waiting-state` Endpoint
**Pros**: Cleaner separation, easier caching
**Cons**: Extra network round trip, data duplication
**Decision**: Rejected - prefer consolidated `/api/agents` response

#### Alternative 2: Polling-Only (No WebSocket Events)
**Pros**: Simpler implementation, no event timing issues
**Cons**: Poor UX for real-time updates, higher server load
**Decision**: Rejected - real-time UX is critical for logic operations

#### Alternative 3: Persistent State in Database
**Pros**: Survives restarts, enables historical analysis
**Cons**: High complexity, unnecessary for in-memory orchestrator
**Decision**: Rejected - in-memory state is sufficient

---

## 7. API Endpoint Summary

### 7.1 REST Endpoints

#### `GET /api/agents` (Enhanced)
**Purpose**: Get all agents with logic operations configuration and waiting state

**Response**:
```json
{
  "agents": [
    {
      "name": "radiologist",
      "description": "Expert radiologist...",
      "status": "waiting",
      "subscriptions": ["XRayImage", "LabResults"],
      "output_types": ["DiagnosticReport"],
      "logic_operations": [
        {
          "subscription_index": 0,
          "subscription_types": ["XRayImage", "LabResults"],
          "join": {
            "correlation_strategy": "by_key",
            "window_type": "time",
            "window_value": 300,
            "window_unit": "seconds",
            "required_types": ["XRayImage", "LabResults"],
            "type_counts": {"XRayImage": 1, "LabResults": 1}
          },
          "waiting_state": {
            "is_waiting": true,
            "correlation_groups": [
              {
                "correlation_key": "patient_123",
                "created_at": "2025-10-13T14:30:00Z",
                "elapsed_seconds": 45.2,
                "expires_in_seconds": 254.8,
                "collected_types": {"XRayImage": 1, "LabResults": 0},
                "required_types": {"XRayImage": 1, "LabResults": 1},
                "waiting_for": ["LabResults"],
                "is_complete": false,
                "is_expired": false
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Performance**: O(A * S * G), typically < 10ms for 100 agents

#### `GET /api/agents/{agent_name}/waiting-state` (Optional New)
**Purpose**: Get detailed waiting state for a specific agent (if needed for efficiency)

**Response**: Same structure as `waiting_state` in `/api/agents`

**Decision**: Start without this, add if `/api/agents` becomes slow.

### 7.2 WebSocket Events

#### `correlation_group_updated`
Emitted when artifact added to correlation group (not yet complete).

```json
{
  "event_type": "correlation_group_updated",
  "timestamp": "2025-10-13T14:30:45Z",
  "agent_name": "radiologist",
  "subscription_index": 0,
  "correlation_key": "patient_123",
  "collected_types": {"XRayImage": 1, "LabResults": 0},
  "required_types": {"XRayImage": 1, "LabResults": 1},
  "waiting_for": ["LabResults"],
  "elapsed_seconds": 45.2,
  "expires_in_seconds": 254.8,
  "artifact_id": "a1b2c3d4",
  "artifact_type": "XRayImage",
  "is_complete": false
}
```

#### `batch_item_added`
Emitted when artifact added to batch (not yet flushed).

```json
{
  "event_type": "batch_item_added",
  "timestamp": "2025-10-13T14:30:45Z",
  "agent_name": "email_processor",
  "subscription_index": 0,
  "items_collected": 18,
  "items_target": 25,
  "items_remaining": 7,
  "elapsed_seconds": 12.5,
  "timeout_seconds": 30,
  "timeout_remaining_seconds": 17.5,
  "will_flush": "on_size",
  "artifact_id": "e5f6g7h8",
  "artifact_type": "Email"
}
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# tests/dashboard/test_logic_operations_api.py

@pytest.mark.asyncio
async def test_get_agents_with_joinspec():
    """Test /api/agents includes JoinSpec configuration."""
    flock = Flock()

    agent = (
        flock.agent("test_agent")
        .consumes(
            TypeA, TypeB,
            join=JoinSpec(by=lambda x: x.key, within=timedelta(minutes=5))
        )
        .publishes(TypeC)
    )

    service = DashboardHTTPService(flock)

    # Make request
    response = await service.app.get("/api/agents")
    data = response.json()

    # Verify logic_operations included
    agent_data = data["agents"][0]
    assert "logic_operations" in agent_data

    logic_config = agent_data["logic_operations"][0]
    assert logic_config["join"]["window_type"] == "time"
    assert logic_config["join"]["window_value"] == 300  # 5 minutes in seconds


@pytest.mark.asyncio
async def test_correlation_group_state():
    """Test correlation group waiting state exposed via API."""
    flock = Flock()

    agent = (
        flock.agent("test_agent")
        .consumes(
            TypeA, TypeB,
            join=JoinSpec(by=lambda x: x.key, within=timedelta(minutes=5))
        )
    )

    # Publish one artifact
    await flock.publish(TypeA(key="test_key"))

    # Get agent state
    response = await service.app.get("/api/agents")
    data = response.json()

    # Verify waiting state
    logic_config = data["agents"][0]["logic_operations"][0]
    waiting_state = logic_config["waiting_state"]

    assert waiting_state["is_waiting"] is True
    assert len(waiting_state["correlation_groups"]) == 1

    group = waiting_state["correlation_groups"][0]
    assert group["correlation_key"] == "test_key"
    assert group["collected_types"]["TypeA"] == 1
    assert group["collected_types"]["TypeB"] == 0
    assert "TypeB" in group["waiting_for"]


@pytest.mark.asyncio
async def test_batch_state():
    """Test batch accumulator state exposed via API."""
    flock = Flock()

    agent = (
        flock.agent("test_agent")
        .consumes(TypeA, batch=BatchSpec(size=5))
    )

    # Publish 3 artifacts
    for i in range(3):
        await flock.publish(TypeA(value=i))

    # Get agent state
    response = await service.app.get("/api/agents")
    data = response.json()

    # Verify batch state
    logic_config = data["agents"][0]["logic_operations"][0]
    batch_state = logic_config["waiting_state"]["batch_state"]

    assert batch_state["items_collected"] == 3
    assert batch_state["items_target"] == 5
    assert batch_state["items_remaining"] == 2
    assert batch_state["will_flush"] == "on_size"
```

### 8.2 Integration Tests

```python
@pytest.mark.asyncio
async def test_websocket_correlation_events():
    """Test correlation group update events emitted via WebSocket."""
    flock = Flock()
    service = DashboardHTTPService(flock)

    # Setup mock WebSocket client
    mock_ws = MockWebSocket()
    await service.websocket_manager.add_client(mock_ws)

    # Create agent with JoinSpec
    agent = (
        flock.agent("test_agent")
        .consumes(
            TypeA, TypeB,
            join=JoinSpec(by=lambda x: x.key, within=timedelta(minutes=5))
        )
    )

    # Publish first artifact
    await flock.publish(TypeA(key="test_key"))

    # Verify event emitted
    events = mock_ws.received_messages
    assert len(events) == 2  # MessagePublishedEvent + CorrelationGroupUpdatedEvent

    corr_event = next(e for e in events if e["event_type"] == "correlation_group_updated")
    assert corr_event["agent_name"] == "test_agent"
    assert corr_event["correlation_key"] == "test_key"
    assert corr_event["collected_types"]["TypeA"] == 1
    assert "TypeB" in corr_event["waiting_for"]
```

### 8.3 Load Tests

```python
@pytest.mark.performance
@pytest.mark.asyncio
async def test_high_throughput_correlation():
    """Test correlation engine under high artifact throughput."""
    flock = Flock()

    agent = (
        flock.agent("test_agent")
        .consumes(
            TypeA, TypeB,
            join=JoinSpec(by=lambda x: x.key, within=timedelta(minutes=5))
        )
    )

    # Publish 10,000 artifacts (5000 pairs)
    start = time.time()

    for i in range(5000):
        await flock.publish(TypeA(key=f"key_{i}"))
        await flock.publish(TypeB(key=f"key_{i}"))

    elapsed = time.time() - start
    throughput = 10000 / elapsed

    # Verify performance
    assert throughput > 1000, f"Throughput too low: {throughput:.0f} artifacts/sec"

    # Verify no correlation groups left waiting
    assert len(flock._correlation_engine.correlation_groups) == 0
```

---

## 9. Migration Path

### 9.1 Phase 1: Backend Foundation (Week 1)
- ✅ Implement enhanced `/api/agents` endpoint
- ✅ Add `_build_logic_config()` helper
- ✅ Add `_get_correlation_groups()` state extractor
- ✅ Add `_get_batch_state()` state extractor
- ✅ Add unit tests for API responses

**Deliverable**: `/api/agents` returns logic operations configuration

### 9.2 Phase 2: WebSocket Events (Week 2)
- ✅ Define new event models in `events.py`
- ✅ Add event emission in `orchestrator.py`
- ✅ Add `_emit_correlation_update()` helper
- ✅ Add `_emit_batch_update()` helper
- ✅ Add integration tests for event emission

**Deliverable**: WebSocket events broadcast correlation/batch updates

### 9.3 Phase 3: Frontend Integration (Week 3)
- ✅ Update frontend to consume new API schema
- ✅ Build JoinSpec UI components (see 02_frontend_architecture.md)
- ✅ Build BatchSpec UI components
- ✅ Add countdown timers and progress indicators
- ✅ Add end-to-end tests

**Deliverable**: Full UX for logic operations

### 9.4 Phase 4: Optimization (Week 4)
- ⚡ Add agent status caching
- ⚡ Batch WebSocket events (1 per 100ms per agent)
- ⚡ Load testing and performance tuning
- ⚡ Monitoring and observability

**Deliverable**: Production-ready performance

---

## 10. Open Questions & Future Work

### 10.1 Open Questions

1. **Q**: Should we expose correlation key extraction function to frontend?
   **A**: No - too complex. Just show "Correlating by key" or infer from first artifact.

2. **Q**: How to handle agents with multiple subscriptions using join/batch?
   **A**: `logic_operations` is an array - one entry per subscription. Use `subscription_index` to correlate.

3. **Q**: Should we show individual artifacts in waiting groups?
   **A**: Phase 1: No, just counts. Phase 2: Add artifact previews if needed.

4. **Q**: How to handle correlation group expiry in UI?
   **A**: Show "expired" state and fade out after 5 seconds.

5. **Q**: Should we persist waiting state to survive restarts?
   **A**: No - orchestrator is in-memory. Document this limitation.

### 10.2 Future Enhancements

1. **Historical Analysis**: Store correlation/batch metrics in DuckDB for performance analysis
2. **Correlation Group Drilldown**: Show individual artifacts in each group
3. **Batch Preview**: Show first N items in batch before flush
4. **Smart Alerts**: Notify when correlation groups about to expire
5. **Correlation Key Visualization**: Show correlation key values in graph edges
6. **Batch Optimization Suggestions**: "Your batch size is too small, consider increasing to 50"

---

## 11. Conclusion

### 11.1 Summary of Decisions

| Decision | Rationale |
|----------|-----------|
| **Extend `/api/agents`** | Consolidate all agent data in one endpoint |
| **Add WebSocket events** | Enable real-time UX without polling |
| **Backend-heavy computation** | Reduce frontend complexity, leverage existing state |
| **No new persistence** | In-memory state is sufficient, avoids DB complexity |
| **Event-driven updates** | Better UX than polling, lower server load |

### 11.2 Success Criteria

**Backend Success Metrics**:
- ✅ `/api/agents` response time < 50ms (p95)
- ✅ WebSocket event latency < 100ms (p95)
- ✅ Support 10,000 artifacts/sec throughput
- ✅ Memory overhead < 10 MB for typical workload
- ✅ Zero breaking changes to existing APIs

**UX Success Metrics** (measured in frontend):
- ✅ Countdown timers update in real-time (< 200ms lag)
- ✅ Progress bars reflect actual state (no stale data)
- ✅ Users understand what agents are waiting for
- ✅ Dashboard responds to logic operations within 1 second

### 11.3 Next Steps

1. **Review & Approval**: Circulate this doc to team for feedback
2. **Prioritization**: Confirm this fits roadmap timeline
3. **Implementation**: Start with Phase 1 (backend foundation)
4. **Testing**: Build comprehensive test suite alongside implementation
5. **Documentation**: Update user-facing docs with new capabilities

---

**Document Status**: ✅ Ready for Review
**Approvers**: [@engineering-team]
**Implementation Target**: Q4 2025
