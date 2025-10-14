# Tracing Quick Start

Get production-grade distributed tracing running in 30 seconds.

---

## Enable Auto-Tracing (30 Seconds)

```bash
# Enable tracing
export FLOCK_AUTO_TRACE=true

# Store traces in DuckDB (optional but recommended)
export FLOCK_TRACE_FILE=true

# Run your agent
python your_agent.py
```

**That's it!** Flock automatically:
- ✅ Instruments all agent methods with OpenTelemetry spans
- ✅ Captures input/output artifacts
- ✅ Records parent-child relationships
- ✅ Stores traces in `.flock/traces.duckdb`

---

## View Traces in Dashboard

```python
await flock.serve(dashboard=True)
# Open browser → Trace Viewer tab
```

**7 visualization modes:**
1. **Timeline** - Waterfall view with span hierarchies
2. **Statistics** - Sortable table with durations
3. **RED Metrics** - Rate, Errors, Duration monitoring
4. **Dependencies** - Agent communication graph
5. **DuckDB SQL** - Interactive queries
6. **Configuration** - Real-time filtering
7. **Guide** - Built-in documentation

---

## Unified Tracing (Single Trace Per Workflow)

Wrap workflows in a single trace for cleaner visualization:

```python
async with flock.traced_run("customer_review_workflow"):
    await flock.publish(customer_review)
    await flock.run_until_idle()
```

**Benefits:**
- ✅ All operations share same trace_id
- ✅ Clear parent-child hierarchy
- ✅ Easy to visualize entire workflow

---

## Export to Grafana/Jaeger

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

---

## Common Use Cases

### Debug Slow Workflows

**Problem:** "Workflow takes 45 seconds but should take 15"

**Solution:**
1. Enable tracing, run workflow
2. Open Timeline view in dashboard
3. Sort by duration → Find bottleneck
4. Optimize the slow operation

### Find Infinite Loops

**Problem:** "Agent keeps executing forever"

**Solution:**
1. Check Dependencies view
2. See circular edge: `critic` → `writer` → `critic`
3. Add `.prevent_self_trigger(True)`

### Monitor Production

**Problem:** "Need to know if system is healthy"

**Solution:**
1. Monitor RED Metrics view
2. Set alerts on error rate > 5%
3. Track p95 latency trends

---

## Next Steps

**Deep Dive:**
- **[Complete Tracing Guide](how_to_use_tracing_effectively.md)** - 30-minute comprehensive guide
- **[Auto-Tracing Setup](auto-tracing.md)** - Configuration details
- **[Unified Tracing](unified-tracing.md)** - Single trace per workflow
- **[Production Patterns](tracing-production.md)** - Deploy to production

**Related:**
- **[Dashboard Guide](../dashboard.md)** - Real-time visualization
- **[Core Concepts](../../getting-started/concepts.md)** - Understand Flock

---

## Troubleshooting

**Traces not appearing?**
- Check: `FLOCK_AUTO_TRACE=true` set?
- Check: `FLOCK_TRACE_FILE=true` for DuckDB storage?
- Check: `.flock/traces.duckdb` file exists?
- Solution: Verify environment variables with `echo $FLOCK_AUTO_TRACE`

**Dashboard not showing traces?**
- Check: Dashboard running? (`flock.serve(dashboard=True)`)
- Check: Trace Viewer tab open?
- Solution: Restart dashboard if opened before tracing enabled

---

**Ready for more?** Read the [complete tracing guide](how_to_use_tracing_effectively.md) for advanced techniques and real-world debugging scenarios.
