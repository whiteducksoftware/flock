## 🧱 Phase Plan – Phase 2: Integration & Configuration

### Parent Feature Issue
- Issue: #298 (🧭 [SPEC] [0.5.0] SQL-backed Blackboard Store)

### Phase Identifier
- Phase 2 – Orchestrator Integration & Testing

### Phase Owner
- @AndreRatzenberger

### Objective & Outcomes
Integrate the SQL-backed store into the Flock orchestrator as a configurable option, add integration tests, and ensure seamless enablement via configuration.

### Deliverables
- Configuration mechanism to select SQLite store (env vars, constructor options)
- Integration tests covering publish/run_until_idle with persistence
- Docs/internal notes describing configuration defaults
- Graceful fallback to in-memory if SQLite unavailable

### Entry & Exit Criteria
- **Entry criteria:**
  - Phase 1 merged with working SQLite store
- **Exit criteria:**
  - Users can enable persistence via documented configuration
  - Integration tests pass in CI
  - Manual restart scenario validated end-to-end

### Scope Clarifications
- **In scope:**
  - `Flock` constructor updates, CLI/config hooks
  - Test harness updates to cover restart behavior
  - Error handling and logging improvements around config
- **Out of scope:**
  - Postgres support
  - UI/dashboard persistence indicators (Phase 3 or later)

### Dependencies & Blocks
- Needs Phase 1 deliverables completed
- Possibly requires updates to examples/tests referencing store

### Risks & Mitigations
- **Risk:** Configuration complexity/confusion
  - **Mitigation:** Provide sensible defaults, clear docs, and fallback
- **Risk:** Integration tests slow due to SQLite file IO
  - **Mitigation:** Use temporary DB file per test, clean up promptly

### Phase Acceptance Criteria
- CI pipeline green with new integration tests
- Manual smoke test (publish artifacts, restart, verify) documented in issue
- README / docs instructions draft prepared for Phase 3

### Validation Strategy
- Automated tests: integration suite (pytest) with restart scenario
- Manual validation: run example scripts with persistence enabled
- Observability: confirm metrics/logging reflect store usage

### Timeline & Milestones
- Kickoff: 2025-10-17
- Integration complete: 2025-10-22
- Testing & review complete: 2025-10-24

### Communication Plan
- Async updates in issue comments twice weekly
- Highlight progress/blockers in stand-up when relevant

### Status Updates Log
- Pending (phase not started)

### Key Artifacts & References
- docs/internal/issues/298/notes.md
- Configuration docs drafts (to be created)

### Follow-Up Work
- [ ] Publish docs & examples (Phase 3)
- [ ] Collect beta feedback (Phase 3)
