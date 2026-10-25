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

### Export over OTLP (gRPC or HTTP)

```bash
# Send traces to an OTLP endpoint over gRPC (Grafana, Jaeger, etc.)
export FLOCK_AUTO_TRACE=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
python your_agent.py
```

Some tools take OTLP over HTTP only, among them Langfuse, Opik and MLflow. Choose HTTP with the
protocol variable; Flock appends `/v1/traces` to the base endpoint, as the OpenTelemetry spec says:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20<base64 credentials>"   # if the tool needs it
python your_agent.py
```

| Variable | Meaning |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base endpoint; setting it switches OTLP export on |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Full traces endpoint, used as given (wins over the base endpoint, also switches export on) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` (default) or `http/protobuf`; `http/json` falls back to `http/protobuf` with a warning |
| `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | The same for traces only (wins over the general one) |
| `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | Headers as `key=value` pairs, comma-separated and URL-encoded, for example authentication |

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

### Trace level: FLOCK_TRACE_LEVEL

By default Flock traces the work of a flock, not itself:

| `FLOCK_TRACE_LEVEL` | Traced |
|---|---|
| `agents` (default) | Workflow roots (`Flock.publish`, `invoke`, `run_until_idle`, `traced_run`, ...), `Agent.execute`, the engines and the agent's own utility components, decision requests, tool and MCP calls, and errors |
| `all` | Also Flock's internals: the dashboard serving itself (`DashboardEventCollector`, `GraphAssembler`, the HTTP requests), the built-in orchestrator components (circuit breaker, deduplication, collection, activation, timer), and building and registering (`Flock.agent`, `register_agent`, `serve`, ...) |

```bash
export FLOCK_TRACE_LEVEL=all   # to debug Flock itself
```

With the triage demo and the dashboard open, 30 seconds wrote 208 spans (1.2 MB of attributes) at `agents` and 1,551 spans (8.3 MB) at `all`. `FLOCK_TRACE_SERVICES` and `FLOCK_TRACE_IGNORE` filter on top of the level: a service the level leaves out stays out.

At both levels, agent work that an HTTP request starts joins the caller's trace (`traceparent` and `baggage` headers), or the request span of a host that instruments the app itself; `agents` only leaves out Flock's own request span.

Classes of your own can do the same: `__trace_level__ = "all"` in a class that uses the auto-tracing metaclass (or a component's subclass), or `@trace_level("all")` on one method (`from flock.logging.auto_trace import trace_level`), traces it only at `all`.

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
3. **Default** - If no filters set, trace everything that's wrapped at the trace level

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
- Cleanup deletes by the `created_at` timestamp in one statement; DuckDB skips the blocks that hold only newer spans
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

### Export in batches

Spans are exported in batches by a background thread, not one at a time by the code that ends them. A batch goes out at least every second, so the dashboard's traces stay current, or once 512 spans are waiting. OpenTelemetry's variables tune this:

```bash
export OTEL_BSP_SCHEDULE_DELAY=5000        # milliseconds between batches (Flock's default: 1000)
export OTEL_BSP_MAX_EXPORT_BATCH_SIZE=512  # spans per batch
export OTEL_BSP_MAX_QUEUE_SIZE=2048        # spans waiting at most; more are dropped
```

`Flock.shutdown()` writes the spans still waiting (it waits at most five seconds for a slow exporter), and so does the end of the process. `Flock.clear_traces()` and the dashboard's clear write them before they delete, so cleared spans do not come back.

### Size of inputs and outputs: FLOCK_TRACE_MAX_ATTRIBUTE_BYTES

A span keeps each input and its output as JSON, up to 4 KB each by default, the marker included. A longer value is cut, and the attribute says so: `{"truncated": true, "bytes": 18234, "preview": "..."}` with as much of the value's start as fits (never splitting a character). Artifacts in inputs and outputs are kept short: `{"artifact": "app.Reply", "id": "...", "produced_by": "support", "payload": {...}}`, without their visibility, tags and timestamps, which the blackboard has for those that reached it.

```bash
export FLOCK_TRACE_MAX_ATTRIBUTE_BYTES=16384  # keep more of each value
export FLOCK_TRACE_MAX_ATTRIBUTE_BYTES=0      # no cap
```

With the triage demo and the dashboard open for 30 seconds at `FLOCK_TRACE_LEVEL=all`, the spans held 7.4 MB of attributes without a cap (the largest span 48 KB) and 6.3 MB with the default cap (the largest 10 KB, a span has several inputs). At `agents` no value of the demo reaches 4 KB; the short artifacts took its spans from 5.8 to 4.7 KB of attributes on average.

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
| `input.<parameter>` | Each argument as JSON, within `FLOCK_TRACE_MAX_ATTRIBUTE_BYTES` | `{"artifact": "app.Reply", "id": "...", "produced_by": "support", "payload": {...}}` |
| `output.value` | The return value as JSON, within `FLOCK_TRACE_MAX_ATTRIBUTE_BYTES` | `[{"artifact": "app.Reply", ...}]` |
| `output.type` | Return type | `list`, `EvalResult`, `Artifact` |
| `output.length` | Collection size (if applicable) | `3` |

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
    │       └── LM.chat                     (one per model call)
    ├── Agent.on_post_evaluate
    ├── Agent.on_post_publish
    └── Agent.on_terminate
```

All spans within the same execution share the same `trace_id`, making it easy to trace a complete request flow.

### Model calls: GenAI spans

Every model call of the DSPy engine gets a span of its own, `LM.chat`, in the
[OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).
Observability tools such as Langfuse, Opik and Phoenix show these spans as model calls with their
model and tokens; Flock's own totals per run stay on `Agent.execute` as `flock.usage.tokens` and
`flock.usage.cost_usd`.

| Attribute | Description | Example |
|-----------|-------------|---------|
| `gen_ai.operation.name` | Always `chat` | `chat` |
| `gen_ai.provider.name` | Provider, from the LiteLLM model name | `azure.ai.openai`, `openai`, `anthropic` |
| `gen_ai.request.model` | Model as configured | `azure/gpt-4.1` |
| `gen_ai.response.model` | Model that answered | `gpt-4.1-2025-04-14` |
| `gen_ai.agent.name` | The Flock agent that made the call | `writer` |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Tokens of this call, streamed calls included | `566`, `162` |
| `gen_ai.request.temperature`, `gen_ai.request.max_tokens`, `gen_ai.request.top_p` | Request parameters, when set | `0.2`, `32000` |
| `gen_ai.response.id`, `gen_ai.response.finish_reasons` | Response ID and finish reasons | `chatcmpl-...`, `["stop"]` |

Message content stays off the spans unless you ask for it, as the conventions recommend:
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` adds `gen_ai.input.messages` and
`gen_ai.output.messages`, each within `FLOCK_TRACE_MAX_ATTRIBUTE_BYTES`. To leave the spans out,
add `LM.chat` to `FLOCK_TRACE_IGNORE`; with `FLOCK_TRACE_SERVICES`, add `lm` to keep them.

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

## When your host owns OpenTelemetry

With `FLOCK_AUTO_TRACE` enabled (the default), importing Flock installs an
OpenTelemetry tracer provider unless one is already installed. A host that
configures OpenTelemetry itself - for example the Microsoft Foundry agent
server - should do so *before* importing Flock, or set
`FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1` (keeps Flock's spans, lets the host's
provider export them) or `FLOCK_AUTO_TRACE=false` (no Flock spans, no DEBUG
logging). Flock chains to the previously installed `sys.excepthook`.

## Using with Jaeger

Jaeger ingests OTLP natively, so Flock exports to it through the OTLP exporter.
The legacy `opentelemetry-exporter-jaeger` packages were removed (they cannot be
installed next to current OpenTelemetry releases); `TelemetryConfig(jaeger_endpoint=...)`
now raises an error pointing to `OTEL_EXPORTER_OTLP_ENDPOINT`.

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
