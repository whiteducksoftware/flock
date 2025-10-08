## 🧱 Phase Plan – Phase 1: Foundational SQLite Store

### Parent Feature Issue
- Issue: #298 (🧭 [SPEC] [0.5.0] SQL-backed Blackboard Store)

### Phase Identifier
- Phase 1 – Schema & Core Store Implementation

### Phase Owner
- @AndreRatzenberger

### Objective & Outcomes
Build the MVP `SQLBlackboardStore` backed by SQLite with working CRUD operations and schema initialization. This phase delivers the core persistence class and ensures basic correctness under single-process load.

### Deliverables
- `SQLBlackboardStore` class implementing `BlackboardStore`
- Schema bootstrap/migration script for SQLite database file
- Unit tests covering publish/get/list/list_by_type/get_by_type
- Preliminary ADR or notes documenting schema decisions

### Entry & Exit Criteria
- **Entry criteria:**
  - Feature spec #298 approved
  - Branch scaffolded with templates and notes
- **Exit criteria:**
  - Store class merged with passing tests
  - Schema creation automated on first use
  - Manual smoke test instructions documented

### Scope Clarifications
- **In scope:**
  - SQLite file persistence, WAL mode configuration
  - Basic migration/version table
  - Error handling for DB connectivity
- **Out of scope:**
  - Postgres backend
  - Config wiring into `Flock` (Phase 2)
  - Documentation updates (Phase 3)

### Dependencies & Blocks
- Dependency: Selection of async SQLite driver (`aiosqlite`)
- Dependency: Agreement on schema fields (mirror Artifact model)
- No external approvals required

### Risks & Mitigations
- **Risk:** Lock contention due to naive connection usage
  - **Mitigation:** Use a shared async connection or connection pool, enable WAL
- **Risk:** Pydantic model changes impacting schema
  - **Mitigation:** Version table + incremental migration strategy

### Phase Acceptance Criteria
- New store passes unit tests executed via CI
- Manual smoke test confirms artifacts persist between process restarts
- Notes/ADR capturing schema decisions stored in docs/internal/issues/298

### Validation Strategy
- Automated tests: pytest suite targeting store behavior
- Manual validation: Local script publishing artifacts, restarting orchestrator, verifying persistence
- Observability: Logging on schema creation and publish operations for debugging

### Timeline & Milestones
- Kickoff: 2025-10-09
- Core implementation complete: 2025-10-15
- Testing & review complete: 2025-10-17

### Communication Plan
- Weekly async updates in issue comments (Fridays)
- Share progress in engineering stand-up if blockers arise

### Status Updates Log
- 2025-10-09 – Phase plan drafted and committed.

### Key Artifacts & References
- docs/internal/issues/298/notes.md
- docs/internal/issues/298/feature_spec.md

### Follow-Up Work
- [ ] Configure store selection in `Flock` (Phase 2)
- [ ] Document persistence usage (Phase 3)
