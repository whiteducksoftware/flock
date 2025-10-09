## 📌 Context
- Parent Issue: #298
- Phase: Phase 3 – Documentation & Release Prep (#301)
- Task ID: Task 2 – Example & Sample Scripts
- Owner: @AndreRatzenberger

### Problem Statement
We need a runnable example demonstrating how to enable persistence, so users can quickly verify the feature works.

### Scope & Boundaries
- **In scope:**
  - Create or adapt an example script enabling SQL persistence
  - Ensure example publishes artifacts, restarts orchestrator, verifies data
  - Add instructions to docs linking to example
- **Out of scope / defer:**
  - Automated benchmark example (future work)

## ✅ Acceptance Criteria
- [ ] Example script added/updated with persistence workflow
- [ ] README/docs reference example
- [ ] Manual run confirmed and documented

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
1. Choose existing example to extend or add dedicated persistence example
2. Implement script enabling SQL store, publishing artifacts, verifying persistence
3. Add README/docs references to run the example
4. Run example manually and capture outputs/logs

### Technical Notes
- Reuse Phase 2 validation steps
- Provide cleanup instructions for generated DB file

### Dependencies & Blocks
- Depends on configuration and integration from Phase 2

## 🧪 Validation Strategy
- **Automated tests:** optional if example has test hook; otherwise N/A
- **Manual verification:** run example following docs
- **Monitoring / rollback:** Document DB cleanup steps

## 📎 Artifacts
- Example script path: examples/?? (to be decided)
- Logs/screenshots: attach to issue

## 📅 Timeline
- Kickoff: 2025-10-24
- Target completion: 2025-10-27
- Reviewers: @AndreRatzenberger

### Status Updates
- Pending

## 🧭 Risk & Mitigation
- **Risk:** Example diverges from docs
  - **Mitigation:** Cross-reference both, include smoke test step in docs

## 🔄 Follow-Ups
- [ ] Promote example in release notes/changelog
