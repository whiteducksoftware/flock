# 🎓 Claude's Flock Workshop: From Zero to Blackboard Master

Welcome to an interactive, hands-on workshop for mastering Flock! This course takes you from complete beginner to confidently building production-ready multi-agent systems using the blackboard architecture.

## 🎯 What You'll Learn

This workshop teaches you **declarative AI orchestration** through progressively complex, engaging examples. No boring corporate demos—we're building detectives, bands, debate clubs, and secret agent networks!

### Core Concepts Covered:
- ✅ **Declarative Type Contracts** - Replace prompts with schemas
- ✅ **Blackboard Architecture** - Decoupled agent collaboration
- ✅ **Agent Chaining** - Multi-step workflows through subscriptions
- ✅ **Conditional Consumption** - Smart filtering with predicates
- ✅ **Feedback Loops** - Iterative refinement with safety
- ✅ **Unified Tracing** - Production-ready debugging
- ✅ **Visibility Controls** - Security and access control
- ✅ **Parallel Processing** - Concurrent agent execution
- ✅ **Data Correlation** - JoinSpec for correlated AND gates
- ✅ **Batch Processing** - BatchSpec for efficient batching
- ✅ **Combined Features** - JoinSpec + BatchSpec together
- ✅ **Orchestrator Components** - Global coordination and monitoring
- ✅ **Agent Components** - Per-agent behavior and quality gates
- ✅ **Custom Engines** - Deterministic logic without LLM costs

## 📚 Course Structure

Each lesson builds on the previous one, introducing new concepts with hands-on examples:

### 🔰 Beginner Track

**Lesson 01: The Code Detective** ⭐ START HERE
- Your first Flock agent
- Single-agent transformation
- Type-safe contracts
- **Time:** 10 minutes

**Lesson 02: Band Formation Pipeline**
- Multi-agent chaining through blackboard
- Automatic workflow emergence
- No graph wiring needed
- **Time:** 15 minutes

### 🎯 Intermediate Track

**Lesson 03: Quality Gate System**
- Conditional consumption with `where=`
- Dynamic routing based on data
- Building decision trees without graphs
- **Time:** 15 minutes

**Lesson 04: The Debate Club**
- Feedback loops and iterative refinement
- Self-triggering safety mechanisms
- When agents should re-process their own outputs
- **Time:** 20 minutes

**Lesson 05: Debugging the Detective**
- Unified tracing with `traced_run()`
- Reading DuckDB traces
- AI-assisted debugging
- Performance analysis
- **Time:** 20 minutes

### 🚀 Advanced Track

**Lesson 06: Secret Agent Network**
- Visibility controls (Private, Public, Tenant, Labelled)
- Multi-tenancy patterns
- Time-delayed artifacts
- Zero-trust architecture
- **Time:** 25 minutes

**Lesson 07: The News Agency**
- Parallel agent execution
- Opportunistic processing
- Concurrent workflows at scale
- **Time:** 20 minutes

### 🚀 Expert Track - Logic Operations

**Lesson 08: The Matchmaker**
- Data correlation with JoinSpec
- Correlated AND gates by common keys
- Time-windowed matching
- E-commerce order-shipment correlation
- **Time:** 25 minutes

**Lesson 09: The Batch Optimizer**
- Efficient processing with BatchSpec
- Size and timeout triggers
- Cost optimization through batching
- Payment processing use case
- **Time:** 25 minutes

**Lesson 10: The Smart Factory** 🏆 MASTER CLASS
- Combining JoinSpec + BatchSpec
- Multi-stage correlation and batching
- IoT sensor monitoring at scale
- Production-grade patterns
- **Time:** 30 minutes

### 🏗️ Architecture Track - Custom Components

**Lesson 11: The Performance Monitor**
- Orchestrator components for global coordination
- Cross-cutting concerns (monitoring, metrics, alerting)
- Lifecycle hooks across all agents
- Real-time performance dashboards
- **Time:** 25 minutes

**Lesson 12: The Confidence Booster**
- Agent components for per-agent behavior
- Confidence scoring and quality gates
- Dynamic prompt enhancement
- Retry logic and validation
- **Time:** 25 minutes

**Lesson 13: The Regex Matcher**
- Custom engines for deterministic logic
- Zero-cost pattern matching
- Hybrid LLM + rule-based architectures
- Cost optimization strategies
- **Time:** 20 minutes

## 🛠️ Prerequisites

```bash
# 1. Ensure you have Python 3.10+ and UV installed
python --version  # Should be 3.10+
uv --version      # Should be installed

# 2. Install Flock (if not already in the repo)
cd /path/to/flock-flow
poe install

# 3. Set up your API key
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4o-mini"

# 4. Enable tracing (highly recommended!)
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
```

## 🚀 How to Use This Course

### Option 1: Sequential Learning (Recommended)
Work through lessons in order, running each example:

```bash
# Start with Lesson 01
uv run examples/03-claudes-workshop/lesson_01_code_detective.py

# Then Lesson 02
uv run examples/03-claudes-workshop/lesson_02_band_formation.py

# And so on...
```

### Option 2: Jump to Topics
Already familiar with basics? Jump to specific lessons:
- Need to learn tracing? → Lesson 05
- Building secure systems? → Lesson 06
- Optimizing performance? → Lesson 07
- Data correlation patterns? → Lesson 08
- Batch processing optimization? → Lesson 09
- Advanced combined features? → Lesson 10

### Option 3: Interactive Exploration
Each lesson is a standalone Python file with:
- Detailed inline comments explaining every concept
- Runnable code you can modify
- Suggestions for experimentation

## 📊 Using Tracing for Learning

Every lesson is designed to work with Flock's tracing system. Enable it to see **exactly** what's happening:

```bash
# Enable tracing before running lessons
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true

# Run a lesson
uv run examples/03-claudes-workshop/lesson_01_code_detective.py

# Query the traces to understand what happened
python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)
traces = conn.execute('''
    SELECT name, duration_ms, status_code
    FROM spans
    ORDER BY start_time DESC
    LIMIT 10
''').fetchall()
for t in traces:
    print(f'{t[0]}: {t[1]:.0f}ms - {t[2]}')
"
```

## 🎓 Learning Tips

1. **Read the Comments First** - Each lesson has extensive inline documentation
2. **Run the Code** - Don't just read, execute and observe
3. **Enable Tracing** - See what's happening under the hood
4. **Experiment** - Modify schemas, add agents, break things (safely!)
5. **Compare Architectures** - Comments highlight how blackboard patterns differ from graph-based approaches

## 🤔 What Makes This Different?

Unlike traditional tutorials:
- ❌ No boring "hello world" examples
- ❌ No corporate CRUD demos
- ❌ No disconnected code snippets

Instead:
- ✅ Engaging, memorable scenarios
- ✅ Progressive complexity
- ✅ Complete, runnable examples
- ✅ Production patterns from day one

## 📖 Additional Resources

After completing this workshop, explore:
- **Main README** - Feature overview and comparisons
- **AGENTS.md** - Development guide for contributors
- **docs/AUTO_TRACING.md** - Deep dive on observability
- **docs/UNIFIED_TRACING.md** - Advanced tracing patterns
- **examples/showcase/** - Additional real-world examples

## 🆘 Getting Help

Stuck on a lesson?
1. Check the inline comments - they're very detailed
2. Enable tracing to see what's happening
3. Read the error messages - Flock gives helpful feedback
4. Review AGENTS.md for debugging tips
5. Open a GitHub issue with your question

## 🎯 Learning Outcomes

By the end of this workshop, you'll be able to:
- ✅ Build type-safe AI agents without prompt engineering
- ✅ Orchestrate multi-agent systems using blackboard architecture
- ✅ Implement conditional routing and feedback loops
- ✅ Debug complex workflows with distributed tracing
- ✅ Secure multi-tenant systems with visibility controls
- ✅ Correlate related data with JoinSpec
- ✅ Optimize processing with BatchSpec batching
- ✅ Combine advanced features for production-grade systems
- ✅ Build custom orchestrator components for global coordination
- ✅ Create agent components for per-agent behavior patterns
- ✅ Implement custom engines for deterministic logic
- ✅ Scale to 100+ agents without graph complexity

## 🚀 Ready to Start?

Begin with **Lesson 01: The Code Detective** and work your way through!

```bash
uv run examples/03-claudes-workshop/lesson_01_code_detective.py
```

**Let's build the future of AI orchestration together!** 🎉

---

*Course designed and tested by Claude Code • Built on Flock 0.5*
