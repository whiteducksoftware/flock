# Flock Logging Quick Reference Card

**Keep this handy when writing Flock code!**

---

## 🚀 Setup (Copy-Paste)

```python
from flock.logging.logging import get_logger

logger = get_logger("flock.your_module_name")
```

**Module naming convention**: `flock.category.module`
- Core: `flock.orchestrator`, `flock.agent`, `flock.store`
- Components: `flock.component.circuit_breaker`
- Engines: `flock.engine.dspy`
- Dashboard: `flock.dashboard.service`
- MCP: `flock.mcp.client`

---

## 📊 Levels (When to Use)

```python
# DEBUG - Internal flow (production: OFF)
logger.debug(f"Checking subscription: agent={name}, type={type}")

# INFO - User-visible events (production: ON)  
logger.info(f"Agent scheduled: name={name}, artifacts={count}")

# WARNING - Issues, approaching limits (production: ON)
logger.warning(f"Circuit breaker at 95%: {count}/{max}")

# ERROR - Failures (production: ON)
logger.error(f"Operation failed: {error}")

# SUCCESS - Completions (production: ON)
logger.success(f"Workflow completed: duration_ms={duration}")
```

---

## ✅ DO's

### Structured Format
```python
# ✅ GOOD - Searchable key-value pairs
logger.info(f"Event: action=schedule, agent={name}, count={len(items)}")

# ❌ BAD - Unstructured prose
logger.info(f"The agent {name} was scheduled with {len(items)} items")
```

### Lifecycle Events
```python
# Initialization
logger.info(f"Component initialized: type={self.__class__.__name__}, config={self.config}")

# Processing
logger.debug(f"Processing started: input_size={len(data)}")

# Completion
logger.success(f"Processing complete: outputs={len(results)}, duration_ms={duration}")

# Errors
try:
    result = await process()
except Exception as e:
    logger.error(f"Processing failed: error={str(e)}")
    raise
```

### Context-Rich Errors
```python
# ✅ GOOD - With context
logger.error(
    f"Agent execution failed: agent={agent.name}, "
    f"artifact_count={len(artifacts)}, error={str(e)}"
)

# ❌ BAD - No context
logger.error(f"Error: {str(e)}")
```

---

## ❌ DON'Ts

```python
# ❌ Don't log sensitive data
logger.info(f"API key: {api_key}")  # NEVER!

# ❌ Don't log in tight loops (use DEBUG + sparse sampling)
for item in huge_list:  # 10,000 items
    logger.info(f"Processing {item}")  # Spam!

# ❌ Don't duplicate OpenTelemetry
# If traced, don't log every span - just key decisions
with tracer.start_span("process"):
    logger.info("Processing")  # ❌ Redundant if span exists
    result = process()
    logger.info("Done")  # ❌ Redundant

# Better: Log decisions not in spans
with tracer.start_span("process"):
    result = process()
    if result.needs_retry:
        logger.warning(f"Retry needed: reason={result.retry_reason}")
```

---

## 🎯 Common Patterns

### Class Initialization
```python
class MyComponent(OrchestratorComponent):
    def __init__(self, max_count: int = 100):
        super().__init__()
        self.max_count = max_count
        logger.info(f"{self.__class__.__name__} initialized: max_count={max_count}")
```

### Async Method
```python
async def process_artifacts(self, artifacts: list[Artifact]) -> list[Result]:
    logger.debug(f"Processing artifacts: count={len(artifacts)}")
    
    results = []
    for artifact in artifacts:
        try:
            result = await self._process_one(artifact)
            results.append(result)
        except Exception as e:
            logger.error(
                f"Artifact processing failed: "
                f"artifact_id={artifact.id}, artifact_type={artifact.type}, error={str(e)}"
            )
            # Decide: continue or raise?
    
    logger.info(f"Processing complete: success={len(results)}/{len(artifacts)}")
    return results
```

### State Transitions
```python
# Circuit breaker example
count = self._counts.get(agent.name, 0)

if count >= self.max_iterations:
    logger.warning(f"Circuit breaker TRIPPED: agent={agent.name}, count={count}")
    return ScheduleDecision.SKIP

# Warn at 95%
if count >= self.max_iterations * 0.95:
    logger.warning(
        f"Circuit breaker approaching limit: agent={agent.name}, "
        f"count={count}/{self.max_iterations} (95%)"
    )

logger.debug(f"Circuit breaker check: agent={agent.name}, count={count}/{self.max_iterations}")
self._counts[agent.name] = count + 1
```

### Decision Points
```python
# Log when making important decisions
if not subscription.matches(artifact):
    logger.debug(
        f"Subscription mismatch: agent={agent.name}, "
        f"artifact_type={artifact.type}, expected_types={subscription.types}"
    )
    continue

if decision == ScheduleDecision.SKIP:
    logger.info(
        f"Scheduling skipped: agent={agent.name}, "
        f"reason=component_decision, component={component.name}"
    )
    return
```

---

## 🔧 Environment Control

### Command Line
```bash
# Set global level
export FLOCK_LOG_LEVEL=DEBUG

# Set per-module
export FLOCK_LOG_ORCHESTRATOR=INFO
export FLOCK_LOG_AGENT=DEBUG
export FLOCK_LOG_MCP=WARNING

# Run
uv run python your_script.py
```

### In Code
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

---

## 🐛 Debugging Tips

### Find Errors
```bash
python script.py 2>&1 | grep "ERROR"
```

### Find Specific Agent
```bash
python script.py 2>&1 | grep "agent=code_detective"
```

### Find Component Activity
```bash
python script.py 2>&1 | grep "flock.component"
```

### Find Scheduling Decisions
```bash
python script.py 2>&1 | grep "scheduled\|skipped\|blocked"
```

---

## 📏 Performance Guidelines

- **Filtered logs (DEBUG in prod)**: <0.01ms overhead
- **Active logs (INFO)**: ~1ms overhead
- **Truncation limit**: 500 chars (customizable)
- **High-frequency ops**: Use DEBUG level
- **Critical path**: INFO for decisions, DEBUG for flow

---

## 🧪 Testing Logs

```python
def test_component_logs_initialization(caplog):
    """Test that component logs initialization."""
    component = MyComponent(max_count=100)
    
    assert "MyComponent initialized" in caplog.text
    assert "max_count=100" in caplog.text
```

---

## 📚 Full Documentation

- **Complete Strategy**: `docs/internal/system-improvements/logging-strategy.md`
- **OrchestratorComponent Guide**: `docs/specs/004-orchestrator-component/LOGGING_GUIDE.md`
- **Summary**: `docs/internal/system-improvements/logging-strategy-summary.md`

---

## ⚡ TL;DR

1. **Import**: `from flock.logging.logging import get_logger`
2. **Initialize**: `logger = get_logger("flock.your_module")`
3. **Use structured format**: `logger.info(f"Action: key=value, key2=value2")`
4. **Choose level wisely**: DEBUG=internal, INFO=events, ERROR=failures
5. **Add context to errors**: Include agent name, artifact type, etc.
6. **Control via env**: `FLOCK_LOG_LEVEL=DEBUG`

**When in doubt**: Log at INFO for user-visible events, DEBUG for internal flow.

---

*Print this card and keep it near your keyboard! 📌*
