# OpenClaw Integration

Flock supports [OpenClaw](https://github.com/openclaw/openclaw) agents as first-class pipeline participants. Instead of calling an LLM directly, agents delegate to an OpenClaw gateway — giving them access to tools, skills, web search, file systems, and multi-step reasoning.

## Why OpenClaw Agents?

Standard Flock agents are powerful but limited to what a single LLM call can do. OpenClaw agents can:

- **Use tools** — web search, file access, code execution, APIs
- **Access skills** — specialized capabilities installed on the OpenClaw instance
- **Reason across steps** — multi-turn problem solving, not just single-shot generation
- **Leverage different models** — each OpenClaw instance can run different models with different configurations

All while preserving Flock's blackboard semantics — subscriptions, visibility, fan-out, conditions, and tracing work unchanged.

## Quick Start

### 1. Configure Gateway

```python
from flock import Flock, OpenClawConfig, GatewayConfig

flock = Flock(
    openclaw=OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token_env="OPENCLAW_CODIE_TOKEN",
            )
        }
    )
)
```

Or auto-discover from environment variables:

```bash
export OPENCLAW_CODIE_URL=http://localhost:19789
export OPENCLAW_CODIE_TOKEN=your-token
```

```python
flock = Flock(openclaw=OpenClawConfig.from_env())
```

### 2. Create OpenClaw Agent

Same fluent API as standard agents — just swap `agent()` for `openclaw_agent()`:

```python
from flock.registry import flock_type
from pydantic import BaseModel, Field

@flock_type
class Spec(BaseModel):
    feature: str = Field(description="Feature to implement")

@flock_type
class Code(BaseModel):
    implementation: str = Field(description="The code")
    explanation: str = Field(description="Why this approach")

implementer = (
    flock.openclaw_agent("codie")
    .description("Implements features from specs")
    .consumes(Spec)
    .publishes(Code)
)
```

### 3. Run

```python
await flock.publish(Spec(feature="Add rate limiting"))
await flock.run_until_idle()
```

## Configuration Reference

### OpenClawConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `gateways` | `dict[str, GatewayConfig]` | `{}` | Alias → gateway mapping |
| `defaults` | `OpenClawDefaults` | See below | Default runtime options |

### GatewayConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | `str` | Yes | Gateway URL (e.g., `http://localhost:19789`) |
| `token_env` | `str` | No | Environment variable name containing auth token |
| `token` | `str` | No | Direct token value (prefer `token_env` for security) |

### OpenClawDefaults

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `"spawn"` | `"spawn"` | Execution mode (Phase 1: spawn only) |
| `timeout` | `int` | `120` | Request timeout in seconds |
| `retries` | `int` | `1` | Retry count for transient failures |
| `response_mode` | `"json_schema"` | `"json_schema"` | How output schema is communicated |

### Per-Agent Overrides

```python
# Override timeout and retries for a specific agent
heavy_agent = (
    flock.openclaw_agent("codie", timeout=300, retries=2)
    .consumes(ComplexInput)
    .publishes(ComplexOutput)
)
```

## Environment-Based Discovery

The `from_env()` method discovers gateways from environment variables following the convention:

```
OPENCLAW_<ALIAS>_URL   → Gateway URL
OPENCLAW_<ALIAS>_TOKEN → Auth token
```

Multiple gateways are supported:

```bash
export OPENCLAW_CODIE_URL=http://localhost:19789
export OPENCLAW_CODIE_TOKEN=token-codie
export OPENCLAW_CLAUDE_URL=http://localhost:18789
export OPENCLAW_CLAUDE_TOKEN=token-claude
```

```python
flock = Flock(openclaw=OpenClawConfig.from_env())

# Both are now available:
writer = flock.openclaw_agent("codie").consumes(Brief).publishes(Draft)
editor = flock.openclaw_agent("claude").consumes(Draft).publishes(Final)
```

## Mixed Pipelines

OpenClaw agents compose freely with standard LLM agents:

```python
# OpenClaw agent writes code
writer = flock.openclaw_agent("codie").consumes(Spec).publishes(Code)

# Standard LLM agent reviews it
reviewer = flock.agent("reviewer").consumes(Code).publishes(Review)

# Another OpenClaw agent fixes issues
fixer = flock.openclaw_agent("claude").consumes(Review).publishes(FixedCode)
```

The blackboard doesn't care where compute comes from — it's all typed artifacts.

## Error Handling

OpenClaw failures map to standard Python exceptions:

| Failure | Exception | Retried? |
|---------|-----------|----------|
| Gateway unreachable | `RuntimeError` | Yes |
| Timeout | `RuntimeError` | Yes |
| Auth failure (401/403) | `ValueError` | No |
| Invalid JSON response | `RuntimeError` | Yes (one repair attempt) |
| Schema validation failure | `RuntimeError` | No (after repair) |

## How It Works

Under the hood, `openclaw_agent()` creates a standard Flock agent with an `OpenClawEngine` — a custom engine that:

1. Serializes the input artifact and output schema into a task prompt
2. Spawns an isolated session on the OpenClaw gateway
3. Parses the structured JSON response
4. Validates against the Pydantic output model
5. Publishes the validated artifact to the blackboard

All Flock features work unchanged because OpenClaw is just an engine swap — the orchestrator, blackboard, subscriptions, visibility, and tracing layers are unaware of the difference.

## Examples

See [`examples/11-openclaw/`](../../examples/11-openclaw/) for working examples:

| Example | Description |
|---------|-------------|
| `01_pizza_with_openclaw.py` | Simplest integration — one agent, one artifact |
| `02_mixed_pipeline.py` | OpenClaw + native agents in one workflow |
| `03_env_config.py` | Environment-based discovery + multi-gateway |
