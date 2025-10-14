# Flock Logging Strategy - Executive Summary

## 📊 Current State Analysis

**Infrastructure**: ✅ Excellent (FlockLogger, Loguru, OpenTelemetry, auto-tracing)  
**Adoption**: ❌ Poor (~20% of modules use logging)  
**Impact**: Debugging production issues is difficult without comprehensive logs

### Key Finding

Flock has production-grade logging infrastructure but inconsistent usage. Critical paths (orchestrator scheduling, store operations, component lifecycle) execute with minimal logging.

---

## 🎯 Strategy Overview

### Three-Pillar Approach

1. **Logging** - Human-readable events, state transitions, errors
2. **Tracing** - Performance analysis, request flow, input/output capture  
3. **Metrics** - Counters, gauges, histograms (future)

### When to Use What

| Need | Solution | Example |
|------|----------|---------|
| "Why did the agent fail?" | **Logging** (ERROR) | `logger.error("Agent execution failed: {error}")` |
| "What's the current state?" | **Logging** (DEBUG) | `logger.debug("Circuit breaker: 950/1000")` |
| "How long did this take?" | **Tracing** | OpenTelemetry span duration |
| "What was the input?" | **Tracing** | Span attribute: `input.artifacts` |
| "How many times per second?" | **Metrics** | Counter: `orchestrator.artifacts.published` |

---

## 📋 Implementation Plan

### Phase 1: Core Modules (Week 1)
Add logging to critical paths:
- ✅ Orchestrator scheduling decisions
- ✅ Store queries and mutations
- ✅ Agent lifecycle events
- ✅ Subscription matching

**Impact**: 80% improvement in debuggability with 20% effort.

### Phase 2: Supporting Modules (Week 2)
Add logging to data structures:
- Registry operations
- Visibility checks
- Correlation/batch engines
- Runtime context

**Impact**: Complete coverage of execution flow.

### Phase 3: Environment Configuration (Week 3)
Enable runtime control:
- `FLOCK_LOG_LEVEL` (global default)
- `FLOCK_LOG_ORCHESTRATOR` (module-specific)
- `.envtemplate` updates
- Documentation

**Impact**: Production operators can adjust verbosity without code changes.

### Phase 4: Documentation (Week 4)
Formalize best practices:
- Logging guidelines (`docs/guides/logging.md`)
- AGENTS.md updates
- CONTRIBUTING.md checklist
- Example patterns

**Impact**: New contributors follow consistent patterns.

---

## 🎨 Logging Levels (Quick Reference)

```python
from flock.logging.logging import get_logger

logger = get_logger("flock.your_module")

# DEBUG: Internal state, flow details (production: OFF)
logger.debug(f"Subscription matched: agent={name}, type={type}")

# INFO: Lifecycle events, user actions (production: ON)
logger.info(f"Agent scheduled: name={name}, artifacts={count}")

# WARNING: Recoverable issues, approaching limits (production: ON)
logger.warning(f"Circuit breaker at 95%: {count}/{max}")

# ERROR: Failures, exceptions (production: ON)
logger.error(f"Agent execution failed: {error}")

# SUCCESS: Important completions (production: ON)
logger.success(f"Workflow completed: artifacts={count}")
```

---

## 📐 Message Format Convention

**Use structured key-value pairs**:

```python
# ✅ GOOD - Searchable, parseable
logger.info(f"Agent scheduled: name={agent.name}, artifacts={len(artifacts)}, priority={priority}")

# ❌ BAD - Unstructured prose
logger.info(f"The agent {agent.name} was scheduled with {len(artifacts)} artifacts at priority {priority}")
```

**Benefits**:
- Grep-friendly: `grep "name=code_detective"`
- Machine-parseable for analytics
- Consistent format across codebase

---

## 🚀 Quick Start

### For Module Authors

```python
# 1. Import logger
from flock.logging.logging import get_logger

# 2. Initialize (top of module)
logger = get_logger("flock.your_module")

# 3. Log lifecycle events
class YourComponent:
    def __init__(self):
        logger.info(f"Component initialized: config={self.config}")
    
    async def process(self, data):
        logger.debug(f"Processing: size={len(data)}")
        try:
            result = await self._do_work(data)
            logger.success(f"Processing complete: results={len(result)}")
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            raise
```

### For Users

```bash
# Set log level globally
export FLOCK_LOG_LEVEL=DEBUG

# Set per-module
export FLOCK_LOG_ORCHESTRATOR=INFO
export FLOCK_LOG_MCP=WARNING

# Run with logging
uv run python your_script.py
```

---

## 🎯 Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Modules with logging | ~20% | 100% |
| Structured log format | ~50% | 90%+ |
| DEBUG overhead | N/A | <0.01ms |
| Time to diagnose issues | 30min | 5min |

---

## 📚 Key Documents

1. **Full Strategy**: `docs/internal/system-improvements/logging-strategy.md`
2. **OrchestratorComponent Logging**: `docs/specs/004-orchestrator-component/LOGGING_GUIDE.md`
3. **Tracing Guide**: `docs/UNIFIED_TRACING.md` (existing)

---

## 💡 Key Insights

### Why This Matters

**Production Scenario**: User reports "my agents aren't running."

**Without logging**:
```
# Mystery! Need to add prints, redeploy, reproduce
# Takes 30+ minutes to diagnose
```

**With logging (DEBUG)**:
```
2025-10-14 15:00:00 | DEBUG | [flock.orchestrator] | Subscription matched: agent=code_detective, type=BugReport
2025-10-14 15:00:00 | INFO  | [flock.component.circuit_breaker] | Circuit breaker TRIPPED: agent=code_detective, iterations=1000/1000
2025-10-14 15:00:00 | INFO  | [flock.orchestrator] | Scheduling skipped by component: agent=code_detective

# Root cause: Circuit breaker limit reached
# Fix: Increase limit or reset on idle
# Time to diagnose: <1 minute
```

### Performance Impact

Logging overhead with level-based filtering:
- **Filtered DEBUG log**: ~0.01ms (just level check)
- **Active INFO log**: ~1ms (format + write)
- **10,000 artifacts workflow**: <10ms total logging overhead

**Conclusion**: Negligible performance cost, massive debuggability gain.

---

## 🔄 Integration with Existing Tools

### Logging + Tracing = Complete Picture

```python
from flock.logging.logging import get_logger
from opentelemetry import trace

logger = get_logger("flock.orchestrator")
tracer = trace.get_tracer(__name__)

async def publish(self, artifact):
    # Trace: Captures timing, input/output
    with tracer.start_as_current_span("publish") as span:
        span.set_attribute("artifact.type", artifact.type)
        
        # Log: Human-readable event
        logger.info(f"Publishing artifact: type={artifact.type}, id={artifact.id}")
        
        try:
            await self.store.publish(artifact)
            logger.success(f"Artifact published: type={artifact.type}")
        except Exception as e:
            # Both logging and tracing
            logger.error(f"Publish failed: {str(e)}")
            span.record_exception(e)
            raise
```

**Result**:
- Logs show WHAT happened (human debugging)
- Traces show HOW (performance analysis, DuckDB queries)
- Together: Complete observability

---

## 🎉 Next Steps

1. **Review** this summary with team
2. **Prototype** Phase 1 (orchestrator logging)
3. **Measure** performance impact
4. **Iterate** based on feedback
5. **Roll out** Phases 2-4

**Timeline**: 4 weeks to complete all phases  
**Effort**: ~20 hours total (5 hours/week)  
**Impact**: 10x improvement in debuggability

---

*For detailed implementation, see full strategy document.*
*Last updated: October 14, 2025*
