# 🦆 Flock Examples

Welcome to the Flock examples! This directory contains a carefully curated learning path that takes you from your first "Hello World" agent to advanced multi-agent systems with security controls.

## 📁 Two Flavors: CLI and Dashboard

Each example comes in **two versions**:

- **`01-cli/`** - Run examples from the command line with detailed console output
- **`02-dashboard/`** - Launch the interactive web dashboard to visualize agent execution

Both versions demonstrate the same concepts, just with different interfaces. Start with CLI to see what's happening under the hood, then switch to dashboard to visualize complex multi-agent interactions.

## 🎓 Learning Path

The examples are ordered by complexity. Start at `01` and work your way up!

### 01 - Declarative Pizza 🍕
**Concept**: Your first Flock agent - declarative agent creation

The simplest possible Flock application. One agent, one task, pure magic. Shows you how to:
- Create a Flock orchestrator
- Define an agent declaratively
- Publish a message and let the agent handle it

**Run it**:
```bash
# CLI version
uv run examples/01-cli/01_declarative_pizza.py

# Dashboard version
uv run examples/02-dashboard/01_declarative_pizza.py
```

---

### 02 - Input and Output 📝
**Concept**: Structured data with Pydantic models

Learn how to use Pydantic models for type-safe input and output. Shows you:
- Defining custom message types with `@flock_type`
- Simple request/response pattern
- Type validation and structured data

**Run it**:
```bash
uv run examples/01-cli/02_input_and_output.py
uv run examples/02-dashboard/02_input_and_output.py
```

---

### 03 - Code Detective 🔍
**Concept**: Complex structured outputs

A bug diagnosis agent that outputs detailed structured analysis. Demonstrates:
- Rich Pydantic models with nested data
- Field descriptions and constraints
- Real-world structured output patterns

**Run it**:
```bash
uv run examples/01-cli/03_code_detective.py
uv run examples/02-dashboard/03_code_detective.py
```

---

### 04 - Input and Output (Advanced) 📊
**Concept**: Multi-field structured data

More complex input/output patterns with multiple fields and validation. Shows:
- Advanced Pydantic field types
- Validation constraints
- Complex data transformation patterns

**Run it**:
```bash
uv run examples/01-cli/04_input_and_output.py
uv run examples/02-dashboard/04_input_and_output.py
```

---

### 05 - MCP and Tools 🛠️
**Concept**: MCP (Model Context Protocol) integration

Connect your agents to external tools and capabilities. Demonstrates:
- Enabling MCP servers
- Tool usage in agents
- Extending agent capabilities beyond pure LLM reasoning

**Run it**:
```bash
uv run examples/01-cli/05_mcp_and_tools.py
uv run examples/02-dashboard/05_mcp_and_tools.py
```

---

### 06 - MCP Roots 📂
**Concept**: Advanced MCP configuration with filesystem access

Control what parts of your filesystem agents can access. Shows:
- MCP server configuration with roots
- Filesystem security boundaries
- Custom MCP server options

**Run it**:
```bash
uv run examples/01-cli/06_mcp_roots.py
uv run examples/02-dashboard/06_mcp_roots.py
```

---

### 07 - Web Detective 🌐
**Concept**: MCP + Tools working together

A research agent that combines web search with file tools. Demonstrates:
- Multiple MCP servers in one application
- Agents using different tools in concert
- Real-world research workflow

**Run it**:
```bash
uv run examples/01-cli/07_web_detective.py
uv run examples/02-dashboard/07_web_detective.py
```

---

### 08 - Band Formation 🎸
**Concept**: Linear multi-agent pipeline

Three agents working in sequence: recruiter → audition → band manager. Shows:
- Agent-to-agent communication
- Linear workflow pipelines
- Message passing between agents

**Run it**:
```bash
uv run examples/01-cli/08_band_formation.py
uv run examples/02-dashboard/08_band_formation.py
```

---

### 09 - Debate Club 🗣️
**Concept**: Parallel agent execution

Three agents working simultaneously: debater_pro, debater_con, and judge. Demonstrates:
- Parallel agent activation
- Multiple agents consuming the same message type
- Consensus building patterns

**Run it**:
```bash
uv run examples/01-cli/09_debate_club.py
uv run examples/02-dashboard/09_debate_club.py
```

---

### 10 - News Agency 📰
**Concept**: Complex multi-agent pipeline with multiple inputs

A news organization with reporter, editor, and publisher. Shows:
- Agents consuming multiple message types
- Complex coordination patterns
- Real-world workflow modeling

**Run it**:
```bash
uv run examples/01-cli/10_news_agency.py
uv run examples/02-dashboard/10_news_agency.py
```

---

### 11 - Tracing Detective 🔬
**Concept**: Observability with traced runs

Track and debug your multi-agent workflows. Demonstrates:
- Using `flock.traced_run()` for observability
- Execution tracing
- Debugging complex agent interactions
- Trace storage in `.flock/traces.duckdb`

**Run it**:
```bash
uv run examples/01-cli/11_tracing_detective.py
uv run examples/02-dashboard/11_tracing_detective.py
```

---

### 12 - Secret Agents 🕵️
**Concept**: Visibility controls for sensitive data

Intelligence agency with classified and public information flows. Shows:
- `Visibility.PRIVATE` for sensitive data
- `Visibility.PUBLIC` for shareable information
- Security boundaries in multi-agent systems
- Protecting classified information while sharing public statements

**Run it**:
```bash
uv run examples/01-cli/12_secret_agents.py
uv run examples/02-dashboard/12_secret_agents.py
```

---

## 🚀 Quick Start

1. **Install Flock**:
   ```bash
   uv pip install -e .
   ```

2. **Pick an example** (start with 01):
   ```bash
   uv run examples/01-cli/01_declarative_pizza.py
   ```

3. **Try the dashboard version**:
   ```bash
   uv run examples/02-dashboard/01_declarative_pizza.py
   ```

4. **Work through the examples in order** - each builds on concepts from the previous ones!

## 💡 Tips

- **Start with CLI** - See detailed output and understand what's happening
- **Switch to Dashboard** - Visualize complex multi-agent interactions
- **Read the code** - Each example is intentionally minimal and well-commented
- **Experiment** - Modify examples to see how Flock responds
- **Check traces** - After running example 11, explore `.flock/traces.duckdb`

## 🎯 Key Concepts Progression

```
Simple → Complex
Single Agent → Multi-Agent
Synchronous → Parallel
Unstructured → Structured
Local → External Tools
Open → Secured
```

## 📚 Next Steps

After completing these examples, you're ready to:
- Build your own multi-agent systems
- Integrate custom MCP servers
- Design complex agent workflows
- Implement security controls
- Debug with tracing

**Happy building! 🦆**
