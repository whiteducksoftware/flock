# Flock × OpenClaw Integration — Concept Document

**Authors:** Claude + Codie | **Date:** 2026-02-11 | **Status:** Proposal for review

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

```
You are acting as a Flock pipeline agent.

## Your Role
Senior code reviewer with security focus

## Instructions
Focus on SQL injection vectors and auth bypass patterns

## Input (CodeDiff)
```json
{"file": "auth.py", "changes": "..."}
```

## Expected Output
Return valid JSON matching this schema:

```json
{
  "type": "object",
  "properties": {
    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
    "findings": {"type": "array", "items": {"type": "string"}},
    ...
  }
}
```

Return ONLY the JSON object. No markdown fences, no explanation.
```

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

## Implementation Plan

### Phase 1 — Core (MVP)
- [ ] `OpenClawConfig` with gateway registration and env discovery
- [ ] `OpenClawEngine` with spawn mode
- [ ] `.openclaw_agent()` builder method on Flock
- [ ] Task prompt builder (artifact serialization + schema + description/instruction)
- [ ] JSON response parser with repair pass
- [ ] Basic error handling (timeout, parse failure, gateway down)
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
