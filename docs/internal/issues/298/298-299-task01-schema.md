## 📌 Context
- Parent Issue: #298
- Phase: Phase 1 – Schema & Store Foundation (#299)
- Task ID: Task 1 – Schema Definition & Migration
- Owner: @AndreRatzenberger

### Problem Statement
We need a durable database schema to persist artifacts with full metadata. Currently there is no schema or migration logic to bootstrap SQLite persistence.

### Scope & Boundaries
- **In scope:**
  - Define SQL schema mirroring Artifact fields (id, type, payload, etc.)
  - Implement migration/bootstrap logic (version table)
  - Ensure WAL mode and basic DB setup
- **Out of scope / defer:**
  - Postgres-specific schema or migrations
  - Retention or cleanup policies

## ✅ Acceptance Criteria
- [ ] Schema created automatically on first use with all necessary indices
- [ ] Version table created to track migration versions
- [ ] WAL mode enabled and verified via logs/test

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
1. Decide on SQLite schema (table columns, indices)
2. Implement migration bootstrap logic in SQL store module
3. Add WAL mode configuration during DB initialization
4. Write unit tests verifying migration and schema creation
5. Document schema details in notes/ADR

### Technical Notes
- Table `artifacts`: id (UUID TEXT), type TEXT, payload JSON TEXT, produced_by TEXT, visibility JSON, tags JSON, correlation_id TEXT, partition_key TEXT, version INTEGER, created_at TIMESTAMP
- Index on type, correlation_id, created_at
- Use simple migration version table `schema_meta`

### Dependencies & Blocks
- None.

## 🧪 Validation Strategy
- **Automated tests:** pytest unit tests performing migration on temp DB file
- **Manual verification:** Run store initialization and inspect schema with sqlite CLI
- **Monitoring / rollback:** Log schema version; fallback to raising exception on migration failure

## 📎 Artifacts
- Design doc: docs/internal/issues/298/notes.md
- Test logs: attach to issue when tests run
- Screenshots / recordings: optional DB schema output
- Relevant PRs: to be linked

## 📅 Timeline
- Kickoff: 2025-10-09
- Target completion: 2025-10-12
- Reviewers: @AndreRatzenberger

### Status Updates
- 2025-10-09 – Task drafted.

## 🧭 Risk & Mitigation
- **Risk:** Schema misses fields due to future Artifact changes
  - **Mitigation:** tie schema creation to Artifact model fields (document mapping)

## 🔄 Follow-Ups
- [ ] Coordinate with configuration task to ensure DB path configurable
