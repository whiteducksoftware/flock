---
title: Changelog Stream Guide
description: Persistent ordered event log over blackboard state changes — for dashboards, audit, replay, and external observers
tags:
  - changelog
  - observability
  - audit
  - guide
search:
  boost: 1.2
---

# Changelog Stream

The changelog stream is an append-only, ordered event log over every blackboard state change. Each artifact publish, consumption, and agent snapshot update emits a `ChangelogEvent` with a monotonically increasing sequence number. Events are durable, filterable, and exposed through three delivery mechanisms:

- **SSE** at `/api/v1/changelog/stream` — push delivery for browser dashboards
- **WebSocket** at `/ws/changelog` — push delivery for richer subscribers
- **Cursor pull** at `/api/v1/changelog/events?after=<seq>&limit=N` — catch-up for cold subscribers

The stream is independently useful — you do **not** need external agents to benefit from it. Common use cases:

- Real-time dashboards over agent activity
- Audit trails (who published what, when, with what visibility)
- Time-travel replay for debugging
- Cross-instance replication via changelog shipping
- Event-sourced metrics

---

## Quick Start

Register the component:

```python
from flock import Flock
from flock.components.server.changelog import ChangelogStreamComponent

flock = Flock()
flock.add_server_component(ChangelogStreamComponent())

await flock.serve(blocking=False)
```

Subscribe via SSE from any HTTP client:

```bash
curl -N http://localhost:8000/api/v1/changelog/stream
```

Or pull historical events:

```bash
curl 'http://localhost:8000/api/v1/changelog/events?after=0&limit=100'
```

Output:

```json
{
  "events": [
    {
      "seq": 1,
      "event_type": "artifact_published",
      "artifact_id": "...",
      "artifact_type": "MyType",
      "produced_by": "agent-name",
      "correlation_id": "abc-123",
      "visibility": {"kind": "Public"},
      "timestamp": "2026-04-16T18:00:00Z",
      "payload_summary": {"...": "..."}
    }
  ],
  "oldest_available_seq": 1,
  "latest_seq": 100
}
```

---

## How It Works

### Atomic event emission

Every artifact publish writes the artifact and a `ChangelogEvent` in a **single SQLite transaction**:

```
publish(artifact)
  → ArtifactManager.persist_and_schedule
    → BlackboardStore.publish(artifact, changelog_event)   ← atomic
       └─ INSERT artifact + INSERT changelog_event + COMMIT
    → AgentScheduler.schedule_artifact
    → StreamDispatcher.publish(event)   ← fire-and-forget
       └─ SSE clients, WebSocket subscribers, cursor consumers
```

Two writes, one commit — no orphaned artifacts without events, no events for non-existent artifacts.

### Sequence numbers

`seq` is a monotonically increasing integer assigned by the store. **Gaps may occur** on transaction rollback; consumers must be gap-tolerant. The cursor API returns `oldest_available_seq` and `latest_seq` so consumers can detect retention-pruned ranges.

### Filtering

Each event carries enough metadata to filter without fetching the full artifact:

| Field | Purpose |
|-------|---------|
| `artifact_type` | Subscribe to events for specific Pydantic types |
| `correlation_id` | Trace a workflow across agent boundaries |
| `produced_by` | Filter by author agent |
| `visibility` | Per-subscriber visibility enforcement (SSE/WS auth-aware) |
| `payload_summary` | Lightweight context (not the full payload) |

SSE and WebSocket connections can supply filters in their initial handshake. Cursor API takes filters as query parameters.

### Retention

Events are retained per the configured policy (default: 7 days). Configure via `RetentionPolicyComponent`:

```python
from datetime import timedelta
from flock.components.orchestrator.retention import RetentionConfig, RetentionPolicyComponent

flock.add_component(RetentionPolicyComponent(
    config=RetentionConfig(
        max_age=timedelta(days=14),
        max_count=1_000_000,
        check_interval=timedelta(hours=1),
    )
))
```

Retention runs in the background and prunes old events without blocking publishes.

---

## Use Cases

### Real-time dashboard

```javascript
const sse = new EventSource('/api/v1/changelog/stream');
sse.addEventListener('artifact_published', (e) => {
  const event = JSON.parse(e.data);
  renderTimeline(event);
});
```

### Audit trail

```python
from flock.models.changelog import ChangelogFilter

events = await store.query_changelog(
    after_seq=0, limit=10_000,
    filters=ChangelogFilter(produced_by="suspicious-agent"),
)
for e in events.events:
    audit_log.append({
        "when": e.timestamp,
        "who": e.produced_by,
        "what": e.artifact_type,
        "context": e.correlation_id,
    })
```

### Workflow replay

```python
# Trace every event in a correlation
events = await store.query_changelog(
    after_seq=0, limit=1000,
    filters=ChangelogFilter(correlation_id="workflow-abc-123"),
)
# Returns the entire causal chain in seq order
```

### Reconnection with `Last-Event-ID`

SSE clients automatically include `Last-Event-ID` on reconnect; the endpoint resumes from that sequence number. If the requested seq is older than the retention window, a `gap` event is yielded so the client knows to refetch state.

---

## Performance Characteristics

The changelog adds a single additional `INSERT` per artifact publish, sharing the SQLite write transaction. Expected overhead is in the single-digit milliseconds per publish on local disks; WSL2 and network filesystems can be slower.

### Recorded benchmarks

From `tests/perf/test_changelog_publish_latency.py` on WSL2 (ext4-on-NTFS), 2026-04-16:

| Backend  | N    | mean    | p50    | p95    | p99    | max    |
|----------|------|---------|--------|--------|--------|--------|
| InMemory | 1000 | 0.002ms | 0.001ms| 0.002ms| 0.017ms| 0.58ms |
| SQLite   |  500 | 0.44ms  | 0.31ms | 0.46ms | 7.2ms  | 10.9ms |

Run them yourself:

```bash
uv run pytest tests/perf -m perf -s
```

In-memory is essentially free. SQLite p99 sits around 7ms on WSL2 — comfortably below the 15ms WSL2 budget and the 5ms native-Linux target. Native Linux disks are typically 2–3× faster than WSL2.

For high-throughput deployments:
- Use the in-memory store for transient workloads
- Configure retention aggressively (`max_age=timedelta(hours=1)`) if disk space is constrained
- The cursor API is recommended over SSE for batch consumers — a single round-trip can pull thousands of events
- Concurrent publishes via `asyncio.gather` produce strictly monotonic seq numbers under contention (verified by `test_concurrent_publish_seq_monotonicity`)

---

## Schema

```sql
CREATE TABLE IF NOT EXISTS changelog_events (
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

CREATE INDEX IF NOT EXISTS idx_changelog_event_type_seq ON changelog_events(event_type, seq);
CREATE INDEX IF NOT EXISTS idx_changelog_artifact_type_seq ON changelog_events(artifact_type, seq);
CREATE INDEX IF NOT EXISTS idx_changelog_produced_by_seq ON changelog_events(produced_by, seq);
CREATE INDEX IF NOT EXISTS idx_changelog_correlation ON changelog_events(correlation_id);
```

Migration to schema v4 (changelog) is automatic on first connect; v6 adds the unrelated `external_sessions` table.

---

## Related

- [Meta-Orchestrator Guide](meta-orchestrator.md) — uses the changelog as part of the broader external-agent flow
- `src/flock/components/server/changelog/` — the implementation
- `src/flock/models/changelog.py` — the `ChangelogEvent` Pydantic model
