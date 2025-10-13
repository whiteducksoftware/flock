# Logic Operations UX Implementation Roadmap
## From Backend Support to Full User Experience

**Document Version:** 1.0
**Date:** October 13, 2025
**Status:** Planning Document
**Target:** Flock v0.6+

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Phase Breakdown](#phase-breakdown)
4. [Detailed Task List](#detailed-task-list)
5. [Dependency Graph](#dependency-graph)
6. [Success Criteria](#success-criteria)
7. [Testing Strategy](#testing-strategy)
8. [Risk Assessment](#risk-assessment)
9. [Timeline Estimates](#timeline-estimates)

---

## Executive Summary

### The Gap

**Backend:** JoinSpec and BatchSpec are implemented and work correctly.
**Frontend:** Dashboard has no visual indication of logic operations state.

### What's Missing

When agents use JoinSpec or BatchSpec, the dashboard cannot show:
- **Waiting indicators** - "Waiting for LabResults (1 of 2 artifacts)"
- **Batch progress** - "Collecting... 23/50 items (timeout in 18s)"
- **Countdown timers** - "Expires in 4m 32s"
- **Join correlation status** - "Patient P123: XRay ✓, Labs pending"

### Impact

Without UX for logic operations, users experience:
- ❌ Agents appear "stuck" when waiting for joins
- ❌ No visibility into batch accumulation
- ❌ Time windows are invisible black boxes
- ❌ Debugging correlation issues is impossible

### Solution Approach

Build UX in 4 phases:
1. **Backend API Enhancement** - Add state metadata to agent responses
2. **Data Layer** - Schema and queries for real-time state
3. **Frontend Integration** - Consume API and display indicators
4. **Polish & Testing** - Animations, edge cases, performance

---

## Current State Assessment

### What Exists Today (v0.5)

#### Backend - Logic Operations Core ✅

**Location:** `/Users/ara/Projects/flock/src/flock/subscription.py`

```python
@dataclass
class JoinSpec:
    """Correlated AND gates with time/count windows."""
    by: Callable[[BaseModel], Any]
    within: timedelta | int

@dataclass
class BatchSpec:
    """Batch processing with size/timeout triggers."""
    size: int | None = None
    timeout: timedelta | None = None
```

**Status:** Implemented and functional in orchestrator.

#### Dashboard - Real-time Events ✅

**Location:** `/Users/ara/Projects/flock/src/flock/dashboard/`

**What works:**
- WebSocket infrastructure (`websocket.py`)
- Event models (`events.py`)
- Agent activation tracking (`AgentActivatedEvent`)
- Message publishing tracking (`MessagePublishedEvent`)
- Streaming output (`StreamingOutputEvent`)
- Agent completion/error tracking

**Event types available:**
```python
AgentActivatedEvent      # Agent starts consuming
MessagePublishedEvent    # Artifact published
StreamingOutputEvent     # LLM tokens or logs
AgentCompletedEvent      # Agent finishes successfully
AgentErrorEvent          # Agent execution fails
```

#### Dashboard - Data Models ✅

**Location:** `/Users/ara/Projects/flock/src/flock/dashboard/models/graph.py`

**What exists:**
- Graph nodes (agents, messages)
- Graph edges (message flows)
- Statistics tracking
- Run history models
- Filter capabilities

### What's Missing ❌

#### 1. Backend State Tracking

**No metadata for:**
- Join buffer state (which artifacts arrived, which pending)
- Batch accumulator state (current count, time elapsed)
- Time window tracking (expiry timestamps)
- Correlation key tracking (grouping by patient_id, etc.)

**Impact:** Backend knows state internally but doesn't expose it.

#### 2. WebSocket Events for State Changes

**No events for:**
- "Artifact added to join buffer"
- "Waiting for correlated artifact"
- "Batch accumulator updated (count changed)"
- "Time window about to expire"

**Impact:** Frontend has no way to know what's happening.

#### 3. Frontend Components

**No UI for:**
- Waiting state indicators on agent nodes
- Progress bars for batch accumulation
- Countdown timers for time windows
- Join correlation visualizations

**Impact:** Users see blank nodes with no feedback.

#### 4. Data Schema Extensions

**No database fields for:**
- Active join buffers
- Batch accumulator state
- Time window metadata
- Correlation tracking

**Impact:** State is ephemeral and not queryable.

---

## Phase Breakdown

### Phase 1: Backend API Enhancement (Week 1-2)

**Goal:** Expose logic operations state via WebSocket events and API endpoints.

**Deliverables:**
- New WebSocket events for state changes
- API endpoints for querying current state
- State tracking in orchestrator
- Metadata in agent responses

**Why First:** Frontend cannot build UX without data from backend.

---

### Phase 2: Data Layer Enhancement (Week 3)

**Goal:** Persist and query logic operations state.

**Deliverables:**
- Schema updates for state tracking
- Query patterns for real-time state
- State aggregation logic
- Historical state retrieval

**Why Second:** Enables efficient queries and reduces WebSocket chatter.

---

### Phase 3: Frontend Integration (Week 4-5)

**Goal:** Display logic operations state in dashboard.

**Deliverables:**
- Waiting indicators on agent nodes
- Batch progress bars
- Countdown timers
- Join correlation visualizations

**Why Third:** Requires Phase 1 and 2 data to be available.

---

### Phase 4: Polish & Testing (Week 6)

**Goal:** Production-ready UX with edge cases handled.

**Deliverables:**
- Smooth animations and transitions
- Edge case handling
- Performance optimization
- Comprehensive testing

**Why Last:** Polish requires complete feature set.

---

## Detailed Task List

### Phase 1: Backend API Enhancement (1-2 weeks)

#### 1.1 State Tracking Infrastructure (3 days) - Size: M

**Tasks:**
- [ ] Create `LogicOperationState` data structure in orchestrator
- [ ] Add state tracking to subscription matcher
- [ ] Track join buffers per agent/subscription
- [ ] Track batch accumulators per agent/subscription
- [ ] Implement time window tracking with expiry timestamps

**Files to modify:**
- `/Users/ara/Projects/flock/src/flock/orchestrator.py`
- `/Users/ara/Projects/flock/src/flock/subscription.py`

**Success criteria:**
- Orchestrator maintains accurate state for all logic operations
- State accessible via internal API

---

#### 1.2 New WebSocket Events (3 days) - Size: M

**Tasks:**
- [ ] Define `JoinBufferUpdatedEvent` schema
- [ ] Define `BatchAccumulatorUpdatedEvent` schema
- [ ] Define `TimeWindowExpiringEvent` schema
- [ ] Emit events on state changes
- [ ] Add correlation metadata to events

**New event schemas:**

```python
class JoinBufferUpdatedEvent(BaseModel):
    """Emitted when artifact added to join buffer."""
    correlation_id: str
    timestamp: str
    agent_name: str
    subscription_index: int

    # Join state
    correlation_key: str
    required_types: list[str]
    arrived_types: list[str]  # Which types have arrived
    pending_types: list[str]  # Which types still pending
    arrived_artifacts: list[str]  # Artifact IDs in buffer

    # Time window
    window_start: str | None
    window_end: str | None
    time_remaining_seconds: float | None

class BatchAccumulatorUpdatedEvent(BaseModel):
    """Emitted when artifact added to batch accumulator."""
    correlation_id: str
    timestamp: str
    agent_name: str
    subscription_index: int

    # Batch state
    current_count: int
    target_size: int | None
    timeout_seconds: float | None
    time_remaining_seconds: float | None
    first_artifact_timestamp: str

class TimeWindowExpiringEvent(BaseModel):
    """Emitted when time window about to expire (e.g., 30s before)."""
    correlation_id: str
    timestamp: str
    agent_name: str
    subscription_index: int
    operation_type: Literal["join", "batch"]
    time_remaining_seconds: float
    will_expire_at: str
```

**Files to create:**
- Add to `/Users/ara/Projects/flock/src/flock/dashboard/events.py`

**Success criteria:**
- Events emitted on every state change
- Event data complete and accurate
- Events broadcast via WebSocket

---

#### 1.3 State Query API Endpoints (2 days) - Size: S

**Tasks:**
- [ ] Add `/api/agents/{agent_name}/logic-state` endpoint
- [ ] Add `/api/logic-operations/active` endpoint for all active operations
- [ ] Return current state for joins and batches
- [ ] Include time window metadata

**New endpoints:**

```typescript
GET /api/agents/{agent_name}/logic-state
→ {
    agent_name: "diagnostician",
    active_joins: [
        {
            subscription_index: 0,
            correlation_key: "patient_123",
            required_types: ["XRayAnalysis", "LabResults"],
            arrived_types: ["XRayAnalysis"],
            pending_types: ["LabResults"],
            window_end: "2025-10-13T20:45:00Z",
            time_remaining_seconds: 287.5
        }
    ],
    active_batches: [
        {
            subscription_index: 1,
            current_count: 23,
            target_size: 50,
            timeout_seconds: 30,
            time_remaining_seconds: 12.3,
            first_artifact_timestamp: "2025-10-13T20:40:12Z"
        }
    ]
}

GET /api/logic-operations/active
→ {
    joins: [
        {agent_name: "agent1", ...state...},
        {agent_name: "agent2", ...state...}
    ],
    batches: [
        {agent_name: "agent3", ...state...}
    ],
    total_active: 5
}
```

**Files to modify:**
- `/Users/ara/Projects/flock/src/flock/dashboard/service.py`

**Success criteria:**
- Endpoints return accurate real-time state
- Response format matches schema
- Performance acceptable (< 100ms)

---

#### 1.4 Integration Testing (2 days) - Size: M

**Tasks:**
- [ ] Test join state tracking with `13_medical_diagnostics_joinspec.py`
- [ ] Test batch state tracking (create test example)
- [ ] Test time window expiry
- [ ] Test correlation key grouping
- [ ] Verify WebSocket events emitted correctly

**Success criteria:**
- All existing tests pass
- New integration tests pass
- Example files demonstrate UX

---

### Phase 2: Data Layer Enhancement (1 week)

#### 2.1 Schema Updates (2 days) - Size: M

**Tasks:**
- [ ] Add `logic_operation_state` table to DuckDB schema
- [ ] Add columns for join/batch metadata
- [ ] Add indexes for efficient queries
- [ ] Implement migration script

**Schema design:**

```sql
CREATE TABLE logic_operation_state (
    id UUID PRIMARY KEY,
    agent_name VARCHAR NOT NULL,
    subscription_index INTEGER NOT NULL,
    operation_type VARCHAR NOT NULL,  -- 'join' | 'batch'
    correlation_key VARCHAR,  -- For joins

    -- Join state
    required_types VARCHAR[],
    arrived_types VARCHAR[],
    pending_types VARCHAR[],
    arrived_artifact_ids UUID[],

    -- Batch state
    current_count INTEGER,
    target_size INTEGER,
    timeout_seconds DOUBLE,
    first_artifact_timestamp TIMESTAMP,

    -- Time window
    window_start TIMESTAMP,
    window_end TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,

    INDEX idx_agent_name (agent_name),
    INDEX idx_correlation_key (correlation_key),
    INDEX idx_window_end (window_end)
);
```

**Files to modify:**
- `/Users/ara/Projects/flock/src/flock/store.py` (or equivalent DuckDB schema file)

**Success criteria:**
- Schema supports all required queries
- Migrations work on existing databases
- Performance acceptable (< 50ms per query)

---

#### 2.2 Query Patterns (2 days) - Size: M

**Tasks:**
- [ ] Implement `get_active_joins(agent_name?)` query
- [ ] Implement `get_active_batches(agent_name?)` query
- [ ] Implement `get_expiring_windows(threshold_seconds)` query
- [ ] Implement state cleanup on completion
- [ ] Add caching for frequent queries

**Success criteria:**
- Queries return accurate data
- Performance optimized with indexes
- State cleanup prevents memory leaks

---

#### 2.3 Real-time State Computation (1 day) - Size: S

**Tasks:**
- [ ] Implement `time_remaining_seconds` calculation
- [ ] Implement state aggregation for dashboard
- [ ] Add computed fields for UX (percentage, status)

**Success criteria:**
- Computed fields accurate
- Calculations efficient
- Edge cases handled (expired windows, etc.)

---

#### 2.4 Historical State Retrieval (1 day) - Size: S

**Tasks:**
- [ ] Add API for historical join/batch operations
- [ ] Support filtering by time range
- [ ] Support filtering by agent

**Success criteria:**
- Historical data queryable
- Supports debugging and analytics

---

### Phase 3: Frontend Integration (2 weeks)

#### 3.1 State Management (2 days) - Size: M

**Tasks:**
- [ ] Add Redux/state store for logic operations
- [ ] Subscribe to new WebSocket events
- [ ] Update state on event receipt
- [ ] Implement local countdown timers

**State structure:**

```typescript
interface LogicOperationsState {
    activeJoins: Map<string, JoinState>,  // key: agent_name
    activeBatches: Map<string, BatchState>,
    expiringWindows: Array<ExpiryNotification>
}

interface JoinState {
    agentName: string;
    correlationKey: string;
    requiredTypes: string[];
    arrivedTypes: string[];
    pendingTypes: string[];
    windowEnd: Date;
    timeRemainingSeconds: number;
}

interface BatchState {
    agentName: string;
    currentCount: number;
    targetSize: number | null;
    timeoutSeconds: number | null;
    timeRemainingSeconds: number | null;
    percentComplete: number;  // computed
}
```

**Files to create/modify:**
- Frontend state management (React Context or Redux)

**Success criteria:**
- State updates in real-time
- Local timers countdown smoothly
- Memory efficient (old state cleaned up)

---

#### 3.2 Waiting Indicators (3 days) - Size: M

**Tasks:**
- [ ] Design waiting indicator component
- [ ] Add badge to agent nodes showing "Waiting"
- [ ] Display required vs. arrived types
- [ ] Show countdown timer for time windows
- [ ] Implement animations (pulse, spinner)

**UI Design:**

```
┌─────────────────────────────┐
│  Diagnostician             │
│                             │
│  ⏳ Waiting for join        │
│  ✅ XRayAnalysis            │
│  ⏱️  LabResults (expires 4m) │
│                             │
│  [Progress: 1/2 artifacts]  │
└─────────────────────────────┘
```

**Success criteria:**
- Indicators appear when agent waiting
- Information clear and concise
- Animations smooth (60fps)
- Responsive to state changes

---

#### 3.3 Batch Progress Bars (2 days) - Size: S

**Tasks:**
- [ ] Design progress bar component
- [ ] Show current/target count
- [ ] Show time remaining if timeout-based
- [ ] Update in real-time
- [ ] Handle edge cases (timeout-only batches)

**UI Design:**

```
┌─────────────────────────────┐
│  Recommender               │
│                             │
│  📊 Collecting batch        │
│  ▓▓▓▓▓▓▓▓▓▓▓░░░░░  23/50    │
│  ⏱️ Flush in 18s or 27 more │
│                             │
└─────────────────────────────┘
```

**Success criteria:**
- Progress bar reflects accurate state
- Countdown updates smoothly
- Clear indication of trigger (count vs. timeout)

---

#### 3.4 Join Correlation Visualization (3 days) - Size: L

**Tasks:**
- [ ] Design correlation grouping component
- [ ] Group artifacts by correlation key
- [ ] Show matched vs. pending artifacts
- [ ] Display correlation key value
- [ ] Support multiple concurrent joins

**UI Design (Expanded view):**

```
┌────────────────────────────────────────┐
│  Diagnostician - Active Joins          │
│                                        │
│  Patient P123:                         │
│    ✅ XRayAnalysis (12:34:56)          │
│    ⏱️  LabResults (pending, expires 4m) │
│                                        │
│  Patient P456:                         │
│    ✅ XRayAnalysis (12:40:12)          │
│    ✅ LabResults (12:41:03) → Ready!   │
│                                        │
└────────────────────────────────────────┘
```

**Success criteria:**
- Clear grouping by correlation key
- Status of each required artifact visible
- Supports many concurrent correlations
- Performance acceptable (< 16ms render)

---

#### 3.5 Time Window Warnings (2 days) - Size: S

**Tasks:**
- [ ] Add warning indicator when window about to expire
- [ ] Change color scheme (yellow → orange → red)
- [ ] Show notification when window expires
- [ ] Handle expired artifacts (grayed out)

**Success criteria:**
- Warnings appear 30s before expiry
- Color coding clear
- Notifications non-intrusive

---

#### 3.6 Agent View & Blackboard View Integration (2 days) - Size: M

**Tasks:**
- [ ] Ensure indicators work in Agent View
- [ ] Ensure indicators work in Blackboard View
- [ ] Test with both view modes
- [ ] Adjust layouts for different views

**Success criteria:**
- Indicators visible in both views
- Layout adjustments appropriate
- No performance degradation

---

### Phase 4: Polish & Testing (1 week)

#### 4.1 Animations & Transitions (2 days) - Size: S

**Tasks:**
- [ ] Add smooth fade-in for indicators
- [ ] Add pulse animation for waiting state
- [ ] Add progress bar fill animation
- [ ] Add completion celebration (checkmark animation)
- [ ] Optimize for 60fps

**Success criteria:**
- Animations smooth and not distracting
- Performance acceptable (< 16ms per frame)
- Accessibility considerations (motion preferences)

---

#### 4.2 Edge Case Handling (2 days) - Size: M

**Tasks:**
- [ ] Handle expired time windows gracefully
- [ ] Handle network disconnections (state recovery)
- [ ] Handle rapid state changes (debouncing)
- [ ] Handle very large batch sizes (performance)
- [ ] Handle many concurrent joins (UI scalability)

**Test cases:**
- Time window expires before correlation completes
- Batch timeout triggers before size reached
- Network disconnection during active join
- 100+ concurrent joins for same agent
- Rapid artifact publishing (1000/sec)

**Success criteria:**
- All edge cases handled gracefully
- No crashes or UI freezes
- Clear error messages

---

#### 4.3 Performance Optimization (1 day) - Size: S

**Tasks:**
- [ ] Profile WebSocket event handling
- [ ] Profile state updates and re-renders
- [ ] Optimize countdown timer updates (RAF)
- [ ] Implement virtualization for large lists
- [ ] Add performance monitoring

**Success criteria:**
- WebSocket events processed < 10ms
- State updates < 50ms
- Re-renders < 16ms (60fps)
- Memory usage stable

---

#### 4.4 Comprehensive Testing (2 days) - Size: M

**Tasks:**
- [ ] Unit tests for state management
- [ ] Integration tests for WebSocket events
- [ ] E2E tests for user workflows
- [ ] Performance tests under load
- [ ] Accessibility testing (WCAG 2.1)

**Test coverage targets:**
- Unit tests: > 90%
- Integration tests: Critical paths covered
- E2E tests: User scenarios covered

**Success criteria:**
- All tests pass
- Test coverage meets targets
- No regressions in existing features

---

## Dependency Graph

```
Phase 1: Backend API Enhancement (Week 1-2)
├── 1.1 State Tracking Infrastructure
│   └── Required by: 1.2, 1.3, 1.4
├── 1.2 New WebSocket Events
│   └── Required by: 3.1 (Frontend State Management)
├── 1.3 State Query API Endpoints
│   └── Required by: 3.1 (Frontend State Management)
└── 1.4 Integration Testing
    └── Required by: Phase 2 sign-off

Phase 2: Data Layer Enhancement (Week 3)
├── 2.1 Schema Updates
│   └── Required by: 2.2, 2.3
├── 2.2 Query Patterns
│   └── Required by: 2.3, 2.4
├── 2.3 Real-time State Computation
│   └── Required by: 3.2, 3.3
└── 2.4 Historical State Retrieval
    └── Optional for Phase 3

Phase 3: Frontend Integration (Week 4-5)
├── 3.1 State Management
│   └── Required by: 3.2, 3.3, 3.4, 3.5
├── 3.2 Waiting Indicators
│   └── Required by: 4.1 (Animations)
├── 3.3 Batch Progress Bars
│   └── Required by: 4.1 (Animations)
├── 3.4 Join Correlation Visualization
│   └── Required by: 4.2 (Edge Cases)
├── 3.5 Time Window Warnings
│   └── Required by: 4.1 (Animations)
└── 3.6 Agent/Blackboard View Integration
    └── Required by: 4.4 (E2E Testing)

Phase 4: Polish & Testing (Week 6)
├── 4.1 Animations & Transitions
│   └── Depends on: 3.2, 3.3, 3.5
├── 4.2 Edge Case Handling
│   └── Depends on: 3.4, 3.1
├── 4.3 Performance Optimization
│   └── Depends on: All Phase 3 tasks
└── 4.4 Comprehensive Testing
    └── Depends on: All tasks

Critical Path:
1.1 → 1.2 → 3.1 → 3.2 → 4.1 → 4.4
```

---

## Success Criteria

### Phase 1: Backend API Enhancement

**Must Have:**
- [ ] WebSocket events emitted for all state changes
- [ ] API endpoints return accurate real-time state
- [ ] State tracking works for joins and batches
- [ ] Integration tests pass with example files

**Nice to Have:**
- [ ] Historical state tracking
- [ ] Performance metrics exposed

---

### Phase 2: Data Layer Enhancement

**Must Have:**
- [ ] Schema supports all queries
- [ ] Queries return accurate data
- [ ] Performance acceptable (< 50ms)
- [ ] State cleanup prevents memory leaks

**Nice to Have:**
- [ ] Advanced filtering options
- [ ] Analytics queries

---

### Phase 3: Frontend Integration

**Must Have:**
- [ ] Waiting indicators appear on agent nodes
- [ ] Batch progress bars update in real-time
- [ ] Countdown timers accurate
- [ ] Join correlation visualizations clear
- [ ] Works in both Agent and Blackboard views

**Nice to Have:**
- [ ] Expanded detail views
- [ ] Historical state browser

---

### Phase 4: Polish & Testing

**Must Have:**
- [ ] Animations smooth (60fps)
- [ ] Edge cases handled gracefully
- [ ] Performance optimized
- [ ] Test coverage > 90%
- [ ] No regressions

**Nice to Have:**
- [ ] Accessibility WCAG 2.1 AA
- [ ] Keyboard navigation support

---

## Testing Strategy

### Unit Tests

**Backend:**
- State tracking logic
- Event emission
- API endpoint responses
- Query functions
- Time window calculations

**Frontend:**
- State management reducers
- Component rendering
- Countdown timer logic
- Event handling

**Coverage target:** > 90%

---

### Integration Tests

**Backend:**
- End-to-end join workflows
- End-to-end batch workflows
- WebSocket event flow
- API + WebSocket coordination

**Frontend:**
- WebSocket event handling
- State updates → UI updates
- Real-time countdown timers

**Coverage target:** Critical paths

---

### E2E Tests

**User workflows:**
1. Publish artifacts and watch join complete
2. Monitor batch accumulation and flush
3. Observe time window expiry
4. Switch between Agent/Blackboard views
5. Filter by correlation ID

**Tools:** Playwright or Cypress

**Coverage target:** Core user scenarios

---

### Performance Tests

**Metrics to track:**
- WebSocket event processing time
- State update latency
- Re-render time
- Memory usage
- Network bandwidth

**Load scenarios:**
- 100 concurrent joins
- 1000 artifacts/second
- 10 simultaneous users
- 24-hour continuous operation

**Targets:**
- Event processing: < 10ms
- State updates: < 50ms
- Re-renders: < 16ms (60fps)
- Memory: Stable over time

---

## Risk Assessment

### High Risk 🔴

**1. Performance at Scale**
- **Risk:** UI becomes sluggish with many concurrent operations
- **Mitigation:** Virtualization, debouncing, lazy loading
- **Fallback:** Simplified view for high load

**2. WebSocket Event Flood**
- **Risk:** Too many events overwhelm frontend
- **Mitigation:** Event batching, debouncing, rate limiting
- **Fallback:** Polling fallback mode

**3. State Synchronization Issues**
- **Risk:** Frontend state diverges from backend reality
- **Mitigation:** Periodic state reconciliation, optimistic UI updates
- **Fallback:** Full state refresh on error

---

### Medium Risk 🟡

**4. Time Window Accuracy**
- **Risk:** Client clock skew causes incorrect countdowns
- **Mitigation:** Server-side timestamps, periodic sync
- **Fallback:** Display ranges instead of exact times

**5. Edge Case Complexity**
- **Risk:** Unexpected combinations of joins + batches
- **Mitigation:** Comprehensive testing, graceful degradation
- **Fallback:** Basic state display without advanced features

**6. Browser Compatibility**
- **Risk:** Animations or timers behave differently across browsers
- **Mitigation:** Cross-browser testing, polyfills
- **Fallback:** Static indicators without animations

---

### Low Risk 🟢

**7. Schema Migration Issues**
- **Risk:** Database migration fails on existing deployments
- **Mitigation:** Thorough migration testing, rollback plan
- **Fallback:** Manual schema updates

**8. API Versioning**
- **Risk:** New API breaks existing clients
- **Mitigation:** API versioning, backward compatibility
- **Fallback:** Feature detection

---

## Timeline Estimates

### Optimistic (Best Case): 5 weeks

Assumes:
- No major blockers
- All tasks complete on schedule
- Minimal bug fixes needed
- Team fully focused

**Breakdown:**
- Phase 1: 1 week
- Phase 2: 0.5 weeks (tasks run in parallel)
- Phase 3: 2 weeks
- Phase 4: 0.5 weeks (minimal issues)

---

### Realistic (Expected): 6 weeks

Assumes:
- Minor blockers and delays
- Some tasks take longer than estimated
- Normal bug fix cycle
- Typical development pace

**Breakdown:**
- Phase 1: 2 weeks (includes debugging and iteration)
- Phase 2: 1 week
- Phase 3: 2 weeks
- Phase 4: 1 week

---

### Pessimistic (Worst Case): 9 weeks

Assumes:
- Major blockers discovered
- Significant architectural changes needed
- Extensive bug fixing
- Resource constraints

**Breakdown:**
- Phase 1: 3 weeks (unexpected complexity)
- Phase 2: 1.5 weeks
- Phase 3: 3 weeks (UI iteration)
- Phase 4: 1.5 weeks (edge cases)

---

## Sprint Planning

### Sprint 1 (Week 1-2): Backend Foundation

**Goal:** Complete Phase 1.1-1.3

**Deliverables:**
- State tracking infrastructure
- WebSocket events
- API endpoints

**Demo:** Show real-time state via API calls and WebSocket logs

---

### Sprint 2 (Week 3): Data Layer

**Goal:** Complete Phase 2

**Deliverables:**
- Schema updates
- Query patterns
- State computation

**Demo:** Query logic operations state via API

---

### Sprint 3 (Week 4-5): Frontend UX

**Goal:** Complete Phase 3.1-3.5

**Deliverables:**
- State management
- Waiting indicators
- Progress bars
- Countdown timers

**Demo:** Live dashboard showing logic operations

---

### Sprint 4 (Week 6): Polish

**Goal:** Complete Phase 4

**Deliverables:**
- Animations
- Edge case handling
- Testing
- Performance optimization

**Demo:** Production-ready feature

---

## Rollout Strategy

### Phase 1: Internal Alpha (Week 6)

**Audience:** Development team only

**Validation:**
- Core functionality works
- No critical bugs
- Performance acceptable

**Feedback mechanism:** GitHub issues

---

### Phase 2: Beta Release (Week 7-8)

**Audience:** Early adopters (opt-in feature flag)

**Validation:**
- Real-world usage patterns
- Edge cases discovered
- Performance at scale

**Feedback mechanism:** Discord channel, surveys

---

### Phase 3: General Availability (Week 9)

**Audience:** All users

**Rollout plan:**
- Documentation published
- Blog post announcement
- Migration guide for existing examples

**Support plan:**
- Monitor error rates
- Quick response to issues
- Patch releases as needed

---

## Maintenance Plan

### Post-Launch (Week 9+)

**Monitoring:**
- Error tracking (Sentry or equivalent)
- Performance metrics (FE/BE latency)
- User analytics (feature usage)

**Iteration priorities:**
1. Critical bugs (P0) - Fix within 24h
2. Performance issues (P1) - Fix within 1 week
3. Feature requests (P2) - Roadmap for v0.7
4. Nice-to-haves (P3) - Backlog

---

## Related Documentation

- [Logic Operations API Design](/Users/ara/Projects/flock/docs/internal/logic-operations/api_design.md)
- [Dashboard Architecture](/Users/ara/Projects/flock/src/flock/dashboard/README.md)
- [Example: Medical Diagnostics JoinSpec](/Users/ara/Projects/flock/examples/02-dashboard/13_medical_diagnostics_joinspec.py)

---

## Appendix: Example Workflow

### User Journey: Medical Diagnostics with JoinSpec

**Scenario:** Radiologist agent waits for both XRay and Lab results for same patient.

#### Step 1: XRay Published

**Backend:**
```python
# XRay artifact published
await orchestrator.publish(XRayImage(patient_id="P123"))
# → Triggers join buffer update
```

**WebSocket event:**
```json
{
  "event_type": "join_buffer_updated",
  "agent_name": "diagnostician",
  "correlation_key": "P123",
  "required_types": ["XRayImage", "LabResults"],
  "arrived_types": ["XRayImage"],
  "pending_types": ["LabResults"],
  "time_remaining_seconds": 300
}
```

**UI Update:**
```
┌─────────────────────────────┐
│  Diagnostician             │
│  ⏳ Waiting for join        │
│  ✅ XRayImage               │
│  ⏱️  LabResults (expires 5m) │
│  [Progress: 1/2 artifacts]  │
└─────────────────────────────┘
```

---

#### Step 2: Lab Results Published (Same Patient)

**Backend:**
```python
# Lab results published
await orchestrator.publish(LabResults(patient_id="P123"))
# → Join complete! Agent triggered
```

**WebSocket event:**
```json
{
  "event_type": "agent_activated",
  "agent_name": "diagnostician",
  "consumed_artifacts": ["xray-uuid", "labs-uuid"],
  "correlation_key": "P123"
}
```

**UI Update:**
```
┌─────────────────────────────┐
│  Diagnostician             │
│  ✅ Join complete!          │
│  ▶️ Processing...           │
└─────────────────────────────┘
```

---

#### Step 3: Diagnosis Published

**Backend:**
```python
# Agent completes and publishes diagnosis
return [DiagnosticReport(...)]
```

**WebSocket event:**
```json
{
  "event_type": "agent_completed",
  "agent_name": "diagnostician",
  "artifacts_produced": ["diagnosis-uuid"]
}
```

**UI Update:**
```
┌─────────────────────────────┐
│  Diagnostician             │
│  ✅ Completed               │
│  📄 Produced: DiagnosticReport │
└─────────────────────────────┘
```

---

## Conclusion

This roadmap provides a clear path from backend implementation to full UX integration for logic operations. By following this phased approach, we ensure:

- **Backend-first:** Data available before UI built
- **Incremental delivery:** Working features every sprint
- **Risk mitigation:** Testing and edge cases prioritized
- **Team alignment:** Clear dependencies and timelines

**Next Steps:**
1. Review and approve this roadmap
2. Allocate resources (backend, frontend, QA)
3. Kick off Sprint 1 (Backend Foundation)
4. Set up tracking (GitHub project board)

**Questions or feedback?** Please open a discussion in the Flock repository.

---

**Document prepared by:** Claude Code
**Last updated:** October 13, 2025
**Status:** Ready for review
