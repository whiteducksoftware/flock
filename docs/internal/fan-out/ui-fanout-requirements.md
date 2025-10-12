# UI Requirements for Fan-Out Pattern Support

## Overview

This document outlines the UI changes required to support fan-out patterns in the Flock dashboard, including graph visualization, WebSocket events, and parallel streaming capabilities.

## Key Requirements

### 1. Runtime Mode Detection

The system needs to differentiate between CLI and dashboard execution modes to enable parallel streaming.

#### Context Enhancement

Add `runtime_mode` to the `Context` class:

```python
class RuntimeMode(Enum):
    CLI = "cli"          # Direct script execution
    DASHBOARD = "dashboard"  # Web UI with WebSocket
    API = "api"          # REST service

class Context:
    runtime_mode: RuntimeMode = RuntimeMode.CLI

    @property
    def allows_parallel_streaming(self) -> bool:
        """Check if current runtime mode supports parallel streaming."""
        return self.runtime_mode in [RuntimeMode.DASHBOARD, RuntimeMode.API]
```

#### Mode Detection

The orchestrator sets the mode when `serve()` is called:

```python
# In Orchestrator.serve()
async def serve(self, dashboard: bool = False, ...):
    # Set runtime mode based on serve configuration
    self._context.runtime_mode = (
        RuntimeMode.DASHBOARD if dashboard else RuntimeMode.API
    )

    # Inject into all agent contexts
    for agent in self.agents:
        agent.context.runtime_mode = self._context.runtime_mode
```

### 2. Parallel Streaming Architecture

#### Current Limitation

The system currently limits streaming to one agent using `_active_streams` counter:

```python
# Current implementation in DSPyEngine
if orchestrator._active_streams > 0:
    # Disable streaming for concurrent agents
    return await self._execute_non_streaming(...)
```

This exists purely for CLI display constraints (Rich Live conflicts).

#### Proposed Solution

Enable parallel streaming based on runtime mode:

```python
class DSPyEngine(EngineComponent):
    async def evaluate(self, agent, ctx: Context, inputs):
        # Check runtime mode instead of active streams
        if not ctx.allows_parallel_streaming and orchestrator._active_streams > 0:
            return await self._execute_non_streaming(...)

        if ctx.runtime_mode == RuntimeMode.DASHBOARD:
            # Stream only to WebSocket, not to Rich console
            return await self._execute_streaming_websocket_only(...)
        else:
            # CLI mode - existing behavior
            return await self._execute_streaming_with_rich(...)
```

### 3. WebSocket Event Structure

#### Enhanced Event Metadata

Extend existing `MessagePublishedEvent` with fan-out fields:

```typescript
interface MessagePublishedEvent {
  // Existing fields
  type: 'message_published';
  agent_name: string;
  artifact: Artifact;

  // Fan-out parent fields
  is_fan_out_parent?: boolean;
  fan_out_count?: number;
  child_artifact_ids?: string[];

  // Fan-out child fields
  parent_artifact_id?: string;
  sequence_index?: number;
  sequence_total?: number;
}
```

#### Batched Events for Performance

For large fan-outs, use batch events:

```typescript
interface FanOutBatchEvent {
  type: 'fan_out_batch';
  parent_artifact_id: string;
  child_artifacts: Artifact[];
  agent_name: string;
  correlation_id: string;
}
```

### 4. Frontend State Management

#### New State Structures

```typescript
// In WebSocketStore
interface FanOutRelationship {
  parentId: string;
  childIds: string[];
  totalCount: number;
  receivedCount: number;
  status: 'pending' | 'expanding' | 'complete' | 'error';
}

fanOutRelationships: Map<string, FanOutRelationship>;
pendingFanOuts: Map<string, Set<string>>;  // parent -> expected children
```

#### Event Processing

```typescript
handleMessagePublished(event: MessagePublishedEvent) {
  // Track fan-out parent
  if (event.is_fan_out_parent) {
    this.fanOutRelationships.set(event.artifact.id, {
      parentId: event.artifact.id,
      childIds: [],
      totalCount: event.fan_out_count || 0,
      receivedCount: 0,
      status: 'expanding'
    });
  }

  // Track fan-out child
  if (event.parent_artifact_id) {
    const relationship = this.fanOutRelationships.get(event.parent_artifact_id);
    if (relationship) {
      relationship.childIds.push(event.artifact.id);
      relationship.receivedCount++;
      if (relationship.receivedCount === relationship.totalCount) {
        relationship.status = 'complete';
      }
    }
  }
}
```

### 5. Graph Visualization Components

#### New Node Type: FanOutNode

```typescript
interface FanOutNodeProps extends NodeProps {
  data: {
    artifactType: string;
    expansionCount: number;
    state: 'pending' | 'expanding' | 'complete' | 'error';
    progress: number;  // 0-1
    isExpanded: boolean;
  };
}

const FanOutNode: React.FC<FanOutNodeProps> = ({ data }) => {
  return (
    <div className="fan-out-node">
      <div className="expansion-indicator">
        <span className="icon">⚡</span>
        <span className="count-badge">×{data.expansionCount}</span>
      </div>
      <div className="artifact-info">
        {data.artifactType}
      </div>
      {data.state === 'expanding' && (
        <ProgressBar value={data.progress} />
      )}
    </div>
  );
};
```

#### Enhanced MessageNode

Add fan-out relationship tracking:

```typescript
interface MessageNodeData extends BaseNodeData {
  // Existing fields
  artifact: Artifact;

  // Fan-out fields
  isFannedOut?: boolean;
  parentArtifactId?: string;
  fanOutIndex?: number;
  fanOutTotal?: number;
}
```

### 6. Visual Design System

#### Node Styling

```css
/* Fan-out source node */
.fan-out-node {
  background: linear-gradient(135deg, #fef3c7 0%, #fed7aa 100%);
  border: 2px dashed #8b5cf6;
  border-radius: 8px;
  position: relative;
}

.fan-out-node .expansion-indicator {
  position: absolute;
  top: -10px;
  right: -10px;
  display: flex;
  align-items: center;
  background: #8b5cf6;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

/* Fanned-out child nodes */
.message-node.fanned-out {
  background: #fffbeb;
  border-style: dotted;
}

.message-node .fan-out-index {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: bold;
}
```

#### Edge Styling

```css
/* Fan-out edges */
.react-flow__edge.fanout {
  stroke: url(#fanout-gradient);
  stroke-width: 2px;
  animation: flow 2s ease-in-out infinite;
}

@keyframes flow {
  0%, 100% { stroke-dashoffset: 0; }
  50% { stroke-dashoffset: 10; }
}
```

### 7. Layout Algorithm

#### Fan-Out Layout Strategy

```typescript
function layoutFanOut(
  sourceNode: Node,
  targetNodes: Node[],
  options: LayoutOptions
): LayoutResult {
  const { direction = 'horizontal', spacing = 120 } = options;

  if (targetNodes.length <= 3) {
    // Linear layout
    return layoutLinear(sourceNode, targetNodes, spacing);
  } else if (targetNodes.length <= 8) {
    // Tree layout
    return layoutTree(sourceNode, targetNodes, spacing);
  } else {
    // Radial layout for many nodes
    return layoutRadial(sourceNode, targetNodes, spacing * 1.5);
  }
}
```

### 8. Animation Sequences

#### Expansion Animation

```typescript
const animateFanOutExpansion = (
  parentNode: Node,
  childNodes: Node[],
  edges: Edge[]
) => {
  // Phase 1: Parent node pulse (300ms)
  animateNode(parentNode, 'pulse', 300);

  // Phase 2: Edges appear with stagger (100ms each)
  edges.forEach((edge, i) => {
    setTimeout(() => animateEdge(edge, 'flow', 600), i * 100);
  });

  // Phase 3: Child nodes fade in with stagger (150ms each)
  childNodes.forEach((node, i) => {
    setTimeout(() => animateNode(node, 'fadeIn', 400), 300 + i * 150);
  });
};
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Add runtime_mode to Context
- [ ] Update DSPyEngine for parallel streaming
- [ ] Enhance WebSocket events with fan-out metadata
- [ ] Create FanOutNode component

### Phase 2: Visualization (Week 2)
- [ ] Implement fan-out layout algorithms
- [ ] Add expansion animations
- [ ] Create visual state indicators
- [ ] Update edge rendering

### Phase 3: Polish & Performance (Week 3)
- [ ] Add batch event handling
- [ ] Implement virtual rendering for large fan-outs
- [ ] Add accessibility features
- [ ] Performance optimization

## Testing Requirements

### Unit Tests
- Runtime mode detection
- Fan-out event processing
- Layout algorithm correctness
- State management

### Integration Tests
- WebSocket event flow
- Graph visualization updates
- Parallel streaming behavior
- Performance under load

### E2E Tests
- Complete fan-out workflow
- User interactions
- Animation sequences
- Error handling

## Performance Considerations

### Thresholds
- Small fan-out (< 10): Individual events, full animation
- Medium fan-out (10-50): Batched events, simplified animation
- Large fan-out (> 50): Single batch, minimal animation

### Optimization Strategies
1. Use requestAnimationFrame for batched UI updates
2. Implement virtual scrolling for large graphs
3. Throttle WebSocket events on frontend
4. Use React.memo for node components
5. Implement progressive rendering

## Accessibility Requirements

- ARIA labels for fan-out nodes
- Keyboard navigation through expanded artifacts
- Screen reader announcements for expansion events
- Reduced motion mode support
- High contrast mode compatibility

## Browser Compatibility

- Chrome 90+ (primary)
- Firefox 88+
- Safari 14+
- Edge 90+

## Dependencies

### Frontend
- React Flow 12.x (existing)
- Zustand (existing)
- React 19.x (existing)

### Backend
- No new dependencies required
- Uses existing WebSocket infrastructure

## Migration Strategy

1. Feature flag for fan-out visualization
2. Backward compatible event structure
3. Graceful degradation for older clients
4. Progressive enhancement approach

## Success Metrics

- Graph renders < 200ms for 50-node fan-out
- WebSocket latency < 50ms per event
- Memory usage < 100MB for 1000 artifacts
- 60 FPS animation performance
- Zero visual glitches or layout conflicts