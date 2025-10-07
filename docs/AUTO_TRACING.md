# Auto-Tracing with OpenTelemetry

Flock includes automatic OpenTelemetry instrumentation for all agent methods, providing detailed observability for debugging and monitoring.

## Quick Start

Enable auto-tracing by setting the environment variable:

```bash
export FLOCK_AUTO_TRACE=true
python your_agent.py
```

This automatically:
- ✅ Wraps all public methods with OTEL spans
- ✅ Configures logging to DEBUG level
- ✅ Captures trace IDs, correlation IDs, and agent metadata
- ✅ Creates parent-child span relationships for call hierarchies

## Configuration

### Basic Usage (Console Only)

```bash
# Enable auto-tracing with console logs only
export FLOCK_AUTO_TRACE=true
python your_agent.py
```

### Export to File

```bash
# Export traces to .flock/traces.jsonl
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
python your_agent.py
```

### Export to Grafana/Jaeger (OTLP)

```bash
# Send traces to OTLP endpoint (Grafana, Jaeger, etc.)
export FLOCK_AUTO_TRACE=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
python your_agent.py
```

### Disable Auto-Tracing

```bash
export FLOCK_AUTO_TRACE=false
python your_agent.py
```

## What Gets Captured

### Span Attributes

Every traced method automatically captures:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `class` | Class name of the method | `Agent`, `Flock`, `DSPyEngine` |
| `function` | Method name | `execute`, `publish`, `evaluate` |
| `module` | Python module path | `flock.orchestrator` |
| `agent.name` | Agent identifier (if applicable) | `movie`, `tagline` |
| `agent.description` | Agent description | `Generate movie ideas` |
| `correlation_id` | Request correlation ID | `12d0fcda-e7f7-4c96-ae8e-14ae4eca1518` |
| `task_id` | Task identifier | `task_abc123` |
| `result.type` | Return type | `list`, `EvalResult`, `Artifact` |
| `result.length` | Collection size (if applicable) | `3` |

### Span Hierarchy Example

```
Flock.publish (trace_id: ae40f0061e3f1bcfebe169191d138078)
└── Agent.execute
    ├── Agent.on_initialize
    │   ├── OutputUtilityComponent.on_initialize
    │   └── DSPyEngine.on_initialize
    ├── Agent.on_pre_consume
    ├── Agent.on_pre_evaluate
    ├── Agent.evaluate
    │   └── DSPyEngine.evaluate
    ├── Agent.on_post_evaluate
    ├── Agent.on_post_publish
    └── Agent.on_terminate
```

All spans within the same execution share the same `trace_id`, making it easy to trace a complete request flow.

## Console Output

With auto-tracing enabled, you'll see:

```
2025-10-07 15:32:40 | DEBUG | [trace_id: ae40f0061e3f1bcfebe169191d138078] | [tools] | Flock.publish executed successfully
2025-10-07 15:32:40 | DEBUG | [trace_id: ae40f0061e3f1bcfebe169191d138078] | [tools] | Agent.execute executed successfully
2025-10-07 15:32:40 | DEBUG | [trace_id: ae40f0061e3f1bcfebe169191d138078] | [tools] | DSPyEngine.evaluate executed successfully
```

Notice how all logs share the same `trace_id`, making it easy to filter and follow execution flow.

## Using with Grafana

### 1. Start Grafana + Tempo (OTLP Collector)

```bash
# docker-compose.yml
version: '3'
services:
  tempo:
    image: grafana/tempo:latest
    command: [ "-config.file=/etc/tempo.yaml" ]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
    ports:
      - "4317:4317"  # OTLP gRPC
      - "3200:3200"  # Tempo

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
```

```yaml
# tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces
```

### 2. Run Your Agent with OTLP Export

```bash
export FLOCK_AUTO_TRACE=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
python your_agent.py
```

### 3. Query in Grafana

- Open Grafana at `http://localhost:3000`
- Add Tempo as a data source
- Query by:
  - `trace_id` - View complete request trace
  - `correlation_id` - Group related agent executions
  - `agent.name` - Filter by specific agent
  - `service.name=flock-auto-trace` - All Flock traces

### 4. Create Dashboards

Useful queries for Grafana panels:

```promql
# Agent execution duration by agent name
histogram_quantile(0.95,
  rate(traces{service.name="flock-auto-trace", agent.name!=""}[5m])
)

# Error rate by agent
sum(rate(traces{service.name="flock-auto-trace", status.code="ERROR"}[5m]))
  by (agent.name)

# Traces by correlation ID
traces{correlation_id="12d0fcda-e7f7-4c96-ae8e-14ae4eca1518"}
```

## Using with Jaeger

### 1. Start Jaeger

```bash
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 4317:4317 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

### 2. Run Your Agent

```bash
export FLOCK_AUTO_TRACE=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
python your_agent.py
```

### 3. View Traces

- Open Jaeger UI at `http://localhost:16686`
- Select service: `flock-auto-trace`
- Search by:
  - Agent name
  - Correlation ID
  - Time range

## Skipping Methods from Tracing

Use `@skip_trace` decorator to exclude specific methods:

```python
from flock.logging.auto_trace import skip_trace

class MyComponent(AgentComponent):
    def important_method(self):
        # This will be traced
        pass

    @skip_trace
    def noisy_helper(self):
        # This will NOT be traced
        pass
```

## Performance Considerations

- **Overhead**: Each span adds ~0.1-0.5ms overhead
- **Console logging**: DEBUG logs can slow down execution significantly
- **File export**: Minimal overhead (~0.01ms per span)
- **OTLP export**: Batched, minimal overhead (~0.02ms per span)

For production:
- Disable auto-tracing or set to WARNING level
- Use sampling (export 1% of traces)
- Use OTLP with batching

## Troubleshooting

### Trace IDs showing as "no-trace"

**Cause**: Telemetry not initialized

**Fix**: Ensure `FLOCK_AUTO_TRACE=true` is set before importing flock

### OTLP connection timeout

**Cause**: OTLP endpoint not reachable

**Fix**: Don't set `OTEL_EXPORTER_OTLP_ENDPOINT` unless you have a collector running

### Too verbose logs

**Cause**: DEBUG level captures everything

**Fix**: Reduce logging or disable auto-trace for production

## Architecture

Auto-tracing uses:
- **Metaclass**: `AutoTracedMeta` wraps all public methods at class creation time
- **Decorator**: `@traced_and_logged` creates OTEL spans with proper context propagation
- **Context Propagation**: Uses OTEL's `start_as_current_span` for parent-child relationships
- **Attribute Extraction**: Automatically extracts agent name, correlation ID, etc. from method arguments

Applied to:
- `Agent` (agent.py)
- `Flock` (orchestrator.py)
- `AgentComponent` (components.py)
- All their subclasses

## Why This Matters for AI Development

When AI agents (like Claude) debug your code, they rely on **printf debugging** since they can't use interactive debuggers. Auto-tracing provides:

1. **Complete execution trace** - See exactly what methods were called and in what order
2. **Correlation tracking** - Group related operations across multiple agents
3. **Automatic context** - No manual logging needed
4. **Visual debugging** - View traces in Grafana/Jaeger for complex flows

This dramatically improves AI-assisted development by making execution flows transparent.

## Example Output

```bash
$ export FLOCK_AUTO_TRACE=true && python examples/showcase/02_hello_flock.py

2025-10-07 15:32:40 | DEBUG | [trace_id: d1339d844b78a63d9a2e2b2f4f726e25] | Flock.register_agent executed successfully
2025-10-07 15:32:40 | DEBUG | [trace_id: d1339d844b78a63d9a2e2b2f4f726e25] | Flock.agent executed successfully
2025-10-07 15:32:40 | DEBUG | [trace_id: ae40f0061e3f1bcfebe169191d138078] | Flock.publish executed successfully
2025-10-07 15:32:40 | DEBUG | [trace_id: ae40f0061e3f1bcfebe169191d138078] | OutputUtilityComponent.on_initialize executed successfully
2025-10-07 15:32:40 | DEBUG | [trace_id: ae40f0061e3f1bcfebe169191d138078] | DSPyEngine.on_initialize executed successfully
...
✅ Movie and tagline generated!
```

Notice:
- Each trace has a unique `trace_id`
- Related operations share the same `trace_id`
- Method names show full context: `Class.method`

## Further Reading

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Grafana Tempo](https://grafana.com/docs/tempo/)
- [Jaeger Tracing](https://www.jaegertracing.io/docs/)
- [OTEL Python SDK](https://opentelemetry-python.readthedocs.io/)
