# Dashboard

The **Flock Dashboard** is a real-time visualization tool that makes your AI agent system observable, debuggable, and interactive. With professional UI/UX and WebSocket streaming, you can watch your agents execute, explore data lineage, and manually test workflows—all in your browser.

**Think of it as a flight control center for your AI agents:** See who's working, what data is flowing, and how your system transforms information in real-time.

<p align="center">
  <img alt="Flock Agent View" src="../img/flock_ui_agent_view.png" width="1000">
  <i>Agent View: See agent communication patterns and message flows in real-time</i>
</p>

---

## Why Use the Dashboard?

**Traditional AI frameworks are black boxes.** You publish data, agents run, and you hope for the best. If something breaks, you're stuck adding print statements and guessing.

**Flock's dashboard makes everything visible:**
- ✅ **See agents execute in real-time** - Watch status change from idle → running → idle
- ✅ **Track data lineage** - Follow how data transforms through your system
- ✅ **Debug conditional consumption** - See which agents filtered which artifacts
- ✅ **Test workflows manually** - Publish artifacts from the UI without code
- ✅ **Monitor live output** - Stream LLM tokens as they generate

---

## Getting Started (One Line)

Start the dashboard with a single line:

```python
await flock.serve(dashboard=True)
```

**That's it.** Flock automatically:
1. Builds the production-optimized frontend
2. Starts the backend API server
3. Opens your browser to `http://localhost:8344`
4. Establishes WebSocket connection for real-time updates

**Expected startup output:**
```
[Dashboard] Production build completed
INFO: Uvicorn running on http://127.0.0.1:8344
[Dashboard] Browser launched successfully
```

### Non-Blocking Mode (New!)

Need to publish messages **after** starting the dashboard? Use non-blocking mode:

```python
# Start dashboard in background
await flock.serve(dashboard=True, blocking=False)

# Now you can publish messages and run logic!
await flock.publish(my_message)
await flock.run_until_idle()

# Dashboard stays alive for inspection
```

**Perfect for:**
- 🎯 Demo scripts that populate data after server starts
- 🧪 Testing scenarios where you control execution flow
- 📊 Scripts that need to perform setup after dashboard is running

**Example:** See [`examples/02-dashboard/02_non_blocking_serve.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/02-dashboard/02_non_blocking_serve.py) for a complete demo that publishes multiple pizza orders after starting the dashboard.

**How it works:**
- `blocking=True` (default): Server runs forever, blocks execution
- `blocking=False`: Returns immediately, server runs in background
- Automatic cleanup when task completes or is cancelled
- Works with both dashboard and non-dashboard modes

<p align="center">
  <img alt="Flock Blackboard View" src="../img/flock_ui_blackboard_view.png" width="1000">
  <i>Blackboard View: Track data lineage and transformations across the system</i>
</p>

---

## Dual Visualization Modes

The dashboard provides **two complementary views** of your system. Switch between them instantly with the mode toggle or `Ctrl+M`.

### Agent View (Default)

**Focus:** Agents and their communication patterns

**Nodes represent:**
- Agent instances (e.g., `pizza_master`, `reviewer_agent`)
- External publishers (when you call `flock.publish()`)

**Edges represent:**
- Message flows between agents
- Artifact subscriptions (who consumes what)

**What you see on each node:**
- Agent name and current status (`idle`, `running`)
- Input types with counts (e.g., `↓ 3 Review`)
- Output types with counts (e.g., `↑ 1 BookOutline`)

**Use when:**
- Understanding agent orchestration patterns
- Debugging which agents are triggered
- Monitoring multi-agent cascades
- Testing parallel execution

### Blackboard View

**Focus:** Data artifacts and transformation lineage

**Nodes represent:**
- Published artifacts (inputs and outputs)
- Complete artifact payloads (expandable JSON)

**Edges represent:**
- Data transformations (input → output)
- Producer-consumer relationships

**What you see on each node:**
- Artifact type (e.g., `__main__.Pizza`)
- Producer agent (e.g., `by: pizza_master`)
- Timestamp of publication
- Full JSON payload (expand/collapse)

**Use when:**
- Tracking data lineage ("where did this artifact come from?")
- Debugging transformation logic
- Verifying output structure
- Understanding data flow patterns

[**👉 See Agent View example**](https://github.com/whiteducksoftware/flock/blob/main/examples/02-dashboard/01_declarative_pizza.py)
[**👉 See Blackboard View with complex lineage**](https://github.com/whiteducksoftware/flock/blob/main/examples/02-dashboard/02_input_and_output.py)

---

## Real-Time Features

### WebSocket Streaming

The dashboard uses **WebSocket connections** for instant updates:

- **Connection status indicator** (top right) shows green when connected
- **2-minute heartbeat** keeps connection alive during idle periods
- **Automatic reconnection** if connection drops
- **Live token streaming** shows LLM output as it generates

**You'll see in the browser console:**
```javascript
[WebSocket] Connected to ws://localhost:8344/ws
[WebSocket] Streaming output: {"content": "Analyzing...", "done": false}
[WebSocket] Agent status changed: pizza_master → running
```

### Live Agent Execution

**Watch agents work in real-time:**

1. **Status transitions** - See `idle` → `running` → `idle` as agents execute
2. **Counter updates** - Input/output counts increment live
3. **Token streaming** - LLM output appears character-by-character
4. **Cascade visualization** - Multi-agent workflows trigger visibly

**Example execution timeline:**
```
Time 0: Publish PizzaIdea artifact
Time 1: pizza_master status → running
Time 2: [Live Output] "To make a truffle pizza, we'll need..."
Time 3: pizza_master status → idle, output count ↑ 1
Time 4: Pizza artifact appears in Blackboard View
```

### Auto-Layout with Dagre Algorithm

**Complex graphs automatically organize:**

- **5 layout algorithms available:**
  - Hierarchical Vertical (top-to-bottom)
  - Hierarchical Horizontal (left-to-right)
  - Circular (nodes in a circle)
  - Grid (organized grid pattern)
  - Random (fresh randomization)

- **Smart spacing** - 200px minimum clearance based on node size
- **Viewport centering** - Layouts center around your current view
- **Right-click activation** - Access via context menu

**When to use:**
- Agent graphs with 3+ nodes
- After publishing multiple artifacts
- When nodes overlap visually
- For screenshot-ready presentation

[**👉 Try auto-layout with multi-agent example**](https://github.com/whiteducksoftware/flock/blob/main/examples/02-dashboard/08_band_formation.py)

---

## Interactive Graph Features

### Navigation and Exploration

**Mouse controls:**
- **Pan** - Click and drag canvas
- **Zoom** - Mouse wheel or pinch gesture
- **Select node** - Click on agent or artifact
- **Context menu** - Right-click canvas or node

**React Flow controls (bottom right):**
- 🔍 **Zoom in/out** - Precise zoom control
- 📍 **Fit view** - Center and fit entire graph
- 🗺️ **Mini-map** - Navigate large graphs quickly

### Node Interactions

**Double-click any node** to open detail window:

**Agent nodes show:**
- Full agent description
- Complete subscription configuration
- Current execution state
- Recent activity log

**Artifact nodes show:**
- Complete JSON payload
- Collapsible tree structure
- Producer information
- Timestamp and correlation ID

**Right-click nodes** for context actions:
- **Agents:** View details, invoke manually, check status
- **Artifacts:** Copy payload, view trace, expand all fields

### Context Menu Features

**Right-click the canvas** (not a node) to access:

- **Auto Layout** - Choose from 5 layout algorithms
- **Add Module** - Dynamically load new agents
- **Reset View** - Return to default zoom/position
- **Export Graph** - Download as PNG/SVG

**Auto-layout is essential** for multi-agent systems:
```python
# Testing with complex graph?
# 1. Run example with 3+ agents
# 2. Right-click canvas → Auto Layout → Hierarchical Vertical
# 3. Graph organizes cleanly with no overlaps
```

---

## Control Panel

### Publishing Artifacts from UI

**Test workflows without writing code:**

1. **Click "Publish" button** (or `Ctrl+P`)
2. **Select artifact type** from dropdown (e.g., `MyDreamPizza`)
3. **Form auto-generates** based on Pydantic schema
4. **Fill in fields** - Text inputs for strings, checkboxes for bools
5. **Click "Publish Artifact"** - Triggers agent cascade

**Example workflow:**
```
1. Select: __main__.MyDreamPizza
2. Form shows: "Pizza Idea" text input
3. Enter: "a spicy Hawaiian with jalapeños"
4. Click Publish
5. Watch pizza_master execute in real-time
```

**Form generation is automatic:**
- String fields → Text inputs
- Int fields → Number inputs
- List fields → Multi-input
- Nested models → Collapsible sections

### Agent Details Panel

**Monitor individual agent execution:**

1. **Click "Agent Details"** button
2. **Select agent** from dropdown
3. **Three tabs available:**
   - **Live Output** - Stream tokens as they generate
   - **Message History** - Past executions and outputs
   - **Run Status** - Current state and metrics

**Live Output features:**
- Real-time token streaming via WebSocket
- Event counter (e.g., "316 events")
- "--- End of output ---" marker when complete
- Scroll to bottom automatically

**Use cases:**
- Debugging agent behavior
- Verifying output format
- Monitoring long-running executions
- Capturing execution logs

---

## Advanced Filtering

### Correlation ID Tracking

**Follow specific workflows through your system:**

```python
# Publish with correlation ID
await flock.publish(data, correlation_id="workflow_123")

# In dashboard:
# 1. Open Filters panel
# 2. Enter "workflow_123" in correlation ID field
# 3. Graph shows only related artifacts and agents
```

**Use cases:**
- Multi-tenant systems (filter by tenant_id)
- Request tracing (follow user_id through system)
- A/B testing (compare workflow_v1 vs workflow_v2)
- Debugging specific executions

### Time Range Filtering

**Focus on recent activity:**

- **Last 5 minutes** - Recent quick tests
- **Last 10 minutes** - Standard debugging window
- **Last 60 minutes** - Full workflow analysis
- **Custom range** - Specific time period

**Active filter pills:**
- One-click removal
- Combine multiple filters (AND logic)
- Persist across view switches

### Autocomplete Search

**Find artifacts quickly:**

- Type-ahead search across artifact types
- Metadata preview on hover
- Recent artifacts at top
- Keyboard navigation (↑↓ arrows, Enter to select)

**Example:**
```
Type: "Pizza"
Results:
  - __main__.Pizza (3 instances)
  - __main__.PizzaIdea (1 instance)
Preview: {"ingredients": ["mozzarella", ...], ...}
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+M` | Toggle Agent View ↔ Blackboard View |
| `Ctrl+F` | Focus filter search |
| `Ctrl+P` | Open Publish dialog |
| `Ctrl+/` | Show shortcuts help |
| `Esc` | Close open panels |

**Accessibility:**
- WCAG 2.1 AA compliant
- Full keyboard navigation
- Screen reader compatible
- High contrast support

---

## Complete Example Walkthrough

### Simple Single-Agent Example

**Code:** `examples/02-dashboard/01_declarative_pizza.py`

```python
@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str

@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]

flock = Flock("openai/gpt-4.1")

pizza_master = (
    flock.agent("pizza_master")
    .consumes(MyDreamPizza)
    .publishes(Pizza)
)

async def main():
    await flock.serve(dashboard=True)
```

**Testing workflow:**

1. **Start example:** `uv run examples/02-dashboard/01_declarative_pizza.py`
2. **Wait for startup:** "Browser launched successfully"
3. **Verify initial state:**
   - Agent View shows `pizza_master` node
   - Status: `idle`
   - Counters: `↓ 0 MyDreamPizza`, `↑ 0 Pizza`

4. **Publish artifact:**
   - Click "Publish" button
   - Select `__main__.MyDreamPizza`
   - Enter: "a spicy Hawaiian pizza with jalapeños and pineapple"
   - Click "Publish Artifact"

5. **Watch execution:**
   - Status changes: `idle` → `running`
   - **External node appears** (shows orchestrator published the artifact)
   - Edge connects: external → pizza_master
   - Live Output streams tokens
   - Status returns: `running` → `idle`

6. **Verify results:**
   - Input counter: `↓ 0` → `↓ 1`
   - Output counter: `↑ 0` → `↑ 1`
   - Switch to Blackboard View
   - See two artifact nodes:
     - `MyDreamPizza` (input, by: external)
     - `Pizza` (output, by: pizza_master)
   - Expand Pizza node to see complete structured output

**Expected execution time:** ~5 seconds

### Complex Multi-Agent Example

**Code:** `examples/02-dashboard/09_debate_club.py`

```python
book_idea_agent = (
    flock.agent("book_idea_agent")
    .consumes(Idea)
    .consumes(Review, where=lambda r: r.score <= 8)  # Conditional!
    .publishes(BookHook)
)

reviewer_agent = (
    flock.agent("reviewer_agent")
    .consumes(BookHook)
    .publishes(Review)
)

chapter_agent = (
    flock.agent("chapter_agent")
    .consumes(Review, where=lambda r: r.score >= 9)  # Filtered!
    .publishes(BookOutline)
)
```

**What makes this complex:**
- **Conditional consumption** - Agents filter artifacts with `where` clauses
- **Multiple outputs** - `book_idea_agent` produces 3 BookHooks
- **Feedback loops** - Low-scoring Reviews loop back to `book_idea_agent`
- **Parallel execution** - `reviewer_agent` processes 3 BookHooks concurrently

**Testing workflow:**

1. **Start example:** `uv run examples/02-dashboard/09_debate_club.py`
2. **Use auto-layout:** Right-click canvas → Auto Layout → Hierarchical Vertical
3. **Publish initial Idea:**
   - Click "Publish"
   - Select `__main__.Idea`
   - Enter idea text
   - Publish

4. **Watch cascade execution:**

```
Time 0s: Publish Idea artifact
Time 5s: book_idea_agent executes (↓ 1 Idea → ↑ 3 BookHook)
Time 10s: reviewer_agent executes 3x in parallel (↓ 3 BookHook → ↑ 3 Review)
Time 35s: chapter_agent executes (↓ 1 Review → ↑ 1 BookOutline) [filtered: only score >= 9]
Time 45s: book_idea_agent executes again (↓ 2 Review → ↑ 0 BookHook) [feedback loop: score <= 8]
```

5. **Verify filtered consumption:**
   - Edge labels show: `Review(3)` on reviewer → chapter edge
   - chapter_agent input: `↓ 1 Review` (not ↓ 3!) because of filtering
   - book_idea_agent input: `↓ 1 Idea, ↓ 2 Review` (consumed both types)

6. **Switch to Blackboard View:**
   - See complete artifact lineage:
     - 1 Idea → 3 BookHooks → 3 Reviews → 1 BookOutline
   - Edges show transformation chain
   - Timestamps prove execution order

**Expected execution time:** ~60 seconds (multi-agent cascade with feedback loop)

**⚠️ Important:** With 8+ artifacts, use `browser_take_screenshot()` instead of `browser_snapshot()` for visual verification (snapshots exceed token limits).

[**👉 Run the simple example**](https://github.com/whiteducksoftware/flock/blob/main/examples/02-dashboard/01_declarative_pizza.py)
[**👉 Run the complex example**](https://github.com/whiteducksoftware/flock/blob/main/examples/02-dashboard/09_debate_club.py)

---

## Production Features

### Trace Viewer Integration

The dashboard includes a **Jaeger-style trace viewer** with 7 visualization modes:

**Access traces:**
1. Enable tracing: `export FLOCK_AUTO_TRACE=true`
2. Wrap workflows: `async with flock.traced_run("workflow_name"):`
3. Open dashboard → Trace Viewer tab

**7 Visualization Modes:**

1. **Timeline** - Waterfall view with span hierarchies
   - See parent-child relationships
   - Identify bottlenecks visually
   - Measure exact durations

2. **Statistics** - Sortable table view
   - Sort by duration, error rate
   - Filter by operation name
   - Track success/failure rates

3. **RED Metrics** - Service health monitoring
   - **R**ate: Requests per second
   - **E**rrors: Error percentage
   - **D**uration: Latency percentiles

4. **Dependencies** - Service communication graph
   - Who calls whom
   - Request volumes
   - Error rates per connection

5. **DuckDB SQL** - Interactive query editor
   - Query trace data with SQL
   - Export results to CSV
   - Saved query templates

6. **Configuration** - Real-time filtering
   - Filter by service name
   - Filter by operation type
   - Hide/show specific spans

7. **Guide** - Built-in documentation
   - Query examples
   - Keyboard shortcuts
   - Feature explanations

**Additional Features:**
- **Full I/O capture** - Complete input/output for every span
- **JSON viewer** - Collapsible tree with expand all/collapse all
- **Multi-trace support** - Open multiple traces side-by-side
- **CSV export** - Download query results

**Use cases:**
- Production debugging (find slow operations)
- Cost optimization (identify expensive LLM calls)
- Performance analysis (compare execution times)
- Audit trails (who did what, when)

[**👉 Learn more about tracing**](tracing/index.md)

---

## Best Practices

### ✅ Do

- **Start dashboard early** - Run `serve(dashboard=True)` during development, not just debugging
- **Use auto-layout** - Right-click → Auto Layout for clean visualization with 3+ agents
- **Monitor live output** - Open Agent Details panel to watch LLM token streaming
- **Test from UI** - Use Publish button to test edge cases without code changes
- **Enable tracing** - Set `FLOCK_AUTO_TRACE=true` for production visibility
- **Filter by correlation ID** - Track specific workflows through multi-tenant systems
- **Take screenshots** - Document complex workflows for team communication

### ❌ Don't

- **Don't ignore WebSocket status** - Red "Disconnected" means live updates won't work
- **Don't skip auto-layout** - Manual node positioning is tedious with 3+ agents
- **Don't publish too fast** - Wait for previous cascade to complete before next publish
- **Don't forget time filters** - Old artifacts clutter the graph; filter to recent
- **Don't rely on browser snapshot** - Use screenshots for graphs with 8+ artifacts (token limits)
- **Don't test without dashboard** - You'll miss subtle timing and ordering issues

---

## Troubleshooting

### Dashboard doesn't load

**Symptom:** Browser shows blank page or error

**Check:**
- Server started? Look for "Uvicorn running" in console
- Frontend built? Look for "Production build completed"
- Correct URL? Should be `http://localhost:8344`

**Solution:**
- Wait 5-10 seconds after starting for build to complete
- Check console for build errors
- Verify port 8344 not in use: `lsof -i :8344`

### WebSocket shows "Disconnected"

**Symptom:** Red status indicator in top right

**Check:**
- Server running? Backend must be active
- Console errors? Check browser dev tools
- Firewall blocking? WebSocket uses same port as HTTP

**Solution:**
- Refresh page to reconnect
- Restart server if backend crashed
- Check server logs for WebSocket connection messages

### No live output during execution

**Symptom:** Agent Details panel shows "Idle - no output"

**Check:**
- Panel open? Must open before execution starts
- "Live Output" tab active? Default tab should be selected
- Agent executing? Status should show "running"
- WebSocket connected? Check status indicator

**Solution:**
- Close and reopen Agent Details panel
- Verify WebSocket status is green
- Check console for `[WebSocket] Streaming output` messages

### Artifacts not appearing in Blackboard View

**Symptom:** Agent View shows execution, Blackboard View is empty

**Check:**
- Execution completed? Status should return to "idle"
- Output count increased? Should show `↑ 1` or higher
- Viewing correct time range? Check time filters

**Solution:**
- Switch back to Agent View to verify execution finished
- Clear time filters (might be filtering out recent artifacts)
- Refresh page if artifacts still missing after confirmed execution

### Graph performance degraded

**Symptom:** Slow rendering, laggy interactions with 20+ nodes

**Check:**
- Too many artifacts? Blackboard View can get heavy with 50+ artifacts
- Time filter too wide? "Last 60 minutes" may show too much
- Browser memory? Check dev tools performance tab

**Solution:**
- Apply time filter: "Last 5 minutes"
- Filter by correlation ID to focus on specific workflow
- Switch to Agent View (lighter than Blackboard View)
- Restart dashboard to clear graph state

### Auto-layout not centering correctly

**Symptom:** After auto-layout, graph appears off-screen

**Check:**
- Viewport position before layout? Layout centers around current view
- Too many nodes? 10+ nodes may extend beyond viewport

**Solution:**
- Click "Fit View" button (React Flow controls)
- Zoom out before applying auto-layout
- Try different layout algorithm (Horizontal vs Vertical)

---

## Next Steps

- **[Tracing Guide](tracing/index.md)** - Deep dive into trace viewer features
- **[Visibility Controls](visibility.md)** - Secure multi-tenant dashboard filtering
- **[Agent Guide](agents.md)** - Build agents optimized for dashboard visibility
- **[Examples](https://github.com/whiteducksoftware/flock/tree/main/examples/02-dashboard)** - Working dashboard code

---

## Key Features Summary

**Dual Visualization Modes:**
- Agent View: Focus on agent orchestration
- Blackboard View: Focus on data lineage

**Real-Time Updates:**
- WebSocket streaming with 2-minute heartbeat
- Live status transitions and counter updates
- Token-by-token LLM output streaming

**Interactive Graph:**
- Drag, zoom, pan, and explore
- Double-click for details
- Right-click for context menu with 5 layout algorithms

**Control Panel:**
- Publish artifacts from UI (no code needed)
- Agent Details panel with live streaming
- Manual agent invocation for testing

**Advanced Filtering:**
- Correlation ID tracking
- Time range filtering (5/10/60 minutes or custom)
- Autocomplete search with metadata preview

**Keyboard Shortcuts:**
- `Ctrl+M` - Toggle view mode
- `Ctrl+F` - Focus filter
- `Ctrl+P` - Open Publish dialog
- WCAG 2.1 AA accessible

**Production-Grade Trace Viewer:**
- 7 visualization modes (Timeline, Statistics, RED, Dependencies, SQL, Config, Guide)
- Full I/O capture with JSON viewer
- Multi-trace support with CSV export

---

**Ready to visualize your agents?** Start the dashboard with `await flock.serve(dashboard=True)` or explore [working examples](https://github.com/whiteducksoftware/flock/tree/main/examples/02-dashboard).
