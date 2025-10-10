---
title: Persistent Blackboard History
description: Store artifacts beyond process lifetime with the SQLite-backed blackboard store and dashboard history module.
tags:
  - blackboard
  - persistence
  - sqlite
  - dashboard
search:
  boost: 1.4
---

# Persistent Blackboard History

The in-memory blackboard is perfect for local prototyping, but production teams need durable history for audits, debugging, and operator experience. The new **SQLiteBlackboardStore** turns every artifact into long-lived record while the dashboard's **Historical Blackboard** module visualises that history.

---

## Why Persist the Blackboard?

- **Replay & Audits** — Inspect any published artifact (including payloads, tags, visibility, version, correlation IDs) even after the orchestrator restarts.
- **Lifecycle Analytics** — Summaries and agent history endpoints expose production/consumption counts, visibility breakdowns, and tag trends over arbitrary windows.
- **Operator Experience** — Dashboard users can scroll back through previous runs, inspect payload details, and view retention banners that explain how far history goes.
- **Future Backends** — The updated store interface (`FilterConfig`, `ArtifactEnvelope`) paves the way for Postgres, DuckDB, or cloud warehouses with identical semantics.

---

## Swapping in the SQLite Store

```python
from flock import Flock
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(".flock/blackboard.db", timeout=5.0)
await store.ensure_schema()  # idempotent; safe to call on startup

flock = Flock("openai/gpt-4.1", store=store)
```

Key capabilities:

- **Upserts by ID** — Duplicate artifact IDs overwrite previous payloads to remain consistent with the in-memory store.
- **Full-field persistence** — All artifact fields (payload, tags, partition key, visibility) are saved for later hydration.
- **Consumption tracking** — `record_consumptions()` writes `artifact_consumptions` rows so downstream dashboards know who consumed what.
- **Operational helpers** — `sqlite-maintenance` CLI can prune (`--delete-before`) and vacuum the database on a schedule.

> Tip: Run `examples/02-the-blackboard/01_persistent_pizza.py` to seed `.flock/examples/pizza_history.db`, then reuse that file across sessions.

---

## Historical APIs

Once the SQLite store is active, the HTTP control plane exposes richer endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/artifacts` | Paginated artifacts with filter support (type, producer, tags, visibility, correlation ID, time window). |
| `GET /api/v1/artifacts/summary` | Aggregates by type, producer, visibility, tag counts, earliest/latest timestamps. |
| `GET /api/v1/agents/{agent_id}/history-summary` | Produced/consumed totals per agent with optional filters. |

Pass `embed_meta=true` to `GET /api/v1/artifacts` to receive `ArtifactEnvelope` responses that include consumption records (consumer IDs, run IDs, timestamps).

---

## Dashboard: Historical Blackboard Module

Enable the dashboard with `await orchestrator.serve(dashboard=True)` or run `examples/03-the-dashboard/04_persistent_pizza_dashboard.py`. Then open **Add Module → Historical Blackboard** to:

- Load persisted artifacts before WebSocket replay.
- Apply the same multi-select filters as the REST API (types, producers, tags, visibility, correlation ID, time range).
- Inspect payloads with the JSON viewer alongside consumer history (who read the artifact, when, and in which run).
- See retention banners that highlight the earliest/latest artifacts currently stored and whether older pages can be fetched.
- Stream new artifacts as they arrive—persisted history and live events share the same view.

---

## Retention & Maintenance

- **Retention policy** — Use `sqlite-maintenance db.sqlite --delete-before <ISO-8601 timestamp>` to truncate old artifacts. Pair with `--vacuum` to reclaim disk space.
- **Migrations** — `ensure_schema()` is idempotent and applies schema upgrades automatically. Call it during startup before processing any artifacts.
- **Backups** — SQLite files can be copied or snapshotted; do this while the orchestrator is idle or after calling `await store.close()`.

Future releases will add configurable retention windows and additional storage backends, but the contract exposed by `BlackboardStore` already supports them.

---

## Next Steps

1. Switch local examples to `SQLiteBlackboardStore` and explore the persisted history via the dashboard module.
2. Integrate the historical REST endpoints into operational tooling (e.g., CI smoke tests, analytics dashboards).
3. Plan retention and maintenance jobs using the provided CLI commands.
4. Contribute alternative store implementations by targeting the same `BlackboardStore` contract.
