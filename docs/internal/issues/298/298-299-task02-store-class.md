## 📌 Context
- Parent Issue: #298
- Phase: Phase 1 – Schema & Store Foundation (#299)
- Task ID: Task 2 – Implement SQLBlackboardStore
- Owner: @AndreRatzenberger

### Problem Statement
With the schema defined, we still lack a `BlackboardStore` implementation that persists artifacts to SQLite. The orchestrator currently only works with the in-memory store.

### Scope & Boundaries
- **In scope:**
  - Implement `SQLBlackboardStore` class with async CRUD operations
  - Handle serialization/deserialization of Artifact data
  - Ensure thread/async safety with single connection or pooling strategy
- **Out of scope / defer:**
  - Integration into `Flock` constructor/config (Phase 2)
  - Performance optimizations beyond correctness

## ✅ Acceptance Criteria
- [ ] `SQLBlackboardStore` implements `publish`, `get`, `list`, `list_by_type`, `get_by_type`
- [ ] Payloads round-trip between Pydantic models and database rows
- [ ] Concurrent async access tested without data corruption

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
1. Create `SQLBlackboardStore` class and constructor (accept DB path)
2. Connect to SQLite using `aiosqlite`, ensure WAL mode
3. Implement CRUD methods using prepared statements
4. Add helper for converting rows to Artifact objects via `Artifact` model
5. Write unit tests covering each method (temp DB file)

### Technical Notes
- Use context manager to ensure connections committed properly
- Consider connection reuse vs. per-operation connections (document decision)
- Log key operations for debugging

### Dependencies & Blocks
- Depends on schema/migration task completion

## 🧪 Validation Strategy
- **Automated tests:** pytest cases for publish/get/list functions
- **Manual verification:** small script inserting artifacts and verifying via sqlite CLI
- **Monitoring / rollback:** Use logging to trace operations; if failures occur, revert to in-memory store

## 📎 Artifacts
- Design doc: docs/internal/issues/298/notes.md
- Test logs: attach after running tests
- Screenshots / recordings: optional
- Relevant PRs: TBD

## 📅 Timeline
- Kickoff: 2025-10-10
- Target completion: 2025-10-15
- Reviewers: @AndreRatzenberger

### Status Updates
- Pending

## 🧭 Risk & Mitigation
- **Risk:** Concurrency issues (locked DB)
  - **Mitigation:** WAL mode, single connection with transaction guard

## 🔄 Follow-Ups
- [ ] Expose store via configuration (Phase 2)
