# SQLite Blackboard Store Interfaces & Dashboard UX

## Orchestrator Integration

- Expose the store via `Flock(store=SQLiteBlackboardStore(db_path="..."))` so existing constructors keep working (`src/flock/orchestrator.py:807`).
- Provide async `startup()` / `shutdown()` hooks to initialise connections and close them gracefully when the dashboard or CLI stops, matching the lifecycle of `DashboardHTTPService`.

## Backend APIs for Historical Data

- Extend the FastAPI layer with a paginated `GET /api/v1/artifacts` endpoint that supports query parameters: `type`, `produced_by`, `correlation_id`, `tag`, `from`, `to`, `limit`, `offset`. Results should mirror the artifact schema returned by `GET /api/v1/artifacts/{artifact_id}` (`src/flock/service.py:86`).
- Add an optional `GET /api/v1/artifacts/summary` endpoint for aggregations (counts per type, per producer) to let the dashboard populate filters without scanning the entire table.
- Keep WebSocket streaming history for live sessions, but backfill the IndexedDB cache on load by calling the new history endpoint before subscribing to real-time events. That honours the existing IndexedDB schema which already tracks correlation IDs, producers, and timestamps (`src/flock/frontend/src/services/indexeddb.ts:55`).

## Dashboard Filter & View Enhancements

- The current filter store only allows correlation ID and time-range filters (`src/flock/frontend/src/store/filterStore.ts:11`). Persisted history will overwhelm this UX; add multi-select filters for artifact type, producing agent, tags, and visibility class so operators can slice larger datasets.
- Introduce a “Historical Blackboard” view that renders a virtualised table or timeline of artifacts, pulling pages from SQLite via the new endpoints and letting users jump to a specific time window.
- Provide saved filter presets (the IndexedDB schema already reserves a `filters` store, `src/flock/frontend/src/services/indexeddb.ts:127`) so analysts can recall frequent queries quickly.
- For streaming output, keep the existing `/api/streaming-history/{agent_name}` endpoint (`src/flock/dashboard/service.py:703`) but document how far back history can be fetched and surface UI affordances (e.g., “Load older output”) that rely on SQLite retention policies.

## Usability Guardrails

- Indicate the active dataset (live vs archived) directly in the dashboard to avoid confusion when viewing historical records.
- Add server-side limits (max rows per page, time-range caps) with clear UI feedback to prevent slow queries and keep SQLite responsive.
- Provide export actions (CSV/JSON) for selected artifacts so teams can move historical data into external analytics tools without direct database access.
