# Implementation Plan

## Validation Checklist
- [ ] Context Ingestion section complete with all required specs
- [ ] Implementation phases logically organized
- [ ] Each phase starts with test definition (TDD approach)
- [ ] Dependencies between phases identified
- [ ] Parallel execution marked where applicable
- [ ] Multi-component coordination identified (if applicable)
- [ ] Final validation phase included
- [ ] No placeholder content remains

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific SDD sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

If implementation cannot follow specification exactly:
1. Document the deviation and reason
2. Get approval before proceeding
3. Update SDD if the deviation is an improvement
4. Never deviate without documentation

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

---

## Context Priming

*GATE: You MUST fully read all files mentioned in this section before starting any implementation.*

**Specification**:

- `docs/internal/sqlite-blackboard-store/domain.md` - Domain rules for persistent blackboard storage
- `docs/internal/sqlite-blackboard-store/patterns.md` - Implementation blueprint for SQLite store
- `docs/internal/sqlite-blackboard-store/interfaces.md` - API and dashboard interface expectations

**Key Design Decisions**:

- SQLite must faithfully reproduce current in-memory semantics (canonical type resolution, ordered reads, duplicate overwrite) while persisting every `Artifact` field for visibility and audit parity.
- Historical access requires new paginated artifact APIs and richer dashboard filters so operators can query large datasets without overwhelming the live graph.

**Implementation Context**:

- Commands to run: `uv run pytest tests/test_store.py tests/contract/test_artifact_storage_contract.py`, `uv run pytest tests/dashboard -k artifact` (after adding cases), `uv run playwright test` for dashboard validation.
- Patterns to follow: `docs/internal/sqlite-blackboard-store/patterns.md` (schema, write/read paths, concurrency, migrations).
- Interfaces to implement: `docs/internal/sqlite-blackboard-store/interfaces.md` (REST endpoints for historical artifacts, dashboard UX enhancements).

---

## Implementation Phases

- [x] **Phase 1**: Foundation — SQLite schema & store implementation

    - [x] **Prime Context**: `docs/internal/sqlite-blackboard-store/domain.md`, `docs/internal/sqlite-blackboard-store/patterns.md`
        - [x] Confirm semantic parity requirements (canonical type usage, overwrite behaviour) `[ref: docs/internal/sqlite-blackboard-store/domain.md]`
        - [x] Review schema blueprint, migration strategy, and concurrency guidance `[ref: docs/internal/sqlite-blackboard-store/patterns.md]`
    - [x] **Write Tests**: Extend store contract coverage for SQLite backend `[activity: design-tests]`
        - [x] Parameterise `tests/test_store.py` to run against both in-memory and SQLite implementations `[ref: tests/test_store.py; activity: update-tests]`
        - [x] Mirror `tests/contract/test_artifact_storage_contract.py` against SQLite store to enforce canonical name resolution `[ref: tests/contract/test_artifact_storage_contract.py; activity: update-tests]`
        - [x] Add migration/initialisation regression test (e.g., ensuring `ensure_schema()` idempotency) `[activity: add-tests]`
    - [x] **Implement**: Introduce `SQLiteBlackboardStore` following async pattern `[activity: implement-backend]`
        - [x] Create schema management (`ensure_schema`, migrations, PRAGMA setup) and connection lifecycle helpers `[ref: docs/internal/sqlite-blackboard-store/patterns.md]`
        - [x] Implement `publish`, `get`, `list`, `list_by_type`, `get_by_type`, honouring duplicate overwrite, ordered reads, and JSON payload hydration `[activity: implement-backend]`
    - [x] **Implement**: Observability & maintenance tooling `[activity: implement-backend]`
        - [x] Add OpenTelemetry spans around SQL operations, vacuum/retention helpers as defined in research `[ref: docs/internal/sqlite-blackboard-store/patterns.md]`
    - [x] **Validate**: Ensure reliability & parity
        - [x] Run updated pytest suites (`tests/test_store.py`, `tests/contract/test_artifact_storage_contract.py`) `[activity: run-tests]`
        - [x] Execute concurrency stress test (async gather publish) against SQLite backend `[activity: run-tests]`
        - [x] Review schema artefacts for adherence to domain rules and document retention defaults `[activity: review-docs]`

- [x] **Phase 2**: Orchestrator & service integration

    - [x] **Prime Context**: `docs/internal/sqlite-blackboard-store/interfaces.md`, orchestrator/service modules (`src/flock/orchestrator.py`, `src/flock/service.py`)
        - [x] Map new store into orchestrator lifecycle & dependency injection `[ref: docs/internal/sqlite-blackboard-store/interfaces.md]`
        - [x] Review API expansion requirements for artifact history `[ref: docs/internal/sqlite-blackboard-store/interfaces.md]`
    - [x] **Write Tests**: Define acceptance tests for new endpoints & configuration `[activity: design-tests]`
        - [x] Add API contract tests for paginated artifact listing (`/api/v1/artifacts`) and summaries `[activity: add-tests]`
        - [x] Create integration test ensuring `Flock(store=SQLiteBlackboardStore(...))` publishes/reads successfully `[activity: add-tests]`
    - [x] **Implement**: Wiring the store into runtime `[activity: implement-backend]`
        - [x] Allow `Flock` to accept SQLite store via configuration/CLI, update CLI helpers and documentation `[activity: implement-backend]`
        - [x] Extend FastAPI service with historical artifact endpoints (pagination, filtering, summaries) `[activity: implement-backend]`
    - [x] **Implement**: Migration & configuration tooling `[activity: implement-backend]`
        - [x] Provide CLI commands or scripts to initialise database, run migrations, and configure retention `[activity: implement-backend]`
    - [x] **Validate**: Cross-check orchestration guarantees
        - [x] Run FastAPI endpoint tests and contract suites `[activity: run-tests]`
        - [x] Smoke test CLI/orchestrator flows using SQLite backend (publish/list) `[activity: run-tests]`
        - [x] Verify metrics/tracing capture database operations as required `[activity: review-logs]`

- [ ] **Phase 3**: Dashboard & UX enhancements for historical data

    - [ ] **Prime Context**: `docs/internal/sqlite-blackboard-store/interfaces.md`, dashboard filter implementation (`src/flock/frontend/src/store/filterStore.ts`, `src/flock/frontend/src/services/indexeddb.ts`)
        - [ ] Review required filter additions (artifact type, producer, tags, visibility) `[ref: docs/internal/sqlite-blackboard-store/interfaces.md]`
        - [ ] Inspect IndexedDB schema alignment for saved filters/pagination `[ref: src/flock/frontend/src/services/indexeddb.ts]`
    - [ ] **Write Tests**: Outline UI regression coverage `[activity: design-tests]`
        - [ ] Add unit tests for new filter store state and selectors `[activity: add-tests]`
        - [ ] Extend Playwright scenarios for historical blackboard view and pagination `[activity: add-tests]`
    - [ ] **Implement**: Dashboard data ingestion `[activity: implement-frontend]`
        - [ ] Fetch historical artifact pages on load before WebSocket subscription, hydrate IndexedDB caches `[activity: implement-frontend]`
        - [ ] Add multi-select filters (type, producer, tags, visibility) and saved presets UI `[activity: implement-frontend]`
    - [ ] **Implement**: New historical view & affordances `[activity: implement-frontend]`
        - [ ] Create paginated “Historical Blackboard” table/timeline with virtualization `[activity: implement-frontend]`
        - [ ] Surface retention messaging and “Load older output” interactions tied to SQLite limits `[activity: implement-frontend]`
    - [ ] **Validate**: UX & performance gates
        - [ ] Run frontend unit tests and Playwright suite `[activity: run-tests]`
        - [ ] Perform manual UX review using dashboard examples (`uv run python examples/03-the-dashboard/01_declarative_pizza.py`) `[activity: manual-test]`
        - [ ] Confirm accessibility checks (keyboard navigation, screen-reader labels) for new components `[activity: accessibility-review]`

- [ ] **Integration & End-to-End Validation**
    - [ ] Confirm unit and contract tests pass for both in-memory and SQLite stores
    - [ ] Execute integration tests covering orchestrator/API/dashboard interplay with SQLite backend
    - [ ] Run end-to-end workflow (publish artifacts, query history, filter in dashboard) against SQLite store
    - [ ] Validate performance targets for write throughput and dashboard pagination `[ref: docs/internal/sqlite-blackboard-store/patterns.md]`
    - [ ] Perform security review for data-at-rest, visibility enforcement, and endpoint access controls `[ref: docs/internal/sqlite-blackboard-store/domain.md]`
    - [ ] Verify acceptance criteria from research packet (parity, historical access, UX enhancements)
    - [ ] Ensure documentation updated (README, CLI help, dashboard docs) for new backend option
    - [ ] Run build, lint, and formatting checks; confirm deployment scripts handle SQLite configuration
    - [ ] Record final specification compliance report before release

- [ ] **Integration & End-to-End Validation**
    - [ ] [All unit tests passing per component if multi-component]
    - [ ] [Integration tests for component interactions]
    - [ ] [End-to-end tests for complete user flows]
    - [ ] [Performance tests meet requirements] `[ref: SDD/Section 10 "Quality Requirements"]`
    - [ ] [Security validation passes] `[ref: SDD/Section 10 "Security Requirements"]`
    - [ ] [Acceptance criteria verified against PRD] `[ref: PRD acceptance criteria sections]`
    - [ ] [Test coverage meets standards]
    - [ ] [Documentation updated for any API/interface changes]
    - [ ] [Build and deployment verification]
    - [ ] [All PRD requirements implemented]
    - [ ] [Implementation follows SDD design]
