# How to Use Tracing Effectively in Flock

> **The ultimate guide to debugging, optimizing, and monitoring blackboard multi-agent systems**

## Table of Contents

- [Introduction: Why Tracing Matters for Blackboard Systems](#introduction-why-tracing-matters-for-blackboard-systems)
- [Getting Started: Your First Trace](#getting-started-your-first-trace)
- [The Seven Views: Complete Observability](#the-seven-views-complete-observability)
- [Real-World Debugging Scenarios](#real-world-debugging-scenarios)
- [Advanced Techniques](#advanced-techniques)
- [Production Best Practices](#production-best-practices)
- [What Makes Flock's Tracing Unique](#what-makes-flocks-tracing-unique)
- [To Come in 1.0: Roadmap](#to-come-in-10-roadmap)

---

## Introduction: Why Tracing Matters for Blackboard Systems

### The Blackboard Problem

Unlike graph-based frameworks (LangGraph, CrewAI, AutoGen), where agent interactions follow predefined edges, **blackboard systems have emergent behavior**. Agents communicate through shared data artifacts, making it nearly impossible to predict:

- **Why** did Agent B execute after Agent A?
- **What** chain of events led to this error?
- **Which** agent is the bottleneck?
- **How** do agents actually interact in production?

Traditional logging fails here because:
- ❌ No parent-child relationships between agent calls
- ❌ Async execution makes logs non-sequential
- ❌ No visibility into cross-agent data flow
- ❌ Can't see which artifact triggered which agent

### What Tracing Solves

Flock's OpenTelemetry-based tracing provides:

✅ **Parent-child span relationships** - See the complete execution tree
✅ **Correlation IDs** - Track a single request across all agents
✅ **Timing data** - Identify bottlenecks with microsecond precision
✅ **Input/Output capture** - See what data agents consumed and produced
✅ **Service dependencies** - Discover emergent agent interactions
✅ **RED Metrics** - Rate, Errors, Duration for production monitoring

**The key insight**: Blackboard systems require *discovery* tools, not just debugging tools. You need to understand what actually happened, not just verify what you thought would happen.

---

## Getting Started: Your First Trace

### 1. Enable Tracing

Add to your `.env` file:

```bash
# Enable auto-tracing
FLOCK_AUTO_TRACE=true
FLOCK_TRACE_FILE=true

# Filter what gets traced (avoid streaming token overhead)
FLOCK_TRACE_SERVICES=["flock", "agent", "dspyengine", "outpututilitycomponent"]

# Exclude noisy operations
FLOCK_TRACE_IGNORE=["DashboardEventCollector.set_websocket_manager"]

# Auto-cleanup old traces
FLOCK_TRACE_TTL_DAYS=30
```

### 2. Run Your Agent

```bash
python examples/showcase/01_declarative_pizza.py
```

### 3. Open the Trace Viewer

Navigate to the dashboard and select **Trace Viewer** module. You'll see all traces stored in `.flock/traces.duckdb`.

### 4. Your First Investigation

Click on a trace to expand it. You'll see:

```
Flock.publish          [0.00ms - 0.50ms]   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Agent.execute        [0.50ms - 5,200ms]  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    DSPyEngine.evaluate [0.60ms - 5,100ms] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    OutputUtility...    [5,100ms - 5,150ms] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Immediate insights**:
- Total trace duration: 5.2 seconds
- 98% of time spent in `DSPyEngine.evaluate` (LLM call)
- OutputUtility took only 50ms

---

## The Seven Views: Complete Observability

The Trace Viewer provides **7 specialized view modes** for different analysis needs:

### Quick Reference

| View | Icon | Purpose | When to Use |
|------|------|---------|-------------|
| Timeline | 📅 | Waterfall execution flow | Debug sequence and timing |
| Statistics | 📊 | Sortable tabular data | Compare traces, find patterns |
| RED Metrics | 🔴 | Service health monitoring | Production dashboards |
| Dependencies | 🔗 | Service communication | Understand architecture |
| DuckDB SQL | 🗄️ | Custom analytics | Advanced queries, reports |
| Configuration | ⚙️ | Runtime filtering | Fine-tune tracing |
| Guide | 📚 | Documentation & examples | Learn and reference |

### Feature Highlights

**NEW in this version:**
- ✨ **Smart Sorting**: Sort traces by date (newest first), span count, or total duration
- 📥 **CSV Export**: Download SQL query results for Excel/analysis
- 🖥️ **Maximize Mode**: Full-screen view for all modules
- 🎨 **Modern UI**: Emoji-enhanced toolbar for better visual scanning

---

## View Modes Explained

### Timeline View: The Waterfall

**Use case**: "Why is this agent slow?"

The timeline view shows:
- Execution order (top to bottom)
- Duration (bar width)
- Parent-child relationships (indentation)
- Errors (red borders)

**Example: Finding the Bottleneck**

```
Pizza Order Processing (6,500ms total)
├─ Flock.publish (0.5ms) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│  └─ Agent.execute (6,499ms) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│     ├─ DSPyEngine.evaluate (6,200ms) ━━━━━━━━━━━━━━━━━━━━ <- 95% of time!
│     │  └─ LLM Call (6,198ms)
│     └─ OutputUtilityComponent.on_post_evaluate (50ms) ━━━━
└─ Flock.publish (0.1ms)
```

**Finding**: The LLM call dominates execution time. Solutions:
1. Cache results for repeated queries
2. Use a smaller model for simple tasks
3. Implement streaming for better UX

**Click on any span** to see:
- Full attributes (correlation_id, task_id, agent.name)
- Input parameters (JSON formatted)
- Output values
- Error details (if failed)

### Statistics View: JSON Explorer

**Use case**: "What data did the agent receive?"

Shows tabular data with JSON viewer for each span:

| Span ID | Service | Operation | Duration | Status | Attributes |
|---------|---------|-----------|----------|--------|------------|
| abc123 | Agent | execute | 6,499ms | OK | 📄 View JSON |

Click "View JSON" to see:

```json
{
  "input": {
    "ctx": {
      "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
      "task_id": "pizza_order_001"
    },
    "artifacts": [
      {
        "name": "customer_order",
        "content": {
          "pizza": "Margherita",
          "size": "Large",
          "toppings": ["extra cheese", "basil"]
        }
      }
    ]
  },
  "output": {
    "value": {
      "status": "processed",
      "estimated_time": "25 minutes"
    }
  }
}
```

**Why this matters**: You can see exactly what the agent saw, not what you *think* it saw.

### RED Metrics View: Production Monitoring

**Use case**: "Which agent is failing in production?"

RED Metrics = **R**ate + **E**rrors + **D**uration

Each service shows:
- **Rate**: Requests per second
- **Error Rate**: Percentage of failures
- **Avg Duration**: Mean response time
- **P95 Duration**: 95th percentile latency
- **P99 Duration**: 99th percentile latency (worst-case)
- **Total Spans**: Call volume

**Example Output**:

```
┌─────────────────────────────────────────────────────────────┐
│ Agent                                                       │
├─────────────────────────────────────────────────────────────┤
│ Rate:          2.5 req/s                                    │
│ Error Rate:    0.0%          ✓ Healthy                     │
│ Avg Duration:  6,499ms                                      │
│ P95 Duration:  8,200ms                                      │
│ P99 Duration:  12,500ms      ⚠ High variance              │
│ Total Spans:   1,234                                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ DSPyEngine                                                  │
├─────────────────────────────────────────────────────────────┤
│ Rate:          2.5 req/s                                    │
│ Error Rate:    5.2%          ✗ Action needed               │
│ Avg Duration:  6,200ms                                      │
│ P95 Duration:  7,800ms                                      │
│ P99 Duration:  15,000ms      ⚠ Timeout risk                │
│ Total Spans:   1,234                                        │
└─────────────────────────────────────────────────────────────┘
```

**Insights**:
- DSPyEngine has 5.2% error rate → Investigate LLM failures
- P99 of 15s suggests timeout risk → Add retry logic
- Both have high rate → Consider rate limiting

**Why P99 matters**: P95 tells you "most users are fine", P99 tells you "some users are having a terrible experience". In multi-agent systems, P99 latencies compound across agents.

### Dependencies View: Emergent Interactions

**Use case**: "How do my agents actually communicate?"

**⚠ This is where Flock shines** - most frameworks don't provide this for blackboard systems.

Shows service-to-service dependencies with operation-level drill-down:

```
┌─────────────────────────────────────────────────────────────┐
│ Flock → Agent                          3 operations         │
└─────────────────────────────────────────────────────────────┘
    Click to expand:

    Flock.publish → Agent.execute
    ├─ Calls: 1,234
    ├─ Errors: 0.0%
    ├─ Avg: 6,499ms
    └─ P95: 8,200ms

    Flock.publish → Agent.validate_input
    ├─ Calls: 123
    ├─ Errors: 2.4%
    ├─ Avg: 50ms
    └─ P95: 120ms

┌─────────────────────────────────────────────────────────────┐
│ Agent → DSPyEngine                     2 operations         │
└─────────────────────────────────────────────────────────────┘
    Agent.execute → DSPyEngine.evaluate
    ├─ Calls: 1,234
    ├─ Errors: 5.2%
    ├─ Avg: 6,200ms
    └─ P95: 7,800ms

    Agent.refine_output → DSPyEngine.evaluate
    ├─ Calls: 45
    ├─ Errors: 0.0%
    ├─ Avg: 2,100ms
    └─ P95: 2,500ms
```

**Discoveries you can make**:

1. **Unexpected Dependencies**
   - "Why is Agent calling DSPyEngine twice?"
   - Click drill-down: See `Agent.refine_output` is retrying with better prompts
   - Decision: Cache the first result or merge into single call

2. **Error Hotspots**
   - `Agent.validate_input` has 2.4% error rate
   - Drill down to see which inputs fail
   - Fix validation logic

3. **Performance Bottlenecks**
   - `Agent.execute → DSPyEngine.evaluate` has P95 of 7.8s
   - Most calls are fast, but some timeout
   - Solution: Implement circuit breaker

### Configuration View: Tracing Settings

**Use case**: "Configure tracing without editing .env files"

**⚠ NEW IN v0.5.0** - All tracing configuration is now accessible directly in the Trace Viewer!

The Configuration view provides a visual interface for all tracing settings:

**Core Tracing Toggles**:
- ✅ **Enable auto-tracing** (`FLOCK_AUTO_TRACE`)
- ✅ **Store in DuckDB** (`FLOCK_TRACE_FILE`)
- ✅ **Unified workflow tracing** (`FLOCK_AUTO_WORKFLOW_TRACE`)
- ✅ **Trace TTL** (`FLOCK_TRACE_TTL_DAYS`)

**Service Whitelist** (`FLOCK_TRACE_SERVICES`):
- Multi-select with autocomplete
- Populated from actual traced services in database
- Only trace specific services (improves performance)
- Example: `["flock", "agent", "dspyengine"]`

**Operation Blacklist** (`FLOCK_TRACE_IGNORE`):
- Multi-select with autocomplete
- Exclude noisy operations (e.g., health checks)
- Format: `Service.method`
- Example: `["DashboardEventCollector.set_websocket_manager"]`

**Database Statistics**:
```
┌─────────────────────────────────────────┐
│ Trace Database Statistics              │
├─────────────────────────────────────────┤
│ Total Spans:      12,456               │
│ Total Traces:     3,421                │
│ Services Traced:  8                    │
│ Database Size:    24.5 MB              │
│ Oldest Trace:     Oct 1, 09:15 AM     │
│ Newest Trace:     Oct 7, 21:20 PM     │
└─────────────────────────────────────────┘
```

**Clear Traces**:
- One-click database clearing
- Confirmation dialog prevents accidents
- Runs VACUUM to reclaim disk space
- Shows deleted span count

**Why Configuration lives in Trace Viewer**:
- ✅ Settings stay with the data viewer (logical grouping)
- ✅ See immediate impact of filter changes on statistics
- ✅ Access during debugging workflow (no context switch)
- ✅ Separate from UI preferences (Settings panel = appearance/graph only)

**Example Workflow**:
1. Open **Trace Viewer** → **Configuration** tab
2. Check database statistics → 50,000 spans, 2.5 GB
3. Enable service whitelist → Select only `["agent", "dspyengine"]`
4. Clear old traces → Confirmation → 45,000 spans deleted
5. Return to **Timeline** view → Much faster with filtered data!

---

## Real-World Debugging Scenarios

### Scenario 1: "Agent Executed But Shouldn't Have"

**Problem**: Agent processing irrelevant artifacts.

**Investigation**:
1. Go to **Timeline View**
2. Find the unexpected `Agent.execute` span
3. Click to expand → View attributes
4. Check `input.artifacts` in JSON

**Example Finding**:

```json
{
  "input": {
    "artifacts": [
      {
        "name": "customer_order",
        "visibility": "public",
        "status": "draft"  // ← Agent should ignore drafts!
      }
    ]
  }
}
```

**Root Cause**: Agent subscription didn't filter by status.

**Fix**:
```python
agent.subscribe(
    artifact_name="customer_order",
    filter=lambda artifact: artifact.status == "finalized"  # Add filter
)
```

### Scenario 2: "Production is Slow, But Dev Was Fast"

**Problem**: 2x latency increase in production.

**Investigation with RED Metrics**:

1. Go to **RED Metrics View**
2. Compare P95/P99 between environments (use DuckDB SQL):

```sql
-- Dev environment traces
SELECT
    service,
    AVG(duration_ms) as avg,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95
FROM spans
WHERE created_at > '2025-10-01' AND created_at < '2025-10-05'
GROUP BY service;

-- Production environment (different database)
-- Compare results
```

**Example Finding**:

| Service | Dev P95 | Prod P95 | Diff |
|---------|---------|----------|------|
| Agent | 3,200ms | 3,400ms | +6% |
| DSPyEngine | 2,800ms | 7,200ms | **+157%** |

**Root Cause**: Production LLM endpoint has higher latency.

**Solutions**:
- Switch to dedicated LLM endpoint
- Implement request coalescing
- Add caching layer

### Scenario 3: "Cascading Failures"

**Problem**: One agent error crashes entire system.

**Investigation with Dependencies**:

1. Go to **Dependencies View**
2. Find failing agent: `DSPyEngine` (5.2% error rate)
3. Check which agents depend on it

**Example Finding**:

```
DSPyEngine (5.2% errors)
  ↓
Agent (depends on DSPyEngine)
  ↓
OutputUtilityComponent (depends on Agent)

Error cascade: 5.2% → 5.2% → 5.2%
```

**Root Cause**: No error handling, failures propagate.

**Fix**:
```python
try:
    result = await dspy_engine.evaluate(prompt)
except LLMException as e:
    logger.error(f"LLM failed: {e}")
    return fallback_response()  # Graceful degradation
```

**Verify Fix**:
- Check RED Metrics after deployment
- Agent error rate should drop to 0%
- System resilience improved

### Scenario 4: "Memory Leak in Long-Running Agents"

**Problem**: Memory usage grows over time.

**Investigation with Timeline**:

1. Filter traces by `correlation_id` (same session)
2. Compare first vs last trace durations

**Example Finding**:

```
Session start:
Agent.execute: 3,200ms

After 100 iterations:
Agent.execute: 8,500ms  ← 2.6x slower!
```

**Hypothesis**: Agent accumulating data in memory.

**Verification in Statistics View**:
- Click trace #1 → Check `output.value` size: 2KB
- Click trace #100 → Check `output.value` size: 120KB

**Root Cause**: Agent appending to list without cleanup.

**Fix**:
```python
class MyAgent:
    def __init__(self):
        self.history = []  # ← Problem: unbounded growth

    def execute(self, ctx, artifacts):
        self.history.append(result)  # ← Memory leak
        return result

# Solution: Use circular buffer
from collections import deque

class MyAgent:
    def __init__(self):
        self.history = deque(maxlen=100)  # Keep last 100 only
```

### Scenario 5: "LLM Costs Exploding"

**Problem**: Monthly LLM bill increased 10x.

**Investigation with RED Metrics + Statistics**:

1. **RED Metrics View**: Check `DSPyEngine` rate
   - Before: 2.5 req/s
   - Now: 25 req/s (10x increase!)

2. **Dependencies View**: Find what's calling DSPyEngine
   - `Agent.execute → DSPyEngine.evaluate`: 95% of calls
   - `Agent.refine_output → DSPyEngine.evaluate`: New operation!

3. **Timeline View**: Check a trace with `refine_output`

**Finding**: New feature added retry logic that calls LLM multiple times:

```python
# Before
result = dspy_engine.evaluate(prompt)

# After (introduced bug)
for attempt in range(5):  # ← Calls LLM 5x on every request!
    result = dspy_engine.evaluate(prompt)
    if result.confidence > 0.9:
        break
```

**Fix**: Add result caching or reduce retry count.

---

## Advanced Techniques

### Technique 1: Using DuckDB for Custom Analysis

**Access the traces directly**:

```bash
duckdb .flock/traces.duckdb
```

**Example queries**:

```sql
-- Find slowest operations
SELECT
    name,
    AVG(duration_ms) as avg_duration,
    MAX(duration_ms) as max_duration,
    COUNT(*) as call_count
FROM spans
WHERE created_at > NOW() - INTERVAL 24 HOURS
GROUP BY name
ORDER BY avg_duration DESC
LIMIT 10;

-- Find error patterns
SELECT
    name,
    status_code,
    COUNT(*) as error_count,
    json_extract(attributes, '$.error.message') as error_message
FROM spans
WHERE status_code = 'ERROR'
GROUP BY name, status_code, error_message
ORDER BY error_count DESC;

-- Find agents triggered by specific artifact
SELECT DISTINCT
    s1.name as trigger_agent,
    s2.name as executed_agent,
    COUNT(*) as times
FROM spans s1
JOIN spans s2 ON s1.trace_id = s2.trace_id
WHERE json_extract(s1.attributes, '$.artifact.name') = 'customer_order'
  AND s2.start_time > s1.end_time
GROUP BY s1.name, s2.name;

-- Correlation between input size and duration
SELECT
    name,
    CASE
        WHEN LENGTH(json_extract(attributes, '$.input')) < 1000 THEN 'small'
        WHEN LENGTH(json_extract(attributes, '$.input')) < 10000 THEN 'medium'
        ELSE 'large'
    END as input_size,
    AVG(duration_ms) as avg_duration
FROM spans
GROUP BY name, input_size
ORDER BY name, avg_duration;
```

### Technique 2: Filtering for Focus

**Scenario**: Too many traces, need to focus.

**In Timeline View**, use search:
- Search by `correlation_id`: `550e8400-e29b-41d4-a716-446655440000`
- Search by agent name: `PizzaOrderAgent`
- Search by artifact: `customer_order`
- Search by error: `TimeoutError`

**Environment variable filtering**:

```bash
# Development: Trace everything for debugging
FLOCK_TRACE_SERVICES=["flock", "agent", "dspyengine", "outpututilitycomponent"]

# Production: Only critical services
FLOCK_TRACE_SERVICES=["agent"]

# Debugging specific agent
FLOCK_TRACE_SERVICES=["pizzaorderagent", "dspyengine"]
```

### Technique 3: Correlation ID Tracking

**Track a single request end-to-end**:

```python
# In your application
correlation_id = str(uuid.uuid4())

ctx = Context(correlation_id=correlation_id, task_id="order_001")
flock.publish(artifact, ctx)
```

**Then in DuckDB**:

```sql
SELECT
    name,
    start_time,
    end_time,
    duration_ms,
    status_code
FROM spans
WHERE json_extract(attributes, '$.correlation_id') = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY start_time;
```

**Result**: See complete journey of one order through your system.

### Technique 4: Comparative Analysis

**Compare before/after optimization**:

```sql
-- Before optimization (Oct 1-5)
WITH before AS (
    SELECT
        service,
        AVG(duration_ms) as avg_duration
    FROM spans
    WHERE created_at BETWEEN '2025-10-01' AND '2025-10-05'
    GROUP BY service
),
-- After optimization (Oct 6-10)
after AS (
    SELECT
        service,
        AVG(duration_ms) as avg_duration
    FROM spans
    WHERE created_at BETWEEN '2025-10-06' AND '2025-10-10'
    GROUP BY service
)
SELECT
    before.service,
    before.avg_duration as before_ms,
    after.avg_duration as after_ms,
    ((after.avg_duration - before.avg_duration) / before.avg_duration * 100) as improvement_pct
FROM before
JOIN after ON before.service = after.service
ORDER BY improvement_pct;
```

### Technique 5: Focus Mode (Shift+Click)

**In Timeline View**:
- **Shift+Click** any span to focus
- All other spans fade to 40% opacity
- Useful for complex traces with many agents

**Use case**: "I only care about DSPyEngine calls in this trace"
- Shift+click on any DSPyEngine span
- See only DSPyEngine operations clearly
- Shift+click again to unfocus

---

## Production Best Practices

### 1. Configure Sensible Filters

**Don't trace everything in production:**

```bash
# ✅ Good: Trace core services only
FLOCK_TRACE_SERVICES=["flock", "agent", "dspyengine"]

# ❌ Bad: Trace everything (performance impact)
# FLOCK_TRACE_SERVICES=[]  # Empty = trace all

# ✅ Good: Exclude high-frequency operations
FLOCK_TRACE_IGNORE=["DashboardEventCollector.set_websocket_manager", "MetricsUtility.increment_counter"]

# ❌ Bad: Trace streaming tokens (huge overhead)
# FLOCK_TRACE_IGNORE=[]
```

### 2. Set Appropriate TTL

```bash
# Development: Keep 7 days for recent debugging
FLOCK_TRACE_TTL_DAYS=7

# Staging: Keep 14 days for integration testing
FLOCK_TRACE_TTL_DAYS=14

# Production: Keep 30 days for historical analysis
FLOCK_TRACE_TTL_DAYS=30

# Long-term audit: Keep 90 days
FLOCK_TRACE_TTL_DAYS=90
```

### 3. Monitor RED Metrics Daily

**Set SLOs (Service Level Objectives)**:

```python
# Define acceptable thresholds
SLO_THRESHOLDS = {
    "Agent": {
        "error_rate": 1.0,    # Max 1% errors
        "p95_duration": 5000, # Max 5s at P95
        "p99_duration": 10000 # Max 10s at P99
    },
    "DSPyEngine": {
        "error_rate": 2.0,    # LLMs fail more often
        "p95_duration": 8344,
        "p99_duration": 15000
    }
}
```

**Daily check (DuckDB)**:

```sql
-- Check if any service violates SLO
SELECT
    service,
    (SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100) as error_rate,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99
FROM spans
WHERE created_at > NOW() - INTERVAL 24 HOURS
GROUP BY service;
```

**Alert if thresholds exceeded** (pseudo-code):

```python
if error_rate > SLO_THRESHOLDS[service]["error_rate"]:
    send_alert(f"⚠ {service} error rate: {error_rate}% (SLO: {SLO_THRESHOLDS[service]['error_rate']}%)")
```

### 4. Use Correlation IDs Consistently

**Always pass context**:

```python
# ✅ Good: Correlation ID propagates
ctx = Context(correlation_id=request.correlation_id)
flock.publish(artifact, ctx)

# ❌ Bad: Each publish creates new trace
flock.publish(artifact)  # No context = new correlation ID
```

### 5. Regular Database Maintenance

```sql
-- Check database size
SELECT
    COUNT(*) as total_spans,
    MIN(created_at) as oldest_trace,
    MAX(created_at) as newest_trace,
    pg_size_pretty(pg_total_relation_size('spans')) as db_size
FROM spans;

-- Vacuum to reclaim space (after TTL cleanup)
VACUUM ANALYZE spans;
```

### 6. Export Critical Traces

**Save important traces for postmortems**:

```sql
-- Export trace to JSON
COPY (
    SELECT json_group_array(json_object(
        'name', name,
        'start_time', start_time,
        'duration_ms', duration_ms,
        'status_code', status_code,
        'attributes', attributes
    ))
    FROM spans
    WHERE trace_id = '550e8400-e29b-41d4-a716-446655440000'
    ORDER BY start_time
) TO 'incident_2025_10_07_trace.json';
```

---

## What Makes Flock's Tracing Unique

After extensive research into LangGraph, CrewAI, AutoGen, and other agent frameworks, here's what **only Flock provides**:

### 1. ✨ Zero External Dependencies

**Flock**:
- ✅ Built-in DuckDB storage
- ✅ Built-in web UI
- ✅ No external services required
- ✅ Works offline

**Other frameworks**:
- ❌ LangGraph: Requires LangSmith ($) or Langfuse
- ❌ CrewAI: Requires AgentOps, Arize Phoenix, or Datadog
- ❌ AutoGen: Requires AgentOps or custom OpenTelemetry setup

**Why this matters**: You can debug agents on a plane, in secure environments, or without cloud dependencies.

### 2. ✨ Operation-Level Dependency Drill-Down

**Flock**:
```
Agent → DSPyEngine (click to expand)
  ├─ Agent.execute → DSPyEngine.evaluate (1,234 calls, 5.2% errors)
  └─ Agent.refine_output → DSPyEngine.evaluate (45 calls, 0% errors)
```

**Other frameworks**:
- ❌ LangGraph: Service-level dependencies only
- ❌ CrewAI: No dependency visualization in open-source
- ❌ AutoGen: Community solutions show message flow, not operations

**Why this matters**: See **exact method calls** between agents, not just which services talk. Critical for understanding "which operation is slow?"

### 3. ✨ Blackboard-Native Observability

**Flock**:
- ✅ Traces emergent agent interactions
- ✅ Shows which artifact triggered which agent
- ✅ Captures subscription-based execution
- ✅ No predefined graph required

**Other frameworks**:
- ❌ LangGraph: Traces follow graph edges (predefined)
- ❌ CrewAI: Traces follow crew hierarchy (predefined)
- ❌ AutoGen: Traces follow conversation flow (predefined)

**Why this matters**: Blackboard systems have **emergent behavior**. You need to discover what happened, not verify what you planned.

### 4. ✨ P99 Latency Tracking

**Flock**: Shows P95 **and** P99 durations

**Other frameworks**:
- ❌ Most show only P95 or P90
- ❌ Helicone, Langfuse track P95 max

**Why this matters**:
- P95 = "95% of requests are fast"
- P99 = "1% of requests are terrible"

In multi-agent systems, P99 latencies **compound**:
```
Agent1 (P99: 10s) → Agent2 (P99: 10s) → Agent3 (P99: 10s)
Worst case: 30s for user (vs 15s at P95)
```

### 5. ✨ Built-in TTL Management

**Flock**: Automatic trace cleanup with `FLOCK_TRACE_TTL_DAYS`

**Other frameworks**:
- ❌ LangSmith: Manual deletion or retention policies ($)
- ❌ Langfuse: Manual database maintenance
- ❌ AgentOps: Retention based on plan ($)

**Why this matters**: Production databases don't grow unbounded. Set it once, forget it.

### 6. ✨ Filtering at Code Level

**Flock**:
```bash
FLOCK_TRACE_SERVICES=["agent"]  # Whitelist
FLOCK_TRACE_IGNORE=["Agent.health_check"]  # Blacklist
```

**Other frameworks**:
- ❌ Filter in UI only (still capture overhead)
- ❌ Sample-based filtering (lose critical traces)

**Why this matters**: Filtered operations have **near-zero overhead** because span creation is skipped entirely.

### 7. ✨ SQL-Based Analytics

**Flock**: Direct DuckDB access for custom queries

**Other frameworks**:
- ❌ LangSmith: API only (rate limited)
- ❌ AgentOps: Dashboard only
- ❌ Langfuse: PostgreSQL access (complex)

**Why this matters**: Unlimited custom analysis without API quotas.

### What We Don't Have (Yet)

See [To Come in 1.0](#to-come-in-10-roadmap) section below.

---

## To Come in 1.0: Roadmap

Based on analysis of competing frameworks and user needs, here's what Flock's tracing will add:

### 1. 🔄 Time-Travel Debugging

**Feature**: Checkpoint and restart agent execution from any point.

**Inspiration**: LangGraph's time-travel feature allows replaying from checkpoints to explore alternative outcomes.

**Flock implementation**:
```python
# Save checkpoint
checkpoint_id = flock.save_checkpoint(correlation_id, span_id="abc123")

# Restore and continue
flock.restore_checkpoint(checkpoint_id)
flock.resume()
```

**Use case**: "Agent made wrong decision at step 5, restart from there with modified input."

**Status**: Planned for 1.0

---

### 2. 💰 Cost Tracking (Token Usage + API Costs)

**Feature**: Track LLM token usage and costs per operation.

**Inspiration**: Langfuse, Helicone, LiteLLM, Datadog all provide token/cost tracking.

**Flock implementation**:
```python
# In traces, capture:
{
  "tokens": {
    "prompt": 1234,
    "completion": 567,
    "total": 1801
  },
  "cost": {
    "prompt": 0.0012,
    "completion": 0.0011,
    "total": 0.0023,
    "model": "gpt-4o"
  }
}
```

**Dashboard view**:
```
┌─────────────────────────────────────────┐
│ DSPyEngine - Cost Analysis (24h)        │
├─────────────────────────────────────────┤
│ Total Cost:        $145.67              │
│ Total Tokens:      12,456,789           │
│ Avg Cost/Request:  $0.12                │
│ Most Expensive:                         │
│   - Agent.execute: $89.34 (61%)         │
│   - Agent.refine:  $56.33 (39%)         │
└─────────────────────────────────────────┘
```

**SQL Queries**:
```sql
-- Find most expensive operations
SELECT
    name,
    SUM(json_extract(attributes, '$.cost.total')) as total_cost,
    SUM(json_extract(attributes, '$.tokens.total')) as total_tokens
FROM spans
WHERE created_at > NOW() - INTERVAL 24 HOURS
GROUP BY name
ORDER BY total_cost DESC;
```

**Status**: High priority for 1.0

---

### 3. 📊 Comparative Analysis Between Runs

**Feature**: Compare trace performance across deployments, branches, or time periods.

**Inspiration**: Standard observability practice (Datadog, New Relic).

**Flock implementation**:

```sql
-- Compare two time periods
WITH period1 AS (
    SELECT service, AVG(duration_ms) as avg_duration
    FROM spans
    WHERE created_at BETWEEN '2025-10-01' AND '2025-10-05'
    GROUP BY service
),
period2 AS (
    SELECT service, AVG(duration_ms) as avg_duration
    FROM spans
    WHERE created_at BETWEEN '2025-10-06' AND '2025-10-10'
    GROUP BY service
)
SELECT
    p1.service,
    p1.avg_duration as before,
    p2.avg_duration as after,
    ((p2.avg_duration - p1.avg_duration) / p1.avg_duration * 100) as change_pct
FROM period1 p1
JOIN period2 p2 ON p1.service = p2.service;
```

**Dashboard view**:
```
Deployment Comparison
┌─────────────┬─────────┬─────────┬─────────────┐
│ Service     │ Before  │ After   │ Change      │
├─────────────┼─────────┼─────────┼─────────────┤
│ Agent       │ 6,499ms │ 3,200ms │ -50.7% ✅   │
│ DSPyEngine  │ 6,200ms │ 2,800ms │ -54.8% ✅   │
└─────────────┴─────────┴─────────┴─────────────┘
```

**Use cases**:
- Before/after optimization
- Branch comparison (feature vs main)
- Canary deployment validation

**Status**: Medium priority for 1.0

---

### 4. 🔔 Alerts and Notifications

**Feature**: Alert on SLO violations, error spikes, or anomalies.

**Inspiration**: Standard observability (PagerDuty, Datadog alerts).

**Flock implementation**:

```yaml
# alerts.yaml
alerts:
  - name: High Error Rate
    condition: error_rate > 5%
    service: DSPyEngine
    window: 5 minutes
    notify:
      - slack: #ops-alerts
      - email: ops@company.com

  - name: Latency Spike
    condition: p95_duration > 10000ms
    service: Agent
    window: 10 minutes
    notify:
      - pagerduty: escalation-policy-1
```

**Alert logic**:
```python
def check_slo():
    query = """
        SELECT
            service,
            (SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100) as error_rate
        FROM spans
        WHERE created_at > NOW() - INTERVAL 5 MINUTES
        GROUP BY service
    """

    for row in db.execute(query):
        if row['error_rate'] > 5.0:
            send_alert(f"🚨 {row['service']} error rate: {row['error_rate']:.1f}%")
```

**Status**: Medium priority for 1.0

---

### 5. 📤 Export to External Observability Platforms

**Feature**: Export traces to Jaeger, Grafana, Honeycomb, etc.

**Inspiration**: OpenTelemetry standard practice.

**Flock implementation**:

```bash
# Already supported via OTLP
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

**Enhancement needed**:
- ✅ Current: OTLP endpoint (works with Jaeger, Grafana, etc.)
- ❌ Missing: Native exporters for popular platforms
- ❌ Missing: Batch export of historical traces

**Planned features**:
```python
# Export to Jaeger
flock export jaeger --start 2025-10-01 --end 2025-10-05

# Export to S3 for long-term storage
flock export s3 --bucket traces-archive --format parquet

# Export to CSV for analysis
flock export csv --output traces.csv --service Agent
```

**Status**: Low priority for 1.0 (OTLP already works)

---

### 6. 📈 Performance Regression Detection

**Feature**: Automatically detect when performance degrades.

**Inspiration**: Continuous profiling tools (Pyroscope, Datadog).

**Flock implementation**:

```python
# Baseline: Average P95 over last 7 days
baseline_p95 = get_p95_baseline(service="Agent", days=7)

# Current: P95 in last hour
current_p95 = get_p95_recent(service="Agent", hours=1)

# Alert if regression > 20%
if current_p95 > baseline_p95 * 1.2:
    send_alert(f"⚠ Agent P95 regression: {current_p95}ms (baseline: {baseline_p95}ms)")
```

**Dashboard view**:
```
Performance Trends (7 days)
┌─────────────────────────────────────┐
│ Agent P95 Duration                  │
│                                     │
│  8344ms ┤              ╭─╮          │
│  6000ms ┤     ╭──╮    │ │  ← Spike!│
│  4000ms ┤  ╭──╯  ╰────╯ ╰──╮       │
│  2000ms ┼──╯                ╰───    │
│         └──────────────────────────│
│         Mon  Tue  Wed  Thu  Fri    │
└─────────────────────────────────────┘
```

**Status**: Medium priority for 1.0

---

### 7. 🤖 Automatic Anomaly Detection

**Feature**: ML-based detection of unusual patterns.

**Inspiration**: Datadog Watchdog, AWS DevOps Guru.

**Flock implementation**:

```python
# Train on historical data
model = AnomalyDetector.train(spans, features=[
    "duration_ms",
    "error_rate",
    "call_frequency"
])

# Detect anomalies in real-time
for span in new_spans:
    if model.is_anomaly(span):
        alert(f"🔍 Anomaly detected: {span.name} took {span.duration_ms}ms (expected ~{model.expected_duration}ms)")
```

**Examples of anomalies**:
- Agent taking 50x longer than usual
- New error types appearing
- Sudden spike in call frequency
- Dependency graph changes (new edges)

**Status**: Low priority for 1.0 (nice-to-have)

---

### 8. 🌍 Multi-Environment Comparison

**Feature**: Compare dev/staging/prod traces side-by-side.

**Inspiration**: Standard DevOps practice.

**Flock implementation**:

```python
# Tag traces with environment
ctx = Context(
    correlation_id=uuid4(),
    environment="production"  # or "staging", "dev"
)
```

**Dashboard view**:
```
Environment Comparison (Agent.execute)
┌──────────┬─────────┬────────┬───────────┐
│ Env      │ P95     │ Errors │ Rate      │
├──────────┼─────────┼────────┼───────────┤
│ Dev      │ 2,100ms │ 0.1%   │ 0.5 req/s │
│ Staging  │ 3,400ms │ 0.5%   │ 2.0 req/s │
│ Prod     │ 6,200ms │ 5.2%   │ 25 req/s  │← Problem!
└──────────┴─────────┴────────┴───────────┘
```

**Use cases**:
- Validate staging matches prod
- Test capacity before prod deploy
- Debug env-specific issues

**Status**: Medium priority for 1.0

---

### 9. 🎨 Custom Metrics and Dashboards

**Feature**: User-defined metrics and visualizations.

**Inspiration**: Grafana dashboards, Datadog custom metrics.

**Flock implementation**:

```python
# Custom metrics
@traced_and_logged
def my_agent_method(self, ctx, artifacts):
    # Track custom metric
    ctx.set_metric("pizza_toppings_count", len(artifacts[0].toppings))
    ctx.set_metric("is_vegan", artifacts[0].is_vegan)
```

**Dashboard builder**:
```yaml
# custom_dashboard.yaml
dashboard:
  title: "Pizza Orders Analytics"
  panels:
    - type: line_chart
      metric: pizza_toppings_count
      aggregation: avg
      group_by: time(1h)

    - type: pie_chart
      metric: is_vegan
      aggregation: count
      title: "Vegan vs Non-Vegan Orders"
```

**Status**: Low priority for 1.0 (SQL queries work for now)

---

### 10. 👥 Collaboration Features

**Feature**: Share traces, add comments, create issue tickets.

**Inspiration**: Sentry, Datadog incident management.

**Flock implementation**:

```python
# Share trace
share_url = flock.share_trace(trace_id="abc123", expires_days=7)
# Returns: https://flock.app/trace/abc123?token=xyz

# Add comment
flock.comment_on_trace(
    trace_id="abc123",
    span_id="span456",
    user="alice@company.com",
    comment="This span is slow because of database query"
)

# Create JIRA ticket from trace
flock.create_issue(
    trace_id="abc123",
    title="Agent timeout on large orders",
    assignee="bob@company.com"
)
```

**Status**: Low priority for 1.0 (team feature)

---

### Summary: Priority Matrix

| Feature | Priority | Effort | Impact | Status |
|---------|----------|--------|--------|--------|
| Cost Tracking | 🔥 High | Medium | High | Planned |
| Time-Travel Debug | 🔥 High | High | High | Planned |
| Regression Detection | 🟡 Med | Medium | High | Planned |
| Alerts | 🟡 Med | Low | High | Planned |
| Multi-Env Compare | 🟡 Med | Low | Med | Planned |
| Comparative Analysis | 🟡 Med | Low | Med | Planned |
| Anomaly Detection | 🟢 Low | High | Med | Future |
| Custom Dashboards | 🟢 Low | High | Low | Future |
| Collaboration | 🟢 Low | Med | Low | Future |
| Export Historical | 🟢 Low | Low | Low | Works (OTLP) |

**Note**: OTLP export already works for real-time integration with Jaeger, Grafana, etc. Historical batch export is lower priority.

---

## Conclusion

Flock's tracing system is designed specifically for **blackboard multi-agent systems**, where behavior is emergent and unpredictable. Unlike graph-based frameworks where you verify what you planned, Flock helps you **discover what actually happened**.

**Key takeaways**:

1. **Start simple**: Enable tracing with 3 env vars
2. **Use all four views**: Timeline (debug), Statistics (inspect), RED Metrics (monitor), Dependencies (discover)
3. **Filter wisely**: Trace core services, not everything
4. **DuckDB is your friend**: Write custom SQL for deep analysis
5. **Monitor production**: Set SLOs and check RED metrics daily

**What makes Flock unique**:
- Zero external dependencies
- Operation-level drill-down
- Blackboard-native observability
- P99 latency tracking
- Built-in TTL management
- SQL-based analytics

**What's coming in 1.0**:
- Time-travel debugging
- Cost tracking
- Performance regression detection
- Alerts

**Resources**:
- [Auto-Tracing Guide](auto-tracing.md) - Technical reference
- [Tracing Quick Start](tracing-quickstart.md) - Getting started
- [Production Tracing](tracing-production.md) - Production best practices

Happy debugging! 🎯

---

*Last updated: 2025-10-07*
