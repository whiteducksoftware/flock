# Current Frontend Graph Construction Complexity

**Status**: Analysis Complete
**Date**: October 11, 2025
**Context**: Pre-migration to server-side graph rendering

---

## Executive Summary

The Flock Flow frontend currently implements **complex client-side graph construction** logic totaling **~1,400 lines** across two main files: `graphStore.ts` (state management) and `transforms.ts` (edge derivation algorithms). This logic is now **duplicated** on the backend via the `/api/dashboard/graph` endpoint.

**Key Metrics**:
- **Lines of graph construction code**: ~1,400 lines
- **State management complexity**: 7 Maps + 2 arrays
- **Algorithm complexity**: O(a×c) for agent view, O(r×c×p) for blackboard view
- **Test coverage**: 1,066 lines (861 transform tests + 205 graphStore tests)
- **Duplication**: Edge derivation, filter application, label offset calculation

---

## 1. Core Files & Responsibilities

### 1.1 graphStore.ts (State Management)
**File**: `src/flock/frontend/src/store/graphStore.ts` (689 lines)

**State Structure**:
```typescript
interface GraphState {
  agents: Map<string, Agent>;           // Agent registry
  messages: Map<string, Message>;        // Artifact/message registry
  events: Message[];                     // Event log (max 100)
  runs: Map<string, Run>;               // Run tracking for transformations
  consumptions: Map<string, string[]>;   // artifact_id → consumer_ids
  messagePositions: Map<string, {x,y}>; // Message node positions
  nodes: Node[];                         // React Flow nodes (derived)
  edges: Edge[];                         // React Flow edges (derived)
}
```

**Key Methods**:

1. **`toDashboardState()` (lines 73-154)** - 82 lines
   - Converts Messages to Artifacts
   - Builds synthetic runs for historic data
   - Groups artifacts by `(agent, correlation_id)` buckets
   - Generates run IDs: `historic_{agentId}_{correlationId}_{counter}`
   - **Complexity**: O(n×m) where n = messages, m = runs

2. **`generateAgentViewGraph()` (lines 278-321)** - 44 lines
   - Creates agent nodes with status/counts
   - Preserves node positions (saved → current → random)
   - Calls `deriveAgentViewEdges()` from transforms.ts
   - Applies filters
   - **Complexity**: O(a) + transform complexity

3. **`generateBlackboardViewGraph()` (lines 323-372)** - 50 lines
   - Creates message/artifact nodes
   - Uses consumption data for `consumedBy` field
   - Calls `deriveBlackboardViewEdges()` from transforms.ts
   - Applies filters
   - **Complexity**: O(m) + transform complexity

4. **`applyFilters()` (lines 407-549)** - 143 lines
   - Filters by: correlation, time, types, producers, tags, visibility
   - Rebuilds `visibleMessageIds` Set
   - Recalculates agent statistics (sent/recv counts by type)
   - Hides/shows nodes and edges
   - **Complexity**: O(n×t) where n = messages, t = tags/consumers

**Position Preservation Logic**:
```typescript
const position = agent.position          // From backend snapshot
  || currentPositions.get(agent.id)      // From React Flow current state
  || { x: 400 + Math.random() * 200, y: 300 + Math.random() * 200 }; // Random
```

---

### 1.2 transforms.ts (Edge Derivation)
**File**: `src/flock/frontend/src/utils/transforms.ts` (324 lines)

**Key Algorithms**:

#### 1.2.1 `deriveAgentViewEdges()` (lines 93-204) - 112 lines

**Purpose**: Create message flow edges between agents

**Algorithm**:
```typescript
// Step 1: Group artifacts by (producer, consumer, message_type)
const edgeMap = new Map<string, EdgeData>();
state.artifacts.forEach((artifact) => {
  artifact.consumed_by.forEach((consumer) => {
    const edgeKey = `${producer}_${consumer}_${messageType}`;

    if (edgeMap.has(edgeKey)) {
      // Aggregate: add artifact ID, update timestamp
      existing.artifact_ids.push(artifact.artifact_id);
      if (artifact.published_at > existing.latest_timestamp) {
        existing.latest_timestamp = artifact.published_at;
      }
    } else {
      // Create new edge entry
      edgeMap.set(edgeKey, { /* ... */ });
    }
  });
});

// Step 2: Calculate label offsets for overlapping edges
const nodePairEdges = new Map<string, string[]>();
edgeMap.forEach((data, edgeKey) => {
  const nodes = [data.source, data.target].sort(); // Canonical pair
  const pairKey = `${nodes[0]}_${nodes[1]}`;
  nodePairEdges.get(pairKey).push(edgeKey);
});

// Vertical offset calculation
let labelOffset = 0;
if (totalEdgesInPair > 1) {
  const offsetRange = Math.min(40, totalEdgesInPair * 15);
  const step = offsetRange / (totalEdgesInPair - 1);
  labelOffset = edgeIndex * step - offsetRange / 2;
}

// Step 3: Format labels with filtered counts
const totalCount = data.artifact_ids.length;
const consumedCount = data.artifact_ids.filter(artifactId => {
  const consumers = state.consumptions.get(artifactId) || [];
  return consumers.includes(data.target);
}).length;

let label = `${data.message_type} (${totalCount})`;
if (consumedCount < totalCount && consumedCount > 0) {
  label = `${data.message_type} (${totalCount}, filtered: ${consumedCount})`;
}
```

**Complexity**:
- **Edge grouping**: O(a×c) where a = artifacts, c = avg consumers
- **Label offsets**: O(e²) where e = edges per node pair
- **Filter counting**: O(a×c) per edge

**Output**: Array of edges with:
- `id`: `{source}_{target}_{messageType}`
- `label`: `"Type (total)"` or `"Type (total, filtered: consumed)"`
- `labelOffset`: Vertical offset for overlapping edges
- `data`: { messageType, messageCount, artifactIds, latestTimestamp }

#### 1.2.2 `deriveBlackboardViewEdges()` (lines 225-323) - 99 lines

**Purpose**: Create transformation edges between artifacts via runs

**Algorithm**:
```typescript
// Step 1: Iterate completed runs
state.runs.forEach((run) => {
  if (run.status === 'active') return; // Skip active runs
  if (run.consumed_artifacts.length === 0 || run.produced_artifacts.length === 0) return;

  // Step 2: Create consumed × produced cartesian product
  run.consumed_artifacts.forEach(consumedId => {
    run.produced_artifacts.forEach(producedId => {
      const edgeId = `${consumedId}_${producedId}_${run.run_id}`;
      tempEdges.push({
        id: edgeId,
        source: consumedId,
        target: producedId,
        label: run.agent_name,
        data: {
          transformerAgent: run.agent_name,
          runId: run.run_id,
          durationMs: run.duration_ms
        }
      });
    });
  });
});

// Step 3: Calculate label offsets for overlapping transformations
// (Same logic as agent view - spreads labels vertically)
```

**Complexity**: O(r×c×p) where r = runs, c = consumed artifacts per run, p = produced artifacts per run

**Output**: Array of transformation edges with:
- `id`: `{consumedId}_{producedId}_{runId}`
- `label`: Agent name with offset
- `data`: { transformerAgent, runId, durationMs, labelOffset }

---

## 2. Data Flow Architecture

### 2.1 Current WebSocket-Driven Flow

```
┌─────────────────┐
│ WebSocket Events│
└────────┬────────┘
         │
         ├─→ agent_activated
         ├─→ message_published
         ├─→ streaming_output
         ├─→ agent_completed
         └─→ agent_error
         │
         ▼
┌──────────────────────────────┐
│ graphStore State Updates     │
│ - addAgent()                 │
│ - addMessage()               │
│ - recordConsumption()        │
│ - addRun()                   │
│ - updateRunStatus()          │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ State: agents, messages,     │
│ runs, consumptions (Maps)    │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ toDashboardState() Helper    │
│ - Build artifact list        │
│ - Synthesize runs            │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ DashboardState Object        │
│ { artifacts, runs,           │
│   consumptions }             │
└────────┬─────────────────────┘
         │
         ├─────────────────┬─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌────────────────┐ ┌─────────────┐
│deriveAgentView  │ │deriveBlackboard│ │ applyFilters│
│Edges()          │ │ViewEdges()     │ │()           │
└─────────────────┘ └────────────────┘ └─────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌──────────────────────────────────────────────┐
│ graphStore.nodes + graphStore.edges          │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ GraphCanvas Component        │
│ (React Flow rendering)       │
└──────────────────────────────┘
```

### 2.2 WebSocket Event Handlers
**File**: `src/flock/frontend/src/services/websocket.ts`

**Event Impact on Graph Construction**:

1. **`agent_activated`** (lines 161-214):
   - Creates/updates agent in `graphStore.agents`
   - Records consumption: `recordConsumption(consumed_artifacts, agent_id)`
   - Creates Run record: `{ run_id, agent_name, status: 'active', consumed_artifacts: [], produced_artifacts: [] }`
   - **Does NOT trigger graph regeneration** (waits for message_published)

2. **`message_published`** (lines 216-336):
   - Finalizes streaming messages or creates new message
   - Updates producer's `sentCount`, `sentByType`
   - Updates consumers' `recvCount`
   - Adds artifact to Run's `produced_artifacts`
   - **TRIGGERS graph regeneration**: Calls `generateBlackboardViewGraph()` or `generateAgentViewGraph()`

3. **`streaming_output`** (lines 338-396):
   - Creates/updates streaming message node
   - Updates agent's `streamingTokens` for live display
   - **No graph regeneration** (node already exists)

4. **`agent_completed`** (lines 398-421):
   - Updates Run: `{ status: 'completed', duration_ms }`
   - **No graph regeneration** (run status not shown in graph)

5. **`agent_error`** (lines 423-445):
   - Updates Run: `{ status: 'error' }`
   - **No graph regeneration**

**Graph Regeneration Trigger** (websocket.ts lines 332-335):
```typescript
if (viewMode === 'blackboard') {
  generateBlackboardViewGraph();
} else {
  generateAgentViewGraph();
}
```

---

## 3. Dependencies & Component Coupling

### 3.1 Files Importing graphStore

1. **GraphCanvas.tsx** (primary consumer)
   - **Reads**: `nodes`, `edges`, `generateAgentViewGraph()`, `generateBlackboardViewGraph()`, `applyFilters()`
   - **Lines 39-48**: Zustand selectors
   - **Lines 87-103**: Regenerates graph on mode/data changes
   - **Lines 106-118**: Applies filters on filter changes

2. **DashboardLayout.tsx** (agent tracking)
   - **Reads**: `agents` Map
   - **Purpose**: Open/close agent detail windows

3. **DetailWindowContainer.tsx** (node data lookup)
   - **Reads**: `agents`, `messages` Maps
   - **Purpose**: Fetch node data for detail display

4. **websocket.ts** (state mutations)
   - **Writes**: All graph state via store actions
   - **Lines 161-445**: Event handlers

5. **usePersistence.ts** (position loading)
   - **Calls**: `updateNodePosition()`
   - **Purpose**: Apply loaded positions from IndexedDB

6. **HistoricalArtifactsModule.tsx** (historical data)
   - **Reads**: `messages`, `runs`, `consumptions`
   - **Purpose**: Display historical artifacts

### 3.2 Files Importing transforms.ts

**Only graphStore.ts imports transforms**. No other components directly use edge derivation logic.

---

## 4. Test Coverage Analysis

### 4.1 graphStore Tests
**File**: `src/flock/frontend/src/store/graphStore.test.ts` (205 lines)

**Test Cases**:
- ✅ Add/update agents
- ✅ Add/update messages
- ✅ Event log limiting (100 max)
- ✅ Batch updates
- ✅ Agent view graph generation with consumption tracking
- ✅ Consumption hydration from message payload

**Mock Requirements**: Minimal (direct store manipulation)

### 4.2 Transform Tests
**File**: `src/flock/frontend/src/utils/transforms.test.ts` (861 lines)

**Test Cases** (currently scaffolding - throw "not implemented"):
- ✅ Agent view edge creation
- ✅ Edge grouping by message type
- ✅ Artifact count aggregation
- ✅ Label formatting `"Type (N)"`
- ✅ Latest timestamp tracking
- ✅ Unique edge ID generation
- ✅ Fan-out handling (multiple consumers)
- ✅ Empty state handling
- ✅ Blackboard view transformation edges
- ✅ Consumed × produced cartesian product
- ✅ Run metadata inclusion
- ✅ Active run skipping
- ✅ Edge deduplication

**Mock Requirements**: Complex dashboard state objects

### 4.3 Integration Tests
**File**: `src/flock/frontend/src/__tests__/integration/graph-rendering.test.tsx` (640 lines)

**Test Cases**:
- ✅ Agent view rendering
- ✅ Message flow edge rendering
- ✅ Edge label counts
- ✅ Blackboard view artifacts
- ✅ Mode toggle performance (<100ms)
- ✅ WebSocket event integration
- ✅ Incremental update performance (<50ms)
- ✅ Empty state handling

**Mock Requirements**: React Flow, WebSocket client, IndexedDB

**Total Test Lines**: 1,706 lines for graph construction logic

---

## 5. Performance Characteristics

### 5.1 Complexity Analysis

**toDashboardState()**:
- **Time**: O(n×m) where n = messages, m = runs
- **Reason**: Nested loops building buckets + run synthesis
- **Worst case**: 1000 messages × 100 runs = 100,000 iterations

**deriveAgentViewEdges()**:
- **Time**: O(a×c + e²) where a = artifacts, c = avg consumers, e = edges per node pair
- **Breakdown**:
  - Edge grouping: O(a×c)
  - Label offsets: O(e²)
  - Filter counting: O(a×c)
- **Worst case**: 500 artifacts × 5 consumers + 100² edges = 12,500 ops

**deriveBlackboardViewEdges()**:
- **Time**: O(r×c×p) where r = runs, c = consumed artifacts, p = produced artifacts
- **Worst case**: 50 runs × 10 consumed × 10 produced = 5,000 edges

**applyFilters()**:
- **Time**: O(n×t) where n = messages, t = tags/consumers per message
- **Worst case**: 1000 messages × 5 tags = 5,000 checks

### 5.2 Memory Overhead

**Dual Representation**:
- Raw data: `agents`, `messages`, `runs`, `consumptions` Maps
- Derived data: `nodes`, `edges` arrays
- **Duplication**: Every message exists as Map entry AND node/edge data

**Unbounded Growth**:
- `messagePositions` Map grows indefinitely (no cleanup)
- Synthetic runs accumulate without limits
- Event log capped at 100 (only bounded structure)

### 5.3 Observed Bottlenecks

**Graph Regeneration Frequency**:
- Triggered on EVERY `message_published` event
- No debouncing or batching
- Can cause 10-20 regenerations during multi-agent cascade

**Position Preservation Overhead**:
- Three-level fallback (saved → current → random)
- Requires React Flow state snapshot on every regeneration

---

## 6. Pain Points & Technical Debt

### 6.1 Code Duplication

**Duplicated Logic** (frontend vs backend):
1. **Edge derivation algorithms** - `transforms.ts` vs `graph_builder.py`
2. **Label offset calculation** - Identical algorithm in both places
3. **Filter application** - `applyFilters()` vs backend GraphFilters
4. **Consumption tracking** - `consumptions` Map vs backend registry
5. **Run synthesis** - `toDashboardState()` vs backend synthetic runs

**Maintenance Cost**: Every bug fix or feature must be implemented twice

### 6.2 State Synchronization Issues

**Race Conditions**:
- WebSocket events arrive during filter changes
- Graph regeneration mid-update can show inconsistent state
- No locking or transaction boundaries

**Staleness**:
- Backend may have new artifacts not yet received via WebSocket
- Filters applied to stale data until next WebSocket event

### 6.3 Testing Complexity

**Mock Requirements**:
- WebSocket client simulation
- React Flow mocking
- IndexedDB mocking
- Complex dashboard state objects

**Test Maintenance**:
- 1,706 lines of tests for graph construction
- Many tests currently scaffolding (throw "not implemented")
- Integration tests brittle (rely on timing)

### 6.4 Developer Experience

**Debugging Difficulty**:
- Graph bugs require understanding 3 layers: WebSocket → store → transforms
- No tracing for graph construction (unlike backend spans)
- Console logging insufficient for complex edge cases

**Onboarding Friction**:
- New developers must learn Zustand + transform algorithms + React Flow
- No single source of truth for graph structure
- Filter behavior non-obvious (client-side vs server-side)

---

## 7. Why This Complexity Exists

### 7.1 Historical Context

**Original Design** (pre-backend graph API):
- Dashboard needed to work standalone with minimal backend
- Real-time updates required client-side state management
- React Flow integration required specific node/edge format
- No backend persistence initially → all logic client-side

**Evolutionary Growth**:
- Filters added incrementally (correlation, time, types, producers, tags, visibility)
- Label offset feature added for overlapping edges
- Consumption tracking added for filtered count display
- Synthetic run logic added for historical artifacts

### 7.2 Valid Original Reasons

**Real-Time Requirement**:
- WebSocket events must update graph immediately
- Backend round-trip would add latency
- Client-side derivation felt "instant"

**Offline Capability**:
- Frontend can function while backend unreachable
- IndexedDB provides persistence layer
- State reconstruction from local storage

**Customization**:
- Users can drag nodes (position preservation)
- Filter UI provides instant feedback
- No server load for filter changes

---

## 8. Migration Readiness Assessment

### 8.1 What Backend Provides

**From `/api/dashboard/graph` endpoint**:
- ✅ Complete `GraphSnapshot` with nodes + edges
- ✅ Label offsets calculated server-side
- ✅ Filters applied server-side
- ✅ Statistics (produced/consumed by agent)
- ✅ View mode switching (agent/blackboard)
- ✅ Correlation, time, type, producer, tag, visibility filtering
- ✅ Synthetic run generation
- ✅ Consumption tracking

**What Backend Does NOT Provide**:
- ❌ Real-time status updates (running/idle/error)
- ❌ Streaming message tokens
- ❌ Node positions (frontend-specific)
- ❌ Event log

### 8.2 Components Still Needed Client-Side

**Minimal State** (post-migration):
1. **Agent status** - Real-time running/idle/error states
2. **Streaming messages** - Live token-by-token output
3. **Node positions** - User-dragged positions for persistence
4. **Event log** - Recent events display (max 100)

**Actions**:
1. **fetchGraphSnapshot()** - Call backend API
2. **updateAgentStatus()** - WebSocket status updates
3. **updateStreamingMessage()** - WebSocket token streaming
4. **updateNodePosition()** - Position tracking for IndexedDB

### 8.3 Estimated Migration Effort

**Lines Removed**: ~1,435 lines
- `transforms.ts`: 324 lines
- `graphStore.ts` complexity: ~250 lines
- Test files: 861 lines (transform tests become obsolete)

**Lines Added**: ~200 lines
- API integration: ~50 lines
- Simplified graph fetch: ~100 lines
- Position merging: ~50 lines

**Net Reduction**: **-1,235 lines (-85% of graph construction code)**

**Estimated Time**:
- Core refactor: 2-3 days
- Testing: 1-2 days
- Integration: 1 day
- **Total**: 4-6 days

---

## 9. Risk Factors

### 9.1 Low Risk Items

✅ **Removing transform functions**:
- Backend proven to work with concrete examples
- No loss of functionality

✅ **Simplifying filter application**:
- Backend handles all filter types
- UI only needs to send filter selections

✅ **Removing synthetic run logic**:
- Backend handles run synthesis identically

### 9.2 Medium Risk Items

⚠️ **Position persistence integration**:
- Need to merge backend nodes with saved positions
- React Flow position updates must still work
- **Mitigation**: Keep position Map, merge on snapshot receipt

⚠️ **WebSocket event handler changes**:
- Must maintain real-time feel for status updates
- Risk of losing responsiveness if polling-based
- **Mitigation**: Keep status updates WebSocket-driven, only graph data from API

### 9.3 High Risk Items

🚨 **Streaming message handling**:
- Backend may not track streaming state (incomplete messages)
- Risk of losing live token display during agent execution
- **Mitigation**: Keep `streamingMessages` Map client-side

🚨 **Agent status reactivity**:
- Users expect instant status changes (running → idle)
- Backend snapshot may lag WebSocket events
- **Mitigation**: Overlay real-time status on backend nodes

🚨 **Backward compatibility**:
- Existing saved positions may break
- Filter presets may need migration
- **Mitigation**: Version IndexedDB schema, provide migration script

---

## 10. Conclusion

The current frontend graph construction logic represents **significant technical debt** with **1,400+ lines** of duplicated algorithms, complex state management, and difficult-to-test transform functions. The backend `/api/dashboard/graph` endpoint eliminates the need for 85% of this code while improving consistency and reducing bugs.

**Recommendation**: **Proceed with migration** to server-side graph rendering.

**Key Success Factors**:
1. Preserve real-time agent status updates via WebSocket
2. Maintain streaming message token display
3. Keep node position persistence working
4. Add feature flag for gradual rollout
5. Ensure no performance regression (backend snapshot < 100ms)

**Next Steps**:
1. ✅ Document current complexity (this document)
2. ⏭️ Analyze backend contract completeness
3. ⏭️ Design new simplified architecture
4. ⏭️ Create migration implementation plan
5. ⏭️ Prototype position merging logic
6. ⏭️ Implement feature flag system
