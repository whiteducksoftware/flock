# Unified Tracing with traced_run()

## Overview

Flock now supports **unified tracing** - wrapping entire workflows in a single trace for better observability and debugging.

Previously, each top-level operation (`publish()`, `run_until_idle()`, `serve()`) created separate root traces, making it difficult to see the complete execution flow in trace viewers like Jaeger or the Flock dashboard.

With `traced_run()`, all operations within the context manager are grouped under a single parent trace for clean, hierarchical visualization.

---

## The Problem (Before)

```python
async def main():
    await flock.publish(pizza_idea)     # ← Trace 1: Flock.publish
    await flock.run_until_idle()        # ← Trace 2: Flock.run_until_idle (separate!)
```

**Result**: 2 separate traces with different `trace_id` values
- ❌ Hard to see the complete workflow
- ❌ No parent-child relationship
- ❌ Difficult to correlate operations in trace viewers

---

## The Solution (After)

```python
async def main():
    async with flock.traced_run("pizza_workflow"):
        await flock.publish(pizza_idea)     # ← Part of pizza_workflow trace
        await flock.run_until_idle()        # ← Part of pizza_workflow trace
```

**Result**: Single unified trace
- ✅ All operations share the same `trace_id`
- ✅ Clear parent-child hierarchy
- ✅ Easy to visualize entire workflow in trace viewers

---

## Usage

### Basic Usage

```python
import asyncio
from flock import Flock
from pydantic import BaseModel
from flock.registry import flock_type

@flock_type
class Input(BaseModel):
    data: str

flock = Flock("openai/gpt-4o")

agent = (
    flock.agent("processor")
    .consumes(Input)
    .publishes(Output)
)

async def main():
    # Wrap entire workflow in unified trace
    async with flock.traced_run("data_processing"):
        input_data = Input(data="process this")
        await flock.publish(input_data)
        await flock.run_until_idle()

    print("✅ Processing complete!")

asyncio.run(main())
```

### Custom Workflow Names

```python
# Use descriptive names for different workflows
async with flock.traced_run("customer_onboarding"):
    await flock.publish(new_user)
    await flock.run_until_idle()

async with flock.traced_run("daily_batch_job"):
    await flock.publish(batch_data)
    await flock.run_until_idle()
```

### Custom Attributes

```python
async with flock.traced_run("ml_pipeline") as span:
    # Add custom attributes to the workflow span
    span.set_attribute("pipeline.version", "2.0")
    span.set_attribute("dataset.size", 10000)

    await flock.publish(training_data)
    await flock.run_until_idle()
```

### Nested Workflows

```python
async with flock.traced_run("outer_workflow"):
    await flock.publish(data)

    # Nested workflow (creates child span)
    async with flock.traced_run("inner_task"):
        await flock.publish(sub_data)
        await flock.run_until_idle()

    await flock.run_until_idle()
```

---

## Backward Compatibility

The `traced_run()` context manager is **100% opt-in**:

```python
# Without traced_run() - old behavior (separate traces)
await flock.publish(data)
await flock.run_until_idle()

# With traced_run() - new behavior (unified trace)
async with flock.traced_run("workflow"):
    await flock.publish(data)
    await flock.run_until_idle()
```

**No breaking changes** - existing code continues to work exactly as before!

---

## Environment Variables

### Auto-Workflow Tracing (Future)

Enable automatic workflow tracing without code changes:

```bash
export FLOCK_AUTO_WORKFLOW_TRACE=true
python your_script.py
```

**Note**: Auto-workflow detection is implemented but not yet active. For now, use explicit `traced_run()`.

---

## Trace Hierarchy Example

With `traced_run("pizza_workflow")`:

```
pizza_workflow (5319ms) ← ROOT
├─ Flock.publish (3ms)
│  └─ Agent.execute (5218ms)
│     ├─ OutputUtilityComponent.on_initialize (0.15ms)
│     ├─ DSPyEngine.on_initialize (0.15ms)
│     ├─ DSPyEngine.evaluate (4938ms)
│     │  ├─ DSPyEngine.fetch_conversation_context (0.19ms)
│     │  └─ DSPyEngine.should_use_context (0.14ms)
│     └─ OutputUtilityComponent.on_post_evaluate (0.30ms)
└─ Flock.run_until_idle (5268ms)
   └─ Flock.shutdown (0.17ms)
```

All operations share the same `trace_id` and are properly nested!

---

## Querying Unified Traces

### DuckDB Query

```python
import duckdb

conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Find all workflow traces
workflows = conn.execute('''
    SELECT
        trace_id,
        json_extract(attributes, '$.workflow.name') as workflow_name,
        COUNT(*) as span_count,
        MIN(start_time) as start_time,
        MAX(end_time) as end_time,
        (MAX(end_time) - MIN(start_time)) / 1000000.0 as duration_ms
    FROM spans
    WHERE json_extract(attributes, '$.flock.workflow') = 'true'
    GROUP BY trace_id
    ORDER BY start_time DESC
''').fetchall()

for workflow in workflows:
    print(f"Workflow: {workflow[1]} - {workflow[5]:.2f}ms ({workflow[2]} spans)")
```

### Find Slowest Workflows

```sql
SELECT
    json_extract(attributes, '$.workflow.name') as workflow,
    AVG((end_time - start_time) / 1000000.0) as avg_duration_ms,
    COUNT(*) as executions
FROM spans
WHERE name LIKE '%workflow%'
  AND json_extract(attributes, '$.flock.workflow') = 'true'
GROUP BY workflow
ORDER BY avg_duration_ms DESC
LIMIT 10
```

---

## Best Practices

### 1. Always Use Descriptive Names

```python
# ✅ Good - descriptive workflow name
async with flock.traced_run("customer_signup_flow"):
    ...

# ❌ Avoid - generic names
async with flock.traced_run("workflow"):
    ...
```

### 2. Match Workflow Scope to Business Logic

```python
# ✅ Good - one workflow per business operation
async with flock.traced_run("order_processing"):
    await flock.publish(order)
    await flock.run_until_idle()

# ❌ Avoid - wrapping unrelated operations
async with flock.traced_run("everything"):
    await process_orders()
    await send_emails()
    await generate_reports()
```

### 3. Use Custom Attributes for Metadata

```python
async with flock.traced_run("data_import") as span:
    span.set_attribute("file.path", file_path)
    span.set_attribute("record.count", len(records))

    await flock.publish(data)
    await flock.run_until_idle()
```

### 4. Handle Errors Gracefully

```python
try:
    async with flock.traced_run("risky_operation"):
        await flock.publish(data)
        await flock.run_until_idle()
except Exception as e:
    # Exception is automatically recorded in the trace
    print(f"Workflow failed: {e}")
```

---

## Clearing Traces

Use `Flock.clear_traces()` to reset the trace database for fresh debug sessions:

```python
# Clear all traces
result = Flock.clear_traces()
print(f"Deleted {result['deleted_count']} spans")

# Custom database path
result = Flock.clear_traces(".flock/custom_traces.duckdb")

# Check success
if result['success']:
    print("✅ Traces cleared!")
else:
    print(f"❌ Error: {result['error']}")
```

**Use Cases:**
- Resetting debug sessions
- Cleaning up test data
- Reducing database size
- Starting fresh trace analysis

---

## Integration with Dashboard

The Flock dashboard automatically visualizes unified traces:

```python
async def main():
    async with flock.traced_run("pizza_workflow"):
        await flock.publish(pizza_idea)
        await flock.run_until_idle()

# Start dashboard
await flock.serve(dashboard=True)
```

**Dashboard Features:**
- Timeline view with proper parent-child hierarchy
- Statistics view grouped by workflow
- Correlation tracking across workflow executions
- JSON viewer for workflow attributes

---

## Troubleshooting

### Traces Still Separate

**Problem**: Operations still create separate traces despite using `traced_run()`

**Solution**: Ensure you're using `async with` correctly:

```python
# ❌ Wrong - missing async with
flock.traced_run("workflow")
await flock.publish(data)

# ✅ Correct - async with context manager
async with flock.traced_run("workflow"):
    await flock.publish(data)
```

### Nested Traces Not Visible

**Problem**: Nested workflows don't show in trace viewer

**Solution**: Check trace filters - some viewers hide nested spans by default. Use DuckDB to verify:

```python
conn.execute('''
    SELECT name, parent_id
    FROM spans
    WHERE trace_id = 'your_trace_id'
    ORDER BY start_time
''').fetchall()
```

### Missing Workflow Attributes

**Problem**: Workflow attributes not appearing in traces

**Solution**: Verify OpenTelemetry is properly configured:

```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
```

---

## See Also

- [How to Use Tracing Effectively](how_to_use_tracing_effectively.md) - Complete tracing guide
- [Auto-Tracing Guide](auto-tracing.md) - Auto-tracing configuration
- [Production Tracing](tracing-production.md) - Production best practices
- [Trace Module Reference](trace-module.md) - Dashboard trace viewer
