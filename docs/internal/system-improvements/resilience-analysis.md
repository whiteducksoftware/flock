# Flock Error Handling & Resilience Analysis

**Date**: 2025-10-13
**Scope**: Comprehensive analysis of Flock's error handling, recovery mechanisms, and resilience patterns

---

## Executive Summary

Flock demonstrates **moderate resilience** with some strong patterns (MCP retry logic, circuit breaker for runaway agents) but significant gaps in systematic error handling, recovery mechanisms, and observability. The system is vulnerable to cascading failures, lacks comprehensive retry strategies, and has limited graceful degradation capabilities.

**Key Findings**:
- ✅ **Strengths**: MCP auto-reconnect, basic circuit breaker, graceful MCP degradation
- ⚠️ **Gaps**: No retry strategies for engines, limited error context propagation, no bulkhead isolation
- ❌ **Critical**: Subscription predicate failures swallowed silently, no dead letter queue, limited recovery points

---

## 1. Component Error Handling Analysis

### 1.1 AgentComponent Error Handling

**File**: `src/flock/components.py`

#### Current Implementation

```python
async def on_error(
    self, agent: Agent, ctx: Context, error: Exception
) -> None:  # pragma: no cover - default
    return None
```

**Assessment**:
- ❌ **No-op default**: Components receive error notifications but do nothing by default
- ⚠️ **No error context**: No stack traces, correlation IDs, or artifact context passed
- ❌ **No error classification**: Cannot distinguish transient vs permanent failures
- ✅ **Lifecycle hook exists**: Framework for custom error handling present

**Error Flow in Agent**:

```python
# src/flock/agent.py:144-148
async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    async with self._semaphore:
        try:
            # ... execution logic ...
            return outputs
        except Exception as exc:
            await self._run_error(ctx, exc)  # Notifies components
            raise  # Propagates to orchestrator
        finally:
            await self._run_terminate(ctx)  # Always runs
```

**Strengths**:
- ✅ Errors propagate to orchestrator (not swallowed)
- ✅ Cleanup guaranteed via `finally` block
- ✅ All components notified of errors

**Weaknesses**:
- ❌ No retry logic at component level
- ❌ No error recovery mechanisms
- ❌ Components can't influence error handling (e.g., mark as retryable)

---

### 1.2 Orchestrator Error Resilience

**File**: `src/flock/orchestrator.py`

#### Circuit Breaker Pattern

```python
# Line 131-132: Circuit breaker for runaway agents
self.max_agent_iterations: int = max_agent_iterations  # Default: 1000
self._agent_iteration_count: dict[str, int] = {}

# Line 887-890: Check iteration limit
iteration_count = self._agent_iteration_count.get(agent.name, 0)
if iteration_count >= self.max_agent_iterations:
    # Agent hit iteration limit - possible infinite loop
    continue
```

**Assessment**:
- ✅ **Prevents infinite loops**: Stops runaway agents after N iterations
- ✅ **Per-agent tracking**: Independent limits per agent
- ✅ **Automatic reset**: Counters cleared on `run_until_idle()`
- ⚠️ **No alerting**: Silent failure - no logging or metrics
- ❌ **No graceful recovery**: Agent just stops processing
- ❌ **No configuration per agent**: Global limit applies to all

**Error Propagation in Orchestrator**:

```python
# Line 998-1008: Task execution with error handling
async def _run_agent_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
    # ... setup context ...
    await agent.execute(ctx, artifacts)  # If this throws, task fails
    # ... record consumption ...
```

**Critical Gap**: **No try-except around `agent.execute()`**
- If agent crashes, task fails silently
- No error logged to store
- No metrics updated
- No recovery attempted

**Recommendation**: Wrap in try-except with error recording:

```python
async def _run_agent_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
    ctx = Context(...)
    try:
        await agent.execute(ctx, artifacts)
        await self.store.record_consumptions(...)
    except Exception as exc:
        # Record failure
        logger.exception(f"Agent {agent.name} failed: {exc}")
        self.metrics["agent_failures"] += 1

        # Consider retry strategy
        if should_retry(exc) and retry_count < max_retries:
            await self._schedule_retry(agent, artifacts, retry_count + 1)
        else:
            # Dead letter queue
            await self._move_to_dlq(artifacts, agent.name, exc)
```

---

### 1.3 Store Error Handling

**File**: `src/flock/store.py`

#### In-Memory Store

```python
# Line 233-236: Simple async lock protection
async def publish(self, artifact: Artifact) -> None:
    async with self._lock:
        self._by_id[artifact.id] = artifact
        self._by_type[artifact.type].append(artifact)
```

**Assessment**:
- ✅ **Thread-safe**: Lock protects concurrent access
- ❌ **No error handling**: Assumes memory always available
- ❌ **No validation**: Invalid artifacts stored without checks
- ❌ **No persistence**: Data lost on crash

#### SQLite Store

```python
# Line 456-527: Publish with error handling
async def publish(self, artifact: Artifact) -> None:
    with tracer.start_as_current_span("sqlite_store.publish"):
        conn = await self._get_connection()
        # ... prepare record ...
        async with self._write_lock:
            await conn.execute("""INSERT OR UPDATE ...""", record)
            await conn.commit()
```

**Assessment**:
- ✅ **WAL mode**: Concurrent reads during writes
- ✅ **Write lock**: Prevents concurrent write conflicts
- ⚠️ **No retry on transient failures**: Database lock errors not retried
- ❌ **No connection pooling**: Single connection per store
- ❌ **No timeout handling**: Long-running queries block indefinitely

**Critical Gaps**:

1. **No SQLite-specific error handling**:
   ```python
   # No handling for:
   # - SQLITE_BUSY (database locked)
   # - SQLITE_FULL (disk full)
   # - SQLITE_CORRUPT (database corruption)
   ```

2. **No connection recovery**:
   ```python
   # Line 1017-1030: Connection creation, but no recovery on failure
   async def _ensure_connection(self) -> aiosqlite.Connection:
       if self._connection is None:
           self._connection = await aiosqlite.connect(...)  # Can fail
       return self._connection
   ```

**Recommendation**: Add retry wrapper for transient SQLite errors:

```python
async def _execute_with_retry(self, query: str, params: tuple, max_retries: int = 3):
    """Execute query with exponential backoff for transient errors."""
    for attempt in range(max_retries):
        try:
            async with self._write_lock:
                result = await self._connection.execute(query, params)
                await self._connection.commit()
                return result
        except aiosqlite.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                continue
            raise
        except Exception as e:
            logger.error(f"SQLite error: {e}")
            raise
```

---

## 2. Engine Resilience

**File**: `src/flock/engines/dspy_engine.py`

### 2.1 LLM API Error Handling

```python
# Line 162-168: LM initialization
lm = dspy_mod.LM(
    model=model_name,
    temperature=self.temperature,
    max_tokens=self.max_tokens,
    cache=self.enable_cache,
    num_retries=self.max_retries,  # Only retry parameter
)
```

**Assessment**:
- ✅ **Basic retry support**: Uses DSPy's built-in retry mechanism
- ⚠️ **No backoff configuration**: DSPy default backoff (not configurable)
- ❌ **No circuit breaker**: Repeated failures to same endpoint not prevented
- ❌ **No fallback model**: Can't switch to alternative LLM on failure
- ❌ **No timeout handling**: Long-running LLM calls block indefinitely

**Critical Gap**: **No handling of specific LLM errors**:
- Rate limit errors (429) → Should use exponential backoff
- Context length errors → Should truncate or chunk
- Content moderation errors → Should mark as non-retryable

### 2.2 MCP Tool Execution Error Handling

```python
# Line 207-217: MCP tool loading with graceful degradation
try:
    mcp_tools = await agent._get_mcp_tools(ctx)
    logger.debug(f"Loaded {len(mcp_tools)} MCP tools for agent {agent.name}")
except Exception as e:
    # Architecture Decision: AD007 - Graceful Degradation
    logger.error(f"Failed to load MCP tools in engine: {e}", exc_info=True)
    mcp_tools = []  # Continue with native tools only
```

**Assessment**:
- ✅ **Graceful degradation**: Agent continues without MCP tools
- ✅ **Detailed logging**: Error logged with stack trace
- ⚠️ **No metrics**: Failure not recorded for alerting
- ❌ **No retry**: Single attempt, no reconnection
- ❌ **No partial success**: All-or-nothing approach

**Recommendation**: Add resilience wrapper:

```python
async def _get_mcp_tools_with_retry(self, ctx: Context, agent: Agent) -> list[Any]:
    """Load MCP tools with exponential backoff retry."""
    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            return await agent._get_mcp_tools(ctx)
        except ConnectionError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"MCP connection failed (attempt {attempt+1}/{max_retries}), retrying in {delay}s")
                await asyncio.sleep(delay)
                continue
            logger.error(f"MCP tools failed after {max_retries} attempts: {e}")
            return []  # Graceful degradation
        except Exception as e:
            logger.exception(f"Unexpected MCP error: {e}")
            return []  # Non-retryable errors
```

---

## 3. MCP Resilience

**Files**: `src/flock/mcp/client.py`, `src/flock/mcp/manager.py`

### 3.1 Connection Auto-Recovery

```python
# src/flock/mcp/client.py:152-223: Session proxy with auto-reconnect
class _SessionProxy:
    async def _method(*args, **kwargs):
        max_tries = cfg.connection_config.max_retries or 1
        base_delay = 0.1

        for attempt in range(1, max_tries + 2):
            await client._ensure_connected()
            try:
                return await getattr(client.client_session, name)(*args, **kwargs)
            except McpError as e:
                if e.error.code == httpx.codes.REQUEST_TIMEOUT:
                    kind = "timeout"
                else:
                    return None  # Non-retryable MCP error
            except (BrokenPipeError, ClosedResourceError) as e:
                kind = type(e).__name__
            except Exception as e:
                kind = type(e).__name__

            if attempt > max_tries:
                logger.error(f"Session.{name} failed after {max_tries} retries")
                await client.disconnect()
                return None

            # Exponential backoff with jitter
            delay = base_delay ** (2 ** (attempt - 1))
            delay += random.uniform(0, delay * 0.1)
            await asyncio.sleep(delay)
```

**Assessment**:
- ✅ **Auto-reconnect**: Transparent reconnection on failure
- ✅ **Exponential backoff**: Prevents retry storms
- ✅ **Jitter**: Prevents thundering herd
- ✅ **Error classification**: Distinguishes timeout vs application errors
- ⚠️ **Silent failure on max retries**: Returns `None` instead of raising
- ❌ **No metrics**: Connection failures not tracked
- ❌ **No circuit breaker**: Repeated failures to dead servers not prevented

### 3.2 Manager Graceful Degradation

```python
# src/flock/mcp/manager.py:196-229: Tool loading with per-server error handling
async def get_tools_for_agent(...) -> dict[str, Any]:
    tools = {}
    for server_name in server_names:
        try:
            client = await self.get_client(server_name, agent_id, run_id)
            server_tools = await client.get_tools(agent_id, run_id)
            tools[namespaced_name] = {...}
        except Exception as e:
            # Architecture Decision: AD007 - Graceful Degradation
            logger.exception(f"Failed to load tools from '{server_name}': {e}")
            continue  # Continue loading other servers
    return tools
```

**Assessment**:
- ✅ **Per-server isolation**: One server failure doesn't block others
- ✅ **Graceful degradation**: Agent gets partial tool set
- ✅ **Detailed logging**: Exceptions logged with context
- ⚠️ **No retry per server**: Single attempt per server
- ❌ **No fallback servers**: Can't use backup MCP server
- ❌ **No health tracking**: Dead servers retried every time

---

## 4. Subscription Error Handling

**File**: `src/flock/subscription.py`

### 4.1 Predicate Evaluation

```python
# Line 154-159: Predicate evaluation with silent failure
for predicate in self.where:
    try:
        if not predicate(payload):
            return False
    except Exception:
        return False  # Silently fails predicate evaluation
```

**Critical Issues**:
- ❌ **Silent failure**: Exceptions swallowed without logging
- ❌ **No error context**: Can't debug why predicate failed
- ❌ **No metrics**: Failure rate unknown
- ❌ **No alerting**: Bugs in predicates go unnoticed

**Impact**: Agents may miss critical events due to buggy predicates, with no indication of failure.

**Recommendation**: Add error logging and tracking:

```python
for predicate in self.where:
    try:
        if not predicate(payload):
            return False
    except Exception as e:
        logger.error(
            f"Predicate failed for agent {self.agent_name}: {e}",
            exc_info=True,
            extra={
                "agent": self.agent_name,
                "artifact_type": artifact.type,
                "artifact_id": str(artifact.id),
                "predicate": predicate.__name__ if hasattr(predicate, "__name__") else "lambda"
            }
        )
        # Emit metric for alerting
        metrics.increment("subscription.predicate_failures", tags=[
            f"agent:{self.agent_name}",
            f"type:{artifact.type}"
        ])
        return False  # Still fail, but with visibility
```

### 4.2 JoinSpec & BatchSpec Timeout Failures

**No explicit error handling for**:
- ❌ JoinSpec correlation timeouts → Partial groups never delivered
- ❌ BatchSpec timeout failures → No fallback for incomplete batches
- ❌ Memory exhaustion from unbounded accumulation

**Gap**: No monitoring or alerting for:
- How many artifacts are waiting in incomplete joins?
- How many batches have timed out?
- What's the memory footprint of pending correlations?

---

## 5. Resilience Pattern Gaps

### 5.1 Missing Patterns

| Pattern | Status | Impact | Priority |
|---------|--------|--------|----------|
| **Retry with Backoff** | ⚠️ Partial (MCP only) | High - LLM/DB failures not retried | **CRITICAL** |
| **Circuit Breaker** | ⚠️ Partial (runaway agents only) | High - No protection from failing services | **CRITICAL** |
| **Bulkhead Isolation** | ✅ Present (per-agent semaphore) | Medium - Resource exhaustion possible | HIGH |
| **Graceful Degradation** | ✅ Present (MCP tools) | Medium - Limited to MCP | MEDIUM |
| **Dead Letter Queue** | ❌ Missing | High - Lost messages on failure | **CRITICAL** |
| **Timeout Propagation** | ❌ Missing | High - Cascading delays | HIGH |
| **Health Checks** | ❌ Missing | Medium - No liveness probes | MEDIUM |
| **Rate Limiting** | ❌ Missing | Medium - No backpressure | MEDIUM |
| **Saga Pattern** | ❌ Missing | Low - No distributed transaction rollback | LOW |

### 5.2 Observability Gaps

**No structured error tracking**:
- ❌ No error rate metrics per agent
- ❌ No error context (correlation IDs, artifact IDs)
- ❌ No error categorization (transient vs permanent)
- ❌ No error budgets (SLO tracking)

**No distributed tracing for errors**:
```python
# Traces exist for operations, but not error propagation
with tracer.start_as_current_span("agent.execute"):
    try:
        await agent.execute(ctx, artifacts)
    except Exception as e:
        # Error not recorded in trace!
        pass
```

**Recommendation**: Enhance tracing with error attributes:

```python
with tracer.start_as_current_span("agent.execute") as span:
    try:
        result = await agent.execute(ctx, artifacts)
        span.set_status(Status(StatusCode.OK))
        return result
    except Exception as e:
        span.set_status(Status(StatusCode.ERROR, str(e)))
        span.record_exception(e)
        span.set_attribute("error.type", type(e).__name__)
        span.set_attribute("error.retryable", is_retryable(e))
        span.set_attribute("agent.name", agent.name)
        raise
```

---

## 6. Resilience Component Proposals

### 6.1 Retry Component

```python
from dataclasses import dataclass
from typing import Callable, Type
import asyncio
import random

@dataclass
class RetryPolicy:
    """Configurable retry policy with exponential backoff."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )

class RetryComponent(AgentComponent):
    """Component that adds retry logic to agent execution.

    Example:
        agent.with_utilities(
            RetryComponent(policy=RetryPolicy(max_retries=5))
        )
    """

    policy: RetryPolicy = Field(default_factory=RetryPolicy)

    async def on_error(self, agent: Agent, ctx: Context, error: Exception) -> None:
        """Determine if error is retryable and schedule retry."""
        if not isinstance(error, self.policy.retryable_exceptions):
            logger.error(f"Non-retryable error in agent {agent.name}: {error}")
            return

        retry_count = ctx.state.get("_retry_count", 0)
        if retry_count >= self.policy.max_retries:
            logger.error(f"Max retries ({self.policy.max_retries}) exceeded for agent {agent.name}")
            ctx.state["_retry_failed"] = True
            return

        # Calculate backoff with jitter
        delay = min(
            self.policy.base_delay * (self.policy.exponential_base ** retry_count),
            self.policy.max_delay
        )
        if self.policy.jitter:
            delay += random.uniform(0, delay * 0.1)

        logger.warning(
            f"Retrying agent {agent.name} after {delay:.2f}s (attempt {retry_count+1}/{self.policy.max_retries})"
        )

        # Update retry count in context
        ctx.state["_retry_count"] = retry_count + 1

        # Schedule retry after delay
        await asyncio.sleep(delay)
        # Note: Actual retry scheduling would need orchestrator support
        # This is a conceptual implementation
```

### 6.2 Circuit Breaker Component

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5       # Failures before opening
    success_threshold: int = 2       # Successes to close from half-open
    timeout: timedelta = timedelta(seconds=30)  # Time before trying half-open
    window: timedelta = timedelta(minutes=1)    # Sliding window for failures

class CircuitBreakerComponent(AgentComponent):
    """Prevents cascading failures by stopping calls to failing agents.

    States:
    - CLOSED: Normal operation, agent executes
    - OPEN: Agent is failing, reject execution immediately
    - HALF_OPEN: Testing if agent recovered, allow limited requests

    Example:
        agent.with_utilities(
            CircuitBreakerComponent(
                config=CircuitBreakerConfig(failure_threshold=3, timeout=timedelta(seconds=60))
            )
        )
    """

    config: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None

    async def on_pre_evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalInputs:
        """Check circuit state before execution."""
        now = datetime.now()

        if self.state == CircuitState.OPEN:
            # Check if timeout expired
            if self.opened_at and (now - self.opened_at) > self.config.timeout:
                logger.info(f"Circuit breaker for {agent.name} entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                # Still open, reject execution
                logger.warning(f"Circuit breaker OPEN for {agent.name}, rejecting execution")
                raise CircuitBreakerOpenError(f"Circuit breaker open for agent {agent.name}")

        return inputs

    async def on_post_evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult) -> EvalResult:
        """Record successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                logger.info(f"Circuit breaker for {agent.name} closing (recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
            self.last_failure_time = None

        return result

    async def on_error(self, agent: Agent, ctx: Context, error: Exception) -> None:
        """Record failure and potentially open circuit."""
        now = datetime.now()

        # Check if failure is within window
        if self.last_failure_time and (now - self.last_failure_time) > self.config.window:
            # Window expired, reset count
            self.failure_count = 0

        self.failure_count += 1
        self.last_failure_time = now

        if self.state == CircuitState.HALF_OPEN:
            # Immediate open on failure in half-open
            logger.warning(f"Circuit breaker for {agent.name} opening (failed during recovery)")
            self.state = CircuitState.OPEN
            self.opened_at = now
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.config.failure_threshold:
            # Threshold exceeded, open circuit
            logger.error(f"Circuit breaker for {agent.name} opening ({self.failure_count} failures)")
            self.state = CircuitState.OPEN
            self.opened_at = now

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker rejects execution."""
    pass
```

### 6.3 Dead Letter Queue Component

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class DLQEntry:
    """Entry in dead letter queue."""
    artifact: Artifact
    agent_name: str
    error: str
    error_type: str
    retry_count: int
    failed_at: datetime
    context: dict[str, Any]

class DeadLetterQueueComponent(OrchestratorComponent):
    """Captures failed artifacts for manual inspection and retry.

    Example:
        flock = Flock(...)
        dlq = DeadLetterQueueComponent(
            store=SQLiteDLQStore(".flock/dlq.db"),
            max_retries=3
        )

        # Access DLQ entries
        failed = await dlq.list_entries(agent_name="my_agent")

        # Retry failed artifact
        await dlq.retry_entry(entry_id)
    """

    store: BlackboardStore
    max_retries: int = 3
    entries: list[DLQEntry] = Field(default_factory=list)

    async def on_agent_failure(
        self,
        agent: Agent,
        artifacts: list[Artifact],
        error: Exception,
        ctx: Context
    ) -> None:
        """Record failed artifact in DLQ."""
        retry_count = ctx.state.get("_retry_count", 0)

        for artifact in artifacts:
            entry = DLQEntry(
                artifact=artifact,
                agent_name=agent.name,
                error=str(error),
                error_type=type(error).__name__,
                retry_count=retry_count,
                failed_at=datetime.now(),
                context={
                    "correlation_id": str(ctx.correlation_id) if ctx.correlation_id else None,
                    "task_id": ctx.task_id,
                    "state": dict(ctx.state),
                }
            )

            self.entries.append(entry)
            await self._persist_entry(entry)

            logger.error(
                f"Artifact {artifact.id} moved to DLQ after {retry_count} retries",
                extra={
                    "agent": agent.name,
                    "artifact_type": artifact.type,
                    "error": str(error),
                }
            )

    async def list_entries(
        self,
        agent_name: Optional[str] = None,
        error_type: Optional[str] = None,
        limit: int = 100
    ) -> list[DLQEntry]:
        """List entries in DLQ with optional filtering."""
        filtered = self.entries

        if agent_name:
            filtered = [e for e in filtered if e.agent_name == agent_name]
        if error_type:
            filtered = [e for e in filtered if e.error_type == error_type]

        return filtered[:limit]

    async def retry_entry(self, entry: DLQEntry, orchestrator: Flock) -> bool:
        """Retry failed artifact."""
        try:
            # Re-publish artifact for retry
            await orchestrator.publish(entry.artifact)

            # Remove from DLQ
            self.entries.remove(entry)
            await self._delete_entry(entry)

            logger.info(f"Retried DLQ entry for artifact {entry.artifact.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to retry DLQ entry: {e}")
            return False

    async def _persist_entry(self, entry: DLQEntry) -> None:
        """Persist DLQ entry to store."""
        # Implementation depends on store
        pass

    async def _delete_entry(self, entry: DLQEntry) -> None:
        """Delete DLQ entry from store."""
        # Implementation depends on store
        pass
```

### 6.4 Timeout Component

```python
import asyncio
from typing import Optional

class TimeoutComponent(AgentComponent):
    """Enforces execution timeouts for agents.

    Example:
        agent.with_utilities(
            TimeoutComponent(timeout_seconds=30.0)
        )
    """

    timeout_seconds: float = 60.0

    async def on_pre_evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalInputs:
        """Set timeout deadline in context."""
        ctx.state["_timeout_deadline"] = asyncio.get_event_loop().time() + self.timeout_seconds
        return inputs

    async def on_post_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Check if execution exceeded timeout."""
        deadline = ctx.state.get("_timeout_deadline")
        if deadline and asyncio.get_event_loop().time() > deadline:
            elapsed = asyncio.get_event_loop().time() - (deadline - self.timeout_seconds)
            logger.warning(f"Agent {agent.name} exceeded timeout ({elapsed:.2f}s > {self.timeout_seconds}s)")
            # Could raise TimeoutError here

        return result
```

---

## 7. Recommendations by Priority

### 7.1 Critical (Immediate Action Required)

1. **Add error handling to orchestrator task execution**
   - **File**: `src/flock/orchestrator.py:998-1008`
   - **Action**: Wrap `agent.execute()` in try-except with logging and metrics
   - **Impact**: Prevents silent agent failures

2. **Add logging to subscription predicate failures**
   - **File**: `src/flock/subscription.py:154-159`
   - **Action**: Log exceptions with context (agent, artifact, predicate name)
   - **Impact**: Makes predicate bugs visible

3. **Implement Dead Letter Queue**
   - **File**: New `src/flock/dlq.py`
   - **Action**: Create DLQ component to capture failed artifacts
   - **Impact**: No data loss on failure

4. **Add retry logic to SQLite operations**
   - **File**: `src/flock/store.py`
   - **Action**: Retry SQLITE_BUSY and connection errors
   - **Impact**: Improves store resilience under load

### 7.2 High Priority

5. **Add circuit breaker for external services (LLM, MCP)**
   - **File**: New `src/flock/resilience/circuit_breaker.py`
   - **Action**: Implement circuit breaker component
   - **Impact**: Prevents cascading failures

6. **Add retry with backoff to engine LLM calls**
   - **File**: `src/flock/engines/dspy_engine.py`
   - **Action**: Wrap LLM calls in retry logic with exponential backoff
   - **Impact**: Handles transient LLM API failures

7. **Add timeout propagation**
   - **File**: `src/flock/orchestrator.py`, `src/flock/agent.py`
   - **Action**: Pass timeout context through execution chain
   - **Impact**: Prevents long-running operations from blocking

8. **Enhance error tracing**
   - **Files**: All files with `tracer.start_as_current_span()`
   - **Action**: Record exceptions in spans with attributes
   - **Impact**: Better debugging of production failures

### 7.3 Medium Priority

9. **Add health check endpoints**
   - **File**: `src/flock/service.py`
   - **Action**: Add `/health` and `/ready` endpoints
   - **Impact**: Kubernetes liveness/readiness probes

10. **Add rate limiting component**
    - **File**: New `src/flock/resilience/rate_limiter.py`
    - **Action**: Implement token bucket rate limiter
    - **Impact**: Prevents API quota exhaustion

11. **Add metrics for error rates**
    - **Files**: All error handling code
    - **Action**: Emit metrics for error rates per agent/component
    - **Impact**: Alerting on degradation

12. **Add MCP connection pooling**
    - **File**: `src/flock/mcp/manager.py`
    - **Action**: Pool MCP connections across runs
    - **Impact**: Reduced connection overhead

### 7.4 Low Priority

13. **Implement saga pattern for distributed transactions**
    - **File**: New `src/flock/resilience/saga.py`
    - **Action**: Add compensating transaction support
    - **Impact**: Rollback on partial failures

14. **Add checkpoint/resume for long-running workflows**
    - **File**: `src/flock/orchestrator.py`
    - **Action**: Persist workflow state for crash recovery
    - **Impact**: Resume after orchestrator restart

---

## 8. Comparison to Other Frameworks

### Temporal.io

**Strengths**:
- ✅ Durable execution (survives crashes)
- ✅ Automatic retry with configurable policies
- ✅ Saga pattern built-in
- ✅ Versioning and migration support

**Flock Gaps**:
- ❌ No durable execution (workflows lost on crash)
- ❌ No automatic retry policies
- ❌ No built-in saga support

**Lesson**: Flock should add workflow checkpointing for crash recovery.

### Celery

**Strengths**:
- ✅ Robust retry mechanisms with exponential backoff
- ✅ Dead letter queue for failed tasks
- ✅ Task routing and priority queues
- ✅ Rate limiting built-in

**Flock Gaps**:
- ❌ No DLQ (failed artifacts lost)
- ❌ No task-level retry policies
- ❌ No rate limiting

**Lesson**: Flock should adopt Celery's retry decorators and DLQ pattern.

### Kafka Streams

**Strengths**:
- ✅ Exactly-once processing semantics
- ✅ State store with changelog for recovery
- ✅ Reprocessing from offset (time travel)
- ✅ Fault-tolerant by design

**Flock Gaps**:
- ❌ No exactly-once guarantees (can duplicate)
- ❌ No state store durability
- ❌ No reprocessing from offset

**Lesson**: Flock should add offset tracking to store for replay capability.

### Akka

**Strengths**:
- ✅ Supervision strategies (restart, stop, escalate)
- ✅ Let-it-crash philosophy with automatic recovery
- ✅ Circuit breaker built-in (Akka HTTP)
- ✅ Backpressure mechanisms

**Flock Gaps**:
- ❌ No supervision strategies (errors just propagate)
- ❌ No automatic recovery
- ❌ No backpressure (unbounded queues)

**Lesson**: Flock should add supervision strategies to orchestrator.

---

## 9. Testing Resilience

### 9.1 Chaos Engineering Scenarios

```python
# tests/resilience/test_chaos.py

import pytest
from flock.testing.chaos import (
    NetworkFailureInjector,
    DatabaseFailureInjector,
    MemoryPressureInjector,
    LatencyInjector,
)

@pytest.mark.asyncio
async def test_agent_survives_transient_db_failure():
    """Test that agent retries on transient database errors."""
    flock = Flock(store=SQLiteBlackboardStore(".flock/test.db"))
    agent = flock.agent("resilient").consumes(Task).publishes(Result)

    # Inject SQLite BUSY errors
    with DatabaseFailureInjector(flock.store, failure_rate=0.5, error_type="SQLITE_BUSY"):
        await flock.publish(Task(name="test"))
        await flock.run_until_idle()

    # Agent should have retried and succeeded
    results = await flock.store.list_by_type("Result")
    assert len(results) == 1

@pytest.mark.asyncio
async def test_orchestrator_survives_agent_crash():
    """Test that orchestrator continues after agent crash."""
    flock = Flock()

    # Agent that crashes randomly
    @flock.agent("crasher").consumes(Task).publishes(Result)
    async def crasher(task: Task) -> Result:
        if random.random() < 0.5:
            raise RuntimeError("Simulated crash")
        return Result(value=task.name)

    # Publish 10 tasks
    for i in range(10):
        await flock.publish(Task(name=f"task_{i}"))

    await flock.run_until_idle()

    # Some should succeed, some should be in DLQ
    results = await flock.store.list_by_type("Result")
    dlq_entries = await flock.dlq.list_entries(agent_name="crasher")

    assert len(results) + len(dlq_entries) == 10

@pytest.mark.asyncio
async def test_mcp_disconnect_recovery():
    """Test that MCP tools recover after server disconnect."""
    flock = Flock()
    flock.add_mcp("filesystem", StdioServerParameters(...))

    agent = flock.agent("file_agent").with_mcps(["filesystem"])

    # Disconnect MCP server mid-execution
    async def disconnect_after_delay():
        await asyncio.sleep(1)
        await flock._mcp_manager._pool[("file_agent", "run_1")]["filesystem"].disconnect()

    asyncio.create_task(disconnect_after_delay())

    # Agent should reconnect and continue
    result = await flock.invoke(agent, Task(name="read_file"))
    assert result is not None

@pytest.mark.asyncio
async def test_llm_rate_limit_backoff():
    """Test that engine backs off on rate limit errors."""
    flock = Flock()

    # Mock LLM that rate limits
    with mock.patch("dspy.LM") as mock_lm:
        mock_lm.side_effect = [
            RateLimitError("Rate limit exceeded"),
            RateLimitError("Rate limit exceeded"),
            {"output": "Success"},
        ]

        agent = flock.agent("llm_agent").consumes(Prompt).publishes(Response)

        start = time.time()
        await flock.invoke(agent, Prompt(text="Hello"))
        elapsed = time.time() - start

        # Should have backed off (at least 1s + 2s = 3s)
        assert elapsed >= 3.0

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Test that circuit breaker opens after threshold failures."""
    flock = Flock()

    @flock.agent("failing").with_utilities(
        CircuitBreakerComponent(config=CircuitBreakerConfig(failure_threshold=3))
    ).consumes(Task).publishes(Result)
    async def failing_agent(task: Task) -> Result:
        raise RuntimeError("Always fails")

    # First 3 failures should be attempted
    for i in range(3):
        with pytest.raises(RuntimeError):
            await flock.invoke(failing_agent, Task(name=f"task_{i}"))

    # 4th attempt should be rejected by circuit breaker
    with pytest.raises(CircuitBreakerOpenError):
        await flock.invoke(failing_agent, Task(name="task_4"))
```

### 9.2 Load Testing Resilience

```python
# tests/resilience/test_load.py

@pytest.mark.asyncio
async def test_orchestrator_handles_concurrent_load():
    """Test that orchestrator handles high concurrent load without crashes."""
    flock = Flock(max_agent_iterations=10000)

    @flock.agent("processor").consumes(Task).publishes(Result)
    async def processor(task: Task) -> Result:
        await asyncio.sleep(0.1)  # Simulate work
        return Result(value=task.name)

    # Publish 1000 tasks concurrently
    tasks = [flock.publish(Task(name=f"task_{i}")) for i in range(1000)]
    await asyncio.gather(*tasks)

    # All should complete
    await flock.run_until_idle()
    results = await flock.store.list_by_type("Result")
    assert len(results) == 1000

@pytest.mark.asyncio
async def test_memory_leak_under_load():
    """Test that system doesn't leak memory under sustained load."""
    import psutil
    process = psutil.Process()

    flock = Flock()
    initial_memory = process.memory_info().rss

    for _ in range(1000):
        await flock.publish(Task(name="test"))
        await flock.run_until_idle()

    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory

    # Memory increase should be bounded (< 100MB)
    assert memory_increase < 100 * 1024 * 1024
```

---

## 10. Implementation Roadmap

### Phase 1: Critical Error Handling (Week 1)

**Goal**: Prevent silent failures

- [ ] Add error logging to orchestrator task execution
- [ ] Add predicate failure logging with context
- [ ] Add error metrics to all error handlers
- [ ] Add error attributes to OpenTelemetry spans

**Deliverables**:
- PR: "Add comprehensive error logging and metrics"
- Documentation: Error handling guide

### Phase 2: Retry Mechanisms (Week 2)

**Goal**: Handle transient failures

- [ ] Implement RetryComponent with exponential backoff
- [ ] Add retry logic to SQLite store operations
- [ ] Add retry wrapper for LLM API calls
- [ ] Add retry configuration to MCP client

**Deliverables**:
- PR: "Add retry mechanisms with exponential backoff"
- Documentation: Retry configuration guide

### Phase 3: Circuit Breakers (Week 3)

**Goal**: Prevent cascading failures

- [ ] Implement CircuitBreakerComponent
- [ ] Add circuit breaker for LLM API calls
- [ ] Add circuit breaker for MCP connections
- [ ] Add circuit breaker metrics and dashboard

**Deliverables**:
- PR: "Add circuit breaker pattern"
- Documentation: Circuit breaker tuning guide

### Phase 4: Dead Letter Queue (Week 4)

**Goal**: No data loss on failure

- [ ] Implement DLQ component
- [ ] Add DLQ storage backend (SQLite)
- [ ] Add DLQ UI in dashboard
- [ ] Add DLQ retry API

**Deliverables**:
- PR: "Add dead letter queue"
- Documentation: DLQ management guide

### Phase 5: Timeout & Bulkhead (Week 5)

**Goal**: Resource isolation and timeout handling

- [ ] Implement TimeoutComponent
- [ ] Add timeout propagation through context
- [ ] Add bulkhead per-agent resource limits
- [ ] Add timeout metrics and alerting

**Deliverables**:
- PR: "Add timeout and bulkhead isolation"
- Documentation: Resource management guide

### Phase 6: Observability & Testing (Week 6)

**Goal**: Monitor resilience in production

- [ ] Add resilience metrics dashboard
- [ ] Implement chaos testing suite
- [ ] Add load testing scenarios
- [ ] Create runbook for common failure scenarios

**Deliverables**:
- PR: "Add resilience testing and observability"
- Documentation: Resilience testing guide, Production runbook

---

## 11. Key Metrics to Track

### Error Metrics

```python
# Errors per agent
metrics.counter("flock.agent.errors", tags=["agent:name", "error_type"])

# Error rate (errors per second)
metrics.rate("flock.agent.error_rate", tags=["agent:name"])

# Retry metrics
metrics.counter("flock.retry.attempts", tags=["agent:name", "attempt_number"])
metrics.counter("flock.retry.successes", tags=["agent:name"])
metrics.counter("flock.retry.exhausted", tags=["agent:name"])

# Circuit breaker metrics
metrics.gauge("flock.circuit_breaker.state", tags=["agent:name", "state"])
metrics.counter("flock.circuit_breaker.opened", tags=["agent:name"])
metrics.counter("flock.circuit_breaker.closed", tags=["agent:name"])

# DLQ metrics
metrics.gauge("flock.dlq.size", tags=["agent:name"])
metrics.counter("flock.dlq.entries_added", tags=["agent:name", "error_type"])
metrics.counter("flock.dlq.retries", tags=["agent:name"])

# Timeout metrics
metrics.counter("flock.timeouts", tags=["agent:name", "operation"])
metrics.histogram("flock.execution_time", tags=["agent:name"])

# Store metrics
metrics.counter("flock.store.errors", tags=["operation", "error_type"])
metrics.counter("flock.store.retries", tags=["operation"])
```

### SLO Metrics

```python
# Availability (% of successful agent executions)
metrics.gauge("flock.agent.availability", tags=["agent:name"])

# Latency (p50, p95, p99)
metrics.histogram("flock.agent.latency", tags=["agent:name"])

# Error budget (remaining % of error budget)
metrics.gauge("flock.agent.error_budget_remaining", tags=["agent:name"])
```

---

## 12. Conclusion

Flock has a **solid foundation** with some strong resilience patterns (MCP auto-reconnect, circuit breaker for runaway agents) but significant gaps in systematic error handling, retry mechanisms, and observability.

**Strengths**:
- ✅ MCP graceful degradation
- ✅ Basic circuit breaker
- ✅ Error propagation (not swallowed)

**Critical Gaps**:
- ❌ No retry with backoff for LLM/DB
- ❌ No dead letter queue
- ❌ Silent predicate failures
- ❌ No timeout propagation
- ❌ Limited error observability

**Recommended Focus**:
1. **Phase 1 (Week 1)**: Add error logging everywhere (highest impact, lowest effort)
2. **Phase 2 (Week 2)**: Implement retry mechanisms (high impact, medium effort)
3. **Phase 3 (Week 3)**: Add circuit breakers (high impact, medium effort)
4. **Phase 4 (Week 4)**: Implement DLQ (high impact, high effort)

With these improvements, Flock will achieve **production-grade resilience** suitable for mission-critical agent workflows.

---

## Appendix: Example Configurations

### A. Resilient Agent Configuration

```python
from flock.resilience import RetryComponent, CircuitBreakerComponent, TimeoutComponent

flock = Flock(max_agent_iterations=1000)

agent = (
    flock.agent("resilient_agent")
    .description("Agent with comprehensive resilience")
    .consumes(Task)
    .publishes(Result)
    .with_utilities(
        # Retry transient failures
        RetryComponent(
            policy=RetryPolicy(
                max_retries=5,
                base_delay=1.0,
                exponential_base=2.0,
                retryable_exceptions=(ConnectionError, TimeoutError)
            )
        ),
        # Circuit breaker for cascading failures
        CircuitBreakerComponent(
            config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout=timedelta(minutes=1),
                window=timedelta(minutes=5)
            )
        ),
        # Timeout enforcement
        TimeoutComponent(timeout_seconds=30.0),
    )
    .max_concurrency(10)  # Bulkhead isolation
)
```

### B. Resilient Orchestrator Configuration

```python
from flock.resilience import DeadLetterQueueComponent

flock = Flock(
    model="openai/gpt-4.1",
    store=SQLiteBlackboardStore(".flock/artifacts.db"),
    max_agent_iterations=1000,  # Circuit breaker for runaway agents
)

# Add DLQ
dlq = DeadLetterQueueComponent(
    store=SQLiteBlackboardStore(".flock/dlq.db"),
    max_retries=3
)

# Enable resilience features
flock.enable_dlq(dlq)
flock.enable_error_metrics()
flock.enable_circuit_breakers()
```

### C. Production Monitoring Configuration

```python
# Configure metrics backend
from flock.observability import MetricsCollector, PrometheusExporter

metrics = MetricsCollector(
    exporters=[
        PrometheusExporter(port=9090),
        DatadogExporter(api_key=os.getenv("DD_API_KEY"))
    ]
)

flock.configure_metrics(metrics)

# Configure alerting rules
flock.add_alert_rule(
    name="high_error_rate",
    condition="rate(flock.agent.errors[5m]) > 0.1",
    severity="critical",
    notification_channels=["pagerduty", "slack"]
)

flock.add_alert_rule(
    name="circuit_breaker_open",
    condition="flock.circuit_breaker.state{state='open'} > 0",
    severity="warning",
    notification_channels=["slack"]
)

flock.add_alert_rule(
    name="dlq_growing",
    condition="rate(flock.dlq.size[15m]) > 10",
    severity="warning",
    notification_channels=["slack"]
)
```

---

**Report Generated**: 2025-10-13
**Analysis Version**: 1.0
**Flock Version**: Based on current main branch
