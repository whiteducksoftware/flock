# Flock × OpenClaw Integration — Concept Document

**Authors:** Claude + Codie | **Date:** 2026-02-11 | **Status:** Approved for Phase 1

---

## Locked Decisions (Phase 1)

These are resolved — no further discussion needed during implementation:

1. **`openclaw_agent()` lives on the Flock class directly** — core API, not an extension. DX over decoupling.
2. **V1 supports single output type only** — no multi-type return envelope. Multi-type fan-out is Phase 3.
3. **Spawn cleanup default = `delete`** — isolated sessions are deleted after result is collected. Configurable override available.
4. **OpenClaw agents show in dashboard with a badge** — they're normal agent nodes with a small OpenClaw icon/indicator to distinguish from LLM agents.

---

## Vision

OpenClaw agents become first-class Flock agents. Same fluent API, same blackboard semantics, different compute backend. Instead of calling an LLM directly, the agent delegates to an OpenClaw agent that can use its full toolkit — tools, skills, web search, file access, reasoning — to produce structured output.

```python
pizza_master = flock.openclaw_agent("codie").consumes(MyPizzaIdea).publishes(Pizza)
```

One line. Same DX. But behind the scenes, Codie (or Claude, or any OpenClaw agent) does the work.

---

## API Design

### Setup — Register Gateways

```python
from flock import Flock
from flock.integrations.openclaw import OpenClawConfig

flock = Flock(
    openclaw=OpenClawConfig(
        gateways={
            "codie": {"url": "http://localhost:19789", "token_env": "OPENCLAW_CODIE_TOKEN"},
            "claude": {"url": "http://localhost:18789", "token_env": "OPENCLAW_CLAUDE_TOKEN"},
        },
        defaults={
            "mode": "spawn",        # "spawn" (isolated) | "session" (persistent)
            "timeout": 120,         # seconds
            "retries": 1,           # retry on failure
            "response_mode": "json_schema",  # how output schema is communicated
        },
    )
)
```

**Env-based auto-discovery** (12-factor friendly):

```bash
# .env
OPENCLAW_CODIE_URL=http://localhost:19789
OPENCLAW_CODIE_TOKEN=xxx
OPENCLAW_CLAUDE_URL=http://localhost:18789
OPENCLAW_CLAUDE_TOKEN=xxx
```

```python
flock = Flock(openclaw=OpenClawConfig.from_env())
```

### Usage — Define Agents

```python
# Simple — one OpenClaw agent, same fluent API
pizza_master = (
    flock.openclaw_agent("codie")
    .consumes(MyPizzaIdea)
    .publishes(Pizza)
)

# With description/instruction — passed to OpenClaw as task context
reviewer = (
    flock.openclaw_agent("claude")
    .description("Senior code reviewer with security focus")
    .instruction("Focus on SQL injection vectors and auth bypass patterns")
    .consumes(CodeDiff)
    .publishes(SecurityReview)
)

# Per-agent overrides
heavy_thinker = (
    flock.openclaw_agent("claude", mode="spawn", timeout=300, model="opus", thinking="high")
    .consumes(ResearchQuestion)
    .publishes(ResearchReport)
)

# Persistent session mode — maintains conversation context across invocations
advisor = (
    flock.openclaw_agent("claude", mode="session", label="flock-advisor")
    .consumes(Question)
    .publishes(Answer)
)

# Mix freely with regular LLM agents
summarizer = flock.agent("summarizer").consumes(SecurityReview).publishes(Summary)
```

### Full Pipeline Example

```python
flock = Flock(openclaw=OpenClawConfig.from_env())

# Codie writes code, Claude reviews, LLM agent summarizes
writer = flock.openclaw_agent("codie").consumes(Spec).publishes(Implementation)
reviewer = flock.openclaw_agent("claude").consumes(Implementation).publishes(Review)
summarizer = flock.agent("summarizer").consumes(Review).publishes(Summary)

await flock.publish(Spec(feature="Add OpenClaw integration to Flock"))
await flock.run_until_idle()
```

---

## Architecture

### Where It Lives

```
src/flock/
├── integrations/
│   └── openclaw/
│       ├── __init__.py          # Public API exports
│       ├── config.py            # OpenClawConfig, GatewayConfig
│       ├── engine.py            # OpenClawEngine (extends BaseEngine)
│       └── builder.py           # .openclaw_agent() builder extension
```

This is an **Engine**, not a new agent type. OpenClaw only handles "how to compute output" — all Flock semantics (blackboard routing, visibility, fan-out, conditions, tracing) work unchanged.

### Engine Implementation

```python
class OpenClawEngine(BaseEngine):
    """Engine that delegates computation to an OpenClaw agent."""
    
    async def evaluate(self, context: EngineContext) -> Any:
        # 1. Build task from input artifact + output schema + description/instruction
        task = self._build_task(context)
        
        # 2. Send to OpenClaw (spawn or session mode)
        if self.mode == "spawn":
            result = await self._spawn_isolated(task)
        else:
            result = await self._send_to_session(task)
        
        # 3. Parse and validate response against output Pydantic model
        return self._parse_and_validate(result, context.output_type)
```

### Communication Protocol

**Spawn mode (default)** — isolated session per invocation:
```
POST {gateway_url}/api/sessions/spawn
{
    "task": "<task prompt with artifact + schema>",
    "agentId": "optional-agent-profile",
    "label": "flock-{agent_name}-{correlation_id}",
    "runTimeoutSeconds": 120
}
```
- Clean context per invocation — no memory bleed
- Predictable, parallelizable
- Best for: stateless transformations, fan-out

**Session mode** — persistent conversation:
```
POST {gateway_url}/api/sessions/send
{
    "label": "flock-{label}",
    "message": "<task prompt>"
}
```
- Maintains conversation context across invocations
- Good for: iterative refinement, context-dependent work
- Requires explicit label to target the right session

### What the OpenClaw Agent Receives

The task prompt is structured so any OpenClaw agent can process it without special setup:

> You are acting as a Flock pipeline agent.
>
> **Your Role:** Senior code reviewer with security focus
>
> **Instructions:** Focus on SQL injection vectors and auth bypass patterns
>
> **Input (CodeDiff):**
> `{"file": "auth.py", "changes": "..."}`
>
> **Expected Output:** Return valid JSON matching this schema:
> `{"type": "object", "properties": {"severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]}, "findings": {"type": "array", "items": {"type": "string"}}, ...}}`
>
> Return ONLY the JSON object. No markdown fences, no explanation.

The OpenClaw agent can use any tools at its disposal — web search, file reads, code execution — to produce the output. It's not constrained to a single LLM call.

---

## Design Decisions

### Why Engine, Not New Agent Type?

An engine only replaces the "compute" step. Everything else stays the same:

| Feature | Works with OpenClaw Engine? |
|---|---|
| Blackboard routing | ✅ Unchanged |
| Visibility controls | ✅ Unchanged |
| Fan-out publishing | ✅ Spawn N sessions in parallel |
| Predicates / where | ✅ Unchanged |
| JoinSpec / BatchSpec | ✅ Unchanged |
| Workflow conditions (Until) | ✅ Unchanged |
| Tracing / observability | ✅ Engine span wraps OpenClaw call |
| Context providers | ✅ Unchanged |
| Components (agent/orchestrator) | ✅ Unchanged |
| Dashboard visualization | ✅ Shows as agent node |

Zero special-casing needed in the orchestrator.

### Spawn vs Session — When to Use Which

| Aspect | Spawn (default) | Session |
|---|---|---|
| Context isolation | ✅ Clean per invocation | ❌ Accumulates |
| Parallelism | ✅ Embarrassingly parallel | ⚠️ Sequential per session |
| Fan-out | ✅ Natural | ❌ Not recommended |
| Stateful workflows | ❌ No memory | ✅ Remembers prior turns |
| Cost | Higher (new session overhead) | Lower (reuses session) |

### Response Parsing Strategy

1. **Primary:** Parse JSON from response body directly
2. **Repair pass:** If JSON is wrapped in markdown fences or has trailing text, extract and retry
3. **Validation:** Run through Pydantic model validation
4. **Failure:** Raise Flock-native execution error with OpenClaw response attached for debugging

---

## Safety & Operational Concerns

### Loop Prevention
Flock ↔ OpenClaw recursion must be prevented. If an OpenClaw agent itself uses Flock (or triggers back to OpenClaw), unbounded loops are possible.

**Mitigation:**
- Default: spawned sessions include a `"flock_origin": true` flag in metadata
- OpenClaw agents can check this to avoid re-entering Flock
- Configurable max depth: `OpenClawConfig(max_recursion_depth=1)`

### Timeout & Error Handling
- Gateway unreachable → retry with backoff, then Flock-native execution error
- Session timeout → configurable per agent, surfaces as execution error
- Invalid JSON response → repair pass, then error with raw response in trace
- All errors map to Flock's existing error handling patterns

### Concurrency Limits
- Don't flood one gateway: `OpenClawConfig(max_concurrent_per_gateway=4)`
- Respects Flock's existing `maxConcurrent` agent settings
- Fan-out uses semaphore to limit parallel spawns

### Observability
- Engine creates trace span wrapping the full OpenClaw call
- Span includes: gateway URL, agent name, session label, response time, token usage (if available from OpenClaw)
- OpenClaw session/message IDs stored in span attributes for cross-system debugging

### Security
- Tokens loaded from env vars, never hardcoded
- Gateway auth validated before first use
- Artifact payloads may contain sensitive data — respect Flock visibility rules (don't send private artifacts to unauthorized gateways)

---

## Wire Contract — Exact JSON Envelopes

### Spawn Request

```http
POST {gateway_url}/api/sessions/spawn
Authorization: Bearer {token}
Content-Type: application/json

{
    "task": "<rendered task prompt - see Task Prompt Format below>",
    "agentId": null,
    "label": "flock-{agent_name}-{correlation_id}",
    "runTimeoutSeconds": 120,
    "cleanup": "delete"
}
```

### Spawn Response

```json
{
    "ok": true,
    "sessionKey": "iso-abc123",
    "result": "<raw text response from OpenClaw agent>"
}
```

On failure:
```json
{
    "ok": false,
    "error": "timeout | agent_error | gateway_unavailable",
    "message": "Human-readable error detail"
}
```

### Session Send Request

```http
POST {gateway_url}/api/sessions/send
Authorization: Bearer {token}
Content-Type: application/json

{
    "label": "flock-{label}",
    "message": "<rendered task prompt>",
    "timeoutSeconds": 120
}
```

### Session Send Response

```json
{
    "ok": true,
    "reply": "<raw text response from OpenClaw agent>"
}
```

### Task Prompt Format

The task prompt is the actual string sent in `task` / `message` fields. Template variables are shown in `{braces}`:

    You are acting as a Flock pipeline agent.

    ## Your Role
    {description}

    ## Instructions
    {instruction}

    ## Input ({input_type_name})
    {input_artifact_json}

    ## Expected Output ({output_type_name})
    Return a single valid JSON object matching this schema:
    {output_json_schema}

    Return ONLY the JSON object. No markdown fences, no explanation, no preamble.

The `description` and `instruction` sections are omitted if not set on the agent. The JSON values are pretty-printed for readability.

### Metadata Propagation

These Flock-side values are passed through for tracing and correlation:

| Field | Where | Purpose |
|---|---|---|
| `correlation_id` | Embedded in `label`: `flock-{name}-{correlation_id}` | Cross-system trace correlation |
| `trace_id` | HTTP header: `X-Flock-Trace-Id` | OpenTelemetry trace linking |
| `agent_name` | Embedded in `label` | Identify which Flock agent spawned this |
| `retry_attempt` | HTTP header: `X-Flock-Retry: {n}` | Distinguish retries in traces |

---

## Error Taxonomy

| Error | Source | Retry? | Flock Mapping |
|---|---|---|---|
| Gateway unreachable | Network | Yes (with backoff) | `ExecutionError(retriable=True)` |
| Auth failure (401/403) | Gateway | No | `ConfigurationError` |
| Session timeout | OpenClaw | Yes (once, configurable) | `ExecutionError(retriable=True)` |
| Invalid JSON response | Agent output | Yes (once, with repair prompt) | `ExecutionError(retriable=True)` |
| Schema validation failure | Pydantic | No (after repair attempt) | `ValidationError` |
| Agent internal error | OpenClaw agent | Yes (once) | `ExecutionError(retriable=True)` |
| Recursion depth exceeded | Loop detection | No | `SafetyError` |

### Retry Policy

```python
RetryPolicy(
    max_retries=1,              # default: 1 retry
    backoff_base_ms=1000,       # exponential backoff base
    backoff_max_ms=10000,       # cap
    retry_on_invalid_json=True, # send repair prompt on bad JSON
    retry_on_timeout=True,      # retry timed-out spawns
    retry_on_network=True,      # retry gateway connection failures
)
```

JSON repair retry sends a follow-up prompt:
```
Your previous response was not valid JSON. The parse error was:
{error_message}

Please return ONLY a valid JSON object matching the schema. No markdown, no explanation.
```

---

## Session Mode — Ordering & Safety

### FIFO Guarantee
Session-mode messages to the same label are sent **strictly sequentially** (one at a time, await response before sending next). This is enforced by a per-label async lock in the engine.

```python
class OpenClawEngine:
    _session_locks: dict[str, asyncio.Lock]  # per-label locks
    
    async def _send_to_session(self, label, task):
        async with self._session_locks[label]:
            return await self._http_send(label, task)
```

### Interleaving Prevention
- Each Flock agent with `mode="session"` gets its own label (default: `flock-{agent_name}`)
- Different agents sharing the same OpenClaw gateway use different labels
- No two Flock agents should share a session label unless explicitly configured

### Session Lifecycle
- **Created:** On first message to a label (OpenClaw auto-creates)
- **Reused:** Subsequent invocations reuse the same session
- **Cleanup:** Optional via `session_ttl` config — engine sends cleanup after idle period

---

## Cancellation

If a Flock workflow is cancelled (e.g., `Until` condition met while OpenClaw is still working):

1. Engine receives cancellation signal via `asyncio.CancelledError`
2. For spawn mode: best-effort — session will complete but result is discarded
3. For session mode: no cancellation sent (session persists for future use)
4. Cleanup of orphaned spawn sessions via periodic garbage collection (Phase 2)

---

## Benchmark Targets

For Phase 1 validation, measure against native DSPy engine on 3 workloads:

| Workload | Native Engine | OpenClaw Engine | Acceptable Overhead |
|---|---|---|---|
| Simple transform (Pizza) | ~2s | ~4-6s | < 3x (spawn overhead) |
| Complex structured (Movie) | ~5s | ~8-12s | < 2.5x |
| Fan-out ×5 (parallel) | ~5s | ~8-12s | < 2.5x (parallel spawns) |

Overhead comes from: HTTP round-trip + session spawn + agent boot. Session mode should approach native latency after first message.

---

## Migration Guide

For existing Flock users adding OpenClaw agents to an existing pipeline:

```python
# Before: Pure LLM agent
pizza_master = flock.agent("pizza_master").consumes(MyPizzaIdea).publishes(Pizza)

# After: OpenClaw agent (2 changes: add config, swap method)
flock = Flock(openclaw=OpenClawConfig.from_env())  # 1. Add config
pizza_master = flock.openclaw_agent("codie").consumes(MyPizzaIdea).publishes(Pizza)  # 2. Swap

# Everything else stays the same — downstream agents, visibility, conditions, dashboard
```

No changes needed to:
- Artifact type definitions
- Downstream agents
- Visibility rules
- Workflow conditions
- Dashboard configuration
- Tracing setup

---

## Implementation Plan

### Phase 1 — Core (MVP)
- [x] `OpenClawConfig` with gateway registration and env discovery
- [x] `OpenClawEngine` with spawn mode
- [x] `.openclaw_agent()` builder method on Flock
- [x] Task prompt builder (artifact serialization + schema + description/instruction)
- [x] JSON response parser with repair pass
- [x] Basic error handling (timeout, parse failure, gateway down)
- [ ] Integration test with real OpenClaw gateway

### Phase 2 — Production Hardening
- [ ] Session mode (persistent conversations)
- [ ] Retry with backoff
- [ ] Concurrency limits (semaphore per gateway)
- [ ] Loop prevention (recursion depth tracking)
- [ ] Trace span integration (OpenTelemetry)
- [ ] Fan-out parallel spawn support

### Phase 3 — Advanced
- [ ] Bidirectional: OpenClaw agents publish TO Flock's blackboard via webhook/REST
- [ ] Streaming: live output from OpenClaw session to Flock dashboard
- [ ] Multi-gateway load balancing
- [ ] Agent capability discovery (query OpenClaw for available tools/skills)
- [ ] Cost tracking aggregation

### Phase 4 — Ecosystem Integration
*Building on the Clawd ecosystem analysis (Feb 2026) — features that belong in Flock core or as thin layers on top.*

- [ ] **Generic lease/claim/lock component** — Reusable workflow primitive for long-running external workers (not just OpenClaw — any async backend: MCP servers, custom HTTP agents, human-in-the-loop). Includes: claim acquisition, heartbeat/keepalive, timeout reclaim, receipt artifacts on completion.
- [ ] **OTLP export convenience layer** — Flock already has `TracingComponent` + OTel spans. Add a batteries-included config for forwarding spans to external collectors (e.g., a future ClawTrace instance). Mostly wiring + sensible defaults.
- [ ] **Trust metadata consumption** — Flock agents can read trust/capability metadata from ClawGuard (skill signatures, permission manifests) to inform routing decisions. Flock doesn't *own* trust policy — it *consumes* it.
- [ ] **Verification workflow primitives** — Generic state machine components for escrow-like patterns (claim → work → verify → settle). Useful as Flock building blocks that products like ClawMarket can compose on top of.

#### What Stays Outside Flock Core
These are **products built on Flock**, not Flock features:
- **ClawTrace** — Trace ingestion, timeline UI, privacy layers, VCR replay, incident-to-eval pipeline. Built as a separate app consuming Flock OTLP + OpenClaw emitter events.
- **ClawGuard** — Skill signing, revocation, runtime policy gating. OpenClaw/ClawHub concern; Flock only reads trust metadata.
- **ClawMarket** — Agent task marketplace with escrow, bidding, settlement. Application layer using Flock's verification workflow primitives as backend.

---

## Test Strategy

| Test | Type | What It Validates |
|---|---|---|
| Happy path (spawn) | Integration | Artifact in → structured output → validated |
| Invalid JSON repair | Unit | Markdown-wrapped / trailing text JSON extraction |
| Timeout handling | Integration | Graceful failure after deadline |
| Fan-out parallel | Integration | N spawns complete independently |
| Session ordering | Integration | Sequential messages maintain context |
| Gateway auth failure | Unit | Clear error, no retry |
| Loop detection | Unit | Recursion depth exceeded → error |
| Mixed pipeline | Integration | OpenClaw + LLM agents in same workflow |

---

## Open Questions

1. **Should `openclaw_agent()` live on the Flock class directly or as an extension?** Direct is cleaner DX; extension avoids coupling core to integration.

2. **Should we support multiple output types per OpenClaw invocation?** (Multi-type fan-out: `publishes(Movie, Script, Campaign, fan_out=3)`) — this requires the OpenClaw agent to return a structured multi-type response.

3. **Session cleanup policy for spawn mode?** Delete after result, or keep for debugging? Configurable with default to delete.

4. **Should OpenClaw agents participate in Flock's dashboard agent graph?** Yes (they're just agents with a different engine), but should they show a special icon/badge?
