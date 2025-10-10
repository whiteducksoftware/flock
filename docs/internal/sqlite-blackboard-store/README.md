# SQLiteBlackboardStore Research Packet

Welcome! This folder collects the working notes for implementing a persistent `SQLiteBlackboardStore`. Start here to understand what already exists and how to extend Flock Flow’s storage layer safely.

## Quickstart

1. **Read the domain rules** (`domain.md`) to learn the behavioural guarantees we must keep (duplicate handling, type resolution, visibility data, retention expectations).
2. **Review the implementation pattern** (`patterns.md`) for schema design, transaction strategy, and migration guidance.
3. **Check the integration notes** (`interfaces.md`) to see which APIs and dashboard affordances need to evolve once historical storage is available.
4. **Plan next steps** using the “Action Items” section below when you’re ready to convert research into issues or pull requests.

## Folder Contents

| File | Purpose |
|------|---------|
| `domain.md` | Business and lifecycle rules the SQLite store must preserve. |
| `patterns.md` | Technical blueprint for schema, read/write flows, concurrency, and observability. |
| `interfaces.md` | Backend API extensions and dashboard UX recommendations for historical data access. |

## Action Items

- Validate schema design and indexing strategy against projected artifact volumes.
- Scope required FastAPI endpoints and dashboard filter updates into implementation tickets.
- Prototype concurrency benchmarks (publish throughput, WAL performance) to confirm operational limits.
