---
title: Meta-Orchestrator Guide
description: Orchestrate external AI agents (Claude Code, Codex) via the changelog stream, token auth, and the external agent runtime
tags:
  - meta-orchestrator
  - external-agents
  - guide
  - advanced
  - changelog
search:
  boost: 1.5
---

# Meta-Orchestrator

The meta-orchestrator extends Flock to manage **external AI agent processes** (Claude Code, OpenAI Codex, or any CLI-based agent) as first-class participants in the blackboard workflow. External agents are spawned on demand, triggered by changelog events, authenticated via bearer tokens, and their results flow back through the same artifact pipeline as internal agents.

---

## Quick Start

Register an external agent using the builder API:

```python
from flock import Flock
from flock.integrations.external.adapters.claude_code import ClaudeCodeAdapter

flock = Flock("my-project", model="openai/gpt-4.1")

# Register the Claude Code adapter
flock.register_adapter("claude_code", ClaudeCodeAdapter())

# Create an external agent that reviews PRDiff artifacts
(flock.agent("pr-reviewer")
    .kind("external")
    .adapter("claude_code")
    .working_dir("/repos/my-project")
    .spawn_timeout(120.0)
    .consumes(PRDiff)
    .session_mode("resume")
    .done())
```

When a `PRDiff` artifact is published to the blackboard, the scheduler automatically:

1. Detects the new changelog event
2. Matches it to `pr-reviewer`'s subscription
3. Spawns Claude Code with the artifact context as prompt
4. Monitors the process until completion or timeout
5. Stores the session ID for future resume

---

## How It Works

### Changelog Stream

Every blackboard state change emits a `ChangelogEvent` to an append-only, ordered log. The `StreamDispatcher` delivers these events to subscribers in real-time via server-sent events (SSE).

```
Artifact Published  -->  ChangelogEvent  -->  StreamDispatcher  -->  Subscribers
                                                     |
                                                     +--> ExternalAgentScheduler
                                                     +--> Dashboard SSE
                                                     +--> REST /changelog endpoint
```

Events carry enough metadata for routing without fetching the full artifact:

- `artifact_type` -- for subscription matching
- `correlation_id` -- for workflow threading
- `produced_by` -- for self-trigger prevention
- `payload_summary` -- lightweight context for prompts

### Token Authentication

External agents authenticate via bearer tokens when calling back to publish artifacts:

```
External Agent  --[POST /artifacts + Bearer token]-->  Flock REST API
                                                           |
                                                    TokenStore.verify()
                                                           |
                                                    TokenRecord (identity, scopes, allowed_types)
```

Tokens are:
- **Scoped** to specific artifact types (`allowed_types`)
- **Time-limited** with optional expiration
- **Revocable** at any time via the token management API
- **Hashed** with per-token salt (SHA-256) -- raw tokens are never stored

### External Agent Lifecycle

```
1. ChangelogEvent arrives
2. Scheduler matches event.artifact_type against agent subscriptions
3. Session resolution: resume (lookup stored session) or new
4. SpawnConfig built (prompt, working_dir, env_vars, session_id)
5. Adapter.spawn() creates the subprocess
6. Adapter.monitor() awaits completion (with timeout)
7. On success: session_id stored for future resume
8. On timeout: Adapter.terminate() sends SIGTERM -> grace -> SIGKILL
```

Each external agent processes events **serially** -- one spawn at a time per agent name. This prevents race conditions in agents that maintain conversational state.

---

## Configuration

### Token Management

Create tokens programmatically:

```python
from flock.auth.token_models import TokenCreateRequest
from flock.auth.token_store import InMemoryTokenStore, create_token

token_store = InMemoryTokenStore()

request = TokenCreateRequest(
    identity_name="pr-reviewer",
    identity_labels={"external", "claude"},
    allowed_types={"ReviewResult", "ReviewSummary"},
    scopes={"artifact:publish", "artifact:read"},
)
raw_token, record = create_token(request)
await token_store.store(record)
# Give raw_token to the external agent (one-time, cannot be recovered)
```

Or via REST (when server components are active):

```bash
curl -X POST http://localhost:8000/tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"identity_name": "reviewer", "allowed_types": ["ReviewResult"]}'
```

### Retention Policy

The changelog supports pruning for long-running deployments:

```python
# Delete events older than sequence 1000
deleted = await store.prune_changelog(before_seq=1000)

# Delete events older than a timestamp
from datetime import datetime, timedelta, UTC
cutoff = datetime.now(UTC) - timedelta(days=7)
deleted = await store.prune_changelog(before_time=cutoff)
```

### Environment Variables

External agents receive these environment variables automatically:

| Variable | Description |
|----------|-------------|
| `FLOCK_API_TOKEN` | Bearer token for authenticating back to Flock |
| `FLOCK_API_URL` | Base URL of the Flock REST API |

Additional env vars can be set per-agent via `spawn_env` on the Agent object or via the `ExternalAgentConfig.env_vars` field.

---

## Example: PR Review Workflow

A complete PR review pipeline with three stages:

```python
from pydantic import BaseModel, Field
from flock import Flock
from flock.integrations.external.adapters.claude_code import ClaudeCodeAdapter

# Define artifact types
class PRDiff(BaseModel):
    repo: str
    pr_number: int
    diff: str
    author: str

class ReviewResult(BaseModel):
    verdict: str  # "approved" | "changes_requested"
    comments: list[str] = Field(default_factory=list)
    reviewer: str

class ReviewSummary(BaseModel):
    pr_number: int
    approved: bool
    summary: str

# Build the flock
flock = Flock("pr-review", model="openai/gpt-4.1")
flock.register_adapter("claude_code", ClaudeCodeAdapter())

# Stage 1: External Claude Code reviews PRDiff
(flock.agent("code-reviewer")
    .kind("external")
    .adapter("claude_code")
    .working_dir("/repos/target")
    .spawn_timeout(300.0)
    .consumes(PRDiff)
    .session_mode("resume")
    .done())

# Stage 2: Internal agent summarizes ReviewResult
(flock.agent("summarizer")
    .consumes(ReviewResult)
    .produces(ReviewSummary)
    .instruction("Summarize the code review verdict and key comments.")
    .done())

# Trigger: publish a PRDiff artifact
await flock.publish(PRDiff(
    repo="my-app",
    pr_number=42,
    diff="...",
    author="developer",
))
# Flow: PRDiff -> code-reviewer (Claude Code) -> ReviewResult -> summarizer -> ReviewSummary
```

All three artifacts share a `correlation_id`, making the full workflow queryable:

```python
result = await store.query_changelog(
    filters=ChangelogFilter(correlation_id="pr-42")
)
# Returns all 3 events in sequence order
```

---

## Reference

### Schema Migration (v4 to v5)

The meta-orchestrator adds the changelog table to the SQLite schema. Migration is automatic on first access:

```sql
-- v5 adds:
CREATE TABLE IF NOT EXISTS changelog (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    artifact_id TEXT,
    artifact_type TEXT,
    produced_by TEXT,
    correlation_id TEXT,
    visibility TEXT,
    timestamp TEXT NOT NULL,
    payload_summary TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_changelog_type ON changelog(artifact_type);
CREATE INDEX idx_changelog_correlation ON changelog(correlation_id);
CREATE INDEX idx_changelog_timestamp ON changelog(timestamp);
```

### New Agent Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_kind` | `str` | `"internal"` | Set to `"external"` for subprocess agents |
| `adapter_name` | `str \| None` | `None` | Registered adapter name (e.g. `"claude_code"`) |
| `working_dir` | `str \| None` | `None` | Filesystem path for the spawned process |
| `spawn_timeout` | `float` | `1800.0` | Max seconds before timeout/kill |
| `spawn_env` | `dict` | `{}` | Extra env vars for the process |
| `prevent_self_trigger` | `bool` | `True` | Skip events produced by this agent |

### Subscription Extensions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_mode` | `str \| None` | `None` | `"new"` or `"resume"` for external agents |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| External agent never triggers | `agent_kind` not set to `"external"` | Use `.kind("external")` in builder |
| "adapter not registered" warning | Adapter name mismatch | Verify `flock.register_adapter(name, ...)` matches `.adapter(name)` |
| Agent times out immediately | `spawn_timeout` too low | Increase timeout (default 1800s) |
| Token rejected (403) | Token expired or revoked | Create a new token; check `expires_at` |
| Type scope error | Token `allowed_types` missing the artifact type | Add the type to `TokenCreateRequest.allowed_types` |
| Resume mode falls back to new | No stored session for this agent+type | First run always uses "new"; session stored after success |
| SQLite latency > 5ms | Expected on WSL2 / network filesystems | Use in-memory store for dev, or accept ~10ms on WSL2 |
| Events not reaching subscriber | Subscriber created after publish | Subscribe before publishing, or use cursor API for history |
| Self-trigger loop | Agent publishes type it subscribes to | Enable `prevent_self_trigger` (default True) |
