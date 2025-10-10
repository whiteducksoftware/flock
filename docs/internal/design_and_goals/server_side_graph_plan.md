# Server-Side Graph Assembly Plan

## 1. Objective
- Eliminate duplicated graph-construction logic that currently lives in `src/flock/frontend/src/store/graphStore.ts` and `src/flock/frontend/src/utils/transforms.ts`.
- Provide the dashboard with a single backend endpoint that returns fully-connected graph snapshots (nodes, edges, metadata) for both **agent view** and **blackboard view**, already filtered according to UI selections.
- Preserve existing behaviour (label offsets, consumption counts, synthetic runs, etc.) while making future enhancements—like additional views or alternate clients—backend-driven.

## 2. Current Frontend Responsibilities (Pain Points)
- **State assembly**: The UI ingests websocket events, then reconstructs maps of agents, messages, runs, and consumptions. (`graphStore` keeps multiple Maps and derives synthetic runs in `toDashboardState()`.)
- **Dual graph derivations**: Frontend derives edges via `deriveAgentViewEdges()` and `deriveBlackboardViewEdges()`, replicating logic already defined in the backend specs.
- **Filter application**: Time-range, correlation, producer/type/tag/visibility filters are applied client-side, forcing the UI to maintain statistics (produced/consumed counts) in addition to graph visibility.
- **Persistence & layout**: FE must preserve node positions on regeneration, leading to repeated random defaults and extra bookkeeping.
- **Testing complexity**: Graph behaviour is difficult to unit-test on the backend, since logic lives in TS; FE tests (e.g., `graphStore.test.ts`) have to simulate backend data manually.

## 3. Target Backend Contract

### 3.1 Endpoint
- `POST /api/dashboard/graph`
- Request body:
  ```json
  {
    "view_mode": "agent" | "blackboard",
    "filters": {
      "correlation_id": "optional-string",
      "time_range": {"preset": "last10min" | "last5min" | "last1hour" | "all" | "custom", "start": "...", "end": "..."},
      "artifact_types": ["TypeA", ...],
      "producers": ["agent_a", ...],
      "tags": ["tag"],
      "visibility": ["Public", "Tenant", ...]
    },
    "options": {
      "include_statistics": true,
      "label_offset_strategy": "stack" | "none"
    }
  }
  ```
- Response body (shared schema for both modes):
  ```json
  {
    "generated_at": "ISO timestamp",
    "view_mode": "...",
    "filters": {...echoed...},
    "nodes": [
      {
        "id": "agent::pizza_master",
        "type": "agent",
        "position": {"x": 123.4, "y": 456.7},   // Optional; UI can store overrides
        "data": {...payload...}
      }
    ],
    "edges": [
      {
        "id": "pizza_master_food_critic_FoodCritique",
        "type": "message_flow" | "transformation",
        "source": "agent::pizza_master",
        "target": "agent::food_critic",
        "label": "FoodCritique (5, filtered: 3)",
        "data": {...},
        "marker": {...}
      }
    ],
    "statistics": {
      "produced_by_agent": {"pizza_master": {"total": 5, "by_type": {"Pizza": 3}}},
      "consumed_by_agent": {...},
      "artifact_summary": {...mirrors existing summary...}
    }
  }
  ```
- Response should mirror React Flow-compatible structure so UI only handles rendering & local position persistence.

### 3.2 Additional behaviours
- Support pagination/limit in future (scoped out for initial version, but design should allow optional `cursor` field).
- Respect tenant/visibility constraints based on caller auth (align with future multi-tenant roadmap).
- Allow incremental updates later via websocket “graph_delta” events reusing same payload structure.

## 4. Backend Implementation Steps

### 4.1 Core domain models (Pydantic)
- Create `GraphNode` / `GraphEdge` Pydantic models in `src/flock/dashboard/models/graph.py`.
- Mirror fields used by frontend components (`AgentNodeData`, `MessageNodeData`, etc.) ensuring names align with TS consumers.
- Include optional metadata containers for future analytics (e.g., `metrics`, `synthetic` flag).

### 4.2 Graph state assembler
- Implement `GraphAssembler` service in `src/flock/dashboard/graph_builder.py`.
  - Inputs: `view_mode`, `GraphFilters`, optional `layout_overrides`.
  - Data sources:
    - Blackboard store (`SQLiteBlackboardStore` or configured persistence) for artifacts + created timestamps.
    - Runtime run registry (existing `DashboardEventCollector` data or orchestrator run history) for run status and consumptions.
    - Recorded consumption map (`agent_activated` events) to match actual consumer IDs.
  - Responsibilities:
    1. Fetch artifacts/runs filtered server-side (consider new queries in `SQLiteBlackboardStore` to avoid pulling entire table).
    2. Build synthetic runs (same logic as `toDashboardState()`).
    3. Compute edges using Python ports of `deriveAgentViewEdges` / `deriveBlackboardViewEdges`.
    4. Assemble nodes with aggregated stats (recv/sent counts, tags, etc.).
    5. Return `GraphSnapshot` object (nodes, edges, stats).

### 4.3 Filter evaluation
- Introduce reusable `GraphFilterEvaluator` that:
  - Normalises preset time ranges to epoch boundaries.
  - Applies correlation/producer/type/tag/visibility filtering before graph computation.
  - Produces summary counts (total, by type, by producer, by visibility, tag counts) to replace UI `filterStore.setSummary`.
- Ensure optional filters default to existing behaviour: time defaults to `last10min`, empty list => no filter.

### 4.4 API layer
- Add FastAPI route in `DashboardHTTPService._register_dashboard_routes()` (or dedicated router under `/api/dashboard/graph`).
- Validate incoming payload with Pydantic schemas (`GraphRequest`).
- Call `GraphAssembler.build_snapshot(...)`.
- Return serialized result.
- Consider caching the last snapshot per filter signature if identical requests are frequent (phase 2 optimisation).

### 4.5 Websocket integration (future-friendly)
- Extend `DashboardEventCollector` to maintain in-memory `GraphAssembler` cache or queue diff jobs.
- After initial REST implementation, emit `graph_snapshot` or `graph_diff` events whenever:
  - `AgentActivatedEvent` updates consumptions.
  - `MessagePublishedEvent` adds artifacts.
  - `AgentCompletedEvent` updates run metadata.
- UI can subscribe to deltas, falling back to REST refresh.

## 5. Data & Storage Considerations
- **Blackboard persistence**: Ensure `SQLiteBlackboardStore` exposes APIs for filtered retrieval (by time range, type, producer). Might add method `fetch_artifacts(filters: GraphFilters) -> Iterable[ArtifactRecord]`.
- **Run history**: If run data is not persisted, maintain in-memory registry keyed by `run_id` within `DashboardEventCollector`. Provide method `collector.snapshot_runs()` returning safe copy.
- **Consumption tracking**: Persist actual consumption map server-side to avoid relying on FE heuristics. Either:
  - Extend `DashboardEventCollector.on_pre_consume` to update shared `ConsumptionRegistry`.
  - Or compute consumption by cross-referencing run `consumed_artifacts`.
- **Thread safety**: Use asyncio locks or `asyncio.TaskGroup` to avoid race conditions when multiple requests read shared state.
- **Auto tracing**: Register new long-lived services (assemblers, registries) with the auto tracer (`metaclass=AutoTracedMeta`) so their spans land in `.flock/traces.duckdb` for inspection.

## 6. Migration Plan (Frontend)
1. **Phase A – Backend first**: Implement REST endpoint, keep FE logic as-is but behind feature flag to fetch snapshot for initial load (replace `batchUpdate` bootstrap).
2. **Phase B – Simplify stores**:
   - Replace `generateAgentViewGraph`/`generateBlackboardViewGraph` with thin wrappers that consume backend snapshot.
   - Move filter application to backend; FE filter store becomes selector-only (send filters downstream, update summary from response).
   - Deprecate `derive*Edges` and `toDashboardState`.
3. **Phase C – Realtime**: Subscribe to `graph_snapshot` websocket events to update UI without full refresh.
4. Remove dead code, update tests, and bump frontend version.

## 7. Testing & Validation
- **Backend unit tests**:
  - Graph builder for agent view: ensure correct edge grouping, label offsets, filtered counts.
  - Graph builder for blackboard view: ensures produced/consumed cross-product matches spec, synthetic run logic holds.
  - Filter evaluator: coverage for each preset and custom range, multi-filter intersections.
- **Integration tests**:
  - FastAPI route test using `TestClient` verifying 200 responses, schema adherence, filter propagation.
  - Property-based tests for consumption tracking (optional).
- **Frontend smoke tests**:
  - Adjust vitest mocks to consume backend contract.
  - E2E (Playwright) scenario verifying graphs render correctly after switching views/filters.

## 8. Observability & Performance
- Emit tracing spans (`GraphAssembler.build_snapshot`, `SQLiteBlackboardStore.fetch_graph_artifacts`) to integrate with existing DuckDB auto-tracing.
- Capture metrics: request latency, artifact counts, node/edge counts.
- Set sensible response size limits—if graphs exceed threshold, include `truncated: true` flag and optional cursor for further pagination.
- Encourage active tracing while iterating: set `FLOCK_AUTO_TRACE=true` and run `uv run examples/02-the-blackboard/01_persistent_pizza.py` (or new showcase scripts) to capture manageable graphs and confirm spans for build_snapshot + filter evaluation land in DuckDB.

## 9. Next Steps
- [ ] Create Pydantic schemas and graph assembler scaffolding.
- [ ] Implement filtered datastore queries.
- [ ] Port edge derivation algorithms to Python, matching current TS behaviour (including label offsets and filtered label text).
- [ ] Wire new FastAPI endpoint and unit tests.
- [ ] Ship behind `DASHBOARD_GRAPH_V2` feature flag to allow opt-in testing.
- [ ] Coordinate frontend refactor once backend contract stabilises.

## 10. Showcase Examples
- **Purpose**: Demonstrate the backend-driven graph API end-to-end, validate filters, and illustrate tracing-based debugging.
- **Planned scripts** (under `examples/05-dashboard-graphs/`):
  - `01_agent_view_snapshot.py`: spins up a minimal orchestrator (pizza maker + critic), calls the new REST endpoint for `view_mode="agent"`, prints formatted nodes/edges, and highlights relevant trace spans.
  - `02_blackboard_transforms.py`: builds a transformation-heavy workflow, exercises `view_mode="blackboard"`, and inspects transformation edges plus synthetic runs.
  - `03_filtering_and_tracing.py`: seeds multiple correlation IDs, applies diverse filters, and walks through querying `.flock/traces.duckdb` to verify filtered counts.
- **Execution guidance**:
  - Each script documents enabling tracing (`export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true`) and suggests post-run DuckDB queries to validate payloads.
- Scripts reuse the existing pizza example (`uv run examples/02-the-blackboard/01_persistent_pizza.py`) as a baseline for small graphs, ensuring developers can sanity-check the API quickly.
- **Tracing integration**: Any helper service introduced for examples (e.g., `GraphApiClient`) should inherit `AutoTracedMeta` so the auto tracer captures request/response processing for diagnostics.

## 11. Historical Agent Metadata (Persistent)
- **Current state**: `DashboardEventCollector` now persists agent snapshots to the store (`agent_snapshots` table / in-memory map) and hydrates itself at startup. `GraphAssembler` consumes persisted snapshots and still falls back to artifact provenance for unknown actors.
- **Implementation notes**:
  - Snapshots capture description, subscriptions, output types, labels, first/last seen timestamps, and a signature hash.
  - `clear_agent_registry()` wipes both runtime cache and persisted records.
  - Synthetic nodes are only needed when neither runtime agents nor persisted snapshots exist (e.g., `external`).
- **Operator guidance**: Continue treating agent names as stable identities; the signature hash surfaces drift when names are reused intentionally.

## 12. Remaining Frontend-Friendly Enhancements
The new REST snapshot covers the graph topology and statistics, but a few optional backend endpoints would further simplify the UI:

| Area | Why | Potential backend support |
| --- | --- | --- |
| Streaming history / event logs | Detail tabs still fetch and assemble raw events. | Provide `/api/dashboard/agents/{id}/stream` + `/history` endpoints returning ready-to-render entries. |
| Filter facets | Filter UI currently derives options from live websocket events. | Include available artifact types, producers, tags, visibility counts in the snapshot payload. |
| Layout persistence | Node positions are managed in IndexedDB. | (Optional) Expose save/load layout endpoints keyed by view mode. |
| Operational telemetry | Run timelines or budgets still rely on websocket glue. | Decide which data belongs in REST vs streaming updates and document accordingly. |
