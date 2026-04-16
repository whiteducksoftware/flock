---
title: Meta-Orchestrator Guide
description: Orchestrate external AI agents (Claude Code, Codex) as engine-driven blackboard participants
tags:
  - meta-orchestrator
  - external-agents
  - guide
  - advanced
search:
  boost: 1.5
---

# Meta-Orchestrator

Flock can drive external CLI-based AI agents (Claude Code, OpenAI Codex, or any subprocess-based agent) as first-class blackboard participants. External agents are spawned on demand when their subscriptions match, do their work, and publish typed results back through the same `EvalResult` pipeline as internal LLM agents.

The mechanism is the standard engine pattern: an external agent is just an agent whose `EngineComponent` happens to spawn a subprocess instead of calling an LLM directly. From the orchestrator's perspective, there is no special-casing.

---

## Quick Start

Declare an external agent and let auto-wiring do the rest:

```python
from pydantic import BaseModel
from flock import Flock
from flock.registry import flock_type

@flock_type
class PRDiff(BaseModel):
    repo: str
    pr_number: int
    diff: str

@flock_type
class ReviewResult(BaseModel):
    verdict: str
    comments: list[str] = []

flock = Flock()

(flock.agent("pr-reviewer")
    .kind("external")
    .adapter("claude_code")
    .working_dir("/repos/my-project")
    .spawn_timeout(300.0)
    .consumes(PRDiff)
    .publishes(ReviewResult)
    .session_mode("resume"))

await flock.serve(blocking=False)
await flock.publish(PRDiff(repo="x", pr_number=42, diff="..."))
await flock.run_until_idle()
```

When `flock.serve()` runs, Flock detects every agent with `kind("external")` and attaches an `ExternalEngineComponent` configured with the named adapter. No scheduler, no token wiring, no REST return path setup — the engine pipeline handles everything.

---

## How It Works

### Engine attachment

```
agent.kind("external").adapter("claude_code")
                  │
                  ▼
   Flock._run_initialize()
                  │
                  ▼
   ExternalEngineComponent(adapter=ClaudeCodeRuntime(), ...) → agent.engines.append(...)
```

When you publish an artifact:

```
publish(A)
  → ArtifactManager.persist_and_schedule
  → AgentScheduler.schedule_artifact          (same path as internal agents)
  → Agent._run_engines
  → ExternalEngineComponent.evaluate
       ├─ compose prompt (input artifacts + output schemas)
       ├─ adapter.spawn → subprocess
       ├─ adapter.monitor → text response
       ├─ JSON parse + Pydantic validate
       └─ return EvalResult → publish(B) → cascade continues
```

### Output coercion

The engine composes a prompt that includes:
- The agent's `description` (instructions)
- Each input artifact's payload as JSON
- The JSON schema(s) of the expected output type(s)
- A strict instruction to reply with valid JSON only

The adapter returns text. The engine parses it as JSON, validates each item against the corresponding output type, and returns an `EvalResult`. Validation failure raises `ExternalEngineExecutionError` and surfaces through the agent's normal error path.

### Session management

External CLIs (Claude Code, Codex) maintain conversation state via session IDs. Two modes are supported per subscription:

- `"new"` — always start a fresh session
- `"resume"` — look up the stored session ID for `(agent_name, artifact_type)` and pass it to the adapter; falls back to `"new"` with a warning if no stored session exists

Session IDs persist in the `external_sessions` table when the blackboard is SQLite-backed (via the auto-wired `LazySQLiteExternalSessionStore`). For in-memory blackboards, sessions live for the lifetime of the process.

### Available adapters

| Adapter name | Runtime | Notes |
|---|---|---|
| `"claude_code"` | `ClaudeCodeRuntime` | Uses your logged-in subscription by default; set `bare=True` + `ANTHROPIC_API_KEY` for CI |
| `"codex"` | `CodexRuntime` | Uses your logged-in subscription by default; supports `OPENAI_API_KEY` |

Custom adapters can be registered by attaching an `ExternalEngineComponent` directly via `.with_engines(...)` instead of relying on `.adapter("name")`.

---

## Configuration

### Builder methods

| Method | Default | Description |
|--------|---------|-------------|
| `.kind("external")` | `"internal"` | Marks the agent for engine attachment |
| `.adapter(name)` | required | Adapter to use (`"claude_code"`, `"codex"`, …) |
| `.working_dir(path)` | `"."` | Filesystem cwd for the spawned process |
| `.spawn_timeout(seconds)` | `1800.0` | Maximum wall-clock time before terminate |
| `.spawn_env({"K": "V"})` | `{}` | Extra env vars (allowlisted in adapter) |
| `.session_mode("new" \| "resume")` | none | Per-subscription session policy |

### Optional: changelog stream

If you want dashboard streaming, audit logs, or replay-from-cursor over external agent activity, register the `ChangelogStreamComponent`:

```python
from flock.components.server.changelog import ChangelogStreamComponent
flock.add_server_component(ChangelogStreamComponent())
```

This exposes `/api/v1/changelog/events` (cursor pull), `/api/v1/changelog/stream` (SSE), and `/ws/changelog` (WebSocket). See [`changelog-stream.md`](changelog-stream.md) — it is independently useful even without external agents.

### Optional: token authentication

External agents do **not** need tokens — they return results in-process via `evaluate()`. Tokens are only relevant for **HTTP clients** publishing artifacts into Flock from outside the process. To enable bearer-token auth for those clients:

```python
from flock.components.server.auth import AuthenticationComponent
from flock.components.server.auth.token_management_component import TokenManagementComponent
flock.add_server_component(AuthenticationComponent())
flock.add_server_component(TokenManagementComponent())
```

See the auth-related modules under `src/flock/auth/` and `src/flock/components/server/auth/` for token lifecycle.

---

## Example: Multi-Agent Code Review

```python
from pydantic import BaseModel, Field
from flock import Flock
from flock.registry import flock_type

@flock_type
class PRDiff(BaseModel):
    repo: str
    pr_number: int
    diff: str

@flock_type
class SecurityReview(BaseModel):
    verdict: str
    issues: list[str] = Field(default_factory=list)

@flock_type
class PerformanceReview(BaseModel):
    verdict: str
    suggestions: list[str] = Field(default_factory=list)

flock = Flock()

# Two external agents fan out from the same artifact
(flock.agent("security-reviewer")
    .kind("external").adapter("claude_code").working_dir(".")
    .consumes(PRDiff).publishes(SecurityReview)
    .session_mode("resume"))

(flock.agent("performance-reviewer")
    .kind("external").adapter("codex").working_dir(".")
    .consumes(PRDiff).publishes(PerformanceReview)
    .session_mode("new"))

# Internal agent merges the two reviews
(flock.agent("merger")
    .consumes(SecurityReview, PerformanceReview)
    .publishes(...)  # your merged type
    .description("Merge security + performance findings into a single verdict."))
```

See `examples/12-external-agents/02_multi_agent_code_review.py` for the full runnable version.

---

## Reference

### Schema (SQLite v6)

The blackboard schema includes external-agent session storage:

```sql
CREATE TABLE IF NOT EXISTS external_sessions (
    agent_name TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (agent_name, artifact_type)
);
```

Migration is automatic on first SQLite connection.

### Agent fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_kind` | `str` | `"internal"` | Set to `"external"` for subprocess agents |
| `adapter_name` | `str \| None` | `None` | Adapter to instantiate at auto-wire time |
| `working_dir` | `str \| None` | `None` | Filesystem path for the spawned process |
| `spawn_timeout` | `float` | `1800.0` | Max seconds before timeout/kill |
| `spawn_env` | `dict` | `{}` | Extra env vars |

### Subscription fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_mode` | `str \| None` | `None` | `"new"` or `"resume"` |

### `ExternalEngineComponent` errors

| Exception | When |
|-----------|------|
| `ExternalEngineExecutionError` | Subprocess non-zero exit, JSON parse failure, schema validation failure, no output, no adapter |
| `FileNotFoundError` | Adapter raised because the CLI is not installed |
| `asyncio.TimeoutError` | `spawn_timeout` exceeded — adapter is terminated; engine re-raises |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent never spawns | `agent_kind` not set to `"external"` | Use `.kind("external")` in builder |
| `ValueError: External agent 'X' has no .adapter` | Missing `.adapter("name")` call | Add it |
| `ValueError: ... unknown adapter` | Typo in adapter name | Use `"claude_code"` or `"codex"` |
| Agent times out | `spawn_timeout` too low for the workload | Increase via `.spawn_timeout(seconds)` |
| `ExternalEngineExecutionError: non-JSON output` | Agent ignored the JSON instruction | Tighten the agent's `.description()` to emphasise JSON-only output |
| `ExternalEngineExecutionError: does not match <Type>` | Agent's JSON does not match the published type's schema | Inspect the schema; the model may need clearer field constraints/descriptions |
| Resume mode falls back to new | No stored session for this agent+type yet | Expected on first run; session stored after success |
| Agent process orphaned on crash | Adapter spawn failed mid-write | Already handled — adapter kills the process on `BrokenPipeError`. File a bug if you see it persist |
