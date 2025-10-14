# Future Work: Historical State Persistence

**Status**: Deferred - Implement when user need arises
**Effort**: ~4-6 hours (Medium complexity)
**Priority**: LOW

## Context

Phase 1 and Phase 1.5 of Logic Operations UX have been successfully delivered:
- ✅ Real-time WebSocket events for correlation groups and batches
- ✅ Pending edges visualization (purple for JoinSpec, orange for BatchSpec)
- ✅ Client-side timers and progress indicators
- ✅ Smart flush prediction for hybrid batches

**Current limitation**: Correlation groups and batch state exist only in-memory. They are lost on dashboard restart.

## What Phase 2 Would Add

### Historical State Persistence
Store correlation/batch state in SQLite alongside existing artifact data.

**New table schema**:
```sql
CREATE TABLE logic_operation_state (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    subscription_index INTEGER NOT NULL,
    operation_type TEXT NOT NULL,  -- 'join' or 'batch'
    correlation_key TEXT,
    created_at TEXT NOT NULL,
    window_end TEXT,
    collected_types TEXT,          -- JSON array of collected artifact types
    required_types TEXT,           -- JSON array of required types (JoinSpec)
    items_collected INTEGER,       -- Batch count
    items_target INTEGER,          -- Batch size threshold
    state_snapshot TEXT NOT NULL   -- Full JSON state for restoration
);
```

### Features Enabled
- Survive dashboard restarts without losing correlation/batch context
- Historical debugging ("What artifacts were in that correlation group?")
- Audit trail for compliance scenarios
- Resume timers for ongoing operations

## Implementation Checklist

When implementing, follow these steps:

### 1. Schema Design & Migration (1-1.5 hours)
- [ ] Add `logic_operation_state` table to `src/flock/store.py`
- [ ] Design JSON schema for `state_snapshot` field
- [ ] Bump schema version (3 → 4)
- [ ] Add migration logic for existing deployments
- [ ] Create indices for efficient queries:
  - `(agent_name, subscription_index)`
  - `(operation_type)`
  - `(created_at)` for cleanup

### 2. Persistence Hooks (1.5-2 hours)
- [ ] Modify `CorrelationEngine._handle_new_artifact()` to persist updates
- [ ] Modify `BatchEngine._handle_new_artifact()` to persist updates
- [ ] Add `_serialize_state()` methods to both engines
- [ ] Add `_deserialize_state()` methods to both engines
- [ ] Handle rapid concurrent updates (debouncing/batching)

### 3. State Restoration (1-1.5 hours)
- [ ] Add `restore_logic_state()` to CorrelationEngine
- [ ] Add `restore_logic_state()` to BatchEngine
- [ ] Call restoration on dashboard startup
- [ ] Recalculate remaining timeouts based on elapsed time
- [ ] Validate restored state (handle stale/corrupted data)
- [ ] Resume client-side timers via WebSocket

### 4. Cleanup & Maintenance (0.5-1 hour)
- [ ] Background task to prune completed entries
- [ ] Retention policy (e.g., keep last 7 days)
- [ ] Cleanup trigger on agent shutdown
- [ ] Handle orphaned state (artifacts consumed while down)

### 5. Testing (0.5-1 hour)
- [ ] Test restart scenarios (mid-correlation, mid-batch)
- [ ] Verify timer resumption accuracy
- [ ] Edge case: corrupted state handling
- [ ] Edge case: missing artifacts after restoration
- [ ] Performance: large state snapshots

## Why Deferred

**Current architecture works well because**:
1. Dashboard restarts are rare in practice
2. Correlations/batches complete quickly (seconds to minutes)
3. Losing in-memory state is acceptable for development/testing
4. No production users yet demanding persistence

**Complexity considerations**:
- Timer restoration requires careful time math
- Stale state handling (artifacts consumed while down)
- Keeping SQLite + in-memory state synchronized
- Migration path for running systems

## When to Implement

Implement Phase 2 when:
- Production users report pain from losing state on restarts
- Long-running batches (hours/days) become common
- Compliance requirements demand audit trails
- Historical debugging becomes a frequent need

**Timing sweet spot**: After gathering real-world usage patterns and retention requirements.

## References

- Original spec: `docs/specs/004-logic-operations-ux/PLAN.md` (Phase 2)
- Current SQLite schema: `src/flock/store.py` (schema version 3)
- Correlation engine: `src/flock/engine/correlation.py`
- Batch engine: `src/flock/engine/batch.py`
- Dashboard service: `src/flock/dashboard/service.py`

---

**Last updated**: 2025-10-14
**Decision**: Deferred until user need arises
**Estimated effort**: ~4-6 hours when implemented
