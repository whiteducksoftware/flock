# 📊 Dashboard Examples

Visual interface examples for Flock—the same examples from `01-cli/` but with an interactive web dashboard showing real-time agent execution, artifact flow, and blackboard state.

## 🎯 Why Dashboard Examples?

- **Visual feedback** - See agents, artifacts, and connections in real-time
- **Real-time updates** - WebSocket streaming shows execution as it happens
- **Agent view** - Visualize agent graph, status, input/output counts
- **Blackboard view** - Browse all artifacts with full JSON payloads
- **Perfect for demos** - Show stakeholders how your multi-agent system works
- **Complex workflows** - Easier to understand 5+ agent interactions visually

## 🚀 Quick Start

```bash
# Start any dashboard example
uv run 02-dashboard/01_declarative_pizza.py

# Wait for:
# ✅ "Production build completed"
# ✅ "Uvicorn running on http://127.0.0.1:8344"
# ✅ "Browser launched successfully"

# Dashboard opens automatically in your browser!
```

## 📊 Dashboard Features

### Agent View
- **Visual graph** of all agents and their relationships
- **Live status updates** - see agents go from idle → running → idle
- **Input/Output counters** - track artifacts consumed/produced
- **Edge labels** - show artifact types and counts flowing between agents
- **Auto layout** - right-click canvas for automatic graph organization

### Blackboard View
- **All artifacts** displayed as nodes
- **Full JSON payloads** - browse complete artifact data
- **Producer information** - see which agent created each artifact
- **Timestamps** - track when artifacts were created
- **Data flow visualization** - see how artifacts connect

### Live Output Panel
- **Token-by-token streaming** - watch LLM responses in real-time
- **Message history** - review all agent outputs
- **Run status tracking** - see when agents start and complete
- **Event counter** - track total events processed

### Controls
- **Publish artifacts** - Manually publish to the blackboard via UI form
- **Agent details** - Click agents to see detailed information
- **Filters** - Control what's displayed in the graph
- **Settings** - Customize dashboard behavior

## 🎓 Example Catalog

All examples mirror their CLI counterparts—see `01-cli/README.md` for detailed concept explanations.

### 🔰 Beginner Track

```bash
uv run 02-dashboard/01_declarative_pizza.py      # Your first agent
uv run 02-dashboard/02_input_and_output.py       # Structured I/O
uv run 02-dashboard/03_code_detective.py         # Complex outputs
uv run 02-dashboard/04_input_and_output.py       # Advanced I/O
```

### 🛠️ Tool Integration

```bash
uv run 02-dashboard/05_mcp_and_tools.py          # MCP integration
uv run 02-dashboard/06_mcp_roots.py              # Filesystem security
uv run 02-dashboard/07_web_detective.py          # Multi-tool research
```

### 🔄 Multi-Agent Workflows

```bash
uv run 02-dashboard/08_band_formation.py         # Linear pipeline
uv run 02-dashboard/09_debate_club.py            # Parallel execution
uv run 02-dashboard/10_news_agency.py            # Complex coordination
```

### 🔬 Advanced Features

```bash
uv run 02-dashboard/11_tracing_detective.py      # Observability
uv run 02-dashboard/12_secret_agents.py          # Security controls
```

### 🚀 Expert Track - Logic Operations

```bash
uv run 02-dashboard/13_medical_diagnostics_joinspec.py  # JoinSpec correlation
uv run 02-dashboard/14_ecommerce_batch_processing.py    # BatchSpec batching
uv run 02-dashboard/15_iot_sensor_batching.py           # Combined JoinSpec+BatchSpec
uv run 02-dashboard/16_news_batching.py                 # News batch processing
```

## 💡 Dashboard Tips

### First Time Using the Dashboard?

1. **Start with Example 01** - Simple single-agent workflow
2. **Try publishing** - Use the "Publish" button to send artifacts manually
3. **Click agents** - Open the Agent Details panel to see live output
4. **Switch views** - Toggle between Agent View and Blackboard View
5. **Use auto-layout** - Right-click canvas → Auto Layout for complex graphs

### For Multi-Agent Examples (08-10)

- **Watch status changes** - See agents activate in sequence or parallel
- **Monitor counters** - Input ↓ and output ↑ counts update in real-time
- **Follow edges** - See artifacts flow from producer to consumer
- **External nodes** - Show who published the initial input

### For Complex Examples (13-15)

- **Enable auto-layout** - Essential for 3+ agent workflows
- **Use screenshots** - `browser_take_screenshot()` for visual verification
- **Track filtered consumption** - Edge labels show `Type(consumed/total)`
- **Monitor batch formation** - Watch artifacts accumulate before processing

## 🎨 Visual Guide

### Agent Node Anatomy
```
┌─────────────────────┐
│   agent_name        │ ← Agent identifier
│   Status: idle      │ ← Current state (idle/running)
├─────────────────────┤
│ ↓ 5 InputType       │ ← Artifacts consumed (count)
│ ↑ 3 OutputType      │ ← Artifacts produced (count)
└─────────────────────┘
```

### Status Indicators
- **🟢 Idle** - Agent waiting for work
- **🔵 Running** - Agent currently executing
- **⚪ External** - Source of manually published artifacts

### Edge Labels
- **`Type(5)`** - 5 artifacts of this type
- **`Type(2/5)`** - 2 consumed out of 5 available (filtered consumption)

## 🔍 Testing & Debugging with Dashboard

### Manual Testing Workflow

1. **Start dashboard example**
   ```bash
   uv run 02-dashboard/01_declarative_pizza.py
   ```

2. **Verify initial load**
   - ✅ WebSocket status: "Connected" (green)
   - ✅ Agent nodes visible
   - ✅ Control buttons present

3. **Publish test artifact**
   - Click "Publish" button
   - Select artifact type
   - Fill in fields
   - Click "Publish Artifact"

4. **Monitor execution**
   - Watch agent status change
   - See counters increment
   - View live output in Agent Details panel

5. **Verify results**
   - Switch to Blackboard View
   - Inspect artifact nodes
   - Check payload data

### Common Issues

**Dashboard doesn't load:**
- Wait 5-10 seconds for build to complete
- Check for "Production build completed" message
- Verify port 8344 is available

**WebSocket disconnected:**
- Check console for errors
- Refresh page
- Verify server is still running

**No live output:**
- Ensure Agent Details panel is open
- Check "Live Output" tab is active
- Verify WebSocket connection status

## 📈 Performance Notes

### Execution Times
- **Simple examples (01-07):** ~5-10 seconds
- **Multi-agent (08-10):** ~15-30 seconds
- **Expert examples (13-16):** ~30-60 seconds (depending on batch/join parameters)

### Browser Limits
- **8+ artifacts:** Use `browser_take_screenshot()` instead of `browser_snapshot()`
- **Large payloads:** May cause UI slowdown; use filters

## 🎯 When to Use Dashboard vs CLI?

| Use Case | CLI | Dashboard |
|----------|-----|-----------|
| Learning basics | ✅ | ✅ |
| Debugging single agent | ✅ | |
| Understanding multi-agent flow | | ✅ |
| Demo to stakeholders | | ✅ |
| Production monitoring | | ✅ |
| Quick iteration | ✅ | |
| Complex visualization | | ✅ |

## 📚 Related Resources

- **01-cli/** - Same examples with console output (better for learning)
- **03-claudes-workshop/** - Structured course with dashboard examples
- **04-misc/** - Advanced dashboard features (persistence, scale testing)
- **AGENTS.md** - Dashboard testing guide (search "How do I test UI features")

## 🆘 Getting Help

**Dashboard-specific issues:**
1. Check browser console (F12) for errors
2. Look for WebSocket connection messages
3. Verify server logs in terminal
4. Review AGENTS.md dashboard testing section
5. Try the CLI version to isolate issues

---

**Ready to visualize your agents? Start with example 01! 🚀**
