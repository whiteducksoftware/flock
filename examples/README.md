# 🦆 Flock Showcase 🦆

Welcome to the Flock examples repository! This carefully curated collection takes you from your first "Hello World" agent to advanced multi-agent systems with production-grade patterns.

## 📁 Repository Structure

### 🏗️ Core Learning Path

Start here for a systematic introduction to Flock:

#### **`00-patterns/`** - Publishing Patterns Reference
Quick-reference examples showing different ways agents publish to the blackboard:
- Single publish (1 input → 1 output)
- Multi-publish (1 input → multiple types)
- Fan-out (1 input → multiple instances)
- Multi fan-out (1 input → multiple instances of multiple types)

👉 **[View Publishing Patterns Guide →](00-patterns/README.md)**

#### **`01-cli/`** - Interactive CLI Examples (15 examples)
Command-line examples with detailed console output. Perfect for learning and debugging:
- 🔰 Beginner: Single agents, structured I/O
- 🛠️ Tool Integration: MCP servers, filesystem access
- 🔄 Multi-Agent: Pipelines, parallel execution
- 🔬 Advanced: Tracing, security controls
- 🚀 Expert: JoinSpec, BatchSpec, combined operations

👉 **[View CLI Examples Guide →](01-cli/README.md)**

#### **`02-dashboard/`** - Visual Dashboard Examples (16 examples)
Same examples as CLI but with interactive web interface:
- Real-time agent execution visualization
- Live WebSocket streaming
- Agent and blackboard views
- Manual artifact publishing via UI

👉 **[View Dashboard Examples Guide →](02-dashboard/README.md)**

---

### 🎓 Structured Learning

#### **`03-claudes-workshop/`** - Complete Workshop Course (13 lessons)
Structured course from beginner to expert with hands-on lessons:
- **Beginner Track** - First agent, chaining, structured output
- **Intermediate Track** - Conditional consumption, feedback loops, tracing
- **Advanced Track** - Security, parallel execution
- **Expert Track** - JoinSpec correlation, BatchSpec batching, combined features
- **Architecture Track** - Components, engines, extensibility

👉 **[View Workshop Guide →](03-claudes-workshop/README.md)**

---

### 🧩 Advanced Features

#### **`04-misc/`** - Production Features (5 examples)
Advanced capabilities and specialized use cases:
- **Persistent storage** - SQLite blackboard for audit trails
- **Dashboard edge cases** - Complex multi-agent testing scenarios
- **Scale testing** - 100+ agent orchestration
- **LM Studio** - Using local LLMs

👉 **[View Advanced Features Guide →](04-misc/README.md)**

#### **`05-engines/`** - Custom Processing Logic (2 examples)
Deterministic business logic without LLM calls:
- **Zero-cost operations** - Rule-based processing
- **Hybrid architectures** - Mix LLM and deterministic logic
- **Pattern matching** - Regex, keywords, calculations

👉 **[View Custom Engines Guide →](05-engines/README.md)**

#### **`06-agent-components/`** - Per-Agent Extensions (2 examples)
Extend individual agents with lifecycle hooks:
- **Quality gates** - Validation and filtering
- **Metrics tracking** - Per-agent KPIs
- **State injection** - Dynamic behavior modification

👉 **[View Agent Components Guide →](06-agent-components/README.md)**

#### **`07-orchestrator-components/`** - Global Coordination (2 examples)
System-wide monitoring and coordination:
- **Operational dashboards** - Real-time status boards
- **Alerting** - Threshold-based notifications
- **Cross-agent correlation** - Track workflows system-wide

👉 **[View Orchestrator Components Guide →](07-orchestrator-components/README.md)**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ with UV package manager
- OpenAI API key (or LM Studio for local models)
- Node.js 18+ for dashboard examples

### Installation

```bash
# Clone and enter repository
cd flock-showcase

# Install dependencies
uv pip install flock-flow

# Set up environment
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"

# Verify installation
uv run python -c "from flock import Flock; print('✅ Ready!')"
```

### Your First Example

```bash
# Start with the simplest example
uv run 01-cli/01_declarative_pizza.py

# Try the dashboard version
uv run 02-dashboard/01_declarative_pizza.py

# Or dive into the workshop
uv run 03-claudes-workshop/lesson_01_code_detective.py
```

---

## 🎯 Recommended Learning Paths

### Path 1: Quick Start (1-2 hours)
Perfect for getting a feel for Flock:

1. **Publishing Patterns** - `00-patterns/` (15 min)
2. **First CLI Example** - `01-cli/01_declarative_pizza.py` (5 min)
3. **Dashboard Version** - `02-dashboard/01_declarative_pizza.py` (10 min)
4. **Multi-Agent** - `01-cli/08_band_formation.py` (15 min)
5. **Advanced Features** - `01-cli/13_medical_diagnostics_joinspec.py` (20 min)

### Path 2: Comprehensive Workshop (6-8 hours)
For deep understanding:

1. **Workshop Lessons 01-04** - Fundamentals (1.5 hours)
2. **Workshop Lessons 05-07** - Advanced patterns (2 hours)
3. **Workshop Lessons 08-10** - Expert logic operations (2.5 hours)
4. **Workshop Lessons 11-13** - Architecture & extensibility (2 hours)

### Path 3: Production Patterns (3-4 hours)
For building real systems:

1. **CLI Examples 01-07** - Core patterns (1 hour)
2. **Persistent Storage** - `04-misc/01_persistent_pizza.py` (30 min)
3. **Custom Engines** - `05-engines/` (45 min)
4. **Components** - `06-agent-components/` + `07-orchestrator-components/` (1.5 hours)

---

## 📊 Example Catalog by Feature

### Single Agent Patterns
- `01-cli/01_declarative_pizza.py` - Simplest example
- `01-cli/02_input_and_output.py` - Structured I/O
- `01-cli/03_code_detective.py` - Complex outputs

### Multi-Agent Coordination
- `01-cli/08_band_formation.py` - Linear pipeline
- `01-cli/09_debate_club.py` - Parallel execution
- `01-cli/10_news_agency.py` - Complex coordination

### Tool Integration (MCP)
- `01-cli/05_mcp_and_tools.py` - Basic MCP
- `01-cli/06_mcp_roots.py` - Filesystem boundaries
- `01-cli/07_web_detective.py` - Multi-tool orchestration

### Advanced Logic Operations
- `01-cli/13_medical_diagnostics_joinspec.py` - JoinSpec (correlation)
- `01-cli/14_ecommerce_batch_processing.py` - BatchSpec (batching)
- `01-cli/15_iot_sensor_batching.py` - Combined JoinSpec + BatchSpec

### Observability & Security
- `01-cli/11_tracing_detective.py` - Distributed tracing
- `01-cli/12_secret_agents.py` - Visibility controls

### Publishing Patterns
- `00-patterns/01-single_publish.py` - One output
- `00-patterns/02-multi_publish.py` - Multiple types
- `00-patterns/04-fan-out.py` - Multiple instances
- `00-patterns/05-multi-fan-out.py` - Maximum creativity

### Production Features
- `04-misc/01_persistent_pizza.py` - SQLite storage
- `04-misc/03-scale-test-100-agents.py` - Scale testing
- `04-misc/05_lm_studio.py` - Local LLMs

### Extensibility
- `05-engines/emoji_mood_engine.py` - Deterministic logic
- `06-agent-components/cheer_meter_component.py` - Per-agent hooks
- `07-orchestrator-components/kitchen_monitor_component.py` - Global monitoring

---

## 💡 Tips for Success

### Learning Tips
- **Start simple** - Begin with `01-cli/01_declarative_pizza.py`
- **Read the code** - Examples are intentionally minimal and well-commented
- **Try both interfaces** - CLI for learning, Dashboard for visualization
- **Enable tracing** - Set `FLOCK_AUTO_TRACE=true` to see what's happening
- **Experiment** - Modify examples to understand behavior

### Development Tips
- **Use the workshop** - `03-claudes-workshop/` has detailed lessons
- **Check folder READMEs** - Each folder has comprehensive guides
- **Review patterns** - `00-patterns/` for publishing reference
- **Study components** - Learn extensibility patterns

### Debugging Tips
- **Enable tracing** - `export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true`
- **Query trace DB** - Explore `.flock/traces.duckdb` after running
- **Use CLI first** - Console output shows exactly what's happening
- **Check AGENTS.md** - Complete debugging guide in main Flock repo

---

## 🎓 Key Concepts Progression

```
Publishing Patterns → Single Agent → Multi-Agent → Tools → Logic Operations
    ↓                      ↓              ↓           ↓           ↓
Simple Outputs      Structured I/O   Pipelines    MCP      JoinSpec/Batch
Fan-out             Complex Models   Parallel     Tools    Correlation
Multi-publish       Validation       Feedback     API      Batching
```

```
Observability → Security → Storage → Extensibility
     ↓              ↓          ↓           ↓
 Tracing      Visibility  SQLite     Engines
 Debugging    Private     Audit      Components
 Metrics      Labels      Replay     Hybrid Logic
```

---

## 📚 Additional Resources

### Documentation
- **[AGENTS.md](AGENTS.md)** - Complete AI agent development guide
- **[Main Flock Repo](https://github.com/whiteducksoftware/flock)** - Framework source
- **[Official Docs](https://whiteducksoftware.github.io/flock/)** - Comprehensive guides

### Folder READMEs
Each folder has its own detailed guide:
- [Publishing Patterns](00-patterns/README.md)
- [CLI Examples](01-cli/README.md)
- [Dashboard Examples](02-dashboard/README.md)
- [Workshop Course](03-claudes-workshop/README.md)
- [Advanced Features](04-misc/README.md)
- [Custom Engines](05-engines/README.md)
- [Agent Components](06-agent-components/README.md)
- [Orchestrator Components](07-orchestrator-components/README.md)

---

## 🆘 Getting Help

### Common Questions
- **"Where do I start?"** → `01-cli/01_declarative_pizza.py`
- **"How do I visualize?"** → `02-dashboard/` examples
- **"Want structured learning?"** → `03-claudes-workshop/`
- **"Need production patterns?"** → `04-misc/` + components folders

### Troubleshooting
1. Check the folder README for specific guidance
2. Enable tracing: `export FLOCK_AUTO_TRACE=true`
3. Review AGENTS.md debugging section
4. Compare CLI vs Dashboard output
5. Open GitHub issue with details

---

## 🎯 What's Next?

After completing these examples, you'll be ready to:
- ✅ Build production multi-agent systems
- ✅ Integrate external tools via MCP
- ✅ Implement advanced logic operations (joins, batching)
- ✅ Add observability and security
- ✅ Extend with custom components and engines
- ✅ Scale to 100+ agents

**Ready to start? Pick your learning path above! 🚀**

---

*This is a showcase repository for [Flock](https://github.com/whiteducksoftware/flock) - a production-grade blackboard-first AI agent orchestration framework.*
