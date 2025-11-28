# Solution Design Document (Minimal)

> **Note:** This is a minimal SDD. The complete design is in GitHub issue #364.

## References

- **GitHub Issue #364:** Complete DSL design and examples
- **Orchestrator:** `src/flock/core/orchestrator.py` (`run_until_idle`, scheduler loop)
- **Store API:** `src/flock/core/store.py` (`query_artifacts`, `FilterConfig`)
- **Subscription:** `src/flock/core/subscription.py`
- **Scheduler:** `src/flock/orchestrator/scheduler.py`
- **Component Hooks:** `src/flock/components/orchestrator/base.py`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Code                                   │
│                                                                      │
│  await flock.run_until(                                             │
│      Until.artifact_count(UserStory, cid).at_least(5)               │
│      | Until.workflow_error(cid).exists()                           │
│  )                                                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Condition DSL Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │  RunCondition   │  │  Until Helper   │  │  When Helper    │      │
│  │  (Protocol)     │  │  (Builders)     │  │  (Activation)   │      │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘      │
│           │                    │                    │                │
│           ▼                    ▼                    ▼                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Condition Implementations                        │   │
│  │  • ArtifactCountCondition  • ExistsCondition                 │   │
│  │  • FieldPredicateCondition • WorkflowStateCondition          │   │
│  │  • IdleCondition           • CompositeCondition (And/Or/Not) │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Orchestrator Integration                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  run_until(condition, timeout) - NEW                        │    │
│  │  • Loop: check condition → if true, return                  │    │
│  │  • Else: run one scheduler step → repeat                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ActivationComponent - NEW (for subscription activation)    │    │
│  │  • on_before_agent_schedule: evaluate activation condition  │    │
│  │  • False → DEFER, True → CONTINUE                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. RunCondition Protocol

**New file: `src/flock/core/conditions.py`**

```python
from typing import Protocol, TYPE_CHECKING
from abc import abstractmethod

if TYPE_CHECKING:
    from flock.core import Flock

class RunCondition(Protocol):
    """Protocol for workflow termination/activation conditions."""

    @abstractmethod
    async def evaluate(self, orchestrator: "Flock") -> bool:
        """Evaluate condition against current orchestrator state."""
        ...

    def __and__(self, other: "RunCondition") -> "RunCondition":
        return AndCondition(self, other)

    def __or__(self, other: "RunCondition") -> "RunCondition":
        return OrCondition(self, other)

    def __invert__(self) -> "RunCondition":
        return NotCondition(self)
```

### 2. Condition Implementations

```python
@dataclass
class ArtifactCountCondition:
    """Condition based on artifact count."""
    model: type[BaseModel]
    correlation_id: str | None = None
    tags: set[str] | None = None
    produced_by: str | None = None
    min_count: int | None = None
    max_count: int | None = None
    exact_count: int | None = None

    async def evaluate(self, orchestrator: Flock) -> bool:
        filters = FilterConfig(
            type_names={type_registry.name_for(self.model)},
            correlation_id=self.correlation_id,
            tags=self.tags,
            produced_by={self.produced_by} if self.produced_by else None,
        )
        _, total = await orchestrator.store.query_artifacts(filters, limit=0)

        if self.min_count is not None and total < self.min_count:
            return False
        if self.max_count is not None and total > self.max_count:
            return False
        if self.exact_count is not None and total != self.exact_count:
            return False
        return True

    def at_least(self, n: int) -> "ArtifactCountCondition":
        return replace(self, min_count=n)

    def at_most(self, n: int) -> "ArtifactCountCondition":
        return replace(self, max_count=n)

    def exactly(self, n: int) -> "ArtifactCountCondition":
        return replace(self, exact_count=n)


@dataclass
class ExistsCondition:
    """Condition that checks if any matching artifact exists."""
    model: type[BaseModel]
    correlation_id: str | None = None
    tags: set[str] | None = None

    async def evaluate(self, orchestrator: Flock) -> bool:
        filters = FilterConfig(
            type_names={type_registry.name_for(self.model)},
            correlation_id=self.correlation_id,
            tags=self.tags,
        )
        _, total = await orchestrator.store.query_artifacts(filters, limit=1)
        return total > 0


@dataclass
class FieldPredicateCondition:
    """Condition based on a field value predicate."""
    model: type[BaseModel]
    field: str
    predicate: Callable[[Any], bool]
    correlation_id: str | None = None

    async def evaluate(self, orchestrator: Flock) -> bool:
        filters = FilterConfig(
            type_names={type_registry.name_for(self.model)},
            correlation_id=self.correlation_id,
        )
        artifacts, _ = await orchestrator.store.query_artifacts(filters, limit=100)
        for artifact in artifacts:
            value = artifact.payload.get(self.field)
            if self.predicate(value):
                return True
        return False


@dataclass
class IdleCondition:
    """Condition that checks if orchestrator is idle."""

    async def evaluate(self, orchestrator: Flock) -> bool:
        return not orchestrator.has_pending_work()


@dataclass
class WorkflowErrorCondition:
    """Condition that checks for WorkflowError artifacts."""
    correlation_id: str

    async def evaluate(self, orchestrator: Flock) -> bool:
        status = await orchestrator.get_correlation_status(self.correlation_id)
        return status.get("error_count", 0) > 0


# Composite conditions
@dataclass
class AndCondition:
    left: RunCondition
    right: RunCondition

    async def evaluate(self, orchestrator: Flock) -> bool:
        return await self.left.evaluate(orchestrator) and await self.right.evaluate(orchestrator)


@dataclass
class OrCondition:
    left: RunCondition
    right: RunCondition

    async def evaluate(self, orchestrator: Flock) -> bool:
        return await self.left.evaluate(orchestrator) or await self.right.evaluate(orchestrator)


@dataclass
class NotCondition:
    condition: RunCondition

    async def evaluate(self, orchestrator: Flock) -> bool:
        return not await self.condition.evaluate(orchestrator)
```

### 3. Until Helper (Builder Pattern)

```python
class Until:
    """Builder for workflow termination conditions."""

    @staticmethod
    def idle() -> IdleCondition:
        return IdleCondition()

    @staticmethod
    def no_pending_work() -> IdleCondition:
        return IdleCondition()

    @staticmethod
    def artifact_count(
        model: type[BaseModel],
        *,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        produced_by: str | None = None,
    ) -> ArtifactCountCondition:
        return ArtifactCountCondition(
            model=model,
            correlation_id=correlation_id,
            tags=tags,
            produced_by=produced_by,
        )

    @staticmethod
    def exists(
        model: type[BaseModel],
        *,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
    ) -> ExistsCondition:
        return ExistsCondition(model=model, correlation_id=correlation_id, tags=tags)

    @staticmethod
    def none(
        model: type[BaseModel],
        *,
        correlation_id: str | None = None,
    ) -> NotCondition:
        return NotCondition(ExistsCondition(model=model, correlation_id=correlation_id))

    @staticmethod
    def any_field(
        model: type[BaseModel],
        *,
        field: str,
        predicate: Callable[[Any], bool],
        correlation_id: str | None = None,
    ) -> FieldPredicateCondition:
        return FieldPredicateCondition(
            model=model, field=field, predicate=predicate, correlation_id=correlation_id
        )

    @staticmethod
    def workflow_error(correlation_id: str) -> WorkflowErrorCondition:
        return WorkflowErrorCondition(correlation_id=correlation_id)
```

### 4. run_until() Method

**Add to `src/flock/core/orchestrator.py`:**

```python
async def run_until(
    self,
    condition: RunCondition,
    *,
    timeout: float | None = None,
) -> bool:
    """Run until condition is satisfied or timeout.

    Args:
        condition: RunCondition to evaluate between scheduler steps
        timeout: Maximum time to wait (None = no timeout)

    Returns:
        True if condition was satisfied, False if timeout
    """
    start = time.monotonic()

    while True:
        # Check condition first
        if await condition.evaluate(self):
            return True

        # Check timeout
        if timeout is not None:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                return False

        # Run one scheduler step
        has_work = await self._run_one_step()

        # If no work and condition not met, we're stuck
        if not has_work:
            # One more condition check after final step
            return await condition.evaluate(self)
```

### 5. When Helper & Subscription Activation (P1)

```python
class When:
    """Builder for subscription activation conditions."""

    @staticmethod
    def correlation(model: type[BaseModel]) -> "CorrelationConditionBuilder":
        return CorrelationConditionBuilder(model)


@dataclass
class CorrelationConditionBuilder:
    model: type[BaseModel]

    def count_at_least(self, n: int) -> ArtifactCountCondition:
        return ArtifactCountCondition(model=self.model, min_count=n)

    def any_field(
        self, *, field: str, predicate: Callable[[Any], bool]
    ) -> FieldPredicateCondition:
        return FieldPredicateCondition(model=self.model, field=field, predicate=predicate)
```

### 6. ActivationComponent (P1)

**New file: `src/flock/components/orchestrator/activation.py`**

```python
class ActivationComponent(OrchestratorComponent):
    """Evaluates subscription activation conditions before scheduling."""

    name: str = "activation"
    priority: int = 15  # After circuit breaker (10), before dedup (20)

    async def on_before_agent_schedule(
        self,
        orchestrator: Flock,
        agent: Agent,
        artifacts: list[Artifact],
    ) -> list[Artifact]:
        """Filter artifacts based on activation conditions."""
        result = []
        for artifact in artifacts:
            # Find matching subscription
            subscription = self._find_subscription(agent, artifact)
            if subscription and subscription.activation:
                # Set correlation context for condition evaluation
                ctx_condition = self._bind_correlation(
                    subscription.activation,
                    artifact.correlation_id
                )
                if not await ctx_condition.evaluate(orchestrator):
                    continue  # Skip this artifact (DEFER)
            result.append(artifact)
        return result
```

---

## Data Flow

### run_until() Flow
```
1. User calls flock.run_until(condition, timeout=60)
2. Loop:
   a. Evaluate condition against orchestrator
   b. If True → return True (success)
   c. If timeout exceeded → return False
   d. Run one scheduler step (process pending work)
   e. If no pending work → final condition check → return result
   f. Repeat from (a)
```

### Subscription Activation Flow
```
1. Artifact published matching agent subscription
2. Scheduler prepares to schedule agent
3. ActivationComponent.on_before_agent_schedule() called
4. For each artifact:
   a. Find matching subscription
   b. If subscription has activation condition:
      - Evaluate condition
      - False → skip artifact (DEFER)
      - True → include artifact
5. Agent scheduled with filtered artifacts
```

---

## Testing Strategy

| Component | Test Type | Key Scenarios |
|-----------|-----------|---------------|
| ArtifactCountCondition | Unit | at_least, at_most, exactly |
| ExistsCondition | Unit | exists, not exists |
| FieldPredicateCondition | Unit | match found, no match |
| Composite conditions | Unit | And, Or, Not combinations |
| run_until() | Integration | success, timeout, idle fallback |
| ActivationComponent | Integration | defer, proceed, no condition |

---

## Migration Notes

- `run_until_idle()` remains unchanged (backward compatible)
- `run_until(Until.idle())` is equivalent to `run_until_idle()`
- Subscription activation is opt-in via `activation=` parameter
- No database schema changes required
