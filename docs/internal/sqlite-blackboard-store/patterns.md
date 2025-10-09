# SQLiteBlackboardStore Implementation Pattern

## Storage Strategy

- Use `aiosqlite` (or another async driver) so `publish`, `get`, and `list*` stay awaitable and integrate with the orchestrator’s async scheduling pipeline (`src/flock/orchestrator.py:807`).
- Open one shared connection per process with `row_factory=aiosqlite.Row`, wrap statements in `asyncio.Lock`/connection-level transactions, and enable WAL mode plus `journal_mode=wal` + `synchronous=normal` to reduce writer contention.

## Schema Design

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `artifacts` | Primary artifact store | `artifact_id` (PK TEXT UUID), `type`, `canonical_type`, `produced_by`, `payload` (JSON), `version`, `visibility` (JSON), `tags` (TEXT[] as JSON), `correlation_id`, `partition_key`, `created_at` (TIMESTAMP) |
| `artifact_consumers` (optional) | Future-proof actual consumer tracking | `artifact_id`, `agent_name`, `consumed_at` |

- Indexes: `(canonical_type, created_at)`, `(produced_by, created_at)`, `(correlation_id)`, `(tags_json -> '$[*]')` using `json_each` for tag filtering, plus `(partition_key)`. These support list-by-type, producer history, correlation filters, and eventual dashboard queries (`src/flock/frontend/src/services/indexeddb.ts:55`).

## Write Path (`publish`)

1. Resolve canonical type via `type_registry.resolve_name` before persistence so simple names remain queryable (`src/flock/store.py:73`).
2. Convert sets (`tags`) and visibility models to JSON. Persist `created_at` using the artifact’s timestamp rather than `CURRENT_TIMESTAMP` to preserve ingest order (`src/flock/artifacts.py:26`).
3. Execute an UPSERT on `artifact_id`. On conflict update payload, metadata, version, and `created_at` so duplicate publishes follow the “latest wins” rule (`tests/test_store.py:152`).

## Read Path (`get`, `list`, `list_by_type`, `get_by_type`)

- `get` selects by `artifact_id` and rehydrates the Pydantic model by feeding the stored payload into the registered class (`src/flock/store.py:79`).
- `list` orders by `created_at ASC`, returning rows mapped back to `Artifact`.
- `list_by_type` filters on `canonical_type` so both canonical and simple names pass the contract tests (`tests/contract/test_artifact_storage_contract.py:56`).
- `get_by_type` builds the target model directly by deserialising JSON payloads (no extra round-trip through `Artifact`), ensuring users still receive typed lists.

## Concurrency & Backpressure

- SQLite serialises writes; wrap publishes in short transactions and batch inserts when ingesting cascades. For heavy workloads, queue writes through an `asyncio.TaskGroup` that coalesces `publish` calls to amortise commit cost.
- Explicitly document write throughput limits and point teams toward sharding or an alternative store for high-frequency publish workloads.

## Schema Migration & Maintenance

- Ship an `ensure_schema()` coroutine that runs during store initialisation to create tables, indexes, and PRAGMA settings idempotently.
- Provide a migration table (`schema_version INTEGER`) so future upgrades (e.g., adding artifact lineages) can run without manual SQL.
- Offer housekeeping helpers: vacuum/pragma toggles, “delete before timestamp” utilities for retention, and export routines for snapshotting.

## Observability & Testing

- Emit OpenTelemetry spans around SQL operations so they appear in the existing DuckDB trace summaries (`src/flock/dashboard/service.py:683`).
- Reuse `tests/test_store.py` and `tests/contract/test_artifact_storage_contract.py` via parametrised fixtures to validate behaviour parity, then add integration tests for persistence, WAL mode, and concurrent writers to cover new failure modes.
