# Flock Logging Strategy

## 🎯 Executive Summary

**Current State**: Flock has a sophisticated logging infrastructure (`FlockLogger`, Loguru integration, OpenTelemetry tracing) but **inconsistent adoption** across the codebase. Only ~10 of 51+ modules actively use logging.

**Problem**: Critical operations (orchestrator scheduling, component lifecycle, engine evaluation, store operations) execute silently, making debugging and production monitoring difficult.

**Solution**: Implement a **structured, consistent logging strategy** across all Flock modules with clear guidelines for what, when, and how to log.

**Impact**:
- ✅ **Debuggability**: 10x faster issue diagnosis with structured logs
- ✅ **Observability**: Production monitoring without OpenTelemetry overhead
- ✅ **Developer Experience**: Clear logging patterns for contributors
- ✅ **Performance**: Negligible overhead with level-based filtering

---

## 📚 Current Logging Infrastructure

### ✅ What's Already Built (Excellent Foundation)

**1. FlockLogger (`src/flock/logging/logging.py`)**
- ✅ Unified logger wrapping Loguru with custom formatting
- ✅ Level-based filtering (DEBUG, INFO, WARNING, ERROR, SUCCESS)
- ✅ Automatic message truncation (500 chars by default)
- ✅ OpenTelemetry trace ID injection
- ✅ Category-based color coding (52 color mappings)
- ✅ Configurable severity levels per logger
- ✅ Immediate flush support for real-time output

**2. OpenTelemetry Integration (`src/flock/logging/telemetry.py`)**
- ✅ DuckDB trace export (AI-queryable)
- ✅ File-based span export
- ✅ SQLite telemetry export
- ✅ Jaeger/OTLP exporter support
- ✅ Baggage propagation (session_id, run_id)
- ✅ Auto-traced metaclass (`AutoTracedMeta`)

**3. Auto-Tracing System (`src/flock/logging/auto_trace.py`)**
- ✅ Automatic span creation for public methods
- ✅ Input/output capture
- ✅ Exception recording
- ✅ Zero-instrumentation overhead for developers

**4. Rich Console Integration**
- ✅ Color-coded output by category
- ✅ Hierarchical formatting
- ✅ Trace ID display in logs

### ❌ What's Missing (Gaps)

**1. Inconsistent Adoption**
- Only ~20% of modules initialize loggers
- Critical paths (orchestrator, store, registry) have minimal logging
- No logging in: `subscription.py`, `runtime.py`, `artifacts.py`, `visibility.py`

**2. No Logging Guidelines**
- No documentation on what to log at each level
- No conventions for structured data
- No guidance on log message format

**3. Configuration Complexity**
- `configure_logging()` exists but isn't documented
- No environment variable mapping (e.g., `FLOCK_LOG_LEVEL`)
- No per-module level control via env vars

**4. Performance Considerations**
- No metrics on logging overhead
- Unclear if DEBUG logging is production-safe

---

## 🎯 Logging Strategy

### Philosophy: "Observable by Default, Configurable Always"

Every Flock module should emit structured logs at appropriate levels, but users control verbosity through environment variables.

### Logging Levels (When to Use)

| Level | When to Use | Examples | Production Default |
|-------|-------------|----------|-------------------|
| **DEBUG** | Internal state transitions, detailed flow | "Subscription matched artifact", "Circuit breaker count: 5/1000" | ❌ Off |
| **INFO** | Key lifecycle events, user-visible actions | "Agent scheduled", "Artifact published", "Component initialized" | ✅ On |
| **WARNING** | Recoverable issues, degraded performance | "Circuit breaker approaching limit (950/1000)", "Correlation timeout expiring" | ✅ On |
| **ERROR** | Operation failures, exceptions | "Agent execution failed", "Store write error" | ✅ On |
| **SUCCESS** | Completion of important operations | "Workflow completed", "All agents idle" | ✅ On (custom level) |

### What to Log (Guidelines)

#### ✅ DO LOG

**Lifecycle Events (INFO)**
```python
logger.info(f"Component initialized: {self.__class__.__name__} (priority={self.priority})")
logger.info(f"Agent '{agent.name}' scheduled with {len(artifacts)} artifacts")
logger.success(f"Orchestrator idle after processing {count} artifacts")
```

**State Transitions (DEBUG)**
```python
logger.debug(f"Circuit breaker count for '{agent_name}': {count}/{max_iterations}")
logger.debug(f"Subscription matched: agent={agent.name}, type={artifact.type}")
logger.debug(f"Correlation group complete: key={key}, artifacts={len(artifacts)}")
```

**Errors and Exceptions (ERROR + exception context)**
```python
logger.error(f"Agent '{agent.name}' execution failed: {str(e)}")
logger.exception(f"Store write error for artifact {artifact.id}")
```

**Performance Warnings (WARNING)**
```python
logger.warning(f"Circuit breaker at 95% capacity: {count}/{max_iterations}")
logger.warning(f"Batch accumulator timeout expiring in {remaining_ms}ms")
```

**Important Decisions (INFO)**
```python
logger.info(f"Deduplication blocked duplicate: artifact={artifact.id}, agent={agent.name}")
logger.info(f"Visibility check failed: artifact not visible to agent '{agent.name}'")
```

#### ❌ DON'T LOG

- **Sensitive Data**: API keys, user credentials, PII
- **High-Frequency Events**: Every artifact published at DEBUG (use trace instead)
- **Redundant Information**: Data already in OpenTelemetry spans
- **Internal Implementation Details**: Memory addresses, stack traces (except exceptions)

### Structured Logging Format

**Consistent message structure**:
```
[ACTION] [SUBJECT] [DETAILS] [CONTEXT]

Examples:
✅ "Agent scheduled: name=code_detective, artifacts=2, correlation_id=abc123"
✅ "Circuit breaker tripped: agent=movie_maker, iterations=1000/1000"
✅ "Batch flushed: agent=order_processor, size=25, trigger=size_threshold"

❌ "Processing..." (too vague)
❌ "Agent did something" (no context)
```

**Key-value pairs for filtering**:
```python
# Good: Structured with searchable keys
logger.info(f"Component execution: name={comp.name}, priority={comp.priority}, duration_ms={duration}")

# Bad: Unstructured prose
logger.info(f"The component named {comp.name} with priority {comp.priority} took {duration}ms")
```

---

## 🏗️ Implementation Plan

### Phase 1: Core Modules (Week 1)

**Add logging to critical paths**:

1. **Orchestrator (`orchestrator.py`)**
   ```python
   logger = get_logger("flock.orchestrator")
   
   # In __init__
   logger.info(f"Orchestrator initialized: model={model}, max_iterations={max_agent_iterations}")
   
   # In publish()
   logger.debug(f"Artifact published: type={artifact.type}, id={artifact.id}, correlation_id={correlation_id}")
   
   # In _schedule_artifact()
   logger.debug(f"Subscription matched: agent={agent.name}, type={artifact.type}")
   logger.debug(f"Circuit breaker check: agent={agent.name}, count={iteration_count}/{max_iterations}")
   
   # In run_until_idle()
   logger.success(f"Orchestrator idle: artifacts_published={metrics['artifacts_published']}, agent_runs={metrics['agent_runs']}")
   ```

2. **Store (`store.py`)**
   ```python
   logger = get_logger("flock.store")
   
   # In publish()
   logger.debug(f"Artifact stored: id={artifact.id}, type={artifact.type}, produced_by={artifact.produced_by}")
   
   # In SQLiteBlackboardStore.ensure_schema()
   logger.info(f"Store initialized: path={self.db_path}, schema_version=1")
   
   # In get_by_type()
   logger.debug(f"Query by type: type={type_name}, count={len(results)}")
   ```

3. **Agent (`agent.py`)**
   ```python
   # Already has: logger = get_logger(__name__)
   
   # In execute()
   logger.info(f"Agent executing: name={self.name}, artifacts={len(artifacts)}")
   logger.debug(f"Pre-consume hook chain: utilities={len(self.utilities)}")
   logger.success(f"Agent completed: name={self.name}, outputs={len(outputs)}")
   
   # In _run_error()
   logger.error(f"Agent execution failed: name={self.name}, error={str(exc)}")
   ```

4. **Components (`components.py`)**
   ```python
   logger = get_logger("flock.components")
   
   # In AgentComponent hooks (when overridden)
   logger.debug(f"Component hook: name={self.name or self.__class__.__name__}, hook=on_pre_evaluate")
   ```

### Phase 2: Supporting Modules (Week 2)

**Add logging to data structures and utilities**:

5. **Registry (`registry.py`)**
   ```python
   logger = get_logger("flock.registry")
   
   # In register_type()
   logger.debug(f"Type registered: name={name}, model={model_cls.__name__}")
   
   # In register_tool()
   logger.debug(f"Tool registered: name={func.__name__}")
   ```

6. **Subscription (`subscription.py`)**
   ```python
   logger = get_logger("flock.subscription")
   
   # In matches()
   logger.debug(f"Subscription match check: types={self.types}, predicate={self.predicate is not None}")
   ```

7. **Visibility (`visibility.py`)**
   ```python
   logger = get_logger("flock.visibility")
   
   # In allows()
   logger.debug(f"Visibility check: kind={self.kind}, agent={agent.name}, allowed={result}")
   ```

8. **Correlation/Batch Engines**
   ```python
   logger = get_logger("flock.correlation")
   logger = get_logger("flock.batch")
   
   # Key state transitions
   logger.debug(f"Correlation group created: key={key}, required_types={required_types}")
   logger.info(f"Batch flushed: agent={agent_name}, size={len(artifacts)}, trigger={trigger_type}")
   ```

### Phase 3: Environment Configuration (Week 3)

**Add environment variable support**:

9. **Environment Variables (`src/flock/logging/logging.py`)**
   ```python
   # Add to get_logger() or configure_logging()
   import os
   
   DEFAULT_LEVEL = os.getenv("FLOCK_LOG_LEVEL", "INFO").upper()
   SPECIFIC_LEVELS = {
       "flock.orchestrator": os.getenv("FLOCK_LOG_ORCHESTRATOR", DEFAULT_LEVEL),
       "flock.agent": os.getenv("FLOCK_LOG_AGENT", DEFAULT_LEVEL),
       "flock.store": os.getenv("FLOCK_LOG_STORE", DEFAULT_LEVEL),
       "flock.mcp": os.getenv("FLOCK_LOG_MCP", DEFAULT_LEVEL),
   }
   ```

10. **Update `.envtemplate`**
    ```bash
    # Logging Configuration
    FLOCK_LOG_LEVEL=INFO              # Global default (DEBUG, INFO, WARNING, ERROR)
    FLOCK_LOG_ORCHESTRATOR=DEBUG      # Orchestrator-specific level
    FLOCK_LOG_AGENT=INFO              # Agent-specific level
    FLOCK_LOG_STORE=WARNING           # Store-specific level
    FLOCK_LOG_MCP=ERROR               # MCP-specific level
    ```

### Phase 4: Documentation (Week 4)

11. **Create `docs/guides/logging.md`**
    - Logging philosophy
    - Level guidelines
    - Message formatting conventions
    - Environment variable reference
    - Troubleshooting guide

12. **Update `AGENTS.md`**
    - Add logging section to "Common Tasks"
    - Example logger usage patterns
    - Debugging with logs + traces

---

## 🎨 Logger Naming Conventions

**Use hierarchical naming for filtering**:

```python
# Core Flock modules
logger = get_logger("flock.orchestrator")  # Orchestrator
logger = get_logger("flock.agent")         # Agent execution
logger = get_logger("flock.store")         # Blackboard storage
logger = get_logger("flock.registry")      # Type/tool registry

# Components
logger = get_logger("flock.component.circuit_breaker")  # CircuitBreakerComponent
logger = get_logger("flock.component.deduplication")    # DeduplicationComponent
logger = get_logger("flock.component.metrics")          # MetricsComponent

# Engines
logger = get_logger("flock.engine.dspy")          # DSPy engine
logger = get_logger("flock.engine.correlation")   # CorrelationEngine
logger = get_logger("flock.engine.batch")         # BatchEngine

# Dashboard
logger = get_logger("flock.dashboard.service")    # Dashboard HTTP service
logger = get_logger("flock.dashboard.websocket")  # WebSocket manager
logger = get_logger("flock.dashboard.collector")  # Event collector

# MCP
logger = get_logger("flock.mcp.client")         # MCP client
logger = get_logger("flock.mcp.server")         # MCP server
logger = get_logger("flock.mcp.tool")           # MCP tool execution

# API
logger = get_logger("flock.api.artifacts")      # Artifact API
logger = get_logger("flock.api.traces")         # Trace API
```

**Benefits**:
- ✅ Filter by prefix: `FLOCK_LOG_MCP=DEBUG` enables all MCP logs
- ✅ Hierarchical control: `flock.component.*` at DEBUG, others at INFO
- ✅ Clear module identification in logs

---

## 🔍 Logging vs Tracing (When to Use What)

### Use **Logging** For:
- ✅ **Human-readable events**: "Agent scheduled", "Batch flushed"
- ✅ **State transitions**: Circuit breaker counts, correlation status
- ✅ **Errors and warnings**: Exceptions, degraded performance
- ✅ **Production monitoring**: Counting events, alerting on errors

### Use **OpenTelemetry Tracing** For:
- ✅ **Performance analysis**: Method duration, bottleneck identification
- ✅ **Request flow**: Correlation across agents, parent-child relationships
- ✅ **Input/output capture**: Full artifact payloads, evaluation results
- ✅ **Post-mortem debugging**: Querying DuckDB for historical data

### Use **Both** For:
- ✅ **Critical operations**: Log at INFO + capture in span
- ✅ **Errors**: Log exception + record in span with `span.record_exception()`
- ✅ **Correlation**: Log with trace_id, trace captures full context

**Example (combining logs + traces)**:
```python
from flock.logging.logging import get_logger
from opentelemetry import trace

logger = get_logger("flock.orchestrator")
tracer = trace.get_tracer(__name__)

async def publish(self, artifact):
    with tracer.start_as_current_span("orchestrator.publish") as span:
        span.set_attribute("artifact.type", artifact.type)
        span.set_attribute("artifact.id", str(artifact.id))
        
        logger.debug(f"Publishing artifact: type={artifact.type}, id={artifact.id}")
        
        try:
            await self.store.publish(artifact)
            logger.info(f"Artifact published: type={artifact.type}")
        except Exception as e:
            logger.error(f"Publish failed: {str(e)}")
            span.record_exception(e)
            raise
```

---

## 📊 Performance Considerations

### Logging Overhead Targets

| Scenario | Target | Measurement |
|----------|--------|-------------|
| Logger initialization | <1ms | First `get_logger()` call |
| DEBUG log (filtered) | <0.01ms | Level check + early return |
| INFO log (active) | <1ms | Format + write to stdout |
| Structured formatting | <0.5ms | Key-value extraction |
| Trace ID lookup | <0.1ms | OpenTelemetry context fetch |

### Optimization Strategies

**1. Early Level Filtering**
```python
# Current implementation (GOOD)
def info(self, message: str, ...):
    if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or ...:
        return  # ← Early return before formatting
    message = self._truncate_message(message, max_length)
    self._get_logger().info(message)
```

**2. Lazy Message Formatting**
```python
# Good: Only format if logging
logger.debug(f"Expensive operation: {expensive_function()}")  # ❌ Always calls expensive_function()

# Better: Use lambda for expensive operations
if logger.min_level_severity <= LOG_LEVELS["DEBUG"]:
    logger.debug(f"Expensive operation: {expensive_function()}")  # ✅ Only if DEBUG enabled
```

**3. Truncation Limits**
```python
# Current: 500 chars (reasonable for most logs)
MAX_LENGTH = 500

# For high-frequency logs, reduce truncation
logger.debug(message, max_length=100)  # Faster truncation
```

**4. Async Logging (Future Enhancement)**
```python
# Consider for high-throughput scenarios
# Queue logs to background thread, flush async
# Trade-off: Latency vs throughput
```

---

## 🧪 Testing Strategy

### Unit Tests for Logging

**1. Test logger initialization**
```python
def test_logger_initialization():
    logger = get_logger("flock.test")
    assert logger.name == "flock.test"
    assert logger.min_level_severity == LOG_LEVELS["ERROR"]  # Default
```

**2. Test level filtering**
```python
def test_debug_filtered_by_default():
    logger = get_logger("flock.test")
    with captured_logs() as logs:
        logger.debug("This should be filtered")
    assert len(logs) == 0
```

**3. Test structured logging**
```python
def test_structured_log_format():
    logger = get_logger("flock.test")
    configure_logging(flock_level="INFO", external_level="ERROR")
    with captured_logs() as logs:
        logger.info(f"Agent scheduled: name=test, artifacts=5")
    assert "Agent scheduled" in logs[0]
    assert "name=test" in logs[0]
```

### Integration Tests

**4. Test logging + tracing correlation**
```python
async def test_log_trace_correlation():
    with tracer.start_as_current_span("test_span") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        logger.info("Test message")
    # Verify log contains trace_id
```

### Performance Tests

**5. Benchmark logging overhead**
```python
def test_logging_performance():
    logger = get_logger("flock.perf")
    
    # Measure filtered DEBUG (should be ~0.01ms)
    start = time.perf_counter()
    for _ in range(10000):
        logger.debug("Filtered message")
    duration_ms = (time.perf_counter() - start) * 1000
    assert duration_ms < 100  # <0.01ms per call
```

---

## 📋 Migration Checklist

### Per-Module Checklist

For each module without logging:

- [ ] Import logger: `from flock.logging.logging import get_logger`
- [ ] Initialize logger: `logger = get_logger("flock.module_name")`
- [ ] Add INFO logs for lifecycle events (init, key operations)
- [ ] Add DEBUG logs for state transitions
- [ ] Add ERROR logs for exceptions
- [ ] Add WARNING logs for degraded states
- [ ] Test log output at different levels
- [ ] Update module docstring with logging behavior

### Files Needing Logging (Priority Order)

**High Priority** (Critical paths):
- [ ] `src/flock/orchestrator.py` - Already has logger, add more strategic logs
- [ ] `src/flock/store.py` - Add query and mutation logs
- [ ] `src/flock/subscription.py` - Add matching logic logs
- [ ] `src/flock/visibility.py` - Add access control logs
- [ ] `src/flock/correlation_engine.py` - Add correlation state logs
- [ ] `src/flock/batch_accumulator.py` - Add batching logs
- [ ] `src/flock/artifact_collector.py` - Add AND gate logs

**Medium Priority** (Supporting modules):
- [ ] `src/flock/registry.py` - Add registration logs
- [ ] `src/flock/runtime.py` - Add context logs
- [ ] `src/flock/artifacts.py` - Add artifact creation logs
- [ ] `src/flock/mcp/client.py` - Already has logger, verify coverage
- [ ] `src/flock/mcp/manager.py` - Already has logger, verify coverage

**Low Priority** (Utilities):
- [ ] `src/flock/utilities.py` - Add utility function logs
- [ ] `src/flock/helper/cli_helper.py` - Add CLI logs
- [ ] `src/flock/dashboard/events.py` - Add event emission logs
- [ ] `src/flock/dashboard/graph_builder.py` - Add graph construction logs

---

## 🎯 Success Metrics

### Measurable Goals

1. **Coverage**: 100% of core modules have logger initialization (up from ~20%)
2. **Consistency**: All modules follow naming convention (`flock.module_name`)
3. **Structured**: 90%+ logs use key-value format for searchability
4. **Performance**: <0.01ms overhead for filtered DEBUG logs
5. **Documentation**: Logging guide published with examples
6. **Developer Adoption**: New PRs include appropriate logging

### Validation Criteria

- [ ] All orchestrator scheduling decisions logged at DEBUG
- [ ] All agent lifecycle events logged at INFO
- [ ] All errors logged at ERROR with context
- [ ] All state transitions logged at DEBUG
- [ ] All performance warnings logged at WARNING
- [ ] Log output readable in production (no spam)
- [ ] Logs complement traces (no redundancy)
- [ ] Environment variables control verbosity

---

## 🚀 Quick Start Guide

### For Module Authors

**1. Initialize logger in your module**:
```python
from flock.logging.logging import get_logger

logger = get_logger("flock.your_module")
```

**2. Log lifecycle events**:
```python
class YourComponent:
    def __init__(self):
        logger.info(f"YourComponent initialized: config={self.config}")
    
    async def process(self, data):
        logger.debug(f"Processing: data_size={len(data)}")
        try:
            result = await self._do_work(data)
            logger.success(f"Processing complete: result_count={len(result)}")
            return result
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            raise
```

**3. Use structured format**:
```python
# Good
logger.info(f"Agent scheduled: name={agent.name}, artifacts={len(artifacts)}, priority={priority}")

# Bad
logger.info(f"The agent {agent.name} was scheduled with {len(artifacts)} artifacts at priority {priority}")
```

### For Users

**1. Set log level via environment**:
```bash
export FLOCK_LOG_LEVEL=DEBUG
export FLOCK_LOG_ORCHESTRATOR=INFO
uv run python your_script.py
```

**2. Configure in code**:
```python
from flock.logging.logging import configure_logging

configure_logging(
    flock_level="INFO",
    external_level="ERROR",
    specific_levels={
        "flock.orchestrator": "DEBUG",
        "flock.mcp": "WARNING"
    }
)
```

**3. Grep logs for debugging**:
```bash
# Find all orchestrator logs
uv run python script.py 2>&1 | grep "flock.orchestrator"

# Find all errors
uv run python script.py 2>&1 | grep "ERROR"

# Find logs for specific agent
uv run python script.py 2>&1 | grep "agent=code_detective"
```

---

## 📚 References

- **Current Implementation**: `src/flock/logging/logging.py`
- **Loguru Documentation**: https://loguru.readthedocs.io/
- **OpenTelemetry Logging**: https://opentelemetry.io/docs/specs/otel/logs/
- **Structured Logging Best Practices**: https://www.structlog.org/en/stable/
- **Related**: `docs/UNIFIED_TRACING.md` (OpenTelemetry trace guide)

---

## 🎉 Next Steps

1. **Review this strategy** with team
2. **Prototype Phase 1** (orchestrator logging) in dev branch
3. **Measure performance** impact of logging overhead
4. **Create PR template** checklist item: "Appropriate logging added"
5. **Update CONTRIBUTING.md** with logging guidelines
6. **Schedule migration sprints** for Phases 2-4

---

*Last updated: October 14, 2025*
*Strategy version: 1.0*
