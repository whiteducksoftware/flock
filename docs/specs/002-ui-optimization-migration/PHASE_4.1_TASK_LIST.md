# Phase 4.1: Complete OLD Architecture Removal

**Goal**: Fix all 68 TypeScript build errors by removing/rewriting OLD Phase 1 architecture code

**Status**: 🔴 BLOCKING - Build currently fails with 68 errors

---

## Error Analysis Summary

- **Total Errors**: 68 TypeScript compilation errors
- **Affected Files**: 20 files (components, services, tests, types)
- **Root Cause**: Components still using removed Phase 1 APIs (`agents`, `messages`, `runs` Maps, OLD methods)

---

## Task Categories

### **Category 1: Components Using Removed Store Properties** (HIGH PRIORITY - 6 files, ~15 errors)

These components access removed `agents`, `messages`, `runs` Maps from graphStore.

#### 1.1 **DetailWindowContainer.tsx**
**Errors**:
- Line 13: `Property 'agents' does not exist on type 'GraphState'`
- Line 14: `Property 'messages' does not exist on type 'GraphState'`

**OLD Code Pattern**:
```typescript
const agents = useGraphStore((state) => state.agents);
const messages = useGraphStore((state) => state.messages);
```

**NEW Approach**: Read from `state.nodes` (which contains GraphNode[]) instead of Maps

**Complexity**: MEDIUM - Need to filter nodes by type (agent vs artifact)

---

#### 1.2 **MessageHistoryTab.tsx**
**Errors**:
- Line 19: `Property 'messages' does not exist on type 'GraphState'`
- Line 20: `Property 'agents' does not exist on type 'GraphState'`
- Line 32: `Parameter 'message' implicitly has an 'any' type`

**OLD Code Pattern**:
```typescript
const messages = useGraphStore((state) => state.messages);
const agents = useGraphStore((state) => state.agents);
```

**NEW Approach**: Read artifact nodes from `state.nodes`, filter by type

**Complexity**: MEDIUM - Need to filter and sort artifact nodes

---

#### 1.3 **RunStatusTab.tsx**
**Errors**:
- Line 24: `Property 'runs' does not exist on type 'GraphState'`
- Line 34: `Parameter 'run' implicitly has an 'any' type`

**OLD Code Pattern**:
```typescript
const runs = useGraphStore((state) => state.runs);
```

**NEW Approach**: Run data should come from GraphNode metadata or separate API call

**Complexity**: HIGH - Need to define how run status data flows in Phase 2 architecture

---

#### 1.4 **GraphCanvas.tsx**
**Errors**:
- Line 41: `Property 'agents' does not exist on type 'GraphState'`
- Line 42: `Property 'messages' does not exist on type 'GraphState'`
- Line 43: `Property 'runs' does not exist on type 'GraphState'`

**OLD Code Pattern**:
```typescript
const agents = useGraphStore((state) => state.agents);
const messages = useGraphStore((state) => state.messages);
const runs = useGraphStore((state) => state.runs);
```

**NEW Approach**: These are likely unused debug/logging variables - DELETE

**Complexity**: LOW - Just remove unused references

---

#### 1.5 **DashboardLayout.tsx**
**Errors**:
- Line 43: `Property 'agents' does not exist on type 'GraphState'`
- Line 53: `Parameter 'agent' implicitly has an 'any' type`
- Line 69: `Object literal may only specify known properties, and 'agents' does not exist`

**OLD Code Pattern**:
```typescript
const agents = useGraphStore((state) => state.agents);
```

**NEW Approach**: Read agent nodes from `state.nodes`, filter by type

**Complexity**: MEDIUM - Need to filter agent nodes for agent list

---

#### 1.6 **useModules.ts**
**Errors**:
- Line 37: `Property 'agents' does not exist on type 'GraphState'`
- Line 38: `Property 'messages' does not exist on type 'GraphState'`

**OLD Code Pattern**:
```typescript
const agents = useGraphStore.getState().agents;
const messages = useGraphStore.getState().messages;
```

**NEW Approach**: Read from `nodes` array, filter by type

**Complexity**: MEDIUM - Hook for module system, needs careful refactoring

---

### **Category 2: Services Using Removed Methods** (HIGH PRIORITY - 1 file, ~7 errors)

#### 2.1 **websocket.ts**
**Errors**:
- Line 4: `'useUIStore' is declared but its value is never read`
- Line 37: `'store' is declared but its value is never read`
- Line 47: `Property 'addAgent' does not exist`
- Line 48: `Property 'updateAgent' does not exist`
- Line 49: `Property 'addMessage' does not exist`
- Line 50: `Property 'updateMessage' does not exist`
- Line 51: `Property 'batchUpdate' does not exist`

**OLD Code Pattern**:
```typescript
addAgent(agent);
updateAgent(agentId, update);
addMessage(message);
updateMessage(messageId, update);
batchUpdate({ agents, messages });
```

**NEW Approach**: WebSocket should trigger `refreshCurrentView()` to fetch updated snapshot from backend

**Complexity**: HIGH - Critical integration point, need to define WebSocket → backend snapshot refresh flow

**Migration Strategy**:
- WebSocket receives events → triggers `useGraphStore.getState().refreshCurrentView()`
- Backend includes latest changes in snapshot response
- No more client-side mutations via WebSocket

---

### **Category 3: Type Imports for Removed Types** (MEDIUM PRIORITY - 7 files, ~10 errors)

These files import OLD Phase 1 types that were removed.

#### 3.1 **AgentNode.tsx + AgentNode.test.tsx**
**Errors**:
- `Module '"../../types/graph"' has no exported member 'AgentNodeData'`
- Line 22: `Parameter 'type' implicitly has an 'any' type`
- Line 29: `Parameter 'type' implicitly has an 'any' type`
- Line 49: `Type 'unknown' is not assignable to type 'number'`

**OLD Import**: `import { AgentNodeData } from '../../types/graph'`

**NEW Approach**: Use `GraphNode` type, extract agent-specific data from `metadata`

**Complexity**: MEDIUM - Need to define agent node metadata structure

---

#### 3.2 **MessageNode.tsx + MessageNode.test.tsx**
**Errors**:
- `Module '"../../types/graph"' has no exported member 'MessageNodeData'`

**OLD Import**: `import { MessageNodeData } from '../../types/graph'`

**NEW Approach**: Use `GraphNode` type, extract artifact-specific data from `metadata`

**Complexity**: MEDIUM - Need to define artifact node metadata structure

---

#### 3.3 **EventLogModule.tsx + EventLogModule.test.tsx**
**Errors**:
- `Module '"../../types/graph"' has no exported member 'Agent'`

**OLD Import**: `import { Agent } from '../../types/graph'`

**NEW Approach**: Use `GraphNode` type or define NEW Agent interface in backend contract

**Complexity**: MEDIUM - EventLog module needs agent metadata

---

#### 3.4 **ModuleRegistry.ts**
**Errors**:
- `Module '"../../types/graph"' has no exported member 'Agent'`

**OLD Import**: `import { Agent } from '../../types/graph'`

**NEW Approach**: Update module context to use GraphNode or backend Agent type

**Complexity**: LOW - Type import only

---

#### 3.5 **api.ts**
**Errors**:
- `Namespace '"C:/workspace/whiteduck/flock/src/flock/frontend/src/types/graph"' has no exported member 'Agent'`

**OLD Import**: Uses `graph.Agent` namespace

**NEW Approach**: Import Agent type from backend contract or remove if unused

**Complexity**: LOW - Type reference only

---

#### 3.6 **mockData.ts**
**Errors**:
- `Module '"../types/graph"' has no exported member 'Agent'`

**OLD Import**: `import { Agent } from '../types/graph'`

**NEW Approach**: Update mock data to use GraphNode format

**Complexity**: LOW - Test utility, update mock structure

---

### **Category 4: graphStore Type Mismatches** (MEDIUM PRIORITY - 2 files, ~7 errors)

#### 4.1 **graphStore.ts**
**Errors**:
- Line 138: `Type 'TimeRange' is not assignable to type 'TimeRangeFilter'` (number vs string)
- Lines 183, 226: `Type 'GraphEdge[]' is not assignable to type 'Edge[]'` (markerEnd type)
- Lines 194, 237: `Type 'ArtifactSummary' is not assignable to parameter of type 'FilterFacets'`

**Issues**:
1. **TimeRange mismatch**: filterStore uses `TimeRange` (number timestamps), backend expects `TimeRangeFilter` (ISO string timestamps)
2. **GraphEdge mismatch**: Backend `GraphEdge.markerEnd` type doesn't match React Flow `Edge` type
3. **ArtifactSummary mismatch**: Can't pass `ArtifactSummary` directly to `updateAvailableFacets()` (expects `FilterFacets`)

**NEW Approach**:
1. Convert TimeRange to TimeRangeFilter when building backend request
2. Fix GraphEdge markerEnd type to match React Flow expectations
3. Transform ArtifactSummary to FilterFacets format (already done in App.tsx, replicate here)

**Complexity**: MEDIUM - Type alignment issues with backend contract

---

#### 4.2 **graphStore.test.ts**
**Errors**:
- Line 377: `'mockSavedPositions' is declared but its value is never read`
- Line 416: `Object is possibly 'undefined'`
- Line 529: Argument type mismatch (OLD Message format)
- Line 541: `'artifact_type' does not exist in type 'Message'`
- Line 550: `Object is possibly 'undefined'`

**Issues**: Test data using OLD Phase 1 format

**NEW Approach**: Update test data to match NEW GraphNode/Message formats

**Complexity**: LOW - Test data updates

---

### **Category 5: Test Utility Issues** (LOW PRIORITY - 1 file, ~26 errors)

#### 5.1 **graphService.test.ts**
**Errors**: 26 "Object is possibly 'undefined'" errors across multiple test cases

**Issues**: Tests not handling undefined responses from graph service

**NEW Approach**: Add null checks or use non-null assertions in tests

**Complexity**: LOW - Test robustness improvements

---

## Phase 4.1 Implementation Plan

### **Step 1: Fix graphStore Type Mismatches** (FOUNDATION)
**Priority**: HIGH - Blocks everything else
**Files**: `graphStore.ts`

**Tasks**:
- [ ] Fix TimeRange → TimeRangeFilter conversion in `buildGraphRequest()`
- [ ] Fix GraphEdge markerEnd type compatibility
- [ ] Transform ArtifactSummary to FilterFacets before calling `updateAvailableFacets()`

**Estimated Lines**: ~20 lines changed

---

### **Step 2: Fix WebSocket Integration** (CRITICAL PATH)
**Priority**: HIGH - Core data flow
**Files**: `websocket.ts`

**Tasks**:
- [ ] Remove OLD method calls (`addAgent`, `updateAgent`, `addMessage`, etc.)
- [ ] Implement NEW approach: WebSocket events → `refreshCurrentView()`
- [ ] Remove unused imports (`useUIStore`, `store`)

**Estimated Lines**: ~30 lines changed

---

### **Step 3: Define Node Metadata Structure** (FOUNDATION)
**Priority**: HIGH - Required for components
**Files**: `types/graph.ts` (or create new types file)

**Tasks**:
- [ ] Define `AgentNodeMetadata` interface
- [ ] Define `ArtifactNodeMetadata` interface
- [ ] Document metadata extraction from GraphNode

**Estimated Lines**: ~40 lines added

---

### **Step 4: Fix Graph Components** (USER-FACING)
**Priority**: HIGH
**Files**: `GraphCanvas.tsx`, `AgentNode.tsx`, `MessageNode.tsx`

**Tasks**:
- [ ] GraphCanvas: Remove unused `agents`, `messages`, `runs` references
- [ ] AgentNode: Use GraphNode type, extract metadata
- [ ] MessageNode: Use GraphNode type, extract metadata
- [ ] Update tests for both node components

**Estimated Lines**: ~60 lines changed

---

### **Step 5: Fix Detail Panel Components** (USER-FACING)
**Priority**: MEDIUM
**Files**: `DetailWindowContainer.tsx`, `MessageHistoryTab.tsx`, `RunStatusTab.tsx`

**Tasks**:
- [ ] DetailWindowContainer: Read from `nodes` array instead of Maps
- [ ] MessageHistoryTab: Filter artifact nodes from `nodes` array
- [ ] RunStatusTab: Define run status data source (backend or metadata)

**Estimated Lines**: ~80 lines changed

---

### **Step 6: Fix Layout and Hooks** (SUPPORTING)
**Priority**: MEDIUM
**Files**: `DashboardLayout.tsx`, `useModules.ts`

**Tasks**:
- [ ] DashboardLayout: Read agent nodes from `nodes` array
- [ ] useModules: Read from `nodes` array instead of Maps

**Estimated Lines**: ~40 lines changed

---

### **Step 7: Fix Module and Type Imports** (CLEANUP)
**Priority**: LOW
**Files**: `EventLogModule.tsx`, `ModuleRegistry.ts`, `api.ts`, `mockData.ts`

**Tasks**:
- [ ] EventLogModule: Use GraphNode or backend Agent type
- [ ] ModuleRegistry: Update Agent type import
- [ ] api.ts: Fix Agent namespace import
- [ ] mockData.ts: Update mock data to GraphNode format

**Estimated Lines**: ~30 lines changed

---

### **Step 8: Fix Test Files** (QUALITY)
**Priority**: LOW
**Files**: `graphStore.test.ts`, `graphService.test.ts`, component test files

**Tasks**:
- [ ] graphStore.test.ts: Update test data to NEW formats
- [ ] graphService.test.ts: Add null checks for undefined objects
- [ ] Component tests: Update to match NEW implementations

**Estimated Lines**: ~50 lines changed

---

## Success Criteria

✅ **Build passes**: `npm run build` completes with 0 errors
✅ **Tests pass**: All 311+ tests still passing
✅ **Types align**: All components use NEW Phase 2 GraphNode/GraphEdge types
✅ **WebSocket works**: Real-time updates trigger backend snapshot refresh
✅ **UI functional**: All components render correctly with NEW data structure

---

## Estimated Effort

- **Total Lines Changed**: ~350 lines
- **Total Files Changed**: 20 files
- **Complexity**: HIGH (core architecture changes + WebSocket integration)
- **Dependencies**: Backend contract must define GraphNode metadata structure

---

## Risk Assessment

🔴 **HIGH RISK**:
- WebSocket integration (critical data flow, impacts real-time updates)
- Node metadata structure (affects ALL components)
- Type mismatches with backend contract

🟡 **MEDIUM RISK**:
- Detail panel components (user-facing, complex filtering logic)
- Run status data flow (unclear source in Phase 2 architecture)

🟢 **LOW RISK**:
- Type imports (straightforward replacements)
- Test file updates (isolated changes)

---

## Phase 4.1 Execution Strategy

### **Approach**: Incremental fixes with continuous validation

1. **Foundation First**: Fix graphStore types + define metadata structure
2. **Critical Path**: Fix WebSocket integration
3. **Component Migration**: Fix components in order of user impact
4. **Test Cleanup**: Fix test files last

### **Validation After Each Step**:
- Run `npm run build` to check for new/remaining errors
- Run `npm test` to ensure no test regressions
- Commit working increments

### **Rollback Strategy**:
- Each step should be independently committable
- If blocked, document blocker and move to next step
- Return to blocked items after dependencies resolved

---

## Notes

- **Phase 4 is NOT complete until this build passes**
- Some fixes may require backend contract updates (GraphNode metadata)
- WebSocket integration is the most critical and complex change
- Run status data flow needs architectural decision

---

**Created**: 2025-10-11
**Status**: 🔴 READY TO START
**Target**: Complete before Phase 5 (Integration Tests Rewrite)
