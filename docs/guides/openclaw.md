# OpenClaw Integration

Flock supports [OpenClaw](https://github.com/openclaw/openclaw) agents as first-class pipeline participants. Instead of calling an LLM directly, agents delegate to an OpenClaw gateway — giving them access to tools, skills, web search, file systems, and multi-step reasoning.

## Why OpenClaw Agents?

Standard Flock agents are powerful but limited to what a single LLM call can do. OpenClaw agents can:

- **Use tools** — web search, file access, code execution, APIs
- **Access skills** — specialized capabilities installed on the OpenClaw instance
- **Reason across steps** — multi-turn problem solving, not just single-shot generation
- **Leverage different models** — each OpenClaw instance can run different models with different configurations

All while preserving Flock's blackboard semantics — subscriptions, visibility, fan-out, conditions, and tracing work unchanged.

## Gateway Prerequisite (Required)

Flock's OpenClaw integration calls the OpenResponses endpoint:

- `POST /v1/responses`

That endpoint is disabled by default on OpenClaw and **must** be enabled:

```json5
{
  gateway: {
    http: {
      endpoints: {
        responses: { enabled: true },
      },
    },
  },
}
```

Also ensure gateway auth is configured and Flock provides a valid token (or password-based bearer value).

## Quick Start

### 1. Configure Gateway

```python
from flock import Flock, OpenClawConfig, GatewayConfig

flock = Flock(
    openclaw=OpenClawConfig(
        gateways={
            "codex": GatewayConfig(
                url="http://localhost:19789",
                token_env="OPENCLAW_CODEX_TOKEN",  # env var name (not token value)
                agent_id="main",  # optional, defaults to "main"
            )
        }
    )
)
```

⚠️ Important:
- `token_env` expects the **environment variable name** (for example `"OPENCLAW_CODEX_TOKEN"`), not the token itself.
- If you want to pass a token directly, use `token="..."` instead.
- The alias passed to `flock.openclaw_agent("<alias>")` must match the configured gateway key (for example `"codex"`).

Or auto-discover from environment variables:

```bash
export OPENCLAW_CODEX_URL=http://localhost:19789
export OPENCLAW_CODEX_TOKEN=your-token
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
    flock.openclaw_agent("codex")
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

## Streaming Behavior (CLI + Dashboard)

OpenClaw now mirrors DSPy streaming defaults:

- `stream=True` by default in normal runtime.
- `stream=False` automatically under pytest (`PYTEST_CURRENT_TEST`), so tests stay deterministic.

### Runtime routing

When streaming is enabled, `OpenClawEngine` routes by sink availability:

- **Dashboard/WebSocket available** → streams SSE deltas to `WebSocketSink`.
- **No dashboard (CLI/headless run)** → streams through `RichSink` for terminal/live output.

In both cases, final output is still validated against your declared Pydantic output model before artifact publish.

### CLI concurrency guard

CLI streaming uses the same single-stream guard as DSPy:

- If another CLI stream is already active, the current run is marked queued (`_flock_output_queued=True`) and falls back to non-streaming execution.
- This prevents overlapping Rich live panels from multiple agents.

### SSE fallback behavior

- If SSE streaming fails mid-flight, the engine automatically falls back to the normal non-streaming request path.
- If fallback succeeds, the pipeline still publishes a valid typed artifact.
- Auth/token failures (`401/403`) remain fail-fast and are **not** converted into generic parse errors.

Per-agent override remains available by setting `engine.stream` explicitly.

## Local + Remote (Tailscale) Setup

### Local machine setup

1. Start OpenClaw gateway on your dev machine.
2. Enable `gateway.http.endpoints.responses.enabled: true`.
3. Set an auth token/password and export matching env vars for Flock.
4. Point Flock to local gateway URL (`http://127.0.0.1:19789` or `http://localhost:19789`).

Quick check:

```bash
curl -sS http://127.0.0.1:19789/v1/responses \
  -H "Authorization: Bearer $OPENCLAW_CODEX_TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'x-openclaw-agent-id: main' \
  -d '{"model":"openclaw","input":"ping","stream":false}'
```

### Remote machine via Tailscale Serve

Use this when OpenClaw runs on another machine and you want secure tailnet access.

1. On the gateway host, keep OpenClaw bound to loopback.
2. Enable Tailscale Serve (`tailscale serve ...`) or OpenClaw's `gateway.tailscale.mode: "serve"`.
3. Use the Serve HTTPS URL from another tailnet device in Flock:

```python
GatewayConfig(
    url="https://my-gateway.my-tailnet.ts.net",
    token_env="OPENCLAW_CODEX_TOKEN",
)
```

Notes:
- Use `https://<magicdns-host>` directly. Do **not** append `:443` unless your Serve output explicitly requires a non-default port.
- Keep the token in env vars on the client machine that runs Flock.
- If you use Tailscale identity auth (`allowTailscale`), bearer tokens may still be preferred for reproducible automation.

### Troubleshooting remote setup

- `405 Method Not Allowed` on `/api/sessions/spawn`: client is using old transport; Flock requires `/v1/responses`.
- `404`/`connection refused` on `/v1/responses`: endpoint not enabled or wrong host URL.
- `401/403`: token/password mismatch.
- `401` with seemingly correct token: check `token_env` value — it must be the **env var name** (e.g. `OPENCLAW_CODEX_TOKEN`), not the token string.
- `Unknown OpenClaw gateway alias: <alias>`: alias passed to `openclaw_agent()` does not match configured/discovered alias.
- Works locally but not remotely: verify Tailscale Serve is active and DNS name resolves from the client device.

## Configuration Reference

### OpenClawConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `gateways` | `dict[str, GatewayConfig]` | `{}` | Alias → gateway mapping |
| `defaults` | `OpenClawDefaults` | See below | Default runtime options |

### GatewayConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | `str` | Yes | Gateway URL (for example `http://localhost:19789` or a Tailscale Serve HTTPS URL) |
| `token_env` | `str` | No | Environment variable name containing auth token |
| `token` | `SecretStr` | No | Direct token value (masked in repr/logs; prefer `token_env` for security) |
| `agent_id` | `str` | No | OpenClaw agent id sent via `x-openclaw-agent-id` (default: `"main"`) |

### OpenClawDefaults

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `"spawn"` | `"spawn"` | Execution mode flag (Phase 1 transport uses stateless `/v1/responses`) |
| `timeout` | `int` | `120` | Request timeout in seconds |
| `retries` | `int` | `1` | Retry count for transient failures |
| `response_mode` | `"json_schema" \| "prompt_only"` | `"json_schema"` | Output contract mode (`json_schema` = token-level schema enforcement; `prompt_only` = prompt-embedded schema only) |

### `openclaw_agent()` Parameters

Signature:

```python
flock.openclaw_agent(
    alias: str,
    *,
    name: str | None = None,
    mode: str | None = None,
    timeout: int | None = None,
    retries: int | None = None,
    response_mode: str | None = None,
    instructions: str | None = None,
)
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `alias` | Yes | Gateway alias. Must match `OpenClawConfig.gateways` key (or `<ALIAS>` discovered by `from_env()`). |
| `name` | No | Flock agent name override (defaults to alias). |
| `mode` | No | Runtime mode override. Phase 1 supports `"spawn"` only. |
| `timeout` | No | Per-agent timeout override in seconds. |
| `retries` | No | Per-agent retry override for transient failures. |
| `response_mode` | No | Output contract mode (`"json_schema"` or `"prompt_only"`). |
| `instructions` | No | Engine-level instruction override (takes precedence over `agent.description`). |

### Per-Agent Overrides

```python
# Override timeout and retries for a specific agent
heavy_agent = (
    flock.openclaw_agent("codex", timeout=300, retries=2)
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
export OPENCLAW_CODEX_URL=http://localhost:19789
export OPENCLAW_CODEX_TOKEN=token-codex
export OPENCLAW_CLAUDE_URL=http://localhost:18789
export OPENCLAW_CLAUDE_TOKEN=token-claude
```

```python
flock = Flock(openclaw=OpenClawConfig.from_env())

# Both are now available:
writer = flock.openclaw_agent("codex").consumes(Brief).publishes(Draft)
editor = flock.openclaw_agent("claude").consumes(Draft).publishes(Final)
```

## Mixed Pipelines

OpenClaw agents compose freely with standard LLM agents:

```python
# OpenClaw agent writes code
writer = flock.openclaw_agent("codex").consumes(Spec).publishes(Code)

# Standard LLM agent reviews it
reviewer = flock.agent("reviewer").consumes(Code).publishes(Review)

# Another OpenClaw agent fixes issues
fixer = flock.openclaw_agent("claude").consumes(Review).publishes(FixedCode)
```

The blackboard doesn't care where compute comes from — it's all typed artifacts.

## Fan-Out + Multi-Output Semantics (OpenClaw)

OpenClaw supports both single-output fan-out and multi-output groups.

### Single output (existing behavior)

```python
scout = (
    flock.openclaw_agent("codex")
    .consumes(CompetitorBrief)
    .publishes(CompetitorProfile, fan_out=(3, 8))
)
```

Behavior:
- For fan-out outputs, the engine requests a JSON **array** contract.
- It materializes one artifact per returned item.
- Fan-out artifacts keep unique identities (no shared artifact-id reuse across items).
- **Fixed fan-out** (`fan_out=3`) requires exact count.
- **Dynamic fan-out range** (`fan_out=(3, 8)`) requires at least `min`; values above `max` are capped to `max`.
- Count violations use full-request retry behavior.

### Multi-output groups (envelope contract)

```python
producer = (
    flock.openclaw_agent("codex")
    .consumes(Brief)
    .publishes(Draft, Summary)
)
```

For multi-output groups, OpenClaw expects one JSON **envelope object** keyed by slot/type name:

```json
{
  "Draft": {"draft": "..."},
  "Summary": {"summary": "..."}
}
```

Rules:
- Slot keys are declaration-driven (type name in v1).
- Slot shape follows declaration:
  - non-fan-out slot → object
  - fan-out slot → array with that slot's cardinality constraints
- Unknown slots fail.
- Missing required slots fail.
- Per-slot schema + fan-out constraints are validated before publishing artifacts.

Current v1 limitation:
- If multiple declarations resolve to the same slot key (name collision), execution fails fast.
- Alias-based slot naming is the long-term fix and planned as follow-up.

## Context + Batch Parity Notes

OpenClaw request shaping now mirrors native execution semantics more closely:

- **Context history:** when context is enabled and available (`ctx.artifacts`), OpenClaw payload includes a serialized `Context:` section using JSON-safe normalization (e.g., datetimes are converted safely, no serialization crash).
- **Batch mode:** when `ctx.is_batch=True`, request text includes explicit batch-processing guidance.
- **Group description:** `publishes(..., description="...")` is injected as output guidance in the OpenClaw task prompt.
- **Instructions precedence:** engine-level `instructions=` override wins over `agent.description`.
- **response_mode:**
  - `json_schema` (default): sends strict `text.format` schema contract
  - `prompt_only`: omits `text.format` and relies on prompt-embedded schema

## Error Handling

OpenClaw failures map to standard Python exceptions:

| Failure | Exception | Retried? |
|---------|-----------|----------|
| Gateway unreachable | `RuntimeError` | Yes |
| Timeout | `RuntimeError` | Yes |
| Auth failure (401/403) | `ValueError` | No |
| 400 invalid request | `RuntimeError` | No |
| 429 / 5xx / status=`failed` | `RuntimeError` | Yes |
| Invalid JSON response | `RuntimeError` | Yes (repair attempt) |
| Schema validation failure | `RuntimeError` | No (after repair) |

## How It Works

Under the hood, `openclaw_agent()` creates a standard Flock agent with an `OpenClawEngine` — a custom engine that:

1. Serializes input artifact payload(s) and output schema into a task prompt.
2. Calls `POST /v1/responses` on the configured gateway.
3. Extracts `output[].content[].output_text`.
4. Parses and validates JSON against declared output contract:
   - single-output groups: object or fan-out array
   - multi-output groups: envelope object with per-slot validation
5. Publishes the validated artifact(s) to the blackboard.

All Flock features work unchanged because OpenClaw is just an engine swap — the orchestrator, blackboard, subscriptions, visibility, and tracing layers are unaware of the difference.

## Examples

See [`examples/11-openclaw/`](../../examples/11-openclaw/) for working examples:

| Example | Description |
|---------|-------------|
| `01_pizza_with_openclaw.py` | Simplest integration — one agent, one artifact |
| `02_mixed_pipeline.py` | OpenClaw + native agents in one workflow |
| `03_env_config.py` | Environment-based discovery + multi-gateway |
| `04_streaming_on_off.py` | Dedicated streaming mode demo (headless OFF vs dashboard ON) |
| `05_competitive_intelligence.py` | Full competitive-intelligence orchestration (comprehensive, slower) |
| `06_fast_orchestration_smoke.py` | Fast headless smoke: fan-out ID uniqueness + datetime-safe shaping + stream ON/OFF |
