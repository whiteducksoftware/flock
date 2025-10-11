# Trace Viewer Module 🔍

A beautiful, interactive OpenTelemetry trace visualization module for the Flock dashboard. View agent execution traces with waterfall timelines, search capabilities, and detailed span inspection.

## Features

### 🎨 Beautiful Waterfall Visualization
- **Interactive timeline view** showing span execution order and duration
- **Color-coded spans** by type (Agent, Engine, Component)
- **Hierarchical display** with expandable span details
- **Duration indicators** showing execution time in milliseconds

### 🔍 Smart Filtering & Search
- **Real-time search** across trace IDs, span names, and agent names
- **Automatic grouping** by trace ID
- **Error highlighting** for failed traces
- **Trace statistics** (span count, total duration, status)

### 📊 Rich Span Details
- **Expandable spans** showing all OTEL attributes
- **Agent metadata** (name, description)
- **Correlation tracking** via correlation_id
- **Task tracking** via task_id
- **Status indicators** (OK, ERROR)

### ⚡ Live Updates
- **Auto-refresh** every 5 seconds
- **Real-time trace loading** from `.flock/traces.jsonl`
- **No configuration needed** - just enable auto-tracing

## Quick Start

### 1. Enable Auto-Tracing

```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
python your_agent.py
```

### 2. Start Dashboard

```python
# In your agent code
await orchestrator.serve(dashboard=True)
```

### 3. Access Trace Viewer

1. Open dashboard at `http://localhost:8344`
2. Right-click on canvas → **Add Module** → **🔍 Trace Viewer**
3. Traces will appear automatically!

## Architecture

### Components Created

```
src/flock/
├── frontend/src/components/modules/
│   ├── TraceModule.tsx          # Main trace viewer component
│   ├── TraceModuleWrapper.tsx   # Module context wrapper
│   └── registerModules.ts       # Updated with trace module registration
└── dashboard/
    └── service.py               # Added /api/traces endpoint

docs/guides/tracing/
├── auto-tracing.md              # Auto-tracing guide
└── trace-module.md              # This file!
```

### Data Flow

```
1. Auto-Tracing generates spans → .flock/traces.jsonl
2. Backend /api/traces reads file → Returns JSON array
3. Frontend polls every 5s → Groups spans by trace_id
4. React renders waterfall → Interactive visualization
```

### API Endpoint

**`GET /api/traces`**

Returns array of OTEL span objects:

```json
[
  {
    "name": "Agent.execute",
    "context": {
      "trace_id": "ae40f0061e3f1bcfebe169191d138078",
      "span_id": "739aa78e2ff5267d",
      "trace_flags": 1,
      "trace_state": "[]"
    },
    "start_time": 1759843976996907490,
    "end_time": 1759843977012345678,
    "status": {
      "status_code": "OK"
    },
    "attributes": {
      "class": "Agent",
      "function": "execute",
      "module": "flock.agent",
      "agent.name": "movie",
      "agent.description": "Generate movie ideas",
      "correlation_id": "12d0fcda-e7f7-4c96-ae8e-14ae4eca1518",
      "task_id": "task_abc123",
      "result.type": "EvalResult",
      "result.length": 1
    },
    "kind": "INTERNAL",
    "resource": {
      "service.name": "flock-auto-trace"
    }
  }
]
```

## UI Walkthrough

### Trace List View

```
┌──────────────────────────────────────────────────────────┐
│  🔍 Search: [trace ID, span name, agent...]       3 traces│
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ▶ ae40f006...                          15.23ms          │
│    2025-10-07 15:32:40 • 29 spans                       │
│                                                           │
│  ▼ d14a167a...                          12.41ms  ⚠️ Error│
│    2025-10-07 15:33:05 • 15 spans                       │
│    ┌────────────────────────────────────────────────────┐│
│    │ Waterfall View                                     ││
│    │                                                     ││
│    │ ▶ Agent.execute (movie)  ████████████  4.25ms     ││
│    │ ▶ DSPyEngine.evaluate    ████  1.15ms             ││
│    │ ▼ Component.on_init      █  0.05ms                ││
│    │   Span ID: 739aa78e...                            ││
│    │   Status: OK                                       ││
│    │   agent.name: movie                                ││
│    │   correlation_id: 12d0fcda-e7f7...                ││
│    └────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

### Color Coding

| Span Type | Color | Example |
|-----------|-------|---------|
| **Agent.execute** | Primary Blue | Main agent execution |
| **Engine** | Green | DSPyEngine.evaluate |
| **Component** | Orange | OutputComponent.on_init |
| **Other** | Info Blue | Generic methods |
| **Error** | Red | Any span with status ERROR |

## Usage Examples

### Example 1: Debug Slow Agent

```bash
# Enable tracing
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true

# Run your agent
python my_slow_agent.py
```

**In Trace Viewer:**
1. Find trace with long duration
2. Expand trace → see waterfall
3. Identify bottleneck spans
4. Click span → view attributes
5. Find which component is slow

### Example 2: Track Correlation Flow

```bash
# Run multi-agent workflow
python examples/showcase/02_hello_flock.py
```

**In Trace Viewer:**
1. Search for correlation ID: `12d0fcda`
2. See all related traces
3. Track data flow across agents
4. Verify execution order

### Example 3: Error Investigation

```bash
# Run workflow that fails
python my_failing_agent.py
```

**In Trace Viewer:**
1. Look for ⚠️ Error indicators
2. Click trace → expand waterfall
3. Find ERROR status span (red)
4. Expand → see error details
5. Check attributes for context

## Advanced Features

### Span Attributes Captured

Every span automatically includes:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `class` | Class name | `Agent`, `Flock`, `DSPyEngine` |
| `function` | Method name | `execute`, `evaluate` |
| `module` | Python module | `flock.agent` |
| `agent.name` | Agent identifier | `movie`, `tagline` |
| `agent.description` | Agent description | `Generate movies` |
| `correlation_id` | Request tracking | `12d0fcda-...` |
| `task_id` | Task identifier | `task_abc123` |
| `result.type` | Return type | `EvalResult`, `list` |
| `result.length` | Collection size | `3` |

### Performance

- **Lightweight:** No external dependencies
- **Fast rendering:** React memoization
- **Efficient polling:** 5s refresh interval
- **Lazy loading:** Only visible traces render
- **Minimal overhead:** <0.1ms per span display

### Browser Compatibility

- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ⚠️ IE11 (not supported)

## Troubleshooting

### "No traces found"

**Cause:** Trace file doesn't exist

**Fix:**
```bash
# Make sure both are set
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true

# Run your agent
python your_agent.py

# Verify file exists
ls -la .flock/traces.jsonl
```

### "Failed to load traces"

**Cause:** Backend can't read trace file

**Fix:**
```bash
# Check file permissions
chmod 644 .flock/traces.jsonl

# Check backend logs
# Look for "Trace file not found" warnings
```

### "Spans not showing up"

**Cause:** Auto-tracing not enabled

**Fix:**
```python
# Check imports - auto-tracing initializes on import
from flock.agent import Agent  # Should see DEBUG logs

# Verify in logs
# Look for: "Agent.execute executed successfully"
```

### Module not appearing

**Cause:** Frontend not rebuilt

**Fix:**
```bash
cd src/flock/frontend
npm run build

# Restart dashboard
python your_agent.py
```

## Future Enhancements

Possible future improvements:

- [ ] **Flame graphs** for performance profiling
- [ ] **Trace comparison** side-by-side view
- [ ] **Export to Jaeger** direct integration
- [ ] **Custom span filtering** by attributes
- [ ] **Time range selection** with date picker
- [ ] **Span search** within specific trace
- [ ] **Performance metrics** (P50, P95, P99)
- [ ] **Trace aggregation** statistics view
- [ ] **Live streaming** via WebSocket
- [ ] **Span annotations** add notes

## Development

### Adding New Features

```typescript
// frontend/src/components/modules/TraceModule.tsx

// 1. Add state
const [myFeature, setMyFeature] = useState(false);

// 2. Add UI
<button onClick={() => setMyFeature(!myFeature)}>
  Toggle Feature
</button>

// 3. Use in rendering
{myFeature && <div>Feature content</div>}
```

### Testing

```bash
# Frontend tests
cd src/flock/frontend
npm test

# Backend tests
uv run pytest tests/

# E2E test
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
python examples/showcase/02_hello_flock.py
# Then open dashboard and verify traces appear
```

### Module Registration

```typescript
// src/flock/frontend/src/components/modules/registerModules.ts

moduleRegistry.register({
  id: 'traceViewer',
  name: 'Trace Viewer',
  description: 'OpenTelemetry traces with waterfall visualization',
  icon: '🔍',
  component: TraceModuleWrapper,
});
```

## Related Documentation

- [Auto-Tracing Guide](auto-tracing.md) - Complete auto-tracing guide
- [Tracing Overview](index.md) - Tracing system overview
- [Dashboard Guide](../dashboard.md) - Dashboard usage guide
- [Production Tracing](tracing-production.md) - Production best practices

## Credits

Built with ❤️ using:
- **React 19** - UI framework
- **TypeScript** - Type safety
- **OpenTelemetry** - Distributed tracing
- **Flock Dashboard** - Module system

---

**Enjoy visualizing your traces!** 🎉

For questions or issues, see the [Tracing Overview](index.md) or create an issue on [GitHub](https://github.com/whiteducksoftware/flock/issues).
