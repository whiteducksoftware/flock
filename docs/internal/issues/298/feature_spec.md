## 🧭 Feature Specification

### Feature Owner
@AndreRatzenberger

### Stakeholders / Reviewers
@AndreRatzenberger @whiteduck/collab

### Problem Statement
The in-memory blackboard store loses artifacts on restart, preventing long-running workflows, crash recovery, and shared access across orchestrator instances. We need a durable SQL-backed store to persist artifacts locally without requiring heavyweight infrastructure.

### Goals & Success Metrics
- Goal: Provide a drop-in SQL-backed `BlackboardStore` for local durability.
  - Metric: Orchestrator can restart and resume with previous artifacts intact.
  - Metric: Performance overhead ≤ 20% vs in-memory for typical workloads (baseline to be measured).
- Goal: Offer simple configuration to enable SQLite persistence with minimal setup.
  - Metric: Single config flag/env var enables persistence in docs example.

### User Stories / Personas / Narrative
- As a developer, I want blackboard data to survive orchestrator restarts so I can run long-running demos or crash safely.
- As an operator, I want a lightweight persistence option (SQLite) without setting up external databases.
- As an engineer, I want to export artifacts for audit or replay without instrumentation hacks.

### Scope Definition
- **In scope:**
  - Implement `SQLBlackboardStore` using SQLite (WAL mode).
  - Integrate store selection into `Flock` initialization/config.
  - Provide migrations/schema bootstrap for SQLite file.
  - Update docs and examples showing how to enable persistence.
  - Automated tests (unit + integration) covering persistence behavior.
- **Out of scope / defer:**
  - Postgres/Redis backends (future phases).
  - UI/dashboard persistence plumbing beyond store usage.
  - Advanced maintenance tools (pruning, retention policies).

### Functional Requirements
- Store must implement all `BlackboardStore` methods and support concurrent async access.
- Artifacts persisted with full metadata (visibility, tags, correlation_id, etc.).
- Provide optional `extend()` for bulk seeding (if needed).
- Support fetching by ID, type, and `get_by_type` returning Pydantic instances.
- Allow configuring DB file path (default `.flock/blackboard.db`).

### Non-Functional Requirements
- Concurrency: Safe for multiple async tasks in single process (ACID via SQLite).
- Performance: Insert/query latency acceptable for dev workloads (<10ms average). Document expectations.
- Observability: Basic logging on connection/migration, leverage existing metrics counters.
- Reliability: Handle schema initialization automatically; surface errors clearly when DB unavailable.

### Dependencies & Constraints
- Depends on `aiosqlite` (or similar) for async DB access.
- Schema migrations should use simple versioning (module-level constant) for now.
- Requires updates in docs (config, roadmap). No external approvals needed.

### Risks & Open Questions
- **Risk:** SQLite lock contention under heavy parallel load.
  - **Mitigation:** Document best practices (WAL mode), consider connection pooling.
- **Risk:** Migration path when schema evolves.
  - **Mitigation:** Implement version table + simple migration mechanism from start.
- **Open question:** Do we need JSON indexing? For now, rely on TEXT payload; revisit when Postgres backend arrives.

### Rollout & Communication Plan
- Ship behind optional config (default remains in-memory).
- Update README/docs; announce in changelog.
- Encourage feedback via GitHub Discussion.
- No feature flags required.

### High-Level Timeline & Milestones
- Milestone 1 (2025-10-15): Schema + basic store implementation.
- Milestone 2 (2025-10-22): Integration tests + configuration wiring.
- Milestone 3 (2025-10-29): Docs, examples, beta feedback.

### Validation Strategy
- Automated tests: unit tests for CRUD, integration test with orchestrator restart.
- Manual verification: run examples with persistence enabled, confirm artifacts survive restart.
- Monitoring/rollback: Not applicable for local store; document fallback to in-memory.

### Follow-Up Work / Future Enhancements
- [ ] Evaluate Postgres backend (#future)
- [ ] Add maintenance tooling (compaction, retention)
- [ ] Dashboard indication of persistence backend

### Additional Notes / References
- Design doc: Pending (consider short ADR after Phase 1).
- Related issues: #271 (legacy placeholder), will supersede with this spec.
- Research notes: docs/internal/issues/298/notes.md
