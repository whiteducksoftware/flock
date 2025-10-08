## 📌 Context
- Parent Issue: #298
- Phase: Phase 2 – Integration & Configuration (#300)
- Task ID: Task 1 – Configuration & Wiring
- Owner: @AndreRatzenberger

### Problem Statement
The orchestrator currently defaults to the in-memory store and lacks a way to enable the SQL-backed store. We need configuration hooks so users can opt into persistence.

### Scope & Boundaries
- **In scope:**
  - Update `Flock` constructor/CLI to accept store type or DB path
  - Provide environment variable support (e.g., `FLOCK_STORE=sqlite`)
  - Ensure fallback to in-memory if configuration missing/invalid
- **Out of scope / defer:**
  - UI/dashboard visualization of store choice
  - Advanced config (pool sizing, retention policies)

## ✅ Acceptance Criteria
- [ ] Users can enable SQLite store via constructor parameter and env var
- [ ] Invalid configuration falls back to in-memory with warning
- [ ] Configuration documented in notes ready for Phase 3 docs

### Definition of Done Checklist
- [ ] Code implemented following repository style guides
- [ ] Tests added/updated (unit + integration as relevant)
- [ ] All tests green locally (note commands in updates)
- [ ] Documentation updated (docs/, README, CHANGELOG, etc.)
- [ ] Version bump assessed (if touching release surfaces)
- [ ] Security/privacy review complete (if handling data)
- [ ] Demo/validation evidence attached (screenshots, logs, links)
- [ ] Mentioned in weekly status if customer-facing change

## 🛠️ Implementation Plan
1. Add config options in `Flock` constructor and CLI/ENV parsing
2. Wire up store selection to instantiate `SQLBlackboardStore`
3. Implement fallback with logging on configuration errors
4. Update examples/tests to cover new config (if necessary)
5. Document config behavior in internal notes

### Technical Notes
- Consider using a config object pattern for readability
- Ensure lazy initialization if DB path not provided
- Logging should include selected store type

### Dependencies & Blocks
- Depends on Phase 1 completion (store implementation)

## 🧪 Validation Strategy
- **Automated tests:** integration test verifying config toggles
- **Manual verification:** run example with env var to confirm persistence
- **Monitoring / rollback:** log store selection for troubleshooting

## 📎 Artifacts
- Internal notes: docs/internal/issues/298/notes.md
- Test logs: attach after validation
- Relevant PRs: TBD

## 📅 Timeline
- Kickoff: 2025-10-17
- Target completion: 2025-10-20
- Reviewers: @AndreRatzenberger

### Status Updates
- Pending

## 🧭 Risk & Mitigation
- **Risk:** Confusing config overlaps
  - **Mitigation:** Provide clear precedence and defaults

## 🔄 Follow-Ups
- [ ] Integration tests for restart behavior (Task 2)
