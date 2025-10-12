# Server-Side Graph Tasks

## 0. Prep
- [x] Confirm `FLOCK_AUTO_TRACE=true` and `FLOCK_TRACE_FILE=true` in local env.
- [x] Run `uv run examples/02-the-blackboard/01_persistent_pizza.py` to bootstrap sample data.
- [x] Review current dashboard docs (`docs/specs/003-real-time-dashboard/DATA_MODEL.md`).

## 1. Domain Models & Schemas
- [x] Create `GraphFilters`, `GraphNode`, `GraphEdge`, `GraphSnapshot`, `GraphRequest` Pydantic models (`src/flock/dashboard/models/graph.py`).
- [x] Ensure models align with frontend expectations (React Flow structure, statistics payload).
- [x] Integrate `AutoTracedMeta` where appropriate.

## 2. Data Access Enhancements
- [x] Extend `SQLiteBlackboardStore` (or abstract store) with `fetch_graph_artifacts(filters: GraphFilters)` supporting time/type/producer/tag/visibility filtering.
- [x] Expose run history snapshot method within `DashboardEventCollector` or dedicated registry for completed runs.
- [x] Provide consumption tracking registry (actual consumer ids) accessible to graph assembler.
- [x] Ensure data access functions emit tracing spans.

## 3. Graph Assembly Service
- [x] Implement `GraphAssembler` in `src/flock/dashboard/graph_builder.py`.
  - [x] Fetch filtered artifacts/runs/consumptions.
  - [x] Generate synthetic runs (matching `toDashboardState` semantics).
  - [x] Port `deriveAgentViewEdges` logic to Python; include label offsets, filtered counts.
  - [x] Port `deriveBlackboardViewEdges`; include run-specific IDs and offsets.
  - [x] Build node arrays (agent + message variants) with stats.
  - [x] Construct statistics block (produced/consumed counts, artifact summary).
  - [x] Wrap entire build in tracing span (`GraphAssembler.build_snapshot`).

## 4. Historical Agent Metadata
- [x] Extend `DashboardEventCollector` to persist agent activation snapshots (metadata + signature hash).
- [x] Provide `snapshot_agent_registry()` and clear/reset helpers.
- [x] Update `GraphAssembler` to hydrate inactive agent nodes from cached metadata (status + last_seen).
- [x] Surface inactive nodes in response payload (include signature/timestamp fields).
- [x] Add unit tests covering inactive agent reconstruction.

## 5. API Layer
- [x] Add FastAPI router/endpoint `POST /api/dashboard/graph` in `DashboardHTTPService`.
- [x] Validate request payload (view mode, filters, options).
- [x] Invoke `GraphAssembler`, return serialized snapshot.
- [x] Add feature flag `DASHBOARD_GRAPH_V2` to toggle endpoint exposure.
- [x] Register endpoint in auto-tracing discovery if new service class created.

## 6. Frontend v2 Scaffolding
- [ ] Set up `src/flock/frontend_v2/` with Vite/React/TypeScript matching existing stack.
- [ ] Add build scripts and npm workspace configuration for frontend_v2.
- [ ] Update `DashboardHTTPService` to serve new assets via `serve(dashboard_v2=True)` (legacy remains default).
- [ ] Implement minimal page shell that fetches `/api/dashboard/graph` and renders placeholder counts.

## 7. Frontend v2 Core Graph Experience
- [ ] Build new Zustand store for nodes/edges/statistics driven entirely by backend snapshots.
- [ ] Implement React Flow graph component consuming server data (agent & blackboard modes).
- [ ] Wire filter controls to request backend snapshots and display summaries.
- [ ] Integrate node position persistence compatible with new data model.

## 8. Frontend v2 Panels & Modules
- [ ] Recreate detail windows (live output, history, run status) using new store shape.
- [ ] Port optional modules (historical artifacts, etc.) or drop if superseded.
- [ ] Adapt websocket client to merge live events with fetched snapshots.
- [ ] Ensure streaming outputs, event logs, and dashboards align with new contract.

## 9. Legacy Frontend Decommission
- [ ] Remove legacy `graphStore`, transforms, and dependent tests/components.
- [ ] Redirect `serve(dashboard=True)` to frontend_v2 once feature parity achieved.
- [ ] Delete obsolete assets and IndexedDB code specific to v1 layouts.
- [ ] Document migration notes for contributors.

## 10. Testing & Validation
- [x] Backend unit tests for `GraphAssembler` (agent view, blackboard view, filtering).
- [x] Backend tests for new store methods (SQLite queries, consumption registry).
- [x] FastAPI route test hitting `/api/dashboard/graph`.
- [ ] Vitest updates/mocks to support snapshot-based data.
- [ ] Manual validation via tracing: inspect `.flock/traces.duckdb` spans after running pizza example + API call.

## 11. Showcase Examples
- [ ] Create `examples/05-dashboard-graphs/01_agent_view_snapshot.py`.
- [ ] Create `examples/05-dashboard-graphs/02_blackboard_transforms.py`.
- [ ] Create `examples/05-dashboard-graphs/03_filtering_and_tracing.py`.
- [ ] Document tracing workflow inside each script.
- [ ] Update `docs/examples` overview referencing new scripts.

## 12. Documentation
- [ ] Update `docs/internal/design_and_goals/server_side_graph_plan.md` status sections when tasks complete.
- [ ] Add dashboard API reference in `docs/reference/configuration.md` or new doc page.
- [ ] Mention feature flag + tracing expectations in `AGENTS.md`.

## 13. Rollout
- [ ] Verify version bumps (`pyproject.toml`, frontend `package.json` if UI changes shipped).
- [ ] Remove legacy edge derivation utils once frontend fully migrated.
- [ ] Coordinate feature flag rollout & announce in team changelog.
