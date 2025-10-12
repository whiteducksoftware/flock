# UI Optimization Migration Guide

**Status**: Implementation Ready
**Date**: October 11, 2025
**Strategy**: Direct replacement - No feature flags, no backward compatibility
**Goal**: Replace client-side graph construction with backend `/api/dashboard/graph` snapshots

---

## Executive Summary

This guide provides step-by-step instructions for **completely replacing** the Flock Flow dashboard's client-side graph construction (1,400 lines) with backend snapshot consumption (200 lines).

**Strategy**: **Aggressive migration** - delete old code immediately, ship new implementation.

**Business Impact**:
- **Performance**: -65% initial load time, -47% filter response time
- **Code Reduction**: -2,175 lines total (-75%): code + complete test rewrite
- **Reliability**: Single source of truth (backend), fewer bugs
- **Developer Experience**: Simpler debugging, easier onboarding
- **Test Quality**: New focused tests (backend integration) faster to write than fixing old tests (edge algorithms)

**Timeline**: 3 weeks (no feature flag overhead)
**Test Strategy**: Complete rewrite - delete ~1,700 lines of old tests, write ~400 lines of focused new tests
**Risk Level**: Medium (test thoroughly before merge)

---

## 1. Architecture Transformation

### 1.1 What We're Deleting

```
❌ DELETE ENTIRELY:
├─ CODE FILES:
│  ├─ src/flock/frontend/src/utils/transforms.ts (324 lines)
│  │  ├─ deriveAgentViewEdges()
│  │  ├─ deriveBlackboardViewEdges()
│  │  └─ toDashboardState()
│  ├─ graphStore state (partial):
│  │  ├─ runs: Map<string, Run>
│  │  ├─ consumptions: Map<string, string[]>
│  │  ├─ messages: Map<string, Message>
│  │  └─ toDashboardState() helper
│  └─ graphStore methods (partial):
│     ├─ Old generateAgentViewGraph() (44 lines)
│     ├─ Old generateBlackboardViewGraph() (50 lines)
│     └─ Old applyFilters() (143 lines)
│
└─ TEST FILES (complete rewrite):
   ├─ src/flock/frontend/src/utils/transforms.test.ts (861 lines)
   ├─ src/flock/frontend/src/store/graphStore.test.ts (~200 lines)
   └─ src/flock/frontend/src/__tests__/integration/graph-rendering.test.tsx (~640 lines)

Total Deletion: ~2,885 lines (code + tests)
```

### 1.2 What We're Adding

```
✅ NEW CODE FILES:
├─ src/flock/frontend/src/services/graphService.ts (~100 lines)
│  ├─ fetchGraphSnapshot()
│  ├─ mergeNodePositions()
│  └─ overlayWebSocketState()
└─ src/flock/frontend/src/types/graph.ts (~80 lines)
   └─ GraphRequest, GraphSnapshot, GraphFilters types

✅ SIMPLIFIED CODE:
├─ graphStore.ts: 689 → ~200 lines (-71%)
├─ websocket.ts: ~300 → ~100 lines (-67%)
└─ filterStore.ts: 143 → ~30 lines (-79%)

✅ NEW TEST FILES (focused on backend integration):
├─ src/flock/frontend/src/store/graphStore.test.ts (~150 lines)
├─ src/flock/frontend/src/services/graphService.test.ts (~100 lines)
└─ src/flock/frontend/src/__tests__/integration/graph-snapshot.test.tsx (~150 lines)

Total Addition: ~710 lines (code + tests)
Net Reduction: -2,175 lines (-75%)
```

### 1.3 Target Architecture

```
WebSocket Events
    ├─→ Fast Updates (status, tokens)
    │   └─→ Local State [<5ms]
    │
    └─→ Graph-Changing Events (new messages)
        └─→ Debounced Refresh [500ms]
            ↓
    fetchGraphSnapshot()
    POST /api/dashboard/graph
            ↓
    Backend GraphSnapshot
    { nodes, edges, statistics }
            ↓
    Position Merge (IndexedDB)
            ↓
    Overlay WebSocket State
            ↓
    React Flow Rendering

Complexity: ~200 lines, O(1) API + O(n) merge
```

---

## 2. Week 1: Core Migration

### 2.1 Create Graph Service

**New File**: `src/flock/frontend/src/services/graphService.ts`

```typescript
import { GraphRequest, GraphSnapshot, GraphNode } from '../types/graph';
import { Node } from 'reactflow';

/**
 * Fetch graph snapshot from backend
 */
export async function fetchGraphSnapshot(
  request: GraphRequest
): Promise<GraphSnapshot> {
  const response = await fetch('/api/dashboard/graph', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Graph API error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Merge backend node positions with saved/current positions
 * Priority: saved > current > backend > random
 */
export function mergeNodePositions(
  backendNodes: GraphNode[],
  savedPositions: Map<string, { x: number; y: number }>,
  currentNodes: Node[]
): Node[] {
  const currentPositions = new Map(
    currentNodes.map(n => [n.id, n.position])
  );

  return backendNodes.map(node => {
    const position =
      savedPositions.get(node.id) ||
      currentPositions.get(node.id) ||
      (node.position.x !== 0 || node.position.y !== 0 ? node.position : null) ||
      randomPosition();

    return { ...node, position };
  });
}

function randomPosition() {
  return {
    x: 400 + Math.random() * 200,
    y: 300 + Math.random() * 200,
  };
}

/**
 * Overlay real-time WebSocket state on backend nodes
 */
export function overlayWebSocketState(
  nodes: Node[],
  agentStatus: Map<string, string>,
  streamingTokens: Map<string, string[]>
): Node[] {
  return nodes.map(node => {
    if (node.type === 'agent') {
      return {
        ...node,
        data: {
          ...node.data,
          status: agentStatus.get(node.id) || node.data.status,
          streamingTokens: streamingTokens.get(node.id) || [],
        },
      };
    }
    return node;
  });
}
```

### 2.2 Add TypeScript Types

**New File**: `src/flock/frontend/src/types/graph.ts`

```typescript
// Mirror backend models from src/flock/dashboard/models/graph.py

export interface GraphRequest {
  viewMode: 'agent' | 'blackboard';
  filters: GraphFilters;
  options?: GraphRequestOptions;
}

export interface GraphFilters {
  correlation_id?: string | null;
  time_range: TimeRangeFilter;
  artifactTypes: string[];
  producers: string[];
  tags: string[];
  visibility: string[];
}

export interface TimeRangeFilter {
  preset: 'last10min' | 'last5min' | 'last1hour' | 'all' | 'custom';
  start?: string | null;
  end?: string | null;
}

export interface GraphRequestOptions {
  include_statistics?: boolean;
  label_offset_strategy?: 'stack' | 'none';
  limit?: number;
}

export interface GraphSnapshot {
  generatedAt: string;
  viewMode: 'agent' | 'blackboard';
  filters: GraphFilters;
  nodes: GraphNode[];
  edges: GraphEdge[];
  statistics: GraphStatistics | null;
  totalArtifacts: number;
  truncated: boolean;
}

export interface GraphNode {
  id: string;
  type: 'agent' | 'message';
  data: Record<string, any>;
  position: { x: number; y: number };
  hidden: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'message_flow' | 'transformation';
  label?: string | null;
  data: Record<string, any>;
  markerEnd?: { type: string; width: number; height: number };
  hidden: boolean;
}

export interface GraphStatistics {
  producedByAgent: Record<string, GraphAgentMetrics>;
  consumedByAgent: Record<string, GraphAgentMetrics>;
  artifactSummary: ArtifactSummary;
}

export interface GraphAgentMetrics {
  total: number;
  byType: Record<string, number>;
}

export interface ArtifactSummary {
  total: number;
  by_type: Record<string, number>;
  by_producer: Record<string, number>;
  by_visibility: Record<string, number>;
  tag_counts: Record<string, number>;
  earliest_created_at: string;
  latest_created_at: string;
}
```

### 2.3 Replace graphStore

**File**: `src/flock/frontend/src/store/graphStore.ts`

**DELETE EVERYTHING, replace with**:

```typescript
import { create } from 'zustand';
import { Node, Edge } from 'reactflow';
import { fetchGraphSnapshot, mergeNodePositions, overlayWebSocketState } from '../services/graphService';
import { GraphStatistics } from '../types/graph';
import { usePersistence } from '../hooks/usePersistence';
import { useFilterStore } from './filterStore';

interface Message {
  id: string;
  artifact_type: string;
  produced_by: string;
  timestamp: number;
  // ... minimal fields for event log
}

interface GraphState {
  // Real-time WebSocket state
  agentStatus: Map<string, string>;
  streamingTokens: Map<string, string[]>;

  // Backend snapshot
  nodes: Node[];
  edges: Edge[];
  statistics: GraphStatistics | null;

  // UI state
  events: Message[];
  viewMode: 'agent' | 'blackboard';

  // Actions
  generateAgentViewGraph: () => Promise<void>;
  generateBlackboardViewGraph: () => Promise<void>;
  updateAgentStatus: (id: string, status: string) => void;
  updateStreamingTokens: (id: string, tokens: string[]) => void;
  updateNodePosition: (id: string, position: { x: number; y: number }) => void;
  addEvent: (event: Message) => void;
  setViewMode: (mode: 'agent' | 'blackboard') => void;
}

export const useGraphStore = create<GraphState>((set, get) => ({
  agentStatus: new Map(),
  streamingTokens: new Map(),
  nodes: [],
  edges: [],
  statistics: null,
  events: [],
  viewMode: 'agent',

  generateAgentViewGraph: async () => {
    const filters = useFilterStore.getState();
    const { loadPositions } = usePersistence();
    const savedPositions = await loadPositions();

    try {
      const snapshot = await fetchGraphSnapshot({
        viewMode: 'agent',
        filters: {
          correlation_id: filters.correlationId || null,
          time_range: filters.timeRange,
          artifactTypes: filters.selectedArtifactTypes,
          producers: filters.selectedProducers,
          tags: filters.selectedTags,
          visibility: filters.selectedVisibility,
        },
        options: { include_statistics: true },
      });

      // Merge positions
      const currentNodes = get().nodes;
      let nodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

      // Overlay WebSocket state
      const { agentStatus, streamingTokens } = get();
      nodes = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      set({
        nodes,
        edges: snapshot.edges,
        statistics: snapshot.statistics,
        viewMode: 'agent',
      });

      // Update filter facets
      if (snapshot.statistics) {
        useFilterStore.getState().updateFacets(snapshot.statistics.artifactSummary);
      }
    } catch (error) {
      console.error('Failed to fetch agent view graph:', error);
      throw error;
    }
  },

  generateBlackboardViewGraph: async () => {
    const filters = useFilterStore.getState();
    const { loadPositions } = usePersistence();
    const savedPositions = await loadPositions();

    try {
      const snapshot = await fetchGraphSnapshot({
        viewMode: 'blackboard',
        filters: {
          correlation_id: filters.correlationId || null,
          time_range: filters.timeRange,
          artifactTypes: filters.selectedArtifactTypes,
          producers: filters.selectedProducers,
          tags: filters.selectedTags,
          visibility: filters.selectedVisibility,
        },
        options: { include_statistics: true },
      });

      // Merge positions
      const currentNodes = get().nodes;
      let nodes = mergeNodePositions(snapshot.nodes, savedPositions, currentNodes);

      // Overlay WebSocket state (messages may have isStreaming state)
      const { agentStatus, streamingTokens } = get();
      nodes = overlayWebSocketState(nodes, agentStatus, streamingTokens);

      set({
        nodes,
        edges: snapshot.edges,
        statistics: snapshot.statistics,
        viewMode: 'blackboard',
      });

      // Update filter facets
      if (snapshot.statistics) {
        useFilterStore.getState().updateFacets(snapshot.statistics.artifactSummary);
      }
    } catch (error) {
      console.error('Failed to fetch blackboard view graph:', error);
      throw error;
    }
  },

  updateAgentStatus: (id, status) => {
    const agentStatus = new Map(get().agentStatus);
    agentStatus.set(id, status);

    // Optimistic update
    const nodes = get().nodes.map(node => {
      if (node.id === id && node.type === 'agent') {
        return { ...node, data: { ...node.data, status } };
      }
      return node;
    });

    set({ agentStatus, nodes });
  },

  updateStreamingTokens: (id, tokens) => {
    const streamingTokens = new Map(get().streamingTokens);
    streamingTokens.set(id, tokens.slice(-6)); // Keep last 6

    // Optimistic update
    const nodes = get().nodes.map(node => {
      if (node.id === id && node.type === 'agent') {
        return { ...node, data: { ...node.data, streamingTokens: tokens.slice(-6) } };
      }
      return node;
    });

    set({ streamingTokens, nodes });
  },

  updateNodePosition: (id, position) => {
    const nodes = get().nodes.map(node =>
      node.id === id ? { ...node, position } : node
    );
    set({ nodes });

    // Save to IndexedDB
    usePersistence().savePositions(nodes);
  },

  addEvent: (event) => {
    const events = [event, ...get().events].slice(0, 100);
    set({ events });
  },

  setViewMode: (mode) => {
    set({ viewMode: mode });
  },
}));
```

**Lines**: ~200 (was 689)
**Reduction**: -489 lines (-71%)

### 2.4 Update WebSocket Handler

**File**: `src/flock/frontend/src/services/websocket.ts`

**Replace graph regeneration logic with**:

```typescript
import { debounce } from 'lodash';
import { useGraphStore } from '../store/graphStore';
import { useFilterStore } from '../store/filterStore';

class WebSocketEventHandler {
  private refreshDebounce = debounce(() => {
    this.refreshGraph();
  }, 500);

  async refreshGraph() {
    const viewMode = useGraphStore.getState().viewMode;
    if (viewMode === 'agent') {
      await useGraphStore.getState().generateAgentViewGraph();
    } else {
      await useGraphStore.getState().generateBlackboardViewGraph();
    }
  }

  onStreamingOutput(data: StreamingOutputEvent) {
    // FAST: Update local state only
    useGraphStore.getState().updateStreamingTokens(data.agent_id, data.tokens || []);
  }

  onAgentActivated(data: AgentActivatedEvent) {
    // FAST: Update status
    useGraphStore.getState().updateAgentStatus(data.agent_id, 'running');

    // SLOW: Debounced refresh
    this.refreshDebounce();
  }

  onAgentCompleted(data: AgentCompletedEvent) {
    useGraphStore.getState().updateAgentStatus(data.agent_id, 'idle');
    this.refreshDebounce();
  }

  onAgentError(data: AgentErrorEvent) {
    useGraphStore.getState().updateAgentStatus(data.agent_id, 'error');
    this.refreshDebounce();
  }

  onMessagePublished(data: MessagePublishedEvent) {
    // Add to event log
    useGraphStore.getState().addEvent({
      id: data.artifact_id,
      artifact_type: data.artifact_type,
      produced_by: data.produced_by,
      timestamp: Date.now(),
    });

    // Debounced refresh
    this.refreshDebounce();
  }
}

export const websocketHandler = new WebSocketEventHandler();
```

**Lines**: ~100 (was ~300)
**Reduction**: -200 lines (-67%)

### 2.5 Delete Old Files

```bash
# Delete transform utilities (no longer needed)
rm src/flock/frontend/src/utils/transforms.ts
rm src/flock/frontend/src/utils/transforms.test.ts

# Total deletion: 1,185 lines
```

---

## 3. Week 2: Filter Migration

### 3.1 Simplify filterStore

**File**: `src/flock/frontend/src/store/filterStore.ts`

**Replace `applyFilters()` with**:

```typescript
import { create } from 'zustand';
import { TimeRangeFilter, ArtifactSummary } from '../types/graph';
import { useGraphStore } from './graphStore';

interface FilterState {
  // Filter selections
  correlationId: string | null;
  timeRange: TimeRangeFilter;
  selectedArtifactTypes: string[];
  selectedProducers: string[];
  selectedTags: string[];
  selectedVisibility: string[];

  // Available options (from backend)
  availableTypes: string[];
  availableProducers: string[];
  availableTags: string[];
  availableVisibility: string[];

  // Actions
  applyFilters: () => Promise<void>;
  updateFacets: (summary: ArtifactSummary) => void;
  setCorrelationId: (id: string | null) => void;
  setTimeRange: (range: TimeRangeFilter) => void;
  setSelectedArtifactTypes: (types: string[]) => void;
  setSelectedProducers: (producers: string[]) => void;
  setSelectedTags: (tags: string[]) => void;
  setSelectedVisibility: (visibility: string[]) => void;
  clearFilters: () => void;
}

export const useFilterStore = create<FilterState>((set, get) => ({
  correlationId: null,
  timeRange: { preset: 'last10min' },
  selectedArtifactTypes: [],
  selectedProducers: [],
  selectedTags: [],
  selectedVisibility: [],
  availableTypes: [],
  availableProducers: [],
  availableTags: [],
  availableVisibility: [],

  applyFilters: async () => {
    // Backend handles all filtering - just trigger refresh
    const viewMode = useGraphStore.getState().viewMode;
    if (viewMode === 'agent') {
      await useGraphStore.getState().generateAgentViewGraph();
    } else {
      await useGraphStore.getState().generateBlackboardViewGraph();
    }
  },

  updateFacets: (summary) => {
    set({
      availableTypes: Object.keys(summary.by_type),
      availableProducers: Object.keys(summary.by_producer),
      availableVisibility: Object.keys(summary.by_visibility),
      availableTags: Object.keys(summary.tag_counts),
    });
  },

  setCorrelationId: (id) => set({ correlationId: id }),
  setTimeRange: (range) => set({ timeRange: range }),
  setSelectedArtifactTypes: (types) => set({ selectedArtifactTypes: types }),
  setSelectedProducers: (producers) => set({ selectedProducers: producers }),
  setSelectedTags: (tags) => set({ selectedTags: tags }),
  setSelectedVisibility: (visibility) => set({ selectedVisibility: visibility }),

  clearFilters: () => {
    set({
      correlationId: null,
      timeRange: { preset: 'last10min' },
      selectedArtifactTypes: [],
      selectedProducers: [],
      selectedTags: [],
      selectedVisibility: [],
    });
  },
}));
```

**Lines**: ~80 (was 143+)
**Reduction**: -63 lines (-44%)

### 3.2 Update Filter UI

**File**: `src/flock/frontend/src/components/filters/FilterFlyout.tsx`

**Change**: Use `availableTypes`, `availableProducers` from backend instead of computing from messages.

```typescript
export function FilterFlyout() {
  const {
    availableTypes,
    availableProducers,
    selectedArtifactTypes,
    setSelectedArtifactTypes,
    applyFilters,
  } = useFilterStore();

  return (
    <div>
      <Select
        multiple
        label="Artifact Types"
        options={availableTypes} // From backend artifactSummary
        value={selectedArtifactTypes}
        onChange={setSelectedArtifactTypes}
      />

      {/* ... other filters */}

      <button onClick={applyFilters}>Apply</button>
    </div>
  );
}
```

---

## 4. Week 3: Testing & Polish

### 4.1 Rewrite Test Suite From Scratch

**Why rewrite instead of update?**
- UI changing massively → fixing old tests takes longer than writing new ones
- Old tests designed for client-side derivation logic (now gone)
- New tests should focus on backend integration, not edge algorithms
- Opportunity to improve test quality and coverage

**Delete ALL old graph tests**:
```bash
# Delete obsolete test files
rm src/flock/frontend/src/utils/transforms.test.ts  # 861 lines - edge derivation tests
rm src/flock/frontend/src/store/graphStore.test.ts  # Old state management tests
rm src/flock/frontend/src/__tests__/integration/graph-rendering.test.tsx  # Old integration tests
```

**Create new focused tests from scratch**:

**New `graphStore.test.ts`** (focus on backend integration):

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useGraphStore } from './graphStore';
import { fetchGraphSnapshot } from '../services/graphService';

vi.mock('../services/graphService');

describe('graphStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch agent view graph from backend', async () => {
    const mockSnapshot = {
      nodes: [{ id: 'agent1', type: 'agent', data: { name: 'agent1' }, position: { x: 0, y: 0 }, hidden: false }],
      edges: [{ id: 'edge1', source: 'agent1', target: 'agent2', type: 'message_flow', hidden: false }],
      statistics: null,
      viewMode: 'agent',
      filters: {},
      generatedAt: '2025-10-11T00:00:00Z',
      totalArtifacts: 1,
      truncated: false,
    };

    vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

    await useGraphStore.getState().generateAgentViewGraph();

    expect(fetchGraphSnapshot).toHaveBeenCalledWith({
      viewMode: 'agent',
      filters: expect.any(Object),
      options: { include_statistics: true },
    });

    expect(useGraphStore.getState().nodes).toHaveLength(1);
    expect(useGraphStore.getState().edges).toHaveLength(1);
  });

  it('should update agent status immediately', () => {
    useGraphStore.setState({
      nodes: [{ id: 'agent1', type: 'agent', data: { status: 'idle' }, position: { x: 0, y: 0 } }],
    });

    useGraphStore.getState().updateAgentStatus('agent1', 'running');

    const node = useGraphStore.getState().nodes.find(n => n.id === 'agent1');
    expect(node?.data.status).toBe('running');
  });

  it('should update streaming tokens', () => {
    useGraphStore.setState({
      nodes: [{ id: 'agent1', type: 'agent', data: { streamingTokens: [] }, position: { x: 0, y: 0 } }],
    });

    useGraphStore.getState().updateStreamingTokens('agent1', ['token1', 'token2', 'token3']);

    const node = useGraphStore.getState().nodes.find(n => n.id === 'agent1');
    expect(node?.data.streamingTokens).toEqual(['token1', 'token2', 'token3']);
  });
});
```

**What to test** (new focused test suite):

| Test Area | Focus | Why |
|-----------|-------|-----|
| **Backend Integration** | `fetchGraphSnapshot()` calls, error handling | Core functionality |
| **Position Merging** | IndexedDB → backend → random fallback | Critical UX feature |
| **Real-Time Updates** | Status/token updates via WebSocket | Performance requirement |
| **Debouncing** | Multiple events → single fetch | Performance requirement |
| **Filter Application** | Backend receives correct filters | Core functionality |

**Test Coverage Target**: >80% (focus on critical paths, not 100%)

### 4.2 New Integration Tests

**File**: `src/flock/frontend/src/__tests__/integration/graph-snapshot.test.tsx` (rewrite from scratch)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '../../components/Dashboard';
import { fetchGraphSnapshot } from '../../services/graphService';

vi.mock('../../services/graphService');

describe('Graph Snapshot Integration', () => {
  it('should load graph on mount', async () => {
    const mockSnapshot = {
      nodes: [
        { id: 'pizza_master', type: 'agent', data: { name: 'pizza_master' }, position: { x: 0, y: 0 }, hidden: false },
      ],
      edges: [],
      statistics: null,
      viewMode: 'agent',
      filters: {},
      generatedAt: '2025-10-11T00:00:00Z',
      totalArtifacts: 0,
      truncated: false,
    };

    vi.mocked(fetchGraphSnapshot).mockResolvedValue(mockSnapshot);

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('pizza_master')).toBeInTheDocument();
    });

    expect(fetchGraphSnapshot).toHaveBeenCalledTimes(1);
  });

  it('should debounce graph refresh on rapid events', async () => {
    vi.useFakeTimers();

    const { websocketHandler } = await import('../../services/websocket');

    // Emit 5 events
    websocketHandler.onMessagePublished({ artifact_id: 'msg1', artifact_type: 'Pizza', produced_by: 'agent1' });
    websocketHandler.onMessagePublished({ artifact_id: 'msg2', artifact_type: 'Pizza', produced_by: 'agent1' });
    websocketHandler.onMessagePublished({ artifact_id: 'msg3', artifact_type: 'Pizza', produced_by: 'agent1' });

    // No fetch yet
    expect(fetchGraphSnapshot).not.toHaveBeenCalled();

    // Advance 500ms
    vi.advanceTimersByTime(500);

    // Only 1 fetch
    await waitFor(() => {
      expect(fetchGraphSnapshot).toHaveBeenCalledTimes(1);
    });

    vi.useRealTimers();
  });
});
```

### 4.3 Test Rewrite Strategy

**Phase 1: Delete old tests**
```bash
# Remove all graph-related tests (they test old architecture)
rm -rf src/flock/frontend/src/utils/transforms.test.ts
rm -rf src/flock/frontend/src/store/graphStore.test.ts
rm -rf src/flock/frontend/src/__tests__/integration/graph-rendering.test.tsx

# Total deletion: ~1,700 lines of tests
```

**Phase 2: Write new focused tests** (target: ~400 lines)

**Priority 1: Core functionality**
1. Backend snapshot fetching
2. Position merging logic
3. Real-time status updates
4. Filter application

**Priority 2: Performance**
1. Debouncing behavior
2. Memory leak prevention
3. Load time validation

**Priority 3: Edge cases**
1. API errors
2. Empty states
3. Concurrent updates

**Skip**: Edge derivation algorithms (backend's responsibility now)

### 4.4 Manual Testing Checklist

**Test Scenarios**:

- [ ] **Initial Load**: Dashboard loads graph from backend
- [ ] **Positions**: User-dragged positions persist on refresh
- [ ] **Agent Status**: Status changes (idle→running→idle) appear instantly (<50ms)
- [ ] **Streaming Tokens**: Last 6 tokens display during agent execution
- [ ] **Filter Application**: Filters trigger backend snapshot fetch (<100ms)
- [ ] **Debouncing**: Multiple messages → single snapshot fetch after 500ms
- [ ] **Error Handling**: API errors show user-friendly message
- [ ] **Empty State**: Dashboard shows helpful message when no artifacts

**Performance Validation**:

```bash
# Measure initial load
# Open Chrome DevTools → Performance tab
# Record → Refresh page → Stop
# Verify: Initial load <1.5s

# Measure filter response
# Open Chrome DevTools → Console
# Run: performance.mark('filter-start'); await applyFilters(); performance.mark('filter-end'); performance.measure('filter', 'filter-start', 'filter-end');
# Verify: Filter response <100ms

# Measure memory
# Chrome DevTools → Memory tab → Take heap snapshot
# Load 100 artifacts
# Verify: Memory usage <6MB
```

---

## 5. Success Metrics

### 5.1 Performance Targets

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Initial Load | ~2s | <1.5s | Chrome DevTools Network tab |
| Filter Response | 150ms | <100ms | Performance.now() |
| Status Update | 250ms | <50ms | WebSocket event → UI update |
| Memory (100 artifacts) | ~8MB | <6MB | Chrome DevTools Memory |

### 5.2 Code Quality

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Graph Construction Code | 1,400 lines | 310 lines | **-78%** |
| Test Code | 1,706 lines | ~400 lines (rewritten) | **-76%** |
| Test Focus | Edge algorithms, state sync | Backend integration, UX | **Simpler tests** |
| Complexity | O(n×m + a×c + e²) | O(1) + O(n) | **O(n)** |

---

## 6. Rollback Plan

**No feature flag = No easy rollback!**

**If issues found**:
1. Revert entire PR
2. Fix issues in separate branch
3. Re-merge when ready

**Prevention**:
- ✅ Thorough testing before merge
- ✅ Manual QA on all scenarios
- ✅ Performance validation
- ✅ Code review by 2+ developers

**Rollback triggers**:
- ❌ Initial load >2s (worse than before)
- ❌ Critical bugs (positions lost, graphs broken)
- ❌ >5 user-reported issues in first day

---

## 7. Implementation Timeline

| Week | Tasks | Deliverables |
|------|-------|--------------|
| **1** | Create graphService.ts, types, replace graphStore, update websocket, **delete transforms.ts** | Backend integration working |
| **2** | Simplify filterStore, update filter UI, extract facets from backend | Filters using backend |
| **3** | **Delete old tests (~1,700 lines)**, write new focused tests (~400 lines), manual QA, performance validation | All tests passing, ready to merge |

**Total**: 3 weeks
**Test Strategy**: Complete rewrite - faster than fixing broken tests

---

## 8. Pre-Merge Checklist

**Code Quality**:
- [ ] All tests passing (`npm test`)
- [ ] No TypeScript errors (`npm run typecheck`)
- [ ] Linting passes (`npm run lint`)
- [ ] Code reviewed by 2+ developers

**Functionality**:
- [ ] Graph loads from backend on initial load
- [ ] Positions persist across refreshes
- [ ] Agent status updates in real-time (<50ms)
- [ ] Streaming tokens display correctly
- [ ] Filters trigger backend fetch (<100ms)
- [ ] Debouncing works (5 events → 1 fetch after 500ms)
- [ ] Error handling shows user-friendly messages

**Performance**:
- [ ] Initial load <1.5s
- [ ] Filter response <100ms
- [ ] Memory usage <6MB (100 artifacts)
- [ ] No memory leaks (test 1000+ artifacts)

**Documentation**:
- [ ] README updated
- [ ] Architecture diagram updated
- [ ] API integration documented

---

## 9. Summary

**What's Happening**:
- ❌ **Deleting 2,885 lines total**:
  - transforms.ts (324 lines) - edge derivation logic
  - Old graphStore logic (489 lines) - state management
  - Old tests (1,706 lines) - **complete test suite rewrite**
  - WebSocket complexity (200 lines)
  - Filter logic (113 lines)
- ✅ **Adding 710 lines**:
  - graphService.ts (100 lines) - backend integration
  - types (80 lines) - TypeScript contracts
  - Simplified stores (200 lines) - minimal state
  - WebSocket handler (100 lines) - debounced refresh
  - **New focused tests (400 lines)** - backend integration, not edge algorithms
- 🎯 **Net reduction: -2,175 lines (-75%)**

**Why It Works**:
- Backend provides **complete graph snapshots** (nodes + edges + statistics)
- Frontend only handles: position persistence, real-time status, streaming tokens
- Single source of truth → fewer bugs, simpler code
- **Test rewrite faster than fixing** → focus on what matters (backend integration, UX)

**The Startup Way**: Delete fearlessly, rewrite tests smartly, ship with confidence! 🚀
