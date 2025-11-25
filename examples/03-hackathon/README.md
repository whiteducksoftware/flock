# 🎓 Flock Hackathon Track

Welcome to the Flock Hackathon! This track is designed for hands-on learning through progressive examples. Each example builds on the previous one, introducing new concepts while giving you opportunities to experiment and extend.

## 🧠 If You Know LangChain / Graphs / AutoGen

Flock uses a **blackboard architecture**, which is a bit different from most agent “graph” frameworks:

- **Shared blackboard, not direct calls**  
  Agents don’t call each other. They **publish typed artifacts** to a shared blackboard and **subscribe** to the types (and predicates) they care about. The orchestrator decides who runs next.

- **Think “data flow”, not “who do I call?”**  
  Design workflows by asking: *“Which artifact types exist, and which agents produce/consume them?”* rather than wiring explicit edges or next steps between agents.

- **Event-driven and batched**  
  You usually `publish(...)` a bunch of artifacts and then call `run_until_idle()`. Flock then runs **all eligible agents in parallel** until there’s nothing left to do, instead of stepping a graph node by node.

- **Context and security are first‑class**  
  Visibility + context providers control **what each agent is allowed to see**, not just what you happen to pass in a prompt. This is both a security boundary and a cost-optimization layer.

While you go through the examples, try to keep this mental model:  
**“I publish structured artifacts to a shared board, and agents react to them based on types, filters, and schedule”**, instead of **“I orchestrate a chain of function calls between agents”**.

## 🎯 How This Track Works

### Learning Flow

1. **Read** the code and comments carefully
2. **Run** the example to see it in action
3. **Understand** what's happening (check the output)
4. **Experiment** with the "Now It's Your Turn" challenges
5. **Extend** the example with your own ideas

### Structure

Each example follows this pattern:

```python
# ============================================================================
# CONCEPT: What you're learning
# ============================================================================
# Explanation of the concept

# ============================================================================
# SETUP: Code that demonstrates the concept
# ============================================================================

# ============================================================================
# RUN: Execute and observe
# ============================================================================

# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# Challenges and experiments to try
```

## 📚 Track Progression

| Example | Concept | Difficulty | Key Learning |
|---------|---------|------------|--------------|
| **01** | Basic Agent | ⭐ | Agent declaration, consumes, publishes |
| **02** | Multi-Agent Chain | ⭐⭐ | Agent pipelines, data flow |
| **03** | Conditional Consumption | ⭐⭐ | `where` clauses, filtering |
| **04** | Fan-Out Publishing | ⭐⭐⭐ | Multiple outputs, cost optimization |
| **05** | Semantic Subscriptions | ⭐⭐⭐ | AI-powered routing, meaning-based matching |
| **06** | Timer Scheduling | ⭐⭐⭐ | Periodic execution, scheduled tasks |
| **07** | JoinSpec | ⭐⭐⭐⭐ | Correlating multiple artifact types |
| **08** | Custom Engines | ⭐⭐⭐⭐ | Extensibility, custom processing logic |
| **09** | MCP Web Researcher | ⭐⭐⭐⭐ | Using MCP web tools + local tools |
| **10** | MCP Filesystem Explorer | ⭐⭐⭐⭐ | Filesystem MCP, roots, whitelists |
| **11** | News Batching + Components | ⭐⭐⭐⭐ | MCP + batching + agent components |

## 🚀 Quick Start

### Prerequisites

```bash
# Make sure you have Flock installed
poe install

# Set your API key
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"
```

### Running Examples

```bash
# Run the first example from the repo root
uv run 01-hackathon/01_basic_agent.py

# Or enable dashboard mode (edit USE_DASHBOARD = True)
uv run 01-hackathon/01_basic_agent.py
# Then open http://localhost:8344
```

> 🧰 **MCP notes:**  
> Examples 09–11 make use of simple local MCP servers (web search, website reader, filesystem).  
> You’ll need tools like `uvx duckduckgo-mcp-server` and `npx @modelcontextprotocol/server-filesystem` available on your PATH.  
> If they’re missing, the examples will print warnings and still run in a degraded (LLM-only) mode.

## 💡 Tips for Success

### 1. Start Simple
- Don't skip examples - each builds on the previous
- Run each example before moving to the next
- Understand the basic concept before experimenting

### 2. Experiment Freely
- The "Now It's Your Turn" sections are suggestions, not requirements
- Try your own ideas!
- Break things and learn from errors

### 3. Use the Dashboard
- Enable `USE_DASHBOARD = True` to visualize agent execution
- Watch artifacts flow between agents
- Inspect the blackboard to see all data

### 4. Read the Code
- Comments explain the "why" behind patterns
- Type definitions show the data structures
- Agent descriptions guide LLM behavior

### 5. Check Documentation
- See `docs/guides/` for detailed explanations
- Review `03-additional-examples/01-getting-started/` for reference
- Check `AGENTS.md` for patterns and best practices

## 🎯 Hackathon Challenges

After completing all examples, try these advanced challenges:

### Challenge 1: Build a Content Pipeline
Create a multi-agent system that:
- Takes a blog topic
- Generates multiple article outlines (fan-out)
- Routes to specialized writers based on topic (semantic)
- Only processes high-quality drafts (conditional)
- Schedules daily content reviews (timer)

### Challenge 2: E-Commerce Order System
Build an order processing system with:
- Order validation (conditional consumption)
- Payment batching (BatchSpec)
- Inventory correlation (JoinSpec)
- Customer notification (multi-agent chain)
- Daily sales reports (timer scheduling)

### Challenge 3: Custom Domain
Pick your own domain (healthcare, finance, gaming, etc.) and:
- Design artifact types for your domain
- Create specialized agents
- Implement custom engines/components
- Add visibility controls for security
- Build a complete workflow

## 📖 Additional Resources

- **Getting Started Examples**: `03-additional-examples/01-getting-started/` - Reference implementations
- **Pattern Examples**: `02-patterns/` - Specialized patterns
- **Documentation**: `docs/guides/` - Comprehensive guides
- **AGENTS.md**: Framework patterns and best practices
- **Extra Examples Map**: `03-additional-examples/README.md` - Overview of all additional example folders

## 🎓 Learning Objectives

By the end of this track, you should understand:

✅ How to declare agents and their behavior  
✅ How agents communicate through the blackboard  
✅ How to filter and route artifacts  
✅ How to optimize costs with fan-out and batching  
✅ How to schedule periodic tasks  
✅ How to correlate related data  
✅ How to extend Flock with custom logic  
✅ How to integrate MCP tools (web, filesystem, etc.)  
✅ How to use agent components for metrics, logging, and quality gates  

## 🚨 Common Pitfalls

### Don't Skip Steps
Each example introduces concepts you'll need later. Skipping examples leads to confusion.

### Don't Just Copy-Paste
Type the code yourself - muscle memory helps understanding.

### Don't Ignore Errors
Errors teach you how the system works. Read error messages carefully.

### Don't Forget to Experiment
The "Now It's Your Turn" sections are where real learning happens!

## 🎉 Ready to Start?

Begin with `01_basic_agent.py` and work through each example in order. Take your time, experiment, and most importantly - have fun building with Flock!

---

**Happy Hacking! 🚀**
