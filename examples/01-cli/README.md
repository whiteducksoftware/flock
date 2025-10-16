# 💻 CLI Examples

Command-line interface examples for Flock—perfect for learning, debugging, and understanding what's happening under the hood. Each example runs in your terminal with detailed console output.

## 🎯 Why CLI Examples?

- **See detailed logs** - Watch agent execution in real-time
- **Understand behavior** - Console output shows exactly what's happening
- **Easy debugging** - Add print statements, inspect data
- **Fast iteration** - No browser startup time
- **Perfect for learning** - Follow along with code and output together

## 🎓 Learning Path

The examples are ordered by complexity. Start at 01 and work your way up!

### 🔰 Beginner Track (Examples 01-04)

#### 01 - Declarative Pizza 🍕
Your first Flock agent! One agent, one task, pure magic.

```bash
uv run 01-cli/01_declarative_pizza.py
```

**Concepts:** Agent creation, basic publishing, type-safe contracts

---

#### 02 & 04 - Input and Output 📝
Learn structured data with Pydantic models.

```bash
uv run 01-cli/02_input_and_output.py
uv run 01-cli/04_input_and_output.py  # Advanced version
```

**Concepts:** Custom message types, validation, structured transformation

---

#### 03 - Code Detective 🔍
Complex structured outputs with rich nested data.

```bash
uv run 01-cli/03_code_detective.py
```

**Concepts:** Complex Pydantic models, real-world structured analysis

---

### 🛠️ Tool Integration (Examples 05-07)

#### 05 - MCP and Tools 🛠️
Connect agents to external tools via Model Context Protocol.

```bash
uv run 01-cli/05_mcp_and_tools.py
```

**Concepts:** MCP integration, tool usage, extending agent capabilities

---

#### 06 - MCP Roots 📂
Control filesystem access boundaries for security.

```bash
uv run 01-cli/06_mcp_roots.py
```

**Concepts:** MCP configuration, security boundaries, custom server options

---

#### 07 - Web Detective 🌐
Multi-tool research agent combining web search and file operations.

```bash
uv run 01-cli/07_web_detective.py
```

**Concepts:** Multiple MCP servers, tool orchestration, research workflows

---

### 🔄 Multi-Agent Workflows (Examples 08-10)

#### 08 - Band Formation 🎸
Linear pipeline: recruiter → audition → band manager.

```bash
uv run 01-cli/08_band_formation.py
```

**Concepts:** Agent chaining, linear workflows, message passing

---

#### 09 - Debate Club 🗣️
Parallel execution with pro, con, and judge agents.

```bash
uv run 01-cli/09_debate_club.py
```

**Concepts:** Parallel agents, consensus building, multiple consumers

---

#### 10 - News Agency 📰
Complex coordination with reporter, editor, and publisher.

```bash
uv run 01-cli/10_news_agency.py
```

**Concepts:** Multi-input agents, complex workflows, real-world modeling

---

### 🔬 Advanced Features (Examples 11-12)

#### 11 - Tracing Detective 🔬
Observability and debugging with traced runs.

```bash
uv run 01-cli/11_tracing_detective.py
```

**Concepts:** `traced_run()`, execution tracing, debugging multi-agent systems

**After running:** Explore `.flock/traces.duckdb` to see captured execution data!

---

#### 12 - Secret Agents 🕵️
Security controls with visibility boundaries.

```bash
uv run 01-cli/12_secret_agents.py
```

**Concepts:** `Visibility.PRIVATE`, `Visibility.PUBLIC`, security boundaries, classified data

---

### 🚀 Expert Track - Logic Operations (Examples 13-15)

#### 13 - Medical Diagnostics (JoinSpec) 🏥
Correlate related artifacts before processing.

```bash
uv run 01-cli/13_medical_diagnostics_joinspec.py
```

**Concepts:**
- **JoinSpec** - Correlate artifacts by common key
- Time-windowed matching (`within=timedelta(minutes=5)`)
- AND-gate pattern (wait for multiple inputs)
- Order-independent correlation

**Real-world use case:** Hospital system correlating X-rays with lab results by patient ID

---

#### 14 - E-commerce Batch Processing 📦
Efficient batch operations for performance.

```bash
uv run 01-cli/14_ecommerce_batch_processing.py
```

**Concepts:**
- **BatchSpec** - Collect and process artifacts in batches
- Size-based triggers (`max_size=10`)
- Time-based triggers (`max_wait=timedelta(seconds=30)`)
- Cost optimization through batching

**Real-world use case:** Payment processing system batching transactions for efficiency

---

#### 15 - IoT Sensor Batching 📡
Combine JoinSpec + BatchSpec for production-grade patterns.

```bash
uv run 01-cli/15_iot_sensor_batching.py
```

**Concepts:**
- **Combined operations** - JoinSpec + BatchSpec together
- Multi-stage correlation and batching
- IoT sensor monitoring at scale
- Production-ready patterns

**Real-world use case:** Smart factory correlating temperature/pressure/vibration sensors, then batching for analysis

---

## 🎯 Quick Reference

### Run All Examples
```bash
# Basic examples
uv run 01-cli/01_declarative_pizza.py
uv run 01-cli/02_input_and_output.py
uv run 01-cli/03_code_detective.py

# Tool integration
uv run 01-cli/05_mcp_and_tools.py
uv run 01-cli/06_mcp_roots.py
uv run 01-cli/07_web_detective.py

# Multi-agent
uv run 01-cli/08_band_formation.py
uv run 01-cli/09_debate_club.py
uv run 01-cli/10_news_agency.py

# Advanced
uv run 01-cli/11_tracing_detective.py
uv run 01-cli/12_secret_agents.py

# Expert - Logic Operations
uv run 01-cli/13_medical_diagnostics_joinspec.py
uv run 01-cli/14_ecommerce_batch_processing.py
uv run 01-cli/15_iot_sensor_batching.py
```

## 💡 Tips

1. **Read the source code** - Each example is intentionally minimal and well-commented
2. **Run in order** - Each builds on concepts from previous examples
3. **Experiment** - Modify examples to understand behavior
4. **Enable tracing** - Set `FLOCK_AUTO_TRACE=true` to see execution details
5. **Check output** - Pay attention to console logs showing agent execution

## 🔍 Debugging Tips

### Enable Detailed Tracing
```bash
# Before running examples
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true

# Run example
uv run 01-cli/11_tracing_detective.py

# Query traces
python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)
traces = conn.execute('''
    SELECT name, duration_ms, status_code
    FROM spans ORDER BY start_time DESC LIMIT 10
''').fetchall()
for t in traces:
    print(f'{t[0]}: {t[1]:.0f}ms - {t[2]}')
"
```

## 📊 Complexity Progression

```
Simple → Complex
Single Agent → Multi-Agent
Synchronous → Parallel
Basic → Tool Integration
Local → Secured
Sequential → Correlated → Batched
```

## 🎓 Next Steps

After completing CLI examples:
1. **Try Dashboard versions** in `02-dashboard/` - Visualize the same workflows
2. **Take the Workshop** in `03-claudes-workshop/` - Structured learning path
3. **Explore Advanced** - Check `05-engines/`, `06-agent-components/`, `07-orchestrator-components/`

## 📚 Related Resources

- **02-dashboard/** - Same examples with visual interface
- **03-claudes-workshop/** - Structured course with detailed lessons
- **00-patterns/** - Publishing pattern reference
- **AGENTS.md** - Complete development guide

---

**Happy learning! 🦆**
