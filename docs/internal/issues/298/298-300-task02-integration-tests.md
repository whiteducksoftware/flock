## 📌 Context
- Parent Issue: #298
- Phase: Phase 2 – Integration & Configuration (#300)
- Task ID: Task 2 – Integration Tests & Restart Scenario
- Owner: @AndreRatzenberger

### Problem Statement
We need integration tests ensuring the SQL store works end-to-end with the orchestrator, including persistence across restarts.

### Scope & Boundaries
- **In scope:**
  - Integration test that publishes artifacts, restarts orchestrator, verifies persistence
  - Test for fallback to in-memory when SQL store unavailable
  - Update CI pipeline to run tests (if necessary)
- **Out of scope / defer:**
  - Performance benchmarking (Phase 3 feedback)

## ✅ Acceptance Criteria
- [ ] Integration test passes verifying persistence across orchestrator restart
- [ ] Integration test covers fallback scenario
- [ ] Tests integrated into CI pipeline

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
1. Create test harness to spin up `Flock` with SQL store, publish artifacts
2. Simulate orchestrator restart (new instance with same DB)
3. Verify artifacts available after restart
4. Add test for misconfigured DB path falling back to in-memory
5. Ensure tests run as part of CI

### Technical Notes
- Use temp DB file persisted across orchestrator instances
- Consider optional fixture to clean up DB file after test
- Logging should confirm store used in test

### Dependencies & Blocks
- Requires Task 1 (config wiring)

## 🧪 Validation Strategy
- **Automated tests:** run integration suite via pytest
- **Manual verification:** optional manual restart scenario to confirm behavior
- **Monitoring / rollback:** ensure tests can be skipped if environment lacks SQLite (document)

## 📎 Artifacts
- Test logs: attach as needed
- Relevant PRs: TBD

## 📅 Timeline
- Kickoff: 2025-10-20
- Target completion: 2025-10-22
- Reviewers: @AndreRatzenberger

### Status Updates
- Pending

## 🧭 Risk & Mitigation
- **Risk:** Restart simulation flakiness
  - **Mitigation:** Use deterministic test flow, clean DB between runs

## 🔄 Follow-Ups
- [ ] Document manual validation steps (Task 3)
