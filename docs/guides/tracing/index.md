---
title: Distributed Tracing Overview
description: Production-grade observability with OpenTelemetry and DuckDB for debugging multi-agent systems
tags:
  - tracing
  - observability
  - debugging
  - monitoring
  - guide
  - intermediate
search:
  boost: 1.5
---

# Distributed Tracing

**Flock includes production-grade distributed tracing** powered by OpenTelemetry and DuckDB. Understand emergent behavior, debug complex workflows, and monitor production systems with comprehensive observability.

**Unlike traditional logging:** Tracing captures parent-child relationships, timing data, input/output artifacts, and cross-agent dependencies—essential for blackboard systems where workflows emerge from subscriptions, not predefined graphs.

---

## Why Tracing Matters for Blackboard Systems

### The Challenge

**Blackboard systems have emergent behavior.** Agents communicate through shared data artifacts, making it nearly impossible to predict:

- **Why** did Agent B execute after Agent A?
- **What** chain of events led to this error?
- **Which** agent is the bottleneck?
- **How** do agents actually interact in production?

**Traditional logging fails** because:
- ❌ No parent-child relationships between agent calls
- ❌ Async execution makes logs non-sequential
- ❌ No visibility into cross-agent data flow
- ❌ Can't see which artifact triggered which agent

### What Tracing Solves

✅ **Parent-child span relationships** - See the complete execution tree
✅ **Correlation IDs** - Track a single request across all agents
✅ **Timing data** - Identify bottlenecks with microsecond precision
✅ **Input/Output capture** - See what data agents consumed and produced
✅ **Service dependencies** - Discover emergent agent interactions
✅ **RED Metrics** - Rate, Errors, Duration for production monitoring

**The key insight:** Blackboard systems require *discovery* tools, not just debugging tools. You need to understand what actually happened, not just verify what you thought would happen.

---

## Quick Start (30 Seconds)

### Enable Auto-Tracing

```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true  # Store traces in .flock/traces.duckdb

python your_agent.py
```

**That's it.** Flock automatically:
- ✅ Instruments all agent methods with OpenTelemetry spans
- ✅ Captures input/output artifacts
- ✅ Records parent-child relationships
- ✅ Stores traces in high-performance DuckDB

### View Traces in Dashboard

```python
await flock.serve(dashboard=True)
# Open browser → Trace Viewer tab
```

**7 visualization modes:**
1. **Timeline** - Waterfall view with span hierarchies
2. **Statistics** - Sortable table with durations and errors
3. **RED Metrics** - Rate, Errors, Duration monitoring
4. **Dependencies** - Service-to-service communication graph
5. **DuckDB SQL** - Interactive SQL queries with CSV export
6. **Configuration** - Real-time filtering
7. **Guide** - Built-in documentation

[**👉 See auto-tracing setup**](auto-tracing.md)

---

## Unified Tracing: Single Trace Per Workflow

**Wrap workflows in a single trace** for cleaner visualization:

```python
async with flock.traced_run("customer_review_workflow"):
    # All operations share the same trace_id
    await flock.publish(customer_review)
    await flock.run_until_idle()
```

**Before `traced_run()`:**
- ❌ `publish()` creates Trace 1
- ❌ `run_until_idle()` creates Trace 2 (separate!)
- ❌ Hard to see complete workflow

**After `traced_run()`:**
- ✅ All operations share same trace_id
- ✅ Clear parent-child hierarchy
- ✅ Easy to visualize entire workflow

[**👉 Learn about unified tracing**](unified-tracing.md)

---

## Documentation Structure

### Getting Started

**[Auto-Tracing Guide](auto-tracing.md)** ⭐ **Start here**
- Enable tracing with environment variables
- Export to DuckDB, Grafana, or Jaeger
- Configuration options and best practices
- **Time:** 5 minutes

**[Unified Tracing with traced_run()](unified-tracing.md)**
- Group operations into single trace
- Clean hierarchical visualization
- Production workflow patterns
- **Time:** 10 minutes

### Comprehensive Guides

**[How to Use Tracing Effectively](how_to_use_tracing_effectively.md)** 📖 **Deep dive**
- Complete guide to debugging and monitoring
- Seven trace viewer modes explained
- Real-world debugging scenarios
- Advanced techniques and production best practices
- **Time:** 30 minutes

**[Production Tracing Patterns](tracing-production.md)**
- Deploy tracing to production
- Integration with Grafana/Jaeger/Datadog
- Performance considerations
- Cost optimization strategies

### Technical Reference

**[Trace Module Technical Details](trace-module.md)**
- Implementation architecture
- OpenTelemetry integration
- DuckDB schema design
- Extension and customization

---

## The Seven Trace Viewer Modes

### 1. Timeline View (Waterfall)

**Purpose:** Visualize execution flow and identify bottlenecks

**What you see:**
- Parent-child span relationships (nested tree)
- Exact duration of each operation (microsecond precision)
- Concurrent execution patterns
- Critical path analysis

**Use when:**
- Debugging slow workflows
- Understanding execution order
- Identifying parallelization opportunities

### 2. Statistics View (Table)

**Purpose:** Compare performance across operations

**What you see:**
- Sortable table of all spans
- Duration, start time, status (success/error)
- Filter by operation name, service, status
- Export to CSV for analysis

**Use when:**
- Finding slowest operations
- Tracking error rates
- Performance optimization

### 3. RED Metrics (Service Health)

**Purpose:** Monitor production service health

**What you see:**
- **R**ate: Requests per second per service
- **E**rrors: Error percentage and counts
- **D**uration: Latency percentiles (p50, p95, p99)
- Time-series graphs

**Use when:**
- Production monitoring
- SLO tracking
- Capacity planning

### 4. Dependencies View (Graph)

**Purpose:** Discover emergent agent interactions

**What you see:**
- Service-to-service communication graph
- Request volumes between agents
- Error rates per connection
- Circular dependency detection

**Use when:**
- Understanding system architecture
- Finding bottleneck services
- Identifying circular dependencies

### 5. DuckDB SQL View (Query)

**Purpose:** Ad-hoc analysis and custom reporting

**What you see:**
- Interactive SQL query editor
- Full access to trace data schema
- CSV export for offline analysis
- Saved query templates

**Use when:**
- Custom analytics
- Debugging complex issues
- Building reports

### 6. Configuration View (Filtering)

**Purpose:** Focus on specific traces/services

**What you see:**
- Filter by service name
- Filter by operation type
- Time range selection
- Hide/show specific spans

**Use when:**
- Reducing noise in complex systems
- Focusing on specific agents
- Time-based analysis

### 7. Guide View (Documentation)

**Purpose:** Built-in help and examples

**What you see:**
- Query examples
- Keyboard shortcuts
- Feature explanations
- Troubleshooting tips

**Use when:**
- Learning trace viewer features
- Finding SQL query examples
- Quick reference

---

## Real-World Use Cases

### Debugging Slow Workflows

**Symptom:** "Our code review workflow takes 45 seconds but should take 15"

**Solution:**
1. Enable tracing, run workflow
2. Open Timeline view
3. Sort by duration
4. Identify bottleneck: `security_auditor` takes 30 seconds
5. Drill into span: See LLM prompt is 8KB (too long!)
6. Optimize prompt, re-test

**[Full debugging scenarios →](how_to_use_tracing_effectively.md#real-world-debugging-scenarios)**

### Finding Infinite Loops

**Symptom:** "Agent keeps executing forever"

**Solution:**
1. Check Dependencies view
2. See circular edge: `critic` → `writer` → `critic`
3. Add `prevent_self_trigger(True)` to critic
4. Verify in Timeline view

### Production Monitoring

**Symptom:** "Need to know if system is healthy"

**Solution:**
1. Monitor RED Metrics view
2. Set alerts on error rate > 5%
3. Track p95 latency trends
4. Export metrics to Grafana

---

## Integration with Grafana/Jaeger

### Export to OTLP Endpoint

```bash
export FLOCK_AUTO_TRACE=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc

python your_agent.py
```

**Supported backends:**
- Grafana Cloud
- Jaeger
- Datadog APM
- New Relic
- Honeycomb
- Any OTLP-compatible service

**[Full production setup →](tracing-production.md)**

---

## Performance Considerations

### Overhead

**Tracing overhead:**
- CPU: <2% per traced operation
- Memory: ~50KB per trace in memory
- Disk: ~10KB per trace in DuckDB (columnar compression)

**Best practices:**
- ✅ Use tracing in development (always on)
- ✅ Use sampling in production (10-100% depending on volume)
- ✅ DuckDB storage is highly efficient (10-100x faster than JSON)
- ❌ Avoid capturing large artifacts (>100KB) in spans

### Storage

**DuckDB trace storage:**
- Columnar format: 10-100x compression vs JSON
- Built-in analytics: Query traces with SQL
- No external dependencies: Embedded database

**Example sizes:**
- 1 million spans: ~100MB DuckDB
- Query performance: <100ms for most queries
- Retention: Configurable, default 30 days

---

## Clearing Traces (Development)

**During development, clear old traces:**

```python
# Clear all traces in DuckDB
result = Flock.clear_traces()
print(f"Cleared {result['deleted_count']} traces")
```

**When to clear:**
- Before starting fresh debug session
- After completing feature development
- When testing specific scenarios

---

## Best Practices

### ✅ Do

- **Enable tracing in development** - Always on, invaluable for debugging
- **Use `traced_run()` for workflows** - Single trace per logical workflow
- **Monitor RED metrics in production** - Early warning system for issues
- **Query DuckDB for insights** - Discover patterns you didn't expect
- **Export to Grafana for dashboards** - Long-term monitoring and alerting
- **Sample in high-volume production** - 10-100% sampling rate depending on load

### ❌ Don't

- **Don't disable tracing** - Overhead is minimal, visibility is priceless
- **Don't capture giant artifacts** - Keep spans <100KB for performance
- **Don't ignore Dependencies view** - Reveals emergent architecture
- **Don't skip Timeline view** - Best tool for understanding execution flow
- **Don't forget to clear traces** - Old traces clutter analysis in development

---

## What Makes Flock's Tracing Unique?

### 1. Blackboard-Native

**Other frameworks:** Designed for graph-based workflows with known edges

**Flock:** Designed for emergent behavior where agents communicate through artifacts

**Why it matters:** Dependencies view reveals actual agent interactions, not just predefined edges

### 2. DuckDB Storage

**Other frameworks:** Export to external trace collector (Jaeger, Zipkin)

**Flock:** Built-in DuckDB storage with SQL analytics

**Why it matters:**
- No external dependencies
- 10-100x faster queries
- Embedded trace viewer in dashboard
- Offline analysis without network

### 3. Full I/O Capture

**Other frameworks:** Log timestamps and durations

**Flock:** Capture complete input/output artifacts (with size limits)

**Why it matters:** See exactly what data agent consumed and produced, not just that it executed

### 4. Zero Configuration

**Other frameworks:** Configure exporters, collectors, sampling

**Flock:** `export FLOCK_AUTO_TRACE=true`

**Why it matters:** Works out of the box, no YAML configuration files

---

## Troubleshooting

### Traces not appearing in dashboard

**Check:**
- `FLOCK_AUTO_TRACE=true` set?
- `FLOCK_TRACE_FILE=true` for DuckDB storage?
- Dashboard running? (`flock.serve(dashboard=True)`)
- Trace Viewer tab open in dashboard?

**Solution:**
- Verify environment variables: `echo $FLOCK_AUTO_TRACE`
- Check `.flock/traces.duckdb` file exists
- Restart dashboard if opened before tracing enabled

### DuckDB file growing too large

**Check:**
- How many traces stored? `SELECT COUNT(*) FROM traces`
- Retention period configured?

**Solution:**
- Clear old traces: `Flock.clear_traces()`
- Configure retention policy in production
- Export to external system (Grafana) and clear local

### Slow dashboard performance

**Check:**
- How many spans in current trace? Timeline view shows count
- Artifact sizes? Large artifacts (>100KB) slow rendering

**Solution:**
- Filter to recent time range (last 5 minutes)
- Query specific trace_id instead of loading all
- Avoid capturing large artifacts in spans

---

## Next Steps

**Getting Started:**
1. **[Enable auto-tracing](auto-tracing.md)** - 5-minute setup
2. **[Use traced_run()](unified-tracing.md)** - Wrap workflows
3. **[Explore the dashboard](../dashboard.md)** - Seven trace viewer modes

**Deep Dive:**
4. **[How to Use Tracing Effectively](how_to_use_tracing_effectively.md)** - Complete guide
5. **[Production Patterns](tracing-production.md)** - Deploy to production
6. **[Technical Reference](trace-module.md)** - Implementation details

**Related Guides:**
- **[Dashboard Guide](../dashboard.md)** - Real-time visualization
- **[Core Concepts](../../getting-started/concepts.md)** - Understand Flock architecture
- **[Quick Start](../../getting-started/quick-start.md)** - Build your first agent

---

## Summary

**Flock's distributed tracing provides:**

✅ **OpenTelemetry auto-instrumentation** - Zero-code tracing for all agents
✅ **DuckDB storage** - Fast, embedded, no external dependencies
✅ **Seven trace viewer modes** - Timeline, Statistics, RED, Dependencies, SQL, Config, Guide
✅ **Full I/O capture** - See complete input/output artifacts
✅ **Unified tracing** - Single trace per workflow with `traced_run()`
✅ **Production-ready** - Export to Grafana/Jaeger/Datadog
✅ **Blackboard-native** - Discover emergent agent interactions

**Start tracing:** `export FLOCK_AUTO_TRACE=true && python your_agent.py`

**View traces:** Open dashboard → Trace Viewer tab → Explore!
