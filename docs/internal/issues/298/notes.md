# SQL Blackboard Store – Quick Dive Notes

## Existing architecture
- `src/flock/store.py`
  - `BlackboardStore` abstract interface with methods:
    - `publish(artifact: Artifact)`
    - `get(artifact_id: UUID)`
    - `list()` → returns list of Artifact
    - `list_by_type(type_name: str)`
    - `get_by_type(artifact_type: type[T])` → returns list of Pydantic model instances
  - `InMemoryBlackboardStore` (default) keeps a Lock + dicts per id and per type.

- `Flock.__init__` (src/flock/orchestrator.py)
  - Accepts `store: BlackboardStore | None = None`
  - Defaults to `InMemoryBlackboardStore()` if not provided.
  - `publish`, `_persist_and_schedule`, etc. call `self.store.publish()` and retrieval methods.

- No persistence beyond memory currently.

## Touchpoints for SQL store
1. Implement concrete `SQLBlackboardStore(BlackboardStore)`.
   - Backed by SQLite (first target). Could keep file path configurable.
   - Should manage schema creation (artifacts table) with fields: id, type, payload JSON, produced_by, visibility, tags, created_at, correlation_id, partition_key, version.
   - Provide indices on id, type, correlation_id, created_at.
   - Use WAL mode for concurrent reads.
   - JSON payload storage (TEXT) + metadata columns.
   - For `get_by_type`, reconstruct Pydantic models via `type_registry`.

2. Configuration entry points:
   - New config object (in docs + orchestrator) to choose store (memory/sqlite/postgres?). For this feature scope: add optional `sqlite_path` env/argument.
   - Possibly extend `Flock` constructor: allow passing `store="sqlite"` or `store=SQLBlackboardStore(...)`.

3. Tests:
   - Unit tests verifying CRUD on store (temp file per test).
   - Integration test: instantiate `Flock` with SQL store, publish artifacts, restart orchestrator (simulate by constructing new `Flock` with same DB file) and ensure data persists.
   - Concurrency test using async tasks? (Optional but helpful).

4. Docs updates:
   - README / ROADMAP entry referencing deliverable.
   - New doc page: `docs/guides/persistence.md` or augment existing config doc.

5. CLI / utilities:
   - Provide helper command to migrate or vacuum? (Could be follow-up).

6. Observability:
   - Collect simple metrics (counts) or rely on existing metrics? Minimal for first phase.

## Next steps
- Create feature spec issue referencing these notes.
- Plan phases (e.g., Phase 1: schema + store class; Phase 2: config integration + tests; Phase 3: docs + polish).
