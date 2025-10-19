# Getting Started

Welcome to Flock! This directory contains 15 comprehensive examples that cover all core concepts, from basic agent definitions to advanced features like JoinSpec and BatchSpec.

## 🎛️ Configuration: CLI vs Dashboard Mode

**All examples in this directory can run in two modes** by setting the `USE_DASHBOARD` flag at the top of each file:

```python
# At the top of each example file:
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
```

### CLI Mode (`USE_DASHBOARD = False`)
- **Best for**: Learning, scripting, integration testing
- **Output**: Terminal output with results
- **Speed**: Instant execution and results
- **Use when**: You want quick feedback and are experimenting

### Dashboard Mode (`USE_DASHBOARD = True`)
- **Best for**: Visualization, debugging, understanding flow
- **Output**: Interactive web UI at `http://localhost:8344`
- **Speed**: Starts a server and waits for interactions
- **Use when**: You want to visualize agent execution and data flow

## 📚 Examples

### Basic Concepts (01-04)

| Example | Focus | What You'll Learn |
|---------|-------|-------------------|
| **01_declarative_pizza.py** | Core concept | Agent declaration, `consumes()`, `publishes()`, `fan_out` |
| **02_input_and_output.py** | I/O handling | Type definitions, structured input/output, field descriptions |
| **03_code_detective.py** | Analysis workflows | Processing multiple inputs, extracting structured insights |
| **04_movie_generation.py** | Complex types | Nested models, validation rules, Pydantic constraints |

### Integration & Tools (05-07)

| Example | Focus | What You'll Learn |
|---------|-------|-------------------|
| **05_mcp_and_tools.py** | MCP integration | Adding external tools, web search, file I/O |
| **06_mcp_roots.py** | MCP filesystem | Filesystem access with roots feature, directory exploration |
| **07_web_detective.py** | Multi-agent chains | Agent pipelines, one agent consuming from another |

### Advanced Workflows (08-12)

| Example | Focus | What You'll Learn |
|---------|-------|-------------------|
| **08_band_formation.py** | Multi-step pipeline | Agents in sequence, each consuming previous output |
| **09_debate_club.py** | Conditional logic | `where` clauses, conditional subscriptions, feedback loops |
| **10_news_agency.py** | Real-world simulation | Realistic workflows with roles, approvals, distribution |
| **11_tracing_detective.py** | Debugging & tracing | `traced_run()`, execution history, debugging techniques |
| **12_secret_agents.py** | Access control | Visibility controls (PUBLIC, PRIVATE, CLASSIFIED) |

### Advanced Features (13-16)

| Example | Focus | What You'll Learn |
|---------|-------|-------------------|
| **13_medical_diagnostics_joinspec.py** | JoinSpec | Correlating multiple types by key, waiting for both |
| **14_ecommerce_batch_processing.py** | BatchSpec | Grouping artifacts for cost optimization |
| **15_iot_sensor_batching.py** | JoinSpec + BatchSpec | Combining features for complex real-world scenarios |
| **16_news_batching.py** | Parallel + Batch | Multiple agents in parallel with batch aggregation |

## 🚀 Quick Start

### 1. Run in CLI Mode (Recommended for First Time)

```bash
# Try the first example
uv run python 01_declarative_pizza.py

# Try the band formation workflow
uv run python 08_band_formation.py
```

### 2. Run in Dashboard Mode

```bash
# Edit the file to enable dashboard
# USE_DASHBOARD = True

# Run with dashboard
uv run python 01_declarative_pizza.py

# Open browser to http://localhost:8344
```

### 3. Experiment

- **Modify inputs**: Change the pizza idea, debate topic, or research query
- **Switch modes**: Try the same example in both CLI and Dashboard modes
- **Combine features**: Look at how 08_band_formation uses multiple agents together
- **Add tools**: See how 05_mcp_and_tools integrates external functionality

## 📖 Learning Path

**Recommended order for learning:**

1. Start with `01_declarative_pizza.py` - understand basic agent structure
2. Try `02_input_and_output.py` - learn about types and communication
3. Run `08_band_formation.py` in dashboard mode - visualize the workflow
4. Explore `09_debate_club.py` - see conditional logic in action
5. Try `13_medical_diagnostics_joinspec.py` - understand correlations
6. Finally `15_iot_sensor_batching.py` - combine everything

## 💡 Tips

### Switching Between Modes

```python
# Before running, edit the file:
USE_DASHBOARD = False  # CLI mode
# or
USE_DASHBOARD = True   # Dashboard mode with web UI
```

### CLI Output Tips

- Most examples print results to terminal
- Some save files to `.flock/` directory
- Tracing data stored in `.flock/traces.duckdb`

### Dashboard Tips

- Agent status shows as: idle → running → idle
- Input/Output counts increment as data flows
- Use "Blackboard View" to inspect artifact data
- Auto-layout available on agent graph (right-click → Auto Layout)
- WebSocket shows "Connected" when working properly

## 🔧 Troubleshooting

### MCPs Not Working

Some examples (05, 06, 07) require external MCPs:

```bash
# Install prerequisites
pip install uvx npm  # or their equivalents

# Or skip MCP examples initially and come back later
```

### Dashboard Won't Load

- Check if server started: `INFO: Uvicorn running on http://127.0.0.1:8344`
- Wait for frontend build: `[Dashboard] Production build completed`
- Clear browser cache and refresh

### Agents Not Executing

- Check dashboard shows agents connected
- Verify subscription types match (input type must match publish type)
- Enable tracing to debug: `FLOCK_AUTO_TRACE=true`

## 📚 Next Steps

After mastering these examples:

- **Advanced patterns**: Check `../00-patterns/` for specialized patterns
- **Engines**: See `../05-engines/` for custom processing logic
- **Components**: Explore `../06-agent-components/` and `../07-orchestrator-components/`
- **Production**: Review `../04-misc/` for production deployment examples

---

**Pro Tip**: Switch any example to `USE_DASHBOARD = True` to visualize what's happening! 🎛️
