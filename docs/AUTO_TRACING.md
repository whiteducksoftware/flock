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

### Export to DuckDB

```bash
# Export traces to .flock/traces.duckdb
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
python your_agent.py
```

Traces are stored in a DuckDB database, which provides:
- ✅ **10-100x faster** queries than JSON/SQLite
- ✅ Built-in trace viewer UI in the Flock dashboard
- ✅ SQL analytics for debugging and monitoring
- ✅ Efficient columnar storage

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

## Filtering: Whitelist and Blacklist

Control which operations get traced to reduce overhead and noise. This is especially important to **avoid tracing streaming token operations** which can cause performance issues.

### How Filtering Works: Two-Stage Process

#### Stage 1: Wrapping Methods with `@traced_and_logged`

Methods must first be wrapped with the tracing decorator. This happens automatically via metaclasses:

- **`AutoTracedMeta`**: Wraps all public methods in `Agent` and `Flock` classes
- **`TracedModelMeta`**: Wraps all public methods in `AgentComponent` subclasses

Classes using these metaclasses:
- `Agent` (from agent.py)
- `Flock` (from orchestrator.py)
- `AgentComponent` and all subclasses:
  - `EngineComponent` (DSPyEngine, ClaudeEngine, etc.)
  - `OutputUtilityComponent`
  - `DashboardEventCollector`
  - `MetricsUtility`, `LoggingUtility`
  - All custom components

#### Stage 2: Filter Check (Whitelist/Blacklist)

**Only wrapped methods** reach the filter. Before creating an OTEL span, the decorator checks:

```python
service_name = span_name.split('.')[0]  # Extract class name
# Example: "Agent.execute" → service_name = "Agent"

if not should_trace(service_name, span_name):
    return func(*args, **kwargs)  # Skip span creation entirely
```

**Key Point**: Methods that are not wrapped (e.g., plain functions, non-component classes) are never traced, regardless of whitelist/blacklist settings.

### Whitelist: FLOCK_TRACE_SERVICES

**Filters by CLASS NAME** (case-insensitive). Only trace methods from specified classes.

```bash
# Only trace Agent and Flock classes
export FLOCK_TRACE_SERVICES='["agent", "flock"]'
```

**Behavior**:
- If set: Only traces methods from listed classes
- If empty/unset: Traces **ALL** wrapped classes
- Case-insensitive: `"agent"`, `"Agent"`, `"AGENT"` all match `Agent` class

**Example**:
```bash
FLOCK_TRACE_SERVICES='["agent", "flock", "dspyengine"]'
```

**Result**:
- ✅ `Agent.execute` - traced (Agent in whitelist)
- ✅ `Flock.publish` - traced (Flock in whitelist)
- ✅ `DSPyEngine.evaluate` - traced (DSPyEngine in whitelist)
- ❌ `OutputUtilityComponent.on_post_evaluate` - NOT traced (not in whitelist)
- ❌ `DashboardEventCollector.collect_event` - NOT traced (not in whitelist)

### Blacklist: FLOCK_TRACE_IGNORE

**Filters by FULL OPERATION NAME** (exact match). Never trace specific methods.

```bash
# Never trace these specific methods
export FLOCK_TRACE_IGNORE='["DashboardEventCollector.set_websocket_manager", "Agent.get_identity"]'
```

**Behavior**:
- Exact match on `ClassName.method_name`
- Takes priority over whitelist
- Use this to exclude noisy or low-value operations

**Example**:
```bash
FLOCK_TRACE_SERVICES='["agent", "dashboardeventcollector"]'
FLOCK_TRACE_IGNORE='["DashboardEventCollector.set_websocket_manager"]'
```

**Result**:
- ✅ `Agent.execute` - traced (in whitelist, not in blacklist)
- ✅ `DashboardEventCollector.collect_event` - traced (in whitelist, not in blacklist)
- ❌ `DashboardEventCollector.set_websocket_manager` - NOT traced (in blacklist)

### Filter Priority

1. **Blacklist** (highest priority) - If in `FLOCK_TRACE_IGNORE`, never trace
2. **Whitelist** - If `FLOCK_TRACE_SERVICES` is set, only trace listed services
3. **Default** - If no filters set, trace everything that's wrapped

### Recommended Configuration

Add to your `.env` file:

```bash
# Trace core agent execution, avoid streaming token overhead
FLOCK_TRACE_SERVICES=["flock", "agent", "dspyengine", "outpututilitycomponent"]

# Exclude noisy operations
FLOCK_TRACE_IGNORE=["DashboardEventCollector.set_websocket_manager"]

# Auto-delete traces older than 30 days
FLOCK_TRACE_TTL_DAYS=30
```

**Why these defaults?**
- `flock` - Core orchestration (publish, scheduling)
- `agent` - Agent lifecycle and execution
- `dspyengine` - LLM calls and responses
- `outpututilitycomponent` - Output formatting
- Excludes dashboard/streaming operations to avoid performance issues
- TTL keeps database size manageable by removing old debugging data

### Trace Time-To-Live (TTL)

Control database size by automatically deleting old traces:

```bash
# Delete traces older than 30 days
export FLOCK_TRACE_TTL_DAYS=30
```

**How it works:**
- Cleanup runs **on application startup** (when DuckDB exporter initializes)
- Uses the `created_at` timestamp field from the spans table
- Deletes all spans older than the specified number of days
- Prints a summary: `[DuckDB TTL] Deleted 1234 spans older than 30 days`

**When to use TTL:**
- ✅ Development environments - Keep database small, remove old debugging sessions
- ✅ Production - Retain recent traces for debugging, delete historical data
- ✅ CI/CD - Clean up test traces automatically
- ❌ Long-term analytics - If you need historical trace data, disable TTL or export to separate storage

**Performance impact:**
- Cleanup uses indexed `created_at` field for fast deletion
- Runs only once per application startup
- Near-zero runtime overhead

**Example scenarios:**

```bash
# Development: Keep last 7 days only
FLOCK_TRACE_TTL_DAYS=7

# Production: Keep last 30 days
FLOCK_TRACE_TTL_DAYS=30

# Long-term retention: Keep last 90 days
FLOCK_TRACE_TTL_DAYS=90

# No cleanup: Keep all traces forever
# FLOCK_TRACE_TTL_DAYS=  (leave empty or comment out)
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

### Option 1: Use Filtering (Recommended)

Use environment variables to control tracing at runtime without code changes:

```bash
# Exclude specific operations
export FLOCK_TRACE_IGNORE='["MyComponent.noisy_helper"]'
```

This is preferred because:
- ✅ No code changes required
- ✅ Can be adjusted per environment (dev/staging/prod)
- ✅ Easy to add/remove without modifying source

### Option 2: Use `@skip_trace` Decorator

For methods that should **never** be traced in any environment:

```python
from flock.logging.auto_trace import skip_trace

class MyComponent(AgentComponent):
    def important_method(self):
        # This will be traced (if class is whitelisted)
        pass

    @skip_trace
    def noisy_helper(self):
        # This will NEVER be traced, even if whitelisted
        pass
```

**When to use `@skip_trace`**:
- Methods called thousands of times per second
- Methods with sensitive data you never want logged
- Internal helpers that provide no debugging value

## Performance Considerations

- **Overhead**: Each span adds ~0.1-0.5ms overhead
- **Console logging**: DEBUG logs can slow down execution significantly
- **DuckDB export**: Minimal overhead (~0.01ms per span)
- **OTLP export**: Batched, minimal overhead (~0.02ms per span)
- **Filtering**: Filter check happens **before** span creation, so filtered operations have near-zero overhead

For production:
- **Use filtering** to trace only core services (recommended)
- Use DuckDB export instead of OTLP for lower overhead
- Disable DEBUG console logging
- Use blacklist to exclude high-frequency operations

**Example production config**:
```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true  # DuckDB only, no console spam
export FLOCK_TRACE_SERVICES='["agent", "flock"]'  # Core services only
export FLOCK_TRACE_IGNORE='["DashboardEventCollector.set_websocket_manager"]'
```

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

Auto-tracing uses a two-stage approach:

### Stage 1: Method Wrapping (Compile Time)
- **Metaclasses**: `AutoTracedMeta` and `TracedModelMeta` wrap all public methods at class creation time
- **Decorator**: `@traced_and_logged` added to each public method
- Applied to:
  - `Agent` (agent.py) - via `AutoTracedMeta`
  - `Flock` (orchestrator.py) - via `AutoTracedMeta`
  - `AgentComponent` (components.py) - via `TracedModelMeta`
  - All their subclasses inherit the metaclass

### Stage 2: Filter Check (Runtime)
- **Filter Configuration**: `TraceFilterConfig` loaded from environment variables at startup
- **Filter Check**: Before creating spans, decorator checks `should_trace(service, operation)`
- **Early Exit**: Filtered operations skip span creation entirely (near-zero overhead)

### OTEL Span Creation
- **Context Propagation**: Uses OTEL's `start_as_current_span` for parent-child relationships
- **Attribute Extraction**: Automatically extracts agent name, correlation ID, etc. from method arguments
- **Error Handling**: Records exceptions and sets span status
- **Output Capture**: Serializes return values to JSON for debugging

### Data Flow
```
Method Call
  → Filter Check (whitelist/blacklist)
    → If filtered: Execute method directly (no tracing)
    → If not filtered: Create OTEL span
      → Extract attributes (class, agent.name, correlation_id, etc.)
      → Execute method
      → Capture output
      → Set span status
      → Export to DuckDB/OTLP
```

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
