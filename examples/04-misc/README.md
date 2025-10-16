# 🧪 Miscellaneous Examples

Advanced features, experimental patterns, and specialized use cases that don't fit neatly into other categories. These examples showcase production-ready features and edge cases.

## 🎯 What's Inside

This folder contains:
- **Persistent storage** - SQLite blackboard for audit trails
- **Edge case handling** - Complex scenarios for testing dashboard
- **Scale testing** - 100+ agent orchestration
- **Alternative LLMs** - Using local models with LM Studio

## 📚 Examples

### 01 - Persistent Pizza 🗄️
**Feature:** SQLite-backed blackboard for durable artifact storage

Store all artifacts to disk for auditability, compliance, and debugging. Perfect for production systems that need:
- Full historical trail of agent activity
- Compliance and audit requirements
- Post-mortem debugging
- Replay capabilities

```bash
uv run 04-misc/01_persistent_pizza.py
```

**Key Feature:** All artifacts stored in `.flock/examples/pizza_history.db`

**Concepts:**
- `SQLiteBlackboardStore` for persistence
- `store.ensure_schema()` for DB initialization
- Durable artifact history
- Production-ready storage patterns

**Use Cases:**
- Financial services (audit trails)
- Healthcare (compliance requirements)
- Enterprise systems (governance)
- Post-mortem analysis

---

### 02 - Dashboard Edge Cases 🎨
**Feature:** Complex multi-agent scenarios for dashboard testing

Advanced dashboard testing scenario with:
- 3+ agents in cascading workflows
- Conditional consumption with `where` filters
- Feedback loops
- Multiple artifact types
- High artifact counts (8+ artifacts)

```bash
uv run 04-misc/02-dashboard-edge-cases.py
```

**Key Features:**
- **Filtered consumption** - Agents consume only matching artifacts
- **Feedback loops** - Agents can re-process based on quality
- **Auto-layout testing** - Complex graphs need auto-organization
- **High-volume testing** - Tests dashboard with many artifacts

**Dashboard Tips:**
- Use right-click → Auto Layout for clean visualization
- Use `browser_take_screenshot()` instead of `browser_snapshot()` (8+ artifacts exceed token limit)
- Watch filtered edge labels show `Type(consumed/total)` counts

---

### 03 - Scale Test (100 Agents) 🚀
**Feature:** Stress test orchestrator with 100+ agents

Validate Flock's scalability with:
- 100 agents in one orchestrator
- Parallel agent execution
- Large-scale blackboard operations
- Performance benchmarking

```bash
uv run 04-misc/03-scale-test-100-agents.py
```

**What It Tests:**
- Orchestrator performance at scale
- Memory usage with many agents
- Blackboard efficiency
- Dashboard rendering limits

**Expected Results:**
- All agents execute successfully
- No memory leaks
- Reasonable execution time
- Dashboard remains responsive

**Use Cases:**
- Production capacity planning
- Performance benchmarking
- Architecture validation
- Load testing

---

### 04 - Persistent Pizza Dashboard 📊
**Feature:** Dashboard with persistent storage

Combines SQLite persistence with dashboard visualization:
- Historical artifact browsing
- Persistent blackboard state
- Audit trail visualization
- Time-travel debugging

```bash
uv run 04-misc/04_persistent_pizza_dashboard.py
```

**Key Features:**
- Dashboard shows all historical artifacts
- Artifacts survive application restarts
- Full audit trail visible in UI
- Production monitoring patterns

**Use Cases:**
- Production monitoring
- Historical analysis
- Compliance dashboards
- Debug sessions

---

### 05 - LM Studio 🤖
**Feature:** Using local LLMs with LM Studio

Run Flock with locally-hosted models via LM Studio:
- No API costs
- Complete data privacy
- Custom/fine-tuned models
- Offline operation

```bash
# First: Start LM Studio on port 1234
# Then:
export OPENAI_BASE_URL="http://localhost:1234/v1"
uv run 04-misc/05_lm_studio.py
```

**Setup:**
1. Install LM Studio
2. Download a model (e.g., Llama 3)
3. Start local server on port 1234
4. Set `OPENAI_BASE_URL` environment variable
5. Run example with custom model name

**Concepts:**
- Custom LLM endpoints
- Local model integration
- OpenAI-compatible API
- Model selection

**Use Cases:**
- Cost optimization (no API fees)
- Data privacy requirements
- Custom/fine-tuned models
- Air-gapped environments
- Development without internet

---

## 🎓 When to Use These Examples

| Example | Use Case |
|---------|----------|
| **01 - Persistent Pizza** | Need audit trails, compliance, replay |
| **02 - Edge Cases** | Testing dashboard with complex scenarios |
| **03 - Scale Test** | Validate architecture at 100+ agents |
| **04 - Dashboard + Persistence** | Production monitoring setup |
| **05 - LM Studio** | Local LLMs, privacy, cost optimization |

## 🔑 Key Features Demonstrated

### Persistent Storage
- SQLite-backed blackboard
- Schema management
- Historical queries
- Retention policies

### Scale & Performance
- 100+ agent orchestration
- Parallel execution
- Memory efficiency
- Dashboard rendering

### Alternative LLMs
- Custom endpoints
- Local models
- OpenAI-compatible APIs
- Model flexibility

### Advanced Dashboard Testing
- Complex multi-agent graphs
- Auto-layout usage
- High artifact volumes
- Filtered consumption visualization

## 💡 Production Patterns

These examples showcase production-ready patterns:

### Persistence Pattern
```python
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(".flock/history.db")
await store.ensure_schema()
flock = Flock("openai/gpt-4.1", store=store)

# All artifacts now persisted!
```

### Custom LLM Pattern
```python
# Point to local LLM server
import os
os.environ["OPENAI_BASE_URL"] = "http://localhost:1234/v1"

flock = Flock("openai/your-model-name")
```

### Scale Testing Pattern
```python
# Register many agents programmatically
for i in range(100):
    flock.agent(f"agent_{i}").consumes(Input).publishes(Output)

# Test parallel execution
await flock.publish_many([Input() for _ in range(100)])
await flock.run_until_idle()
```

## 🚀 Next Steps

After exploring these examples:
- **05-engines/** - Custom processing logic
- **06-agent-components/** - Per-agent behavior extensions
- **07-orchestrator-components/** - Global coordination patterns
- **03-claudes-workshop/** - Production patterns and best practices

## 📖 Additional Resources

- **AGENTS.md** - "Persistent Blackboard History" section
- **AGENTS.md** - "Test Isolation" section for scale testing
- [Dashboard Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/dashboard.md)
- [Configuration Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/reference/configuration.md)

---

**Ready to explore advanced features? Start with persistent storage! 🗄️**
