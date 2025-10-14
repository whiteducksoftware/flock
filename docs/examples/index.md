# Examples

Learn by example! Explore working code samples demonstrating Flock's features and patterns.

---

## 🎯 Example Categories

### Core Examples
**Production-ready demonstrations of core features**

Explore the numbered example folders in this repository:

- **01 — The Declarative Way** (`examples/01-the-declarative-way`) — minimal and focused
- **02 — The Blackboard** (`examples/02-the-blackboard`) — architecture overview
- **03 — The Dashboard** (`examples/03-the-dashboard`) — real-time monitoring

### Component Examples
**Learn to build custom components and engines**

- **05 — Custom Engines** (`examples/05-engines`) — deterministic logic engines
- **06 — Agent Components** (`examples/06-agent-components`) — per-agent behavior patterns
- **07 — Orchestrator Components** (`examples/07-orchestrator-components`) — global coordination patterns

These examples show how to extend Flock with custom logic:

**Custom Engines** - Replace LLM calls with deterministic logic:
- `emoji_mood_engine.py` - Pattern-based mood detection
- `potion_batch_engine.py` - Batch processing rules

**Agent Components** - Add per-agent behavior:
- `cheer_meter_component.py` - Track agent-specific metrics
- `plot_twist_component.py` - Dynamic agent state

**Orchestrator Components** - Global coordination:
- `quest_tracker_component.py` - Real-time quest scoring system
- `kitchen_monitor_component.py` - Restaurant performance monitoring

### Feature Examples
**Focused examples for specific capabilities**

Feature-focused examples are integrated into the folders above (e.g., dashboard edge cases). Additional feature demos may be added over time.

### Dashboard Examples
**Interactive dashboard demonstrations**

Check out `examples/03-the-dashboard` to explore:

- **Declarative Pizza** - Single-agent dashboard demo
- **Edge Cases** - Multi-agent cascades and filtering
- **Real-time Updates** - WebSocket streaming

### Claude's Workshop
**🎓 Interactive learning course from beginner to expert**

Complete hands-on workshop: `examples/03-claudes-workshop`

**Beginner Track:**
- Lesson 01: Code Detective - Your first agent
- Lesson 02: Band Formation - Multi-agent chaining

**Intermediate Track:**
- Lesson 03: Quality Gates - Conditional consumption
- Lesson 04: Debate Club - Feedback loops
- Lesson 05: Debugging Detective - Unified tracing

**Advanced Track:**
- Lesson 06: Secret Agent Network - Visibility controls
- Lesson 07: News Agency - Parallel execution

**Expert Track:**
- Lesson 08: The Matchmaker - JoinSpec correlation
- Lesson 09: Batch Optimizer - BatchSpec patterns
- Lesson 10: Smart Factory - Combined features

**Architecture Track:**
- Lesson 11: Performance Monitor - Orchestrator components
- Lesson 12: Confidence Booster - Agent components
- Lesson 13: Regex Matcher - Custom engines

Each lesson is self-contained with detailed comments and runnable code!

---

## 🚀 Running Examples

### Prerequisites

```bash
# Install Flock with all features
pip install "flock-core[all]"

# Set your API key
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"
```

### Run an Example

```bash
# Clone the repository
git clone https://github.com/whiteducksoftware/flock.git
cd flock

# Run a minimal example
python examples/01-the-declarative-way/01_declarative_pizza.py

# Run with dashboard
python examples/03-the-dashboard/01_declarative_pizza.py
```

---

## 📚 Example Highlights

### 1. Hello Flock (Minimal)

**What it demonstrates:** Basic agent creation and execution

```python
from flock import Flock, flock_type
from pydantic import BaseModel

@flock_type
class Greeting(BaseModel):
    name: str

@flock_type
class Response(BaseModel):
    message: str

flock = Flock("openai/gpt-4.1")

greeter = (
    flock.agent("greeter")
    .consumes(Greeting)
    .publishes(Response)
)

async def main():
    await flock.invoke(
        greeter,
        Greeting(name="World")
    )

asyncio.run(main())
```

Run it locally: `python examples/01-the-declarative-way/01_declarative_pizza.py`

---

### 2. Dashboard Edge Cases

**What it demonstrates:** Agent cascades, filtering, and real-time updates

Run: `python examples/03-the-dashboard/02-dashboard-edge-cases.py`

---

### 3. Dashboard Demo

**What it demonstrates:** Real-time agent monitoring

**Features:**
- Live agent status updates
- Artifact flow visualization
- Streaming LLM outputs
- WebSocket communication

```python
await orchestrator.serve(
    dashboard=True,
    port=8344
)
```

Run: `python examples/03-the-dashboard/01_declarative_pizza.py`

---

### 4. Feedback Prevention

**What it demonstrates:** Preventing agent feedback loops using built-in safeguards

- Default safeguard: `prevent_self_trigger=True` (agents won’t re-trigger on their own outputs)
- Use label/tenant visibility for finer control (see Visibility guide)

---

### 5. Visibility Controls

**What it demonstrates:** Access control patterns

Examples for:
- **Public** - All agents can access
- **Private** - Only producing agent can access
- **Tenant** - Multi-tenant isolation
- **Label** - Fine-grained control
- **Time** - Temporal constraints

See: Docs → User Guides → Visibility Controls

---

## 💡 Example Patterns

### Pattern: Parallel Batching

```python
# Publish multiple items
for item in items:
    await flock.publish(item)

# Process all in parallel
await flock.run_until_idle()
```

**Used in:** Blog review, pizza ordering

---

### Pattern: Conditional Consumption

```python
agent.consumes(
    Review,
    where=lambda r: r.score >= 9  # Only high scores
)
```

**Used in:** Dashboard edge cases

---

### Pattern: Multi-Type Agents

```python
agent.consumes(
    [RequestType, FeedbackType],  # Multiple inputs
    where=lambda x: x.user_id == current_user
)
```

**Used in:** Feedback prevention

---

### Pattern: Unified Tracing

```python
async with flock.traced_run("workflow_name"):
    await flock.publish(input_data)
    await flock.run_until_idle()
```

**Used in:** Most showcase examples

---

## 🎓 Learning Path

**New to Flock?** We recommend this order:

1. **[Hello Flock](https://github.com/whiteducksoftware/flock/blob/main/examples/showcase/01_hello_flock.py)** - Understand basics
2. **[Pizza Ordering](https://github.com/whiteducksoftware/flock/blob/main/examples/showcase/03_pizza_ordering.py)** - Learn type contracts
3. **[Blog Review](https://github.com/whiteducksoftware/flock/blob/main/examples/showcase/02_blog_review.py)** - Master multi-agent flows
4. **[Dashboard Demo](https://github.com/whiteducksoftware/flock/blob/main/examples/showcase/04_dashboard.py)** - Add observability
5. **[Feedback Prevention](https://github.com/whiteducksoftware/flock/blob/main/examples/features/feedback_prevention.py)** - Handle edge cases

---

## 🔧 Customization Examples

### Custom Component

```python
from flock import Component, Agent

class LoggingComponent(Component):
    async def on_pre_consume(self, agent: Agent, artifacts):
        print(f"Agent {agent.name} processing {len(artifacts)} artifacts")

agent.add_component(LoggingComponent())
```

**[See full example →](https://github.com/whiteducksoftware/flock/tree/main/examples/features/custom_components)**

---

### Custom Engine

```python
from flock import Engine

class CustomEngine(Engine):
    async def evaluate(self, agent: Agent, artifacts):
        # Your custom evaluation logic
        return CustomOutput(...)

flock.engine = CustomEngine()
```

**[See full example →](https://github.com/whiteducksoftware/flock/tree/main/examples/features/custom_engines)**

---

## 📊 Testing Examples

Examples include tests demonstrating:

- Unit testing agents with `publish_outputs=False`
- Integration testing with `run_until_idle()`
- Mocking components and engines
- Tracing-based test verification

**[Browse test examples →](https://github.com/whiteducksoftware/flock/tree/main/tests)**

---

## 🌟 Community Examples

Have you built something cool with Flock? Share it!

- Submit a PR to add your example
- Post in [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- Tag us on social media

---

## Related Documentation

- **[Getting Started](../getting-started/index.md)** - Installation and quick start
- **[User Guides](../guides/index.md)** - Comprehensive guides
- **[API Reference](../reference/index.md)** - Complete API docs

---

**Browse all examples** → [GitHub Repository](https://github.com/whiteducksoftware/flock/tree/main/examples){ .md-button .md-button--primary }
