# SQLiteBlackboardStore Domain Considerations

## Artifact Lifecycle Rules

- A SQLite-backed store must preserve the baseline contract defined by `BlackboardStore.publish`, `get`, `list`, and `list_by_type` so the orchestrator can persist an artifact, bump `artifacts_published`, and immediately schedule consumers without additional coordination (`src/flock/orchestrator.py:807`).
- Artifacts carry canonical business data—including correlation IDs, partition keys, tags, visibility, timestamps, and version counters—because the `Artifact` model already exposes them (`src/flock/artifacts.py:15`). Every field must be recorded to guarantee downstream features like visibility filtering and replay work unchanged.
- Duplicate publishes with the same UUID intentionally overwrite prior values: the tests assert “latest wins” semantics (`tests/test_store.py:152`). A persistent store therefore needs an UPSERT strategy keyed on `artifact_id` so callers never see stale payloads.

## Retrieval & Type Normalisation

- `list()` is expected to return artifacts in insertion order (`tests/test_store.py:126`); a SQLite implementation should sort by `created_at` (or a monotonic sequence) to mirror in-memory behaviour.
- Type-aware queries must keep working: `list_by_type("Document")` resolves the canonical name through `type_registry.resolve_name` before filtering (`src/flock/store.py:73`). That contract is validated by the storage contract tests which mix canonical and simple names (`tests/contract/test_artifact_storage_contract.py:56`). A SQLite store therefore needs a column that stores the canonical type string to make these lookups efficient.
- `get_by_type(ModelClass)` returns fully materialised Pydantic models (`src/flock/store.py:78`). Persisted payloads must remain JSON-serialised dictionaries so they can be rehydrated into model instances without losing validation logic.

## Visibility & Scheduling Guarantees

- Visibility rules (`PublicVisibility`, label/tenant controls, future embargoes) are enforced when the orchestrator schedules agents, so the store has to persist the original `visibility` payload intact for enforcement and later audits (`src/flock/orchestrator.py:826`).
- Because correlation IDs and partition keys participate in routing, they must remain queryable fields. The dashboard’s IndexedDB schema already assumes correlation and producer filters (`src/flock/frontend/src/services/indexeddb.ts:55`), so the canonical store must expose the same columns to keep downstream consumers consistent.

## Historical Retention & Audit

- Moving from volatile memory to SQLite adds expectations around retention windows, GDPR/PII erasure, and audit trails. The store should document default retention, compaction, and purging policies so teams know when old artifacts are deleted or archived.
- Persistent history enables richer diagnostic tools (e.g., the DuckDB trace statistics endpoint at `src/flock/dashboard/service.py:683`). A SQLite store should outline how historical artifact queries and export workflows stay performant without overwhelming the orchestrator.
